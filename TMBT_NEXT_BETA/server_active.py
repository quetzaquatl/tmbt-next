from __future__ import annotations

from copy import deepcopy

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
    return "IFVG" in text


def conflict_locked_models():
    """Safety only: never expose simultaneous opposite active iFVGs on one market.

    This is NOT an HTF bias model.  Until the proper price-action HTF rule is
    defined, opposite active iFVG directions on the same market are both blocked
    rather than choosing a direction with an indicator or arbitrary heuristic.
    """
    models = [deepcopy(m) for m in (_base_ready_models() or [])]
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
        base = str(m.get("message") or "")
        msg = "Long/Short iFVG conflict on same market · waiting for HTF price-action bias"
        m["message"] = f"{msg} · {base}" if base else msg
    return models


core.normalize_models = conflict_locked_models
core.APP_VERSION = "0.9.16-beta-direction-lock"
Handler = ready.Handler


if __name__ == "__main__":
    core.PID_FILE.write_text(str(core.os.getpid()), encoding="utf-8")
    print("TMBT Next", core.APP_VERSION)
    print("Workspace:", core.WORKSPACE)
    print("Desk: compact Active Now queue + Background Monitor + notification history")
    print("Direction safety: opposite active iFVGs on the same market are both BLOCKED")
    print("HTF bias: no EMA / no indicator heuristic; price-action rule still to be defined")
    print("EBP matrix: NQ/ES x 15m/30m/1H · closed-bar evaluator active")
    print("Feed priority: TRUE FUTURES mirror -> QQQ/SPY monitoring-only fallback")
    print("Safety: proxy/stale/out-of-session models cannot enter Active Now")
    print("Preflight: http://127.0.0.1:%s/api/preflight" % core.PORT)
    print("Open: http://127.0.0.1:%s" % core.PORT)
    try:
        core.ThreadingHTTPServer(("127.0.0.1", core.PORT), Handler).serve_forever()
    finally:
        try:
            core.PID_FILE.unlink(missing_ok=True)
        except Exception:
            pass
