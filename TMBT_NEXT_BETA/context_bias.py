from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from typing import Any, Callable

NY = ZoneInfo("America/New_York")
ASIA_START_HOUR = 20  # ICT-style default: 20:00 -> 00:00 New York
ASIA_END_HOUR = 0
SMT_TF = "30m"
SMT_PIVOT_LEFT = 2
SMT_PIVOT_RIGHT = 2
SMT_LOOKAHEAD_BARS = 6


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


def _norm_bar(b: dict[str, Any]) -> dict[str, Any] | None:
    t = _ms(b.get("t") if b.get("t") is not None else b.get("bar_open_ms"))
    close_t = _ms(b.get("close_t") if b.get("close_t") is not None else b.get("bar_close_ms"))
    o = _f(b.get("o") if b.get("o") is not None else b.get("open"))
    h = _f(b.get("h") if b.get("h") is not None else b.get("high"))
    l = _f(b.get("l") if b.get("l") is not None else b.get("low"))
    c = _f(b.get("c") if b.get("c") is not None else b.get("close"))
    if None in (t, o, h, l, c):
        return None
    return {"t": int(t), "close_t": int(close_t or t), "o": o, "h": h, "l": l, "c": c}


def _bars(query_fn: Callable, market: str, tf: str, limit: int = 1000) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    q = query_fn(market, tf, limit, None) or {}
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    out: list[dict[str, Any]] = []
    for raw in q.get("bars") or []:
        b = _norm_bar(raw)
        if not b:
            continue
        if b["close_t"] > now_ms:
            continue
        out.append(b)
    dedup = {b["t"]: b for b in out}
    return [dedup[k] for k in sorted(dedup)], q


def _dt(ms: int) -> datetime:
    return datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc).astimezone(NY)


def _anchor_day(bars: list[dict[str, Any]]) -> datetime | None:
    if not bars:
        return None
    x = _dt(bars[-1]["t"])
    return datetime(x.year, x.month, x.day, tzinfo=NY)


def _session_levels(bars: list[dict[str, Any]]) -> dict[str, Any]:
    day = _anchor_day(bars)
    if day is None:
        return {"available": False, "reason": "no_5m_bars"}

    midnight = day
    asia_start = day - timedelta(hours=4)  # 20:00 previous NY calendar day
    asia_end = day
    asia = [b for b in bars if asia_start <= _dt(b["t"]) < asia_end]
    after_midnight = [b for b in bars if _dt(b["t"]) >= midnight]

    mo_bar = None
    for b in after_midnight:
        d = _dt(b["t"])
        if d <= midnight + timedelta(minutes=15):
            mo_bar = b
            break
        if d > midnight + timedelta(minutes=15):
            break

    result: dict[str, Any] = {
        "available": bool(asia),
        "day_ny": day.date().isoformat(),
        "asia_start_ny": asia_start.isoformat(),
        "asia_end_ny": asia_end.isoformat(),
        "midnight_open": mo_bar["o"] if mo_bar else None,
        "asia_high": max((b["h"] for b in asia), default=None),
        "asia_low": min((b["l"] for b in asia), default=None),
        "last_price": bars[-1]["c"] if bars else None,
    }
    if not asia:
        result["reason"] = "overnight_bars_missing"
        return result

    ah, al, mo = result["asia_high"], result["asia_low"], result["midnight_open"]
    current = [b for b in after_midnight if b["t"] >= int(midnight.astimezone(timezone.utc).timestamp() * 1000)]
    if current and mo is not None:
        result["midnight_position"] = "ABOVE" if current[-1]["c"] > mo else "BELOW" if current[-1]["c"] < mo else "AT"
        result["midnight_bull_reclaim"] = min(b["l"] for b in current) < mo and current[-1]["c"] > mo
        result["midnight_bear_reclaim"] = max(b["h"] for b in current) > mo and current[-1]["c"] < mo
    else:
        result["midnight_position"] = "UNAVAILABLE"
        result["midnight_bull_reclaim"] = False
        result["midnight_bear_reclaim"] = False

    def first_reclaim_down() -> int | None:
        swept = False
        for i, b in enumerate(current):
            if b["l"] < al:
                swept = True
            if swept and b["c"] > al:
                return i
        return None

    def first_reclaim_up() -> int | None:
        swept = False
        for i, b in enumerate(current):
            if b["h"] > ah:
                swept = True
            if swept and b["c"] < ah:
                return i
        return None

    down_i = first_reclaim_down()
    up_i = first_reclaim_up()
    bull = down_i is not None
    bear = up_i is not None
    bull_distributed = bull and any(b["c"] > ah for b in current[down_i + 1 :])
    bear_distributed = bear and any(b["c"] < al for b in current[up_i + 1 :])

    if bull and not bear:
        po3_bias = "BULLISH"
        po3_phase = "DISTRIBUTION" if bull_distributed else "MANIPULATION_RECLAIM"
    elif bear and not bull:
        po3_bias = "BEARISH"
        po3_phase = "DISTRIBUTION" if bear_distributed else "MANIPULATION_RECLAIM"
    elif bull and bear:
        po3_bias = "CONFLICT"
        po3_phase = "BOTH_SIDES_SWEPT"
    else:
        po3_bias = "NEUTRAL"
        po3_phase = "ACCUMULATION_OR_NONE"

    result.update({
        "po3_bias": po3_bias,
        "po3_phase": po3_phase,
        "asia_low_swept_reclaimed": bull,
        "asia_high_swept_reclaimed": bear,
        "bull_distribution_confirmed": bull_distributed,
        "bear_distribution_confirmed": bear_distributed,
    })
    return result


