from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urlparse

import server_desk as desk

core = desk.core
original = desk.original
_BASE_MODELS = core.normalize_models
_BASE_LOCAL_QUERY = original._LOCAL_SQLITE_QUERY

TF_SECONDS = {"5m": 300, "15m": 900, "30m": 1800, "1h": 3600, "4h": 14400, "1d": 86400}
EBP_TFS = ("15m", "30m", "1H")


def _bar_ms(v):
    return desk._robust_to_ms(v)


def _price_scale_ok(market: str, bars: list[dict]) -> bool:
    if not bars:
        return False
    try:
        p = float(bars[-1]["c"])
    except Exception:
        return False
    m = str(market).upper()
    if m == "NQ":
        return p > 5000.0
    if m == "ES":
        return p > 1500.0
    return True


def _local_future_query(market="NQ", tf="1H", limit=500, source=None):
    m = str(market).upper()
    ntf = core.normalize_tf(tf)
    if m not in {"NQ", "ES"}:
        return desk.desk_query_bars(market, tf, limit, source)

    if ntf == "30m":
        base = _local_future_query(m, "15m", max(100, int(limit) * 2), source)
        out = dict(base or {})
        bars = desk._aggregate_30m(out.get("bars") or [])
        out["bars"] = bars[-max(50, int(limit)):]
        out["tf"] = "30m"
        out["derived_from"] = "15m"
        if bars:
            last_ms = _bar_ms(bars[-1].get("close_t")) or _bar_ms(bars[-1].get("t"))
            now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
            age = max(0.0, (now_ms - last_ms) / 1000.0) if last_ms else None
            out["age_seconds"] = age
            out["last_bar_utc"] = datetime.fromtimestamp(last_ms / 1000.0, tz=timezone.utc).isoformat() if last_ms else None
            out["stale"] = age is None or age > 75 * 60
            out["note"] = f"local futures · {m} · 30m aus 15m · {'STALE' if out['stale'] else 'LIVE'}"
        return out

    raw = _BASE_LOCAL_QUERY(m, tf, limit, source)
    result = original._decorate_local(raw, m, tf)
    bars = result.get("bars") or []
    if not bars or not _price_scale_ok(m, bars):
        return {
            "bars": [], "db": result.get("db") if isinstance(result, dict) else None,
            "source": None, "feed": "local_futures_required", "provider": None,
            "ticker": m, "tickerid": m, "stale": True, "age_seconds": None,
            "identity_ok": False,
            "note": f"{m} Futures-Feed fehlt oder falsche Preis-Skala · Proxy wird nicht verwendet",
        }
    result = dict(result)
    result["feed"] = "local_futures"
    result["provider"] = result.get("provider") or "local"
    result["ticker"] = m
    result["tickerid"] = m
    result["identity_ok"] = True
    result["canonical"] = True
    result["note"] = f"local futures · {m} · {'STALE' if result.get('stale') else 'LIVE'} · age {original._age_text(result.get('age_seconds'))}"
    return result


def query_bars(market="NQ", tf="1H", limit=500, source=None):
    m = str(market).upper()
    if m in {"NQ", "ES"}:
        return _local_future_query(m, tf, limit, source)
    return desk.desk_query_bars(market, tf, limit, source)


def _closed_bars(market: str, tf: str, limit=500):
    payload = query_bars(market, tf, limit, None)
    bars = payload.get("bars") or []
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    sec = TF_SECONDS.get(core.normalize_tf(tf), 3600)
    out = []
    for b in bars:
        t = _bar_ms(b.get("t"))
        close_t = _bar_ms(b.get("close_t")) or (t + sec * 1000 if t is not None else None)
        if close_t is not None and close_t <= now_ms + 5000:
            out.append(b)
    return payload, out


def _touch(bar: dict, level: float) -> bool:
    try:
        return float(bar["l"]) <= level <= float(bar["h"])
    except Exception:
        return False


