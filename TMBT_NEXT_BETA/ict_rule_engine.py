from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any

import ict_core_rules

# Source-aware market-logic pipeline.
#
# The purpose of this module is to keep five different questions separate:
#   CONTEXT   - where are we in the market/session/range?
#   EVENT     - what objectively happened on closed bars?
#   SETUP     - does a named strategy accept those events?
#   EXECUTION - how is an accepted setup entered/exited?
#   RISK      - how much is risked and how is the position managed?
#
# Core primitives may populate CONTEXT/EVENT. They do NOT silently create a
# SETUP/EXECUTION/RISK decision. Any model-specific convention remains explicit
# TMBT research unless it has its own sourced rule.

PIPELINE_VERSION = "ict-source-pipeline-v2"

TF_MS = {
    "1m": 60_000,
    "3m": 3 * 60_000,
    "5m": 5 * 60_000,
    "15m": 15 * 60_000,
    "30m": 30 * 60_000,
    "1h": 60 * 60_000,
    "4h": 4 * 60 * 60_000,
    "1d": 24 * 60 * 60_000,
}


@dataclass(frozen=True)
class Bar:
    t: int
    close_t: int
    o: float
    h: float
    l: float
    c: float


def _f(v: Any) -> float | None:
    try:
        return float(v)
    except Exception:
        return None


def _ms(v: Any) -> int | None:
    if v is None or v == "":
        return None
    try:
        n = float(v)
        return int(n if n > 1e12 else n * 1000)
    except Exception:
        try:
            return int(datetime.fromisoformat(str(v).replace("Z", "+00:00")).timestamp() * 1000)
        except Exception:
            return None


def _tf_key(tf: str) -> str:
    z = str(tf or "").strip().lower()
    return {"60m": "1h", "h1": "1h", "1hr": "1h", "h4": "4h", "d1": "1d"}.get(z, z)


def normalize_closed_bars(
    rows: list[dict[str, Any]] | None,
    *,
    timeframe: str,
    as_of_ms: int | None = None,
) -> list[Bar]:
    """Normalize and retain closed candles only.

    If close_t is absent we infer it from the requested timeframe. This keeps the
    source primitive point-in-time safe in both live and historical callers.
    """
    tf = _tf_key(timeframe)
    width = TF_MS.get(tf)
    if width is None:
        raise ValueError(f"Unsupported timeframe for ICT source pipeline: {timeframe!r}")
    if as_of_ms is None:
        as_of_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

    out: dict[int, Bar] = {}
    for raw in rows or []:
        t = _ms(raw.get("t") if raw.get("t") is not None else raw.get("bar_open_ms"))
        o = _f(raw.get("o") if raw.get("o") is not None else raw.get("open"))
        h = _f(raw.get("h") if raw.get("h") is not None else raw.get("high"))
        l = _f(raw.get("l") if raw.get("l") is not None else raw.get("low"))
        c = _f(raw.get("c") if raw.get("c") is not None else raw.get("close"))
        if None in (t, o, h, l, c):
            continue
        close_t = _ms(raw.get("close_t") if raw.get("close_t") is not None else raw.get("bar_close_ms"))
        close_t = int(close_t if close_t is not None else int(t) + width)
        if close_t > int(as_of_ms):
            continue
        out[int(t)] = Bar(int(t), close_t, float(o), float(h), float(l), float(c))
    return [out[k] for k in sorted(out)]


def confirmed_swings(
    bars: list[Bar],
    *,
    left: int = 2,
    right: int = 2,
) -> dict[str, list[dict[str, Any]]]:
    """TMBT pivot quantification of old highs/lows.

    ICT Core explicitly treats old highs/lows as liquidity references, but it
    does not canonically define our left/right pivot integers. The reference
    itself is Core; the exact confirmation algorithm is evidence class D.
    """
    left = max(1, int(left))
    right = max(1, int(right))
    highs: list[dict[str, Any]] = []
    lows: list[dict[str, Any]] = []
    if len(bars) < left + right + 1:
        return {"highs": highs, "lows": lows}

    for i in range(left, len(bars) - right):
        hi = bars[i].h
        lo = bars[i].l
        is_hi = all(hi > bars[j].h for j in range(i - left, i)) and all(
            hi >= bars[j].h for j in range(i + 1, i + right + 1)
        )
        is_lo = all(lo < bars[j].l for j in range(i - left, i)) and all(
            lo <= bars[j].l for j in range(i + 1, i + right + 1)
        )
        confirmed_at = bars[i + right].close_t
        if is_hi:
            highs.append(
                {
                    "kind": "old_high",
                    "index": i,
                    "time_ms": bars[i].t,
                    "confirmed_at_ms": confirmed_at,
                    "price": hi,
                    "core_reference_rule": "ICT_CORE_LIQUIDITY_OLD_EXTREMES",
                    "geometry_evidence_class": "D",
                }
            )
        if is_lo:
            lows.append(
                {
                    "kind": "old_low",
                    "index": i,
                    "time_ms": bars[i].t,
                    "confirmed_at_ms": confirmed_at,
                    "price": lo,
                    "core_reference_rule": "ICT_CORE_LIQUIDITY_OLD_EXTREMES",
                    "geometry_evidence_class": "D",
                }
            )
    return {"highs": highs, "lows": lows}


