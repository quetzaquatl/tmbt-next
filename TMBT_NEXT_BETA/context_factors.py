from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from typing import Any, Callable
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
ACTIVE_STAGES = {"WATCH", "FORMING", "STRONG", "READY", "ARMED", "TRIGGERED", "SIGNAL"}


@dataclass(frozen=True)
class ContextConfig:
    target_market: str = "NQ"
    peer_market: str = "ES"
    asia_start_hour_ny: int = 20
    asia_end_hour_ny: int = 0
    smt_tf: str = "30m"
    smt_pivot_left: int = 2
    smt_pivot_right: int = 2
    smt_lookahead_bars: int = 6
    smt_hard_veto: bool = True
    po3_hard_veto: bool = True
    require_reclaim_for_smt: bool = True


DEFAULT_CONFIG = ContextConfig()

BACKTEST_FIELDS = [
    "ctx_bias",
    "ctx_quality",
    "ctx_allow_long",
    "ctx_allow_short",
    "ctx_veto_reason",
    "ctx_smt_bias",
    "ctx_smt_state",
    "ctx_smt_sweeper",
    "ctx_smt_holder",
    "ctx_po3_bias",
    "ctx_po3_phase",
    "ctx_asia_high",
    "ctx_asia_low",
    "ctx_asia_first_sweep",
    "ctx_asia_low_swept",
    "ctx_asia_high_swept",
    "ctx_midnight_open",
    "ctx_midnight_position",
    "ctx_midnight_bull_reclaim",
    "ctx_midnight_bear_reclaim",
    "ctx_index_session_phase",
    "ctx_index_or_high",
    "ctx_index_or_low",
    "ctx_index_or_complete",
    "ctx_index_am_active",
    "ctx_index_pm_active",
]


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


def _norm_bar(raw: dict[str, Any]) -> dict[str, Any] | None:
    t = _ms(raw.get("t") if raw.get("t") is not None else raw.get("bar_open_ms"))
    close_t = _ms(raw.get("close_t") if raw.get("close_t") is not None else raw.get("bar_close_ms"))
    o = _f(raw.get("o") if raw.get("o") is not None else raw.get("open"))
    h = _f(raw.get("h") if raw.get("h") is not None else raw.get("high"))
    l = _f(raw.get("l") if raw.get("l") is not None else raw.get("low"))
    c = _f(raw.get("c") if raw.get("c") is not None else raw.get("close"))
    if None in (t, o, h, l, c):
        return None
    return {"t": int(t), "close_t": int(close_t or t), "o": o, "h": h, "l": l, "c": c}


def normalize_bars(rows: list[dict[str, Any]] | None, as_of_ms: int | None = None) -> list[dict[str, Any]]:
    if as_of_ms is None:
        as_of_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    out: dict[int, dict[str, Any]] = {}
    for raw in rows or []:
        b = _norm_bar(raw)
        if not b or b["close_t"] > as_of_ms:
            continue
        out[b["t"]] = b
    return [out[k] for k in sorted(out)]


def _dt(ms: int) -> datetime:
    return datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc).astimezone(NY)


