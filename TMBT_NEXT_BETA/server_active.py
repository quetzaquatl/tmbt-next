from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import context_factors
import historical_store
import research_autopilot_bridge
import research_sync_bridge
import research_scheduler
import smt_trade_management
import ttfm_live
import server_ready as ready

core = ready.core
_base_ready_models = ready.ready_models
_ACTIVE = {"WATCH", "FORMING", "STRONG", "READY", "ARMED", "TRIGGERED", "SIGNAL"}
_PRE_ENTRY = {"WATCH", "FORMING", "STRONG", "READY", "ARMED", "TRIGGERED"}
_DATA_SETTINGS = core.WORKSPACE / "live_data" / "tmbt_data_settings.json"
_OBSERVATIONS_FILE = Path(__file__).resolve().parent.parent / "TRADER_OBSERVATIONS.md"


def _read_data_settings():
    try:
        value = json.loads(_DATA_SETTINGS.read_text(encoding="utf-8", errors="ignore"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def _write_data_settings(value):
    _DATA_SETTINGS.parent.mkdir(parents=True, exist_ok=True)
    tmp = _DATA_SETTINGS.with_suffix(_DATA_SETTINGS.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, _DATA_SETTINGS)
    try:
        os.chmod(_DATA_SETTINGS, 0o600)
    except Exception:
        pass


def _masked_secret_status():
    s = _read_data_settings()
    key = str(s.get("twelve_api_key") or "")
    massive = str(s.get("massive_api_key") or "")
    return {
        "twelve_configured": bool(key),
        "twelve_last4": key[-4:] if key else None,
        "massive_configured": bool(massive),
        "massive_last4": massive[-4:] if massive else None,
        "updated_at_utc": s.get("updated_at_utc"),
        "storage": str(_DATA_SETTINGS),
    }


def _save_secret_payload(payload):
    current = _read_data_settings()
    if payload.get("clear_twelve"):
        current.pop("twelve_api_key", None)
    elif str(payload.get("twelve_api_key") or "").strip():
        current["twelve_api_key"] = str(payload.get("twelve_api_key")).strip()
    if payload.get("clear_massive"):
        current.pop("massive_api_key", None)
    elif str(payload.get("massive_api_key") or "").strip():
        current["massive_api_key"] = str(payload.get("massive_api_key")).strip()
    current["updated_at_utc"] = datetime.now(timezone.utc).isoformat()
    _write_data_settings(current)
    return _masked_secret_status()



def _side(v):
    z = str(v or "").strip().upper()
    if z in {"BUY", "BULL", "BULLISH", "LONG"}:
        return "LONG"
    if z in {"SELL", "BEAR", "BEARISH", "SHORT"}:
        return "SHORT"
    return ""


def _stage(m):
    return str(m.get("status") or m.get("stage") or "").strip().upper()


def _is_ifvg(m):
    text = " ".join(str(m.get(k) or "") for k in ("name", "label", "id", "model", "model_type", "strategy")).upper()
    return "IFVG" in text or "SILVER" in text


def _is_open_trade(m):
    if _stage(m) != "SIGNAL":
        return False
    v = m.get("validity") or {}
    return bool(v.get("still_valid", True)) and str(v.get("status") or "ACTIVE").upper() in {"ACTIVE", "VALID", "OPEN"}


def _cfg(target: str):
    target = str(target or "NQ").upper()
    peer = "ES" if target == "NQ" else "NQ"
    return context_factors.ContextConfig(target_market=target, peer_market=peer)


def _append_criterion(m, label, status, detail):
    c = list(m.get("criteria") or [])
    c.append({"label": label, "status": status, "detail": detail})
    m["criteria"] = c


def _apply_market_context(models, target):
    idx = [(i, m) for i, m in enumerate(models) if str(m.get("market") or "").upper() == target]
    if not idx:
        return models

    originals = [deepcopy(m) for _, m in idx]
    filtered, ctx = context_factors.apply_to_models([m for _, m in idx], ready.ready_query, _cfg(target))
    symmetric = smt_trade_management.symmetric_smt(ctx)
    q = ready.ready_query(target, "5m", 20, None) or {}
    bars = q.get("bars") or []
    last_price = (bars[-1] or {}).get("c") if bars else None
    feed_age = q.get("age_seconds")

    out = list(models)
    for (i, _), original, m in zip(idx, originals, filtered):
        m["smt_symmetric"] = symmetric
        m["smt_symmetric_bias"] = symmetric.get("bias")
        m["smt_raw_bias"] = symmetric.get("raw_bias")

        logic = dict(m.get("logic") or {})
        logic["smt_symmetric"] = {
            "confirmed_bias": symmetric.get("bias"),
            "raw_bias": symmetric.get("raw_bias"),
            "sweeper": symmetric.get("sweeper") or symmetric.get("raw_sweeper"),
            "holder": symmetric.get("holder") or symmetric.get("raw_holder"),
            "rule": "one index raids a corresponding swing high/low while the other holds; high divergence bearish, low divergence bullish",
        }
        m["logic"] = logic

        side = _side(original.get("side"))
        original_stage = _stage(original)
        confirmed_bias = symmetric.get("bias")
        adverse_confirmed = (
            (side == "LONG" and confirmed_bias == "BEARISH")
            or (side == "SHORT" and confirmed_bias == "BULLISH")
            or confirmed_bias == "CONFLICT"
        )

        if _is_open_trade(original):
            if m.get("status") == "BLOCKED":
                m["status"] = original.get("status") or original.get("stage") or "SIGNAL"
                m.pop("execution_gate", None)
                m.pop("engine_status", None)
            r_now = smt_trade_management.current_r(side, original.get("entry"), original.get("stop") or original.get("sl"), last_price)
            advice = smt_trade_management.profit_take_advice(ctx, trade_side=side, current_r_value=r_now, partial_min_r=1.0)
            advice["last_price"] = last_price
            advice["feed_age_seconds"] = feed_age
            m["smt_profit_take"] = advice
            action = advice.get("action")
            if action != "HOLD":
                _append_criterion(m, "SMT Profit Taking", "WARN", f"{action} · {advice.get('reason')}")
                base = str(m.get("message") or "")
                m["message"] = f"SMT TP {action} · {base}" if base else f"SMT TP {action}"
        elif _is_ifvg(original) and original_stage in _PRE_ENTRY and adverse_confirmed:
            m["engine_status"] = original_stage
            m["status"] = "BLOCKED"
            m["execution_gate"] = "SYMMETRIC_SMT_VETO"
            reason = symmetric.get("reason") or f"confirmed {confirmed_bias} SMT"
            base = str(m.get("message") or "")
            m["message"] = f"{reason} · {base}" if base else reason

        out[i] = m
    return out


def context_locked_models():
    models = [deepcopy(m) for m in (_base_ready_models() or [])]
    models = _apply_market_context(models, "NQ")
    models = _apply_market_context(models, "ES")

    # TTFM is monitored operationally, but remains execution-locked until its
    # research profile passes the manual review gate. The live evaluator uses
    # true NQ/ES/GC futures only and never substitutes QQQ/SPY/XAU.
    models.extend(ttfm_live.build_monitor_models(core.WORKSPACE))

    active = {}
    for m in models:
        if not _is_ifvg(m) or _stage(m) not in _ACTIVE:
            continue
        market = str(m.get("market") or "").strip().upper()
        side = _side(m.get("side"))
        if market and side:
            active.setdefault(market, set()).add(side)

    conflicts = {market for market, sides in active.items() if {"LONG", "SHORT"}.issubset(sides)}
    if not conflicts:
        return models

    for m in models:
        market = str(m.get("market") or "").strip().upper()
        if market not in conflicts or not _is_ifvg(m) or _stage(m) not in _PRE_ENTRY:
            continue
        old = _stage(m)
        m["engine_status"] = old
        m["status"] = "BLOCKED"
        m["execution_gate"] = "DIRECTION_CONFLICT"
        base_msg = str(m.get("message") or "")
        msg = "Long/Short iFVG conflict on same market · no confirmed directional context"
        m["message"] = f"{msg} · {base_msg}" if base_msg else msg
    return models


core.normalize_models = context_locked_models
core.APP_VERSION = "0.9.59-beta-source-pipeline"


class Handler(ready.Handler):
    def do_GET(self):
        u = urlparse(self.path)
        if u.path in {"/api/context", "/api/context-bias"}:
            q = parse_qs(u.query)
            target = str(q.get("market", ["NQ"])[0]).upper()
            if target not in {"NQ", "ES"}:
                target = "NQ"
            ctx = context_factors.build_context(ready.ready_query, _cfg(target))
            ctx["symmetric_smt"] = smt_trade_management.symmetric_smt(ctx)
            return self.json(ctx)
        if u.path == "/api/data-settings":
            return self.json(_masked_secret_status())
        if u.path == "/api/historical-status":
            return self.json(historical_store.status(core.WORKSPACE))
        if u.path == "/api/research-autopilot/status":
            return self.json(research_autopilot_bridge.status())
        if u.path == "/api/research-autopilot/profiles":
            return self.json({"profiles": research_autopilot_bridge.profiles()})
        if u.path == "/api/research-autopilot/report":
            return self.json(research_autopilot_bridge.latest_report())
        if u.path == "/api/research-sync/status":
            return self.json(research_sync_bridge.status())
        if u.path == "/api/research-scheduler/status":
            return self.json(research_scheduler.status())
        if u.path == "/api/trader-observations":
            try:
                text = _OBSERVATIONS_FILE.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                text = ""
            return self.json({"text": text, "source": str(_OBSERVATIONS_FILE), "mode": "observations_only", "engine_used": False})
        return super().do_GET()

    def do_POST(self):
        u = urlparse(self.path)
        try:
            length = int(self.headers.get("Content-Length") or "0")
            payload = {}
            if length:
                if length > 65536:
                    return self.json({"error": "invalid_body"}, 400)
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                if not isinstance(payload, dict):
                    return self.json({"error": "invalid_json"}, 400)

            if u.path == "/api/research-autopilot/start":
                profile = str(payload.get("profile") or "NQ_EBP_H1")
                return self.json(research_autopilot_bridge.start(
                    profile,
                    test_news=bool(payload.get("test_news", True)),
                    tick_audit=bool(payload.get("tick_audit", False)),
                ))
            if u.path == "/api/research-autopilot/stop":
                return self.json(research_autopilot_bridge.stop())
            if u.path == "/api/research-sync/start":
                return self.json(research_sync_bridge.start())
            if u.path == "/api/research-sync/stop":
                return self.json(research_sync_bridge.stop())
            if u.path == "/api/research-scheduler/start":
                return self.json(research_scheduler.start_background())
            if u.path == "/api/research-scheduler/stop":
                return self.json(research_scheduler.stop())
            if u.path == "/api/data-settings":
                if not payload:
                    return self.json({"error": "invalid_body"}, 400)
                return self.json({"ok": True, "settings": _save_secret_payload(payload)})
            return self.json({"error": "not_found"}, 404)
        except Exception as exc:
            return self.json({"error": str(exc)}, 500)


if __name__ == "__main__":
    core.PID_FILE.write_text(str(core.os.getpid()), encoding="utf-8")
    print("TMBT Next", core.APP_VERSION)
    print("Workspace:", core.WORKSPACE)
    print("Desk: visual-priority live workspace + setup cards + notification history")
    print("Inspector: Active/Monitor click force-opens Setup Inspector and criteria")
    print("Feed automation: self-healing Twelve guardian + persistent local API settings")
    print("Context hierarchy: symmetric SMT -> PO3 -> Asia/Midnight -> iFVG entry")
    print("SMT entry veto: confirmed divergence can block the opposite setup before entry")
    print("SMT trade management: raw opposite divergence warns/takes partial; confirmed divergence triggers exit review")
    print("Open: http://127.0.0.1:%s" % core.PORT)
    try:
        core.ThreadingHTTPServer(("127.0.0.1", core.PORT), Handler).serve_forever()
    finally:
        try:
            core.PID_FILE.unlink(missing_ok=True)
        except Exception:
            pass
