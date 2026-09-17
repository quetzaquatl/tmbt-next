from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from urllib.parse import quote
from urllib.request import Request, urlopen

import server as core

# Temporary near-live chart feed until the dedicated CME/IBKR feed is connected.
# NQ/ES are fetched independently from the local TradingView cache so a stale
# SQLite writer no longer freezes the chart. This is for chart display only;
# it is not an exchange-certified realtime feed and must not be used as the
# final execution/model-data source.

LIVE_SYMBOLS = {
    "NQ": "NQ=F",
    "ES": "ES=F",
}

TF_SPEC = {
    "5m": ("5m", "60d", 5 * 60),
    "15m": ("15m", "60d", 15 * 60),
    "1h": ("60m", "730d", 60 * 60),
    "4h": ("60m", "730d", 60 * 60),
    "1d": ("1d", "10y", 24 * 60 * 60),
}

_CACHE = {}
_CACHE_TTL = 4.0
_LOCAL_QUERY_BARS = core.query_bars


def _to_ms(ts):
    try:
        n = float(ts)
        return int(n if n > 1e12 else n * 1000)
    except Exception:
        return None


def _aggregate_4h(bars):
    groups = []
    current = None
    for b in bars:
        t_ms = _to_ms(b.get("t"))
        if t_ms is None:
            continue
        bucket = (t_ms // (4 * 60 * 60 * 1000)) * (4 * 60 * 60 * 1000)
        if current is None or current["bucket"] != bucket:
            if current is not None:
                groups.append(current)
            current = {
                "bucket": bucket,
                "t": bucket,
                "close_t": bucket + 4 * 60 * 60 * 1000,
                "o": float(b["o"]),
                "h": float(b["h"]),
                "l": float(b["l"]),
                "c": float(b["c"]),
                "v": float(b.get("v") or 0),
                "source": b.get("source"),
                "market": b.get("market"),
                "tf": "4h",
            }
        else:
            current["h"] = max(current["h"], float(b["h"]))
            current["l"] = min(current["l"], float(b["l"]))
            current["c"] = float(b["c"])
            current["v"] += float(b.get("v") or 0)
    if current is not None:
        groups.append(current)
    for g in groups:
        g.pop("bucket", None)
    return groups


def _fetch_yahoo(market="NQ", tf="5m", limit=1500):
    mkt = str(market).upper()
    ntf = core.normalize_tf(tf)
    symbol = LIVE_SYMBOLS.get(mkt)
    if not symbol or ntf not in TF_SPEC:
        raise ValueError("temporary_live_feed_not_supported")

    interval, range_name, interval_seconds = TF_SPEC[ntf]
    key = (mkt, ntf, int(limit))
    now = time.time()
    cached = _CACHE.get(key)
    if cached and now - cached[0] < _CACHE_TTL:
        return cached[1]

    url = (
        "https://query1.finance.yahoo.com/v8/finance/chart/"
        + quote(symbol, safe="=")
        + f"?interval={interval}&range={range_name}&includePrePost=true&events=div%2Csplits"
    )
    req = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 TMBT-Next/0.9",
            "Accept": "application/json,text/plain,*/*",
        },
    )
    with urlopen(req, timeout=7) as r:
        payload = json.loads(r.read().decode("utf-8", errors="replace"))

    chart = (payload.get("chart") or {})
    err = chart.get("error")
    if err:
        raise RuntimeError(str(err))
    result = (chart.get("result") or [None])[0]
    if not isinstance(result, dict):
        raise RuntimeError("empty_live_result")

    timestamps = result.get("timestamp") or []
    quote_rows = (((result.get("indicators") or {}).get("quote") or [{}])[0]) or {}
    opens = quote_rows.get("open") or []
    highs = quote_rows.get("high") or []
    lows = quote_rows.get("low") or []
    closes = quote_rows.get("close") or []
    vols = quote_rows.get("volume") or []

    bars = []
    n = min(len(timestamps), len(opens), len(highs), len(lows), len(closes))
    for i in range(n):
        if None in (timestamps[i], opens[i], highs[i], lows[i], closes[i]):
            continue
        try:
            t_ms = int(float(timestamps[i]) * 1000)
            bars.append({
                "t": t_ms,
                "close_t": t_ms + interval_seconds * 1000,
                "o": float(opens[i]),
                "h": float(highs[i]),
                "l": float(lows[i]),
                "c": float(closes[i]),
                "v": vols[i] if i < len(vols) else None,
                "source": f"Yahoo {symbol}",
                "market": mkt,
                "tf": ntf,
            })
        except Exception:
            continue

    if ntf == "4h":
        bars = _aggregate_4h(bars)
    if not bars:
        raise RuntimeError("no_live_bars")

    bars = bars[-max(50, int(limit)):]
    last_ms = _to_ms(bars[-1].get("t"))
    age = max(0.0, time.time() - (last_ms / 1000.0)) if last_ms else None
    out = {
        "bars": bars,
        "db": None,
        "table": None,
        # Keep source null so the existing UI shows note instead of appending
        # the misleading 'lokaler Cache' suffix.
        "source": None,
        "feed": "temporary_yahoo",
        "symbol": symbol,
        "indicative": True,
        "last_bar_utc": datetime.fromtimestamp(last_ms / 1000.0, tz=timezone.utc).isoformat() if last_ms else None,
        "age_seconds": age,
        "note": f"{mkt} {symbol} · TEMP LIVE fallback · nicht exchange-zertifiziert",
    }
    _CACHE[key] = (now, out)
    return out


def live_query_bars(market="NQ", tf="1H", limit=500, source=None):
    mkt = str(market).upper()
    if mkt in LIVE_SYMBOLS:
        try:
            return _fetch_yahoo(mkt, tf, limit)
        except Exception as exc:
            local = _LOCAL_QUERY_BARS(market, tf, limit, source)
            local = dict(local or {})
            local["live_fallback_error"] = str(exc)
            if not local.get("bars"):
                local["note"] = f"TEMP LIVE nicht erreichbar: {exc}"
            return local
    return _LOCAL_QUERY_BARS(market, tf, limit, source)


# Handler.do_GET in server.py resolves query_bars in the server module at
# request time, so replacing this function upgrades /api/bars and /api/pd
# without duplicating the rest of the backend.
core.query_bars = live_query_bars
core.APP_VERSION = "0.9.1-beta-live"


if __name__ == "__main__":
    core.PID_FILE.write_text(str(core.os.getpid()), encoding="utf-8")
    print("TMBT Next", core.APP_VERSION)
    print("Workspace:", core.WORKSPACE)
    print("Chart feed: TEMP LIVE NQ/ES fallback (Yahoo Finance); local cache remains fallback")
    print("Open: http://127.0.0.1:%s" % core.PORT)
    try:
        core.ThreadingHTTPServer(("127.0.0.1", core.PORT), core.Handler).serve_forever()
    finally:
        try:
            core.PID_FILE.unlink(missing_ok=True)
        except Exception:
            pass