def _session_context(bars: list[dict[str, Any]], as_of_ms: int | None = None, cfg: ContextConfig = DEFAULT_CONFIG) -> dict[str, Any]:
    if not bars:
        return {"available": False, "reason": "no_5m_bars"}
    if as_of_ms is None:
        as_of_ms = bars[-1]["close_t"]
    as_of = _dt(as_of_ms)
    day = datetime(as_of.year, as_of.month, as_of.day, tzinfo=NY)
    asia_start = day - timedelta(hours=(24 - cfg.asia_start_hour_ny))
    asia_end = day + timedelta(hours=cfg.asia_end_hour_ny)
    asia = [b for b in bars if asia_start <= _dt(b["t"]) < asia_end]
    current = [b for b in bars if day <= _dt(b["t"]) <= as_of]

    # ICT Core Month 10 index-futures clock context. These are descriptive,
    # point-in-time-safe features only; they do not auto-trigger a trade.
    index_or_start = day + timedelta(hours=9, minutes=30)
    index_or_end = day + timedelta(hours=10, minutes=30)
    index_am_end = day + timedelta(hours=12)
    index_pm_start = day + timedelta(hours=13)
    index_pm_end = day + timedelta(hours=16)
    index_or = [b for b in current if index_or_start <= _dt(b["t"]) < index_or_end]
    index_or_high = max((b["h"] for b in index_or), default=None)
    index_or_low = min((b["l"] for b in index_or), default=None)
    index_or_complete = as_of >= index_or_end

    if as_of < index_or_start:
        index_session_phase = "PRE_RTH"
    elif as_of < index_or_end:
        index_session_phase = "OPENING_RANGE"
    elif as_of < index_am_end:
        index_session_phase = "AM_AFTER_OR"
    elif as_of < index_pm_start:
        index_session_phase = "MIDDAY"
    elif as_of < index_pm_end:
        index_session_phase = "PM"
    else:
        index_session_phase = "AFTER_RTH"

    if not asia:
        return {
            "available": False,
            "reason": "overnight_bars_missing",
            "day_ny": day.date().isoformat(),
            "asia_start_ny": asia_start.isoformat(),
            "asia_end_ny": asia_end.isoformat(),
        }

    ah = max(b["h"] for b in asia)
    al = min(b["l"] for b in asia)
    midnight_bar = next((b for b in current if _dt(b["t"]) < day + timedelta(minutes=15)), None)
    mo = midnight_bar["o"] if midnight_bar else None

    low_sweep_i = next((i for i, b in enumerate(current) if b["l"] < al), None)
    high_sweep_i = next((i for i, b in enumerate(current) if b["h"] > ah), None)

    def first_reclaim(start_i: int | None, side: str) -> int | None:
        if start_i is None:
            return None
        if side == "LOW":
            return next((i for i in range(start_i, len(current)) if current[i]["c"] > al), None)
        return next((i for i in range(start_i, len(current)) if current[i]["c"] < ah), None)

    low_reclaim_i = first_reclaim(low_sweep_i, "LOW")
    high_reclaim_i = first_reclaim(high_sweep_i, "HIGH")

    if low_sweep_i is None and high_sweep_i is None:
        first_side = "NONE"
    elif high_sweep_i is None or (low_sweep_i is not None and low_sweep_i < high_sweep_i):
        first_side = "LOW"
    elif low_sweep_i is None or high_sweep_i < low_sweep_i:
        first_side = "HIGH"
    else:
        first_side = "BOTH"

    po3_bias = "NEUTRAL"
    po3_phase = "ACCUMULATION_OR_NONE"
    if first_side == "LOW":
        if low_reclaim_i is None:
            po3_phase = "LOW_MANIPULATION_PENDING"
        else:
            po3_bias = "BULLISH"
            distributed = any(b["h"] > ah or b["c"] > ah for b in current[low_reclaim_i + 1 :])
            po3_phase = "DISTRIBUTION" if distributed else "MANIPULATION_RECLAIM"
    elif first_side == "HIGH":
        if high_reclaim_i is None:
            po3_phase = "HIGH_MANIPULATION_PENDING"
        else:
            po3_bias = "BEARISH"
            distributed = any(b["l"] < al or b["c"] < al for b in current[high_reclaim_i + 1 :])
            po3_phase = "DISTRIBUTION" if distributed else "MANIPULATION_RECLAIM"
    elif first_side == "BOTH":
        po3_bias = "CONFLICT"
        po3_phase = "AMBIGUOUS_DOUBLE_SWEEP"

    midnight_position = "UNAVAILABLE"
    bull_midnight_reclaim = False
    bear_midnight_reclaim = False
    if current and mo is not None:
        last = current[-1]["c"]
        midnight_position = "ABOVE" if last > mo else "BELOW" if last < mo else "AT"
        first_below = next((i for i, b in enumerate(current) if b["l"] < mo), None)
        first_above = next((i for i, b in enumerate(current) if b["h"] > mo), None)
        if first_below is not None:
            bull_midnight_reclaim = any(b["c"] > mo for b in current[first_below:])
        if first_above is not None:
            bear_midnight_reclaim = any(b["c"] < mo for b in current[first_above:])

    return {
        "available": True,
        "day_ny": day.date().isoformat(),
        "asia_start_ny": asia_start.isoformat(),
        "asia_end_ny": asia_end.isoformat(),
        "asia_high": ah,
        "asia_low": al,
        "asia_first_sweep": first_side,
        "asia_low_swept": low_sweep_i is not None,
        "asia_high_swept": high_sweep_i is not None,
        "asia_low_reclaimed": low_reclaim_i is not None,
        "asia_high_reclaimed": high_reclaim_i is not None,
        "po3_bias": po3_bias,
        "po3_phase": po3_phase,
        "midnight_open": mo,
        "midnight_position": midnight_position,
        "midnight_bull_reclaim": bull_midnight_reclaim,
        "midnight_bear_reclaim": bear_midnight_reclaim,
        "index_session_phase": index_session_phase,
        "index_or_start_ny": index_or_start.isoformat(),
        "index_or_end_ny": index_or_end.isoformat(),
        "index_or_high": index_or_high,
        "index_or_low": index_or_low,
        "index_or_complete": bool(index_or_complete),
        "index_am_active": bool(index_or_start <= as_of < index_am_end),
        "index_pm_active": bool(index_pm_start <= as_of < index_pm_end),
        "last_price": current[-1]["c"] if current else bars[-1]["c"],
    }


