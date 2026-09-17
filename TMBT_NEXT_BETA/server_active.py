from __future__ import annotations

from copy import deepcopy
from urllib.parse import urlparse, parse_qs

import context_factors
import smt_trade_management
import server_ready as ready

core = ready.core
_base_ready_models = ready.ready_models
_ACTIVE = {"WATCH", "FORMING", "STRONG", "READY", "ARMED", "TRIGGERED", "SIGNAL"}
_PRE_ENTRY = {"WATCH", "FORMING", "STRONG", "READY", "ARMED", "TRIGGERED"}


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

        # Entry SMT is a veto only before an entry. Once SIGNAL is already active,
        # a newly appearing SMT must become trade management, not retroactively
        # erase/block a trade that actually existed.
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
    """Apply NQ/ES price-action context before entries and during open trades.

    Entry hierarchy:
      symmetric SMT veto -> target PO3 -> Asia/Midnight context -> iFVG entry.

    Open-trade hierarchy:
      raw opposite SMT -> tighten / partial-profit advisory;
      confirmed opposite SMT -> exit-review advisory.

    NQ and ES retain separate PO3/Asia/Midnight state, while SMT itself is
    symmetric: it does not matter which of the two correlated indices performs
    the liquidity raid.
    """
    models = [deepcopy(m) for m in (_base_ready_models() or [])]
    models = _apply_market_context(models, "NQ")
    models = _apply_market_context(models, "ES")

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
core.APP_VERSION = "0.9.19-beta-smt-trade-management"


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
        return super().do_GET()


if __name__ == "__main__":
    core.PID_FILE.write_text(str(core.os.getpid()), encoding="utf-8")
    print("TMBT Next", core.APP_VERSION)
    print("Workspace:", core.WORKSPACE)
    print("Desk: visual-priority live workspace + setup cards + notification history")
    print("Context hierarchy: symmetric SMT -> PO3 -> Asia/Midnight -> iFVG entry")
    print("SMT entry veto: confirmed divergence can block the opposite setup before entry")
    print("SMT trade management: raw opposite divergence warns/takes partial; confirmed divergence triggers exit review")
    print("PO3: ordered Asia manipulation/reclaim and distribution state is point-in-time only")
    print("NQ and ES PO3/session context are evaluated separately; SMT direction is symmetric")
    print("Fallback safety: opposite pre-entry iFVGs are both blocked when context stays neutral")
    print("EBP matrix: NQ/ES x 15m/30m/1H · closed-bar evaluator active")
    print("Feed priority: TRUE FUTURES mirror -> QQQ/SPY monitoring-only fallback")
    print("Safety: proxy/stale/out-of-session models cannot enter Active Now")
    print("Context: http://127.0.0.1:%s/api/context?market=NQ" % core.PORT)
    print("Preflight: http://127.0.0.1:%s/api/preflight" % core.PORT)
    print("Open: http://127.0.0.1:%s" % core.PORT)
    try:
        core.ThreadingHTTPServer(("127.0.0.1", core.PORT), Handler).serve_forever()
    finally:
        try:
            core.PID_FILE.unlink(missing_ok=True)
        except Exception:
            pass
