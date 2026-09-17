from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Callable, Iterable

ACTIVE_STAGES = {"WATCH", "FORMING", "STRONG", "READY", "ARMED", "TRIGGERED", "SIGNAL"}
IFVG_TOKEN = "IFVG"


def _to_ms(v):
    if v is None or v == "":
        return None
    try:
        x = float(v)
        return int(x if x > 1e12 else x * 1000)
    except Exception:
        pass
    try:
        z = str(v).strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(z)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.astimezone(timezone.utc).timestamp() * 1000)
    except Exception:
        return None


def _closed_bars(rows: Iterable[dict], tf_ms: int) -> list[dict]:
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    out = []
    for row in rows or []:
        t = _to_ms(row.get("t"))
        close_t = _to_ms(row.get("close_t"))
        if close_t is None and t is not None:
            close_t = t + tf_ms
        if close_t is not None and close_t <= now_ms:
            out.append(row)
    return out


def _ema(values: list[float], period: int) -> float | None:
    if len(values) < period:
        return None
    alpha = 2.0 / (period + 1.0)
    value = float(values[0])
    for x in values[1:]:
        value = alpha * float(x) + (1.0 - alpha) * value
    return value


def _norm_side(v) -> str:
    z = str(v or "").strip().upper()
    if z in {"BUY", "BULL", "BULLISH", "LONG"}:
        return "LONG"
    if z in {"SELL", "BEAR", "BEARISH", "SHORT"}:
        return "SHORT"
    return ""


def _is_ifvg(model: dict) -> bool:
    text = " ".join(
        str(model.get(k) or "")
        for k in ("name", "label", "id", "model", "model_type", "strategy")
    ).upper()
    return IFVG_TOKEN in text


def _stage(model: dict) -> str:
    return str(model.get("status") or model.get("stage") or "").strip().upper()


def htf_bias(query_fn: Callable, market: str) -> dict:
    """Return a conservative 1H directional bias from closed bars only.

    LONG  = last close > EMA20 > EMA50
    SHORT = last close < EMA20 < EMA50
    otherwise NEUTRAL.  This is deliberately simple and deterministic so it can
    be mirrored exactly in Pine/TradingView later and backtested without hidden
    discretionary rules.
    """
    result = query_fn(market, "1H", 240, None) or {}
    rows = _closed_bars(result.get("bars") or [], 60 * 60 * 1000)
    closes = []
    for row in rows:
        try:
            closes.append(float(row.get("c")))
        except Exception:
            continue

    meta = {
        "tf": "1H",
        "mode": "EMA20/50 closed-bar",
        "bias": "NEUTRAL",
        "ok": False,
        "reason": "insufficient 1H data",
        "close": closes[-1] if closes else None,
        "ema20": None,
        "ema50": None,
        "feed": result.get("feed"),
        "stale": bool(result.get("stale", not bool(rows))),
        "last_bar_utc": result.get("last_bar_utc"),
    }
    if len(closes) < 55 or meta["stale"]:
        if meta["stale"]:
            meta["reason"] = "1H feed stale/unavailable"
        return meta

    e20 = _ema(closes, 20)
    e50 = _ema(closes, 50)
    last = closes[-1]
    meta["ema20"] = e20
    meta["ema50"] = e50
    meta["ok"] = e20 is not None and e50 is not None
    if not meta["ok"]:
        return meta

    if last > e20 > e50:
        meta["bias"] = "LONG"
        meta["reason"] = "close > EMA20 > EMA50"
    elif last < e20 < e50:
        meta["bias"] = "SHORT"
        meta["reason"] = "close < EMA20 < EMA50"
    else:
        meta["bias"] = "NEUTRAL"
        meta["reason"] = "no clean 1H EMA alignment"
    return meta


def apply_htf_filter(models: Iterable[dict], query_fn: Callable) -> list[dict]:
    """Attach HTF metadata and block contradictory active iFVG setups.

    This only alters iFVG-family models.  The underlying engine stage is kept in
    engine_status.  A blocked setup cannot enter Active Now because its public
    status becomes BLOCKED.  Neutral HTF also blocks active iFVG execution; this
    prevents simultaneous long/short iFVG exposure when higher timeframe direction
    is not clear.
    """
    out = [deepcopy(m) for m in (models or [])]
    cache: dict[str, dict] = {}

    for m in out:
        if not _is_ifvg(m):
            continue
        market = str(m.get("market") or "").strip().upper()
        if not market:
            continue
        if market not in cache:
            cache[market] = htf_bias(query_fn, market)
        bias = cache[market]
        side = _norm_side(m.get("side"))
        stage = _stage(m)

        m["htf_filter"] = dict(bias)
        m["htf_bias"] = bias.get("bias")
        m["htf_tf"] = "1H"
        m["htf_filter_pass"] = bool(side and bias.get("bias") == side and bias.get("ok"))

        # Only active/actionable stages are execution-gated. Idle/wait/expired
        # rows still carry the HTF metadata for the monitor and inspector.
        if stage not in ACTIVE_STAGES or not side:
            continue

        if not bias.get("ok"):
            m["engine_status"] = stage
            m["status"] = "BLOCKED"
            m["execution_gate"] = "HTF_UNAVAILABLE"
            m["message"] = (
                f"HTF 1H unavailable/stale · {side} iFVG blocked · "
                + str(m.get("message") or "")
            ).strip(" ·")
            continue

        if bias.get("bias") == "NEUTRAL":
            m["engine_status"] = stage
            m["status"] = "BLOCKED"
            m["execution_gate"] = "HTF_NEUTRAL"
            m["message"] = (
                f"HTF 1H NEUTRAL · {side} iFVG blocked · {bias.get('reason')} · "
                + str(m.get("message") or "")
            ).strip(" ·")
            continue

        if bias.get("bias") != side:
            m["engine_status"] = stage
            m["status"] = "BLOCKED"
            m["execution_gate"] = "HTF_CONFLICT"
            m["message"] = (
                f"HTF 1H {bias.get('bias')} · {side} iFVG blocked · {bias.get('reason')} · "
                + str(m.get("message") or "")
            ).strip(" ·")
        else:
            m["execution_gate"] = m.get("execution_gate") or "HTF_PASS"
            base = str(m.get("message") or "")
            prefix = f"HTF 1H {bias.get('bias')} confirmed"
            m["message"] = f"{prefix} · {base}" if base else prefix

    return out