def _pivots(bars: list[dict[str, Any]], side: str, cfg: ContextConfig) -> list[tuple[int, float]]:
    out: list[tuple[int, float]] = []
    left, right = cfg.smt_pivot_left, cfg.smt_pivot_right
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


def _swing_state(bars: list[dict[str, Any]], cfg: ContextConfig) -> dict[str, Any]:
    if len(bars) < max(12, cfg.smt_pivot_left + cfg.smt_pivot_right + 5):
        return {"available": False, "reason": "insufficient_smt_bars"}
    lows = _pivots(bars, "LOW", cfg)
    highs = _pivots(bars, "HIGH", cfg)
    if not lows or not highs:
        return {"available": False, "reason": "no_confirmed_swings"}

    li, lv = lows[-1]
    hi, hv = highs[-1]
    low_window = bars[li + 1 : min(len(bars), li + 1 + cfg.smt_lookahead_bars)]
    high_window = bars[hi + 1 : min(len(bars), hi + 1 + cfg.smt_lookahead_bars)]
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


def _event(state: dict[str, Any], side: str, cfg: ContextConfig) -> bool:
    broke = bool(state.get("broke_low" if side == "LOW" else "broke_high"))
    if not broke:
        return False
    if not cfg.require_reclaim_for_smt:
        return True
    return bool(state.get("reclaimed_low" if side == "LOW" else "reclaimed_high"))


def _target_smt(target: str, peer: str, target_state: dict[str, Any], peer_state: dict[str, Any], cfg: ContextConfig) -> dict[str, Any]:
    if not target_state.get("available") or not peer_state.get("available"):
        return {
            "bias": "UNAVAILABLE",
            "state": "UNAVAILABLE",
            "reason": "synchronized swing context unavailable",
            "target": target,
            "peer": peer,
            "target_state": target_state,
            "peer_state": peer_state,
        }

    target_low = _event(target_state, "LOW", cfg)
    peer_low = _event(peer_state, "LOW", cfg)
    target_high = _event(target_state, "HIGH", cfg)
    peer_high = _event(peer_state, "HIGH", cfg)

    # Target-relative SMT: the peer raids liquidity while the target holds.
    # For NQ this encodes the user's concrete rule: ES new/reclaimed low + NQ holds = bullish NQ.
    bullish = peer_low and not target_low
    bearish = peer_high and not target_high

    if bullish and bearish:
        bias, state = "CONFLICT", "CONFLICT"
        reason = f"{peer} diverged at both sell-side and buy-side liquidity while {target} held"
        sweeper = peer
        holder = target
    elif bullish:
        bias, state = "BULLISH", "CONFIRMED"
        reason = f"{peer} swept/reclaimed its swing low while {target} held its corresponding low"
        sweeper = peer
        holder = target
    elif bearish:
        bias, state = "BEARISH", "CONFIRMED"
        reason = f"{peer} swept/reclaimed its swing high while {target} held its corresponding high"
        sweeper = peer
        holder = target
    else:
        bias, state = "NEUTRAL", "NONE"
        reason = f"no target-relative {target}/{peer} SMT divergence"
        sweeper = None
        holder = None

    return {
        "bias": bias,
        "state": state,
        "reason": reason,
        "sweeper": sweeper,
        "holder": holder,
        "target": target,
        "peer": peer,
        "target_state": target_state,
        "peer_state": peer_state,
        "counterpart_low_divergence": bool(target_low and not peer_low),
        "counterpart_high_divergence": bool(target_high and not peer_high),
    }