def _pivots(bars: list[dict[str, Any]], side: str) -> list[tuple[int, float]]:
    out: list[tuple[int, float]] = []
    left, right = SMT_PIVOT_LEFT, SMT_PIVOT_RIGHT
    for i in range(left, len(bars) - right):
        if side == "LOW":
            v = bars[i]["l"]
            if all(v < bars[j]["l"] for j in range(i - left, i)) and all(v <= bars[j]["l"] for j in range(i + 1, i + right + 1)):
                out.append((i, v))
        else:
            v = bars[i]["h"]
            if all(v > bars[j]["h"] for j in range(i - left, i)) and all(v >= bars[j]["h"] for j in range(i + 1, i + right + 1)):
                out.append((i, v))
    return out


def _swing_state(bars: list[dict[str, Any]]) -> dict[str, Any]:
    if len(bars) < 12:
        return {"available": False, "reason": "insufficient_30m_bars"}
    lows = _pivots(bars, "LOW")
    highs = _pivots(bars, "HIGH")
    if not lows or not highs:
        return {"available": False, "reason": "no_confirmed_30m_swings"}
    li, lv = lows[-1]
    hi, hv = highs[-1]
    low_window = bars[li + 1 : min(len(bars), li + 1 + SMT_LOOKAHEAD_BARS)]
    high_window = bars[hi + 1 : min(len(bars), hi + 1 + SMT_LOOKAHEAD_BARS)]
    low_break = next((k for k, b in enumerate(low_window) if b["l"] < lv), None)
    high_break = next((k for k, b in enumerate(high_window) if b["h"] > hv), None)
    low_reclaim = low_break is not None and any(b["c"] > lv for b in low_window[low_break:])
    high_reclaim = high_break is not None and any(b["c"] < hv for b in high_window[high_break:])
    return {
        "available": True,
        "reference_low": lv,
        "reference_low_t": bars[li]["t"],
        "reference_high": hv,
        "reference_high_t": bars[hi]["t"],
        "broke_low": low_break is not None,
        "reclaimed_low": bool(low_reclaim),
        "broke_high": high_break is not None,
        "reclaimed_high": bool(high_reclaim),
    }


def _smt(nq: dict[str, Any], es: dict[str, Any]) -> dict[str, Any]:
    if not nq.get("available") or not es.get("available"):
        return {"bias": "UNAVAILABLE", "reason": "30m swing context unavailable", "nq": nq, "es": es}
    nq_low = bool(nq.get("broke_low") and nq.get("reclaimed_low"))
    es_low = bool(es.get("broke_low") and es.get("reclaimed_low"))
    nq_high = bool(nq.get("broke_high") and nq.get("reclaimed_high"))
    es_high = bool(es.get("broke_high") and es.get("reclaimed_high"))
    bullish = nq_low != es_low
    bearish = nq_high != es_high
    if bullish and not bearish:
        sweeper = "NQ" if nq_low else "ES"
        holder = "ES" if nq_low else "NQ"
        return {"bias": "BULLISH", "reason": f"{sweeper} made/reclaimed a new 30m swing low while {holder} held its swing low", "sweeper": sweeper, "holder": holder, "nq": nq, "es": es}
    if bearish and not bullish:
        sweeper = "NQ" if nq_high else "ES"
        holder = "ES" if nq_high else "NQ"
        return {"bias": "BEARISH", "reason": f"{sweeper} made/reclaimed a new 30m swing high while {holder} held its swing high", "sweeper": sweeper, "holder": holder, "nq": nq, "es": es}
    if bullish and bearish:
        return {"bias": "CONFLICT", "reason": "both bullish and bearish SMT divergences are active", "nq": nq, "es": es}
    return {"bias": "NEUTRAL", "reason": "NQ and ES are structurally synchronized", "nq": nq, "es": es}


