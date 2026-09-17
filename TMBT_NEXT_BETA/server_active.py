from __future__ import annotations

from copy import deepcopy
from urllib.parse import urlparse, parse_qs

import context_factors
import server_ready as ready

core = ready.core
_base_ready_models = ready.ready_models
_ACTIVE = {"WATCH", "FORMING", "STRONG", "READY", "ARMED", "TRIGGERED", "SIGNAL"}


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


def _cfg(target: str):
    target = str(target or "NQ").upper()
    peer = "ES" if target == "NQ" else "NQ"
    return context_factors.ContextConfig(target_market=target, peer_market=peer)


def _apply_market_context(models, target):
    idx = [(i, m) for i, m in enumerate(models) if str(m.get("market") or "").upper() == target]
    if not idx:
        return models
    filtered, _ctx = context_factors.apply_to_models([m for _, m in idx], ready.ready_query, _cfg(target))
    out = list(models)
    for (i, _), m in zip(idx, filtered):
        out[i] = m
    return out


def context_locked_models():
    """Apply target-relative NQ/ES price-action context before active iFVGs.

    Hierarchy:
      target-relative SMT veto -> target PO3 -> Asia/Midnight context -> iFVG entry.

    NQ and ES are evaluated separately. For example, ES sweeping a low while NQ
    holds can be bullish for NQ without blindly imposing the same bias on ES.
    If neither market has confirmed direction, the older opposite-direction
    safety remains in place.
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
        if market not in conflicts or not _is_ifvg(m) or _stage(m) not in _ACTIVE:
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
core.APP_VERSION = "0.9.18-beta-context-bias"


class Handler(ready.Handler):
    def do_GET(self):
        u = urlparse(self.path)
        if u.path in {"/api/context", "/api/context-bias"}:
            q = parse_qs(u.query)
            target = str(q.get("market", ["NQ"])[0]).upper()
            if target not in {"NQ", "ES"}:
                target = "NQ"
            return self.json(context_factors.build_context(ready.ready_query, _cfg(target)))
        return super().do_GET()


if __name__ == "__main__":
    core.PID_FILE.write_text(str(core.os.getpid()), encoding="utf-8")
    print("TMBT Next", core.APP_VERSION)
    print("Workspace:", core.WORKSPACE)
    print("Desk: visual-priority live workspace + setup cards + notification history")
    print("Context hierarchy: SMT -> PO3 -> Asia/Midnight -> iFVG entry")
    print("SMT veto: peer liquidity raid while target holds can block the opposite NQ/ES direction")
    print("PO3: ordered Asia manipulation/reclaim and distribution state is point-in-time only")
    print("Midnight/Asia: stored as explicit context fields for later backtest linkage")
    print("NQ and ES context are evaluated separately; no shared one-size-fits-all bias")
    print("Fallback safety: opposite active iFVGs are both blocked when context stays neutral")
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