def _ebp_candidate(prev: dict, ebp: dict):
    try:
        po, ph, pl, pc = map(float, (prev["o"], prev["h"], prev["l"], prev["c"]))
        o, h, l, c = map(float, (ebp["o"], ebp["h"], ebp["l"], ebp["c"]))
    except Exception:
        return None
    rng = h - l
    if rng <= 0:
        return None
    body_hi, body_lo = max(po, pc), min(po, pc)
    bull = l < pl and c > body_hi
    bear = h > ph and c < body_lo
    if bull == bear:
        return None
    side = "Long" if bull else "Short"
    retrace = ((h - c) / rng * 100.0) if bull else ((c - l) / rng * 100.0)
    if retrace <= 15.0:
        quality = "Strong"
        if bull:
            entry, stop = h - 0.25 * rng, h - 0.75 * rng
        else:
            entry, stop = l + 0.25 * rng, l + 0.75 * rng
    elif retrace <= 50.0:
        quality = "Indecisive"
        entry = l + 0.50 * rng
        stop = l if bull else h
    else:
        quality = "Very indecisive"
        entry = c
        stop = l if bull else h
    risk = abs(entry - stop)
    if risk <= 0:
        return None
    target = entry + (2.0 * risk if bull else -2.0 * risk)
    return {
        "side": side, "entry": entry, "stop": stop, "target": target,
        "rr": 2.0, "quality": quality, "retrace_pct": retrace,
        "prev_high": ph, "prev_low": pl, "prev_body_high": body_hi, "prev_body_low": body_lo,
        "signal_high": h, "signal_low": l, "signal_close": c,
    }


def _eval_ebp(market: str, tf: str):
    payload, bars = _closed_bars(market, tf, 500)
    model_id = f"{market.lower()}_ebp_{str(tf).lower()}"
    base = {
        "id": model_id,
        "name": f"{market} · EBP {tf}",
        "market": market,
        "tf": tf,
        "source": "local-futures",
        "status": "IDLE",
        "side": "—",
        "entry": None, "sl": None, "tp": None, "rr": None,
        "message": "Kein bestätigtes EBP im aktuellen 4-Bar-Fenster.",
        "validity": {"status": "WAIT", "still_valid": False, "reason": "Kein bestätigtes EBP."},
        "criteria": [],
        "logic": {
            "timeframe": tf,
            "bullish": "sweep previous low and close above previous body high",
            "bearish": "sweep previous high and close below previous body low",
            "same_colour_allowed": True,
            "strong_close_pct": 15.0,
            "strong": "25% limit, 75% stop",
            "indecisive": "50% limit, EBP origin stop",
            "very_indecisive": ">50% retrace => market after confirmed close",
            "limit_valid_bars": 4,
            "target_rr": 2.0,
            "lookahead_rule": "only confirmed/closed candles can create a setup",
        },
        "arrays": {},
        "event": {},
        "setup_key": None,
    }
    if payload.get("stale") or len(bars) < 2:
        base["status"] = "DATA_STALE"
        base["message"] = payload.get("note") or "Futures-Feed nicht frisch genug."
        base["validity"] = {"status": "STALE", "still_valid": False, "reason": base["message"]}
        return base

    latest = None
    start = max(1, len(bars) - 8)
    for i in range(start, len(bars)):
        c = _ebp_candidate(bars[i - 1], bars[i])
        if c:
            latest = (i, c)
    if latest is None:
        base["criteria"] = [
            {"label": "Futures feed fresh", "status": "PASS", "detail": payload.get("note") or "LIVE"},
            {"label": f"Confirmed {tf} pair", "status": "PASS", "detail": f"{len(bars)} closed bars available."},
            {"label": "Previous-bar liquidity sweep + body engulf close", "status": "PENDING", "detail": "No current EBP pair."},
        ]
        return base

    i, c = latest
    post = bars[i + 1:]
    bars_since = len(post)
    entry_hit = any(_touch(b, c["entry"]) for b in post)
    invalidated = False
    if not entry_hit:
        try:
            invalidated = any(float(b["l"]) <= c["stop"] for b in post) if c["side"] == "Long" else any(float(b["h"]) >= c["stop"] for b in post)
        except Exception:
            invalidated = False

    if invalidated or bars_since > 4:
        stage = "EXPIRED"
        msg = "EBP bestätigt, Retest-Fenster abgelaufen/invalidiert."
        still_valid = False
    elif entry_hit:
        stage = "SIGNAL"
        msg = f"{c['side']} EBP Entry berührt."
        still_valid = True
    else:
        stage = "ARMED"
        msg = f"{c['side']} EBP bestätigt · wartet auf Entry-Retest ({max(0, 4-bars_since)} Bars Rest)."
        still_valid = True

    event_ms = _bar_ms(bars[i].get("close_t")) or _bar_ms(bars[i].get("t"))
    base.update({
        "status": stage, "side": c["side"], "entry": c["entry"], "sl": c["stop"], "tp": c["target"], "rr": 2.0,
        "message": msg,
        "validity": {"status": "VALID" if still_valid else "EXPIRED", "still_valid": still_valid, "reason": msg, "bars_remaining": max(0, 4-bars_since)},
        "criteria": [
            {"label": "Futures feed fresh", "status": "PASS", "detail": payload.get("note") or "LIVE"},
            {"label": f"Confirmed {tf} pair", "status": "PASS", "detail": f"{len(bars)} closed bars available."},
            {"label": "Previous-bar liquidity sweep", "status": "PASS", "detail": f"{c['side']} sweep confirmed."},
            {"label": "Engulf close beyond previous body", "status": "PASS", "detail": f"Close confirmed on closed {tf} candle."},
            {"label": "Close strength", "status": "PASS", "detail": f"Retrace {c['retrace_pct']:.1f}% · {c['quality']}."},
            {"label": "Entry retest within 4 bars", "status": "PASS" if entry_hit else ("FAIL" if not still_valid else "PENDING"), "detail": msg},
            {"label": "Stop", "status": "PASS", "detail": f"{c['stop']:.4f}"},
            {"label": "Target 2R", "status": "PASS", "detail": f"{c['target']:.4f}"},
        ],
        "arrays": {
            "entry": c["entry"], "stop": c["stop"], "target": c["target"],
            "prev_high": c["prev_high"], "prev_low": c["prev_low"],
            "prev_body_high": c["prev_body_high"], "prev_body_low": c["prev_body_low"],
            "signal_high": c["signal_high"], "signal_low": c["signal_low"],
        },
        "event": {"event_ms": event_ms, "event_time_utc": datetime.fromtimestamp(event_ms/1000, tz=timezone.utc).isoformat() if event_ms else None, "side": c["side"]},
        "setup_key": f"{c['side']}:{event_ms}",
    })
    return base