def fair_value_gaps(bars: list[Bar]) -> list[dict[str, Any]]:
    """Detect the source-compatible three-candle imbalance primitive.

    We deliberately report later touch/full traversal as observations rather
    than calling either one 'mitigation' or 'invalidation'; those words require
    a model-specific rule and should not be smuggled in here.
    """
    out: list[dict[str, Any]] = []
    for i in range(2, len(bars)):
        a = bars[i - 2]
        c = bars[i]
        if c.l > a.h:
            low, high, side = a.h, c.l, "BULLISH"
        elif c.h < a.l:
            low, high, side = c.h, a.l, "BEARISH"
        else:
            continue

        touched = False
        fully_traversed = False
        first_touch_ms = None
        first_full_ms = None
        for later in bars[i + 1 :]:
            overlap = later.h >= low and later.l <= high
            if overlap and not touched:
                touched = True
                first_touch_ms = later.t
            if side == "BULLISH":
                full = later.l <= low
            else:
                full = later.h >= high
            if full and not fully_traversed:
                fully_traversed = True
                first_full_ms = later.t
                break

        out.append(
            {
                "kind": "FVG",
                "side": side,
                "created_index": i,
                "created_at_ms": c.close_t,
                "low": low,
                "high": high,
                "ce": (low + high) / 2.0,
                "touched_after_creation": touched,
                "first_touch_ms": first_touch_ms,
                "fully_traversed_after_creation": fully_traversed,
                "first_full_traversal_ms": first_full_ms,
                "rule_id": "ICT_CORE_FVG_3_CANDLE",
                "evidence_class": "B",
                "geometry_status": "SOURCE_CERTIFIED",
                "primitive_usable": True,
                "validity_claim": "NONE",
            }
        )
    return out