def evaluate_bars(
    target_5m: list[dict[str, Any]],
    peer_5m: list[dict[str, Any]],
    target_smt: list[dict[str, Any]],
    peer_smt: list[dict[str, Any]],
    *,
    as_of_ms: int | None = None,
    cfg: ContextConfig = DEFAULT_CONFIG,
) -> dict[str, Any]:
    target = cfg.target_market.upper()
    peer = cfg.peer_market.upper()
    t5 = normalize_bars(target_5m, as_of_ms)
    p5 = normalize_bars(peer_5m, as_of_ms)
    ts = normalize_bars(target_smt, as_of_ms)
    ps = normalize_bars(peer_smt, as_of_ms)
    if as_of_ms is None:
        closes = [b["close_t"] for rows in (t5, p5, ts, ps) for b in rows]
        as_of_ms = max(closes) if closes else int(datetime.now(timezone.utc).timestamp() * 1000)

    target_session = _session_context(t5, as_of_ms, cfg)
    peer_session = _session_context(p5, as_of_ms, cfg)
    smt = _target_smt(target, peer, _swing_state(ts, cfg), _swing_state(ps, cfg), cfg)

    po3_bias = target_session.get("po3_bias", "UNAVAILABLE")
    po3_phase = target_session.get("po3_phase", "UNAVAILABLE")
    smt_bias = smt.get("bias", "UNAVAILABLE")

    directional_smt = smt_bias in {"BULLISH", "BEARISH"}
    directional_po3 = po3_bias in {"BULLISH", "BEARISH"} and po3_phase in {"MANIPULATION_RECLAIM", "DISTRIBUTION"}

    if directional_smt and directional_po3:
        if smt_bias == po3_bias:
            bias, quality = smt_bias, "SMT_PO3_CONFIRMED"
        else:
            bias, quality = "CONFLICT", "SMT_PO3_CONFLICT"
    elif directional_smt:
        bias, quality = smt_bias, "SMT_CONFIRMED"
    elif directional_po3:
        bias, quality = po3_bias, "PO3_CONFIRMED"
    elif smt_bias == "CONFLICT" or po3_bias == "CONFLICT":
        bias, quality = "CONFLICT", "CONFLICT"
    else:
        bias, quality = "NEUTRAL", "NO_DIRECTION"

    hard_gate_ready = (cfg.smt_hard_veto and directional_smt) or (cfg.po3_hard_veto and directional_po3) or bias == "CONFLICT"
    allow_long = not (hard_gate_ready and bias in {"BEARISH", "CONFLICT"})
    allow_short = not (hard_gate_ready and bias in {"BULLISH", "CONFLICT"})
    veto_reason = None
    if hard_gate_ready and bias == "BULLISH":
        veto_reason = "bullish SMT/PO3 context blocks shorts"
    elif hard_gate_ready and bias == "BEARISH":
        veto_reason = "bearish SMT/PO3 context blocks longs"
    elif hard_gate_ready and bias == "CONFLICT":
        veto_reason = "SMT/PO3 conflict blocks both directions"

    return {
        "bias": bias,
        "quality": quality,
        "allow_long": allow_long,
        "allow_short": allow_short,
        "veto_reason": veto_reason,
        "hard_gate_ready": hard_gate_ready,
        "smt": smt,
        "po3_bias": po3_bias,
        "po3_phase": po3_phase,
        "markets": {target: target_session, peer: peer_session},
        "settings": asdict(cfg),
        "backtest_fields": BACKTEST_FIELDS,
        "as_of_ms": as_of_ms,
    }


def build_context(query_fn: Callable, cfg: ContextConfig = DEFAULT_CONFIG) -> dict[str, Any]:
    target, peer = cfg.target_market.upper(), cfg.peer_market.upper()
    t5q = query_fn(target, "5m", 1800, None) or {}
    p5q = query_fn(peer, "5m", 1800, None) or {}
    tsq = query_fn(target, cfg.smt_tf, 700, None) or {}
    psq = query_fn(peer, cfg.smt_tf, 700, None) or {}
    ctx = evaluate_bars(
        t5q.get("bars") or [],
        p5q.get("bars") or [],
        tsq.get("bars") or [],
        psq.get("bars") or [],
        cfg=cfg,
    )
    feeds = [t5q, p5q, tsq, psq]
    ctx["data"] = {
        "proxy": any(str(x.get("ticker") or "").upper() in {"QQQ", "SPY"} for x in feeds),
        "true_futures": all((not x.get("bars")) or x.get("feed") == "true_futures_mirror" for x in feeds),
        "target_feed": t5q.get("feed") or t5q.get("source"),
        "peer_feed": p5q.get("feed") or p5q.get("source"),
    }
    return ctx