def build_context(query_fn: Callable) -> dict[str, Any]:
    nq5, nq5q = _bars(query_fn, "NQ", "5m", 1400)
    es5, es5q = _bars(query_fn, "ES", "5m", 1400)
    nq30, nq30q = _bars(query_fn, "NQ", SMT_TF, 500)
    es30, es30q = _bars(query_fn, "ES", SMT_TF, 500)

    nq_levels = _session_levels(nq5)
    es_levels = _session_levels(es5)
    smt = _smt(_swing_state(nq30), _swing_state(es30))

    po3_candidates = [x.get("po3_bias") for x in (nq_levels, es_levels) if x.get("po3_bias")]
    directional = {x for x in po3_candidates if x in {"BULLISH", "BEARISH"}}
    if len(directional) == 1:
        po3_bias = next(iter(directional))
    elif len(directional) > 1:
        po3_bias = "CONFLICT"
    elif any(x == "CONFLICT" for x in po3_candidates):
        po3_bias = "CONFLICT"
    elif po3_candidates:
        po3_bias = "NEUTRAL"
    else:
        po3_bias = "UNAVAILABLE"

    smt_bias = smt.get("bias", "UNAVAILABLE")
    if smt_bias in {"BULLISH", "BEARISH"} and po3_bias in {"BULLISH", "BEARISH"}:
        if smt_bias == po3_bias:
            bias, quality = smt_bias, "CONFIRMED"
        else:
            bias, quality = "CONFLICT", "CONFLICT"
    elif smt_bias in {"BULLISH", "BEARISH"}:
        bias, quality = smt_bias, "SMT_ONLY"
    elif po3_bias in {"BULLISH", "BEARISH"}:
        bias, quality = po3_bias, "PO3_ONLY"
    elif smt_bias == "CONFLICT" or po3_bias == "CONFLICT":
        bias, quality = "CONFLICT", "CONFLICT"
    else:
        bias, quality = "NEUTRAL", "NO_DIRECTION"

    proxy = any(str(q.get("ticker") or "").upper() in {"QQQ", "SPY"} for q in (nq5q, es5q, nq30q, es30q))
    overnight_ok = bool(nq_levels.get("available") and es_levels.get("available"))
    return {
        "bias": bias,
        "quality": quality,
        "smt": smt,
        "po3_bias": po3_bias,
        "markets": {"NQ": nq_levels, "ES": es_levels},
        "settings": {
            "smt_tf": SMT_TF,
            "smt_pivot": [SMT_PIVOT_LEFT, SMT_PIVOT_RIGHT],
            "smt_window_bars": SMT_LOOKAHEAD_BARS,
            "asia_session_ny": "20:00-00:00",
            "midnight_open_ny": "00:00",
            "po3_rule": "Asia sweep + reclaim; distribution confirmed through opposite Asia side",
        },
        "data": {
            "proxy": proxy,
            "overnight_ok": overnight_ok,
            "hard_gate_ready": smt_bias in {"BULLISH", "BEARISH", "CONFLICT"} or (overnight_ok and po3_bias in {"BULLISH", "BEARISH", "CONFLICT"}),
        },
    }


def apply_to_models(models: list[dict[str, Any]], query_fn: Callable, active_stages: set[str]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    context = build_context(query_fn)
    bias = context.get("bias", "NEUTRAL")
    gate_ready = bool(context.get("data", {}).get("hard_gate_ready"))
    out: list[dict[str, Any]] = []
    for src in models:
        m = dict(src)
        market = str(m.get("market") or "").upper()
        if market in {"NQ", "ES"}:
            m["bias_context"] = context
            m["session_bias"] = bias
            m["smt_bias"] = context.get("smt", {}).get("bias", "UNAVAILABLE")
            m["po3_bias"] = context.get("po3_bias", "UNAVAILABLE")
            levels = context.get("markets", {}).get(market, {})
            m["midnight_open"] = levels.get("midnight_open")
            m["asia_high"] = levels.get("asia_high")
            m["asia_low"] = levels.get("asia_low")

        text = " ".join(str(m.get(k) or "") for k in ("name", "label", "id", "model", "model_type", "strategy")).upper()
        intraday_ifvg = market in {"NQ", "ES"} and ("IFVG" in text or "SILVER" in text)
        stage = str(m.get("status") or m.get("stage") or "").upper()
        side = str(m.get("side") or "").upper()
        side = "LONG" if side in {"BUY", "BULL", "BULLISH", "LONG"} else "SHORT" if side in {"SELL", "BEAR", "BEARISH", "SHORT"} else ""
        if intraday_ifvg and stage in active_stages and gate_ready:
            block = bias == "CONFLICT" or (bias == "BULLISH" and side == "SHORT") or (bias == "BEARISH" and side == "LONG")
            if block:
                m["engine_status"] = stage
                m["status"] = "BLOCKED"
                m["execution_gate"] = "BIAS_CONFLICT"
                reason = f"SMT/PO3 bias {bias}; {side or 'unknown'} setup blocked"
                base = str(m.get("message") or "")
                m["message"] = f"{reason} · {base}" if base else reason
        out.append(m)
    return out, context
