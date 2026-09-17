from __future__ import annotations

from typing import Any


def _side(v: Any) -> str:
    z = str(v or "").strip().upper()
    if z in {"BUY", "BULL", "BULLISH", "LONG"}:
        return "LONG"
    if z in {"SELL", "BEAR", "BEARISH", "SHORT"}:
        return "SHORT"
    return ""


def _event(state: dict[str, Any], side: str, confirmed: bool) -> bool:
    if side == "LOW":
        broke = bool(state.get("broke_low"))
        reclaimed = bool(state.get("reclaimed_low"))
    else:
        broke = bool(state.get("broke_high"))
        reclaimed = bool(state.get("reclaimed_high"))
    return broke and (reclaimed if confirmed else True)


def symmetric_smt(ctx: dict[str, Any]) -> dict[str, Any]:
    """Return symmetric NQ/ES SMT, independent of which index raids liquidity.

    High divergence = bearish SMT: one market raids/reclaims a swing high while
    the other does not. Low divergence = bullish SMT. Raw states trigger as soon
    as the liquidity raid is visible; confirmed states additionally require the
    reclaim recorded by the context engine.
    """
    smt = ctx.get("smt") or {}
    target = str(smt.get("target") or "NQ").upper()
    peer = str(smt.get("peer") or ("ES" if target == "NQ" else "NQ")).upper()
    ts = smt.get("target_state") or {}
    ps = smt.get("peer_state") or {}
    if not ts.get("available") or not ps.get("available"):
        return {
            "bias": "UNAVAILABLE",
            "state": "UNAVAILABLE",
            "raw_bias": "UNAVAILABLE",
            "reason": "NQ/ES swing context unavailable",
            "target": target,
            "peer": peer,
        }

    t_low_raw, p_low_raw = _event(ts, "LOW", False), _event(ps, "LOW", False)
    t_high_raw, p_high_raw = _event(ts, "HIGH", False), _event(ps, "HIGH", False)
    t_low_conf, p_low_conf = _event(ts, "LOW", True), _event(ps, "LOW", True)
    t_high_conf, p_high_conf = _event(ts, "HIGH", True), _event(ps, "HIGH", True)

    raw_bull = t_low_raw != p_low_raw
    raw_bear = t_high_raw != p_high_raw
    conf_bull = t_low_conf != p_low_conf
    conf_bear = t_high_conf != p_high_conf

    def who(side: str, confirmed: bool = False) -> tuple[str | None, str | None]:
        tv = _event(ts, side, confirmed)
        pv = _event(ps, side, confirmed)
        if tv == pv:
            return None, None
        return (target, peer) if tv else (peer, target)

    if conf_bull and conf_bear:
        bias, state, reason = "CONFLICT", "CONFIRMED_CONFLICT", "confirmed SMT exists at both lows and highs"
        sweeper = holder = None
    elif conf_bull:
        sweeper, holder = who("LOW", True)
        bias, state = "BULLISH", "CONFIRMED"
        reason = f"{sweeper} swept/reclaimed its swing low while {holder} held -> bullish SMT"
    elif conf_bear:
        sweeper, holder = who("HIGH", True)
        bias, state = "BEARISH", "CONFIRMED"
        reason = f"{sweeper} swept/reclaimed its swing high while {holder} held -> bearish SMT"
    else:
        bias, state, reason = "NEUTRAL", "NONE", "no confirmed symmetric SMT"
        sweeper = holder = None

    if raw_bull and raw_bear:
        raw_bias = "CONFLICT"
        raw_sweeper = raw_holder = None
        raw_reason = "raw SMT raids visible on both sides"
    elif raw_bull:
        raw_sweeper, raw_holder = who("LOW", False)
        raw_bias = "BULLISH"
        raw_reason = f"{raw_sweeper} raided a swing low while {raw_holder} held"
    elif raw_bear:
        raw_sweeper, raw_holder = who("HIGH", False)
        raw_bias = "BEARISH"
        raw_reason = f"{raw_sweeper} raided a swing high while {raw_holder} held"
    else:
        raw_bias = "NEUTRAL"
        raw_sweeper = raw_holder = None
        raw_reason = "no raw symmetric SMT divergence"

    return {
        "bias": bias,
        "state": state,
        "reason": reason,
        "sweeper": sweeper,
        "holder": holder,
        "raw_bias": raw_bias,
        "raw_reason": raw_reason,
        "raw_sweeper": raw_sweeper,
        "raw_holder": raw_holder,
        "target": target,
        "peer": peer,
        "raw_low_divergence": raw_bull,
        "raw_high_divergence": raw_bear,
        "confirmed_low_divergence": conf_bull,
        "confirmed_high_divergence": conf_bear,
    }


def current_r(side: Any, entry: Any, stop: Any, price: Any) -> float | None:
    try:
        e, s, p = float(entry), float(stop), float(price)
    except Exception:
        return None
    risk = abs(e - s)
    if risk <= 0:
        return None
    sd = _side(side)
    if sd == "LONG":
        return (p - e) / risk
    if sd == "SHORT":
        return (e - p) / risk
    return None


def profit_take_advice(
    ctx: dict[str, Any],
    *,
    trade_side: Any,
    current_r_value: float | None = None,
    partial_min_r: float = 1.0,
) -> dict[str, Any]:
    """SMT management signal for an already-open position.

    A raw opposite SMT is an early reversal warning. Once at least partial_min_r
    is available, the default advisory is TAKE_PARTIAL; below that it is TIGHTEN.
    A confirmed opposite SMT upgrades the advisory to EXIT_REVIEW. This module
    does not execute orders; it exposes deterministic states for live/paper and
    historical testing.
    """
    sig = symmetric_smt(ctx)
    side = _side(trade_side)
    raw = sig.get("raw_bias")
    confirmed = sig.get("bias")
    adverse_raw = (side == "LONG" and raw == "BEARISH") or (side == "SHORT" and raw == "BULLISH")
    adverse_confirmed = (side == "LONG" and confirmed == "BEARISH") or (side == "SHORT" and confirmed == "BULLISH")

    if adverse_confirmed:
        action = "EXIT_REVIEW"
        reason = f"confirmed opposite SMT: {sig.get('reason')}"
    elif adverse_raw:
        if current_r_value is not None and current_r_value >= float(partial_min_r):
            action = "TAKE_PARTIAL"
            reason = f"opposite raw SMT at {current_r_value:.2f}R: {sig.get('raw_reason')}"
        else:
            action = "TIGHTEN"
            reason = f"opposite raw SMT reversal warning: {sig.get('raw_reason')}"
    else:
        action = "HOLD"
        reason = "no opposite SMT profit-taking signal"

    return {
        "action": action,
        "reason": reason,
        "trade_side": side,
        "current_r": current_r_value,
        "partial_min_r": float(partial_min_r),
        "adverse_raw": adverse_raw,
        "adverse_confirmed": adverse_confirmed,
        "smt": sig,
    }