def enhanced_models():
    rows = []
    for m in _BASE_MODELS() or []:
        name = str(m.get("name") or "")
        market = str(m.get("market") or "").upper()
        if market in {"NQ", "ES"} and "EBP" in name.upper():
            continue
        rows.append(m)
    for market in ("NQ", "ES"):
        for tf in EBP_TFS:
            rows.append(_eval_ebp(market, tf))
    return rows


def _feed_one(market, tf="5m"):
    x = query_bars(market, tf, 100, None)
    bars = x.get("bars") or []
    last = bars[-1] if bars else {}
    return {
        "market": market, "tf": tf, "ok": bool(bars), "price": last.get("c"), "bars": len(bars),
        "feed": x.get("feed"), "provider": x.get("provider"), "ticker": x.get("ticker"), "tickerid": x.get("tickerid"),
        "last_bar_utc": x.get("last_bar_utc"), "last_received_at_utc": x.get("last_received_at_utc"),
        "age_seconds": x.get("age_seconds"), "stale": bool(x.get("stale", not bool(bars))), "note": x.get("note"),
        "path": x.get("db"), "canonical": bool(x.get("canonical")), "identity_ok": x.get("identity_ok"),
    }


def feed_status():
    markets = {}
    for market in ("NQ", "ES", "XAU"):
        tfs = {tf: _feed_one(market, tf) for tf in ("5m", "15m", "30m", "1H")}
        summary = dict(tfs["5m"])
        summary["timeframes"] = tfs
        markets[market] = summary
    return {"generated_at_utc": core.now_iso(), "markets": markets}


def readiness():
    models = [m for m in enhanced_models() if str(m.get("market")) in {"NQ", "ES"} and "EBP" in str(m.get("name", "")).upper()]
    return {
        "generated_at_utc": core.now_iso(),
        "ready": all(m.get("status") != "DATA_STALE" for m in models) and len(models) == 6,
        "models": models,
        "feeds": feed_status(),
        "note": "Six EBP instances are evaluated from closed futures candles only. No QQQ/SPY proxy can create an actionable EBP signal.",
    }


core.query_bars = query_bars
core.normalize_models = enhanced_models
core.APP_VERSION = "0.9.12-beta-ebp-intraday-futures"


class Handler(desk.Handler):
    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/api/feed-status":
            return self.json(feed_status())
        if u.path == "/api/ebp-readiness":
            return self.json(readiness())
        return super().do_GET()


if __name__ == "__main__":
    core.PID_FILE.write_text(str(core.os.getpid()), encoding="utf-8")
    print("TMBT Next", core.APP_VERSION)
    print("Workspace:", core.WORKSPACE)
    print("NQ/ES: local futures feed only; QQQ/SPY proxies are not actionable")
    print("EBP matrix: NQ + ES on 15m / 30m / 1H")
    print("XAU: existing canonical Twelve feed")
    print("Readiness: http://127.0.0.1:%s/api/ebp-readiness" % core.PORT)
    print("Open: http://127.0.0.1:%s" % core.PORT)
    try:
        core.ThreadingHTTPServer(("127.0.0.1", core.PORT), Handler).serve_forever()
    finally:
        try:
            core.PID_FILE.unlink(missing_ok=True)
        except Exception:
            pass