def liquidity_raids(
    bars: list[Bar],
    swings: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    """Describe raids of already-confirmed old highs/lows without creating bias."""
    out: list[dict[str, Any]] = []
    refs = list(swings.get("highs") or []) + list(swings.get("lows") or [])
    for ref in refs:
        level = float(ref["price"])
        start = int(ref["index"]) + 1
        # A pivot cannot be used before its right-side confirmation exists.
        confirm_ms = int(ref["confirmed_at_ms"])
        for b in bars[start:]:
            if b.close_t < confirm_ms:
                continue
            if ref["kind"] == "old_high":
                raided = b.h > level
                reclaimed = b.c < level
                side = "BUY_SIDE"
            else:
                raided = b.l < level
                reclaimed = b.c > level
                side = "SELL_SIDE"
            if not raided:
                continue
            out.append(
                {
                    "kind": "LIQUIDITY_RAID",
                    "liquidity_side": side,
                    "reference_kind": ref["kind"],
                    "reference_price": level,
                    "reference_time_ms": ref["time_ms"],
                    "event_time_ms": b.t,
                    "event_close_ms": b.close_t,
                    "closed_back_through_reference": bool(reclaimed),
                    "rule_id": "ICT_CORE_LIQUIDITY_OLD_EXTREMES",
                    "reference_evidence_class": "A",
                    "event_geometry_evidence_class": "B",
                }
            )
            break
    out.sort(key=lambda x: (x["event_time_ms"], x["reference_time_ms"]))
    return out


def _latest_dealing_range(
    bars: list[Bar],
    swings: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    """Create a descriptive range from the latest opposite confirmed swings.

    The 50% equilibrium and OTE percentages are Core-sourced. Choosing which
    swing pair defines the active dealing range is discretionary, so this helper
    is explicitly a TMBT quantification (D), not a canonical ICT range selector.
    """
    highs = list(swings.get("highs") or [])
    lows = list(swings.get("lows") or [])
    if not highs or not lows or not bars:
        return {"available": False, "reason": "opposite_confirmed_swings_unavailable"}

    h = highs[-1]
    l = lows[-1]
    high = float(h["price"])
    low = float(l["price"])
    if high <= low:
        return {"available": False, "reason": "invalid_swing_range"}

    direction = "BULLISH" if int(l["time_ms"]) < int(h["time_ms"]) else "BEARISH"
    eq = (high + low) / 2.0
    last = bars[-1].c
    if last > eq:
        location = "PREMIUM"
    elif last < eq:
        location = "DISCOUNT"
    else:
        location = "EQUILIBRIUM"

    rng = high - low
    if direction == "BULLISH":
        p62 = high - 0.62 * rng
        p705 = high - 0.705 * rng
        p79 = high - 0.79 * rng
    else:
        p62 = low + 0.62 * rng
        p705 = low + 0.705 * rng
        p79 = low + 0.79 * rng

    return {
        "available": True,
        "low": low,
        "high": high,
        "equilibrium": eq,
        "last_price": last,
        "location": location,
        "impulse_direction": direction,
        "ote_zone": {
            "available": True,
            "p62": p62,
            "p70_5": p705,
            "p79": p79,
            "low": min(p62, p79),
            "high": max(p62, p79),
            "reference": p705,
            "geometry_status": "SOURCE_CERTIFIED",
        },
        "source_rules": ["ICT_CORE_OTE_ZONE"],
        "range_selection_evidence_class": "D",
        "equilibrium_evidence_class": "A",
        "ote_geometry_evidence_class": "A",
        "note": "OTE percentages are source-certified; latest-opposite-swing active range selection remains a TMBT convention.",
    }


def profile_pipeline_contract(profile_id: str) -> dict[str, Any]:
    prov = ict_core_rules.expanded_provenance(profile_id)
    non_core = list(prov.get("non_core_assumptions") or [])
    core_rules = list(prov.get("core_rules") or [])
    safe_rules = ict_core_rules.production_safe_core_rules(core_rules)
    locked_rules = [rid for rid in core_rules if rid not in safe_rules]
    return {
        "pipeline_version": PIPELINE_VERSION,
        "profile_id": profile_id,
        "context": {
            "status": "SOURCE_AWARE",
            "core_rules": core_rules,
            "production_safe_core_rules": safe_rules,
            "locked_core_rules": locked_rules,
        },
        "event": {
            "status": "SOURCE_AWARE",
            "primitives": [
                x
                for x in ("ICT_CORE_LIQUIDITY_OLD_EXTREMES", "ICT_CORE_FVG_3_CANDLE")
                if x in (prov.get("core_rules") or [])
            ],
        },
        "setup": {
            "status": "MODEL_SPECIFIC",
            "non_core_assumptions": non_core,
            "auto_infer_from_core_events": False,
        },
        "execution": {
            "status": "MODEL_SPECIFIC",
            "auto_infer_from_core_events": False,
        },
        "risk": {
            "status": "MODEL_SPECIFIC",
            "auto_infer_from_core_events": False,
        },
        "auto_live_promotion": False,
    }


def snapshot(
    rows: list[dict[str, Any]] | None,
    *,
    market: str,
    timeframe: str,
    as_of_ms: int | None = None,
    pivot_left: int = 2,
    pivot_right: int = 2,
    max_events: int = 20,
) -> dict[str, Any]:
    """Build the source-aware CONTEXT -> EVENT snapshot for one bar stream."""
    bars = normalize_closed_bars(rows, timeframe=timeframe, as_of_ms=as_of_ms)
    swings = confirmed_swings(bars, left=pivot_left, right=pivot_right)
    fvgs = fair_value_gaps(bars)
    raids = liquidity_raids(bars, swings)
    dealing = _latest_dealing_range(bars, swings)

    events = sorted(
        [
            *[
                {
                    **x,
                    "_sort_ms": int(x.get("created_at_ms") or 0),
                }
                for x in fvgs
            ],
            *[
                {
                    **x,
                    "_sort_ms": int(x.get("event_time_ms") or 0),
                }
                for x in raids
            ],
        ],
        key=lambda x: x["_sort_ms"],
    )
    for x in events:
        x.pop("_sort_ms", None)
    if max_events > 0:
        events = events[-int(max_events) :]

    latest_fvg = fvgs[-1] if fvgs else None
    latest_raid = raids[-1] if raids else None
    return {
        "pipeline_version": PIPELINE_VERSION,
        "market": str(market or "").upper(),
        "timeframe": timeframe,
        "closed_bars": len(bars),
        "as_of_ms": int(as_of_ms) if as_of_ms is not None else (bars[-1].close_t if bars else None),
        "layers": {
            "context": {
                "status": "READY" if bars else "UNAVAILABLE",
                "dealing_range": dealing,
                "latest_confirmed_high": (swings.get("highs") or [None])[-1],
                "latest_confirmed_low": (swings.get("lows") or [None])[-1],
            },
            "event": {
                "status": "READY" if bars else "UNAVAILABLE",
                "latest_fvg": latest_fvg,
                "latest_liquidity_raid": latest_raid,
                "recent_events": events,
                "rules": [
                    "ICT_CORE_FVG_3_CANDLE",
                    "ICT_CORE_LIQUIDITY_OLD_EXTREMES",
                ],
            },
            "setup": {
                "status": "LOCKED",
                "reason": "Core context/events do not imply a strategy entry without a profile-specific setup contract.",
            },
            "execution": {
                "status": "LOCKED",
                "reason": "Execution belongs to the selected model, not to the Core primitive detector.",
            },
            "risk": {
                "status": "LOCKED",
                "reason": "Risk/position management belongs to the selected model and account policy.",
            },
        },
        "audit": {
            "closed_candles_only": True,
            "pivot_geometry_evidence_class": "D",
            "fvg_geometry_evidence_class": "B",
            "fvg_geometry_locked": False,
            "ote_geometry_locked": False,
            "liquidity_reference_evidence_class": "A",
            "profitability_claim": False,
        },
    }