def _side(v: Any) -> str:
    z = str(v or "").strip().upper()
    if z in {"BUY", "BULL", "BULLISH", "LONG"}:
        return "LONG"
    if z in {"SELL", "BEAR", "BEARISH", "SHORT"}:
        return "SHORT"
    return ""


def _stage(m: dict[str, Any]) -> str:
    return str(m.get("status") or m.get("stage") or "").strip().upper()


def _is_intraday_ifvg(m: dict[str, Any]) -> bool:
    market = str(m.get("market") or "").upper()
    text = " ".join(str(m.get(k) or "") for k in ("name", "label", "id", "model", "model_type", "strategy")).upper()
    return market in {"NQ", "ES"} and ("IFVG" in text or "SILVER" in text)


def _criterion(label: str, status: str, detail: str) -> dict[str, str]:
    return {"label": label, "status": status, "detail": detail}


def apply_to_models(models: list[dict[str, Any]], query_fn: Callable, cfg: ContextConfig = DEFAULT_CONFIG) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    ctx = build_context(query_fn, cfg)
    bias = ctx.get("bias", "NEUTRAL")
    out: list[dict[str, Any]] = []
    for src in models or []:
        m = dict(src)
        market = str(m.get("market") or "").upper()
        if market in {cfg.target_market.upper(), cfg.peer_market.upper()}:
            levels = ctx.get("markets", {}).get(market, {})
            m["bias_context"] = ctx
            m["session_bias"] = bias
            m["smt_bias"] = ctx.get("smt", {}).get("bias", "UNAVAILABLE")
            m["po3_bias"] = levels.get("po3_bias", "UNAVAILABLE")
            m["po3_phase"] = levels.get("po3_phase", "UNAVAILABLE")
            m["midnight_open"] = levels.get("midnight_open")
            m["asia_high"] = levels.get("asia_high")
            m["asia_low"] = levels.get("asia_low")

        if _is_intraday_ifvg(m):
            levels = ctx.get("markets", {}).get(market, {})
            smt = ctx.get("smt", {})
            criteria = list(m.get("criteria") or [])
            criteria.extend([
                _criterion("SMT NQ/ES", "PASS" if smt.get("bias") in {"BULLISH", "BEARISH"} else "PENDING", smt.get("reason") or "—"),
                _criterion("PO3", "PASS" if levels.get("po3_bias") in {"BULLISH", "BEARISH"} else "PENDING", f"{levels.get('po3_bias', '—')} · {levels.get('po3_phase', '—')}"),
                _criterion("Asia Range", "PASS" if levels.get("available") else "PENDING", f"first sweep {levels.get('asia_first_sweep', '—')} · H {levels.get('asia_high', '—')} / L {levels.get('asia_low', '—')}"),
                _criterion("Midnight Open", "PASS" if levels.get("midnight_open") is not None else "PENDING", f"{levels.get('midnight_position', '—')} · open {levels.get('midnight_open', '—')}"),
            ])
            m["criteria"] = criteria
            logic = dict(m.get("logic") or {})
            logic["context_filter"] = {
                "bias": bias,
                "quality": ctx.get("quality"),
                "SMT": smt.get("bias"),
                "PO3": levels.get("po3_bias"),
                "PO3_phase": levels.get("po3_phase"),
                "asia_first_sweep": levels.get("asia_first_sweep"),
                "midnight_position": levels.get("midnight_position"),
                "hard_veto": True,
            }
            m["logic"] = logic

            stage = _stage(m)
            side = _side(m.get("side"))
            if stage in ACTIVE_STAGES and ctx.get("hard_gate_ready"):
                blocked = (side == "LONG" and not ctx.get("allow_long", True)) or (side == "SHORT" and not ctx.get("allow_short", True))
                if blocked:
                    m["engine_status"] = stage
                    m["status"] = "BLOCKED"
                    m["execution_gate"] = "SMT_PO3_BIAS_VETO"
                    base = str(m.get("message") or "")
                    reason = ctx.get("veto_reason") or f"context bias {bias} blocks {side}"
                    m["message"] = f"{reason} · {base}" if base else reason
        out.append(m)
    return out, ctx
