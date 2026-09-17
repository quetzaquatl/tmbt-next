from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import server as core

# Compatibility layer for the original TMBT 4.6 live-data architecture.
# No Yahoo/GC proxy or other external fallback is used here. TMBT Next reads
# the same Twelve-generated live JSON mirror used by the original Studio and
# falls back to the local SQLite cache only when that mirror is unavailable.

_LOCAL_SQLITE_QUERY = core.query_bars

_TF_FILE = {
    "5m": "5m",
    "15m": "15m",
    "1h": "1H",
    "4h": "4H",
    "1d": "1D",
}


def _parse_dt(v):
    try:
        if not v:
            return None
        z = str(v).replace("Z", "+00:00")
        dt = datetime.fromisoformat(z)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _to_ms(v):
    try:
        n = float(v)
        return int(n if n > 1e12 else n * 1000)
    except Exception:
        return None


def _twelve_roots():
    roots = [
        core.WORKSPACE / "github_research_repo" / "live" / "twelve",
        core.WORKSPACE / "live" / "twelve",
        core.WORKSPACE / "live_data" / "twelve",
    ]
    out = []
    for p in roots:
        if p not in out:
            out.append(p)
    return out


def _load_twelve_file(market="NQ", tf="1H", limit=500):
    mkt = str(market).upper()
    ntf = core.normalize_tf(tf)
    suffix = _TF_FILE.get(ntf)
    if not suffix:
        return None

    filename = f"{mkt}_{suffix}.json"
    payload = None
    path = None
    for root in _twelve_roots():
        p = root / filename
        x = core.read_json(p, None)
        if isinstance(x, dict) and isinstance(x.get("bars"), list) and x.get("bars"):
            payload = x
            path = p
            break
    if payload is None:
        return None

    bars = []
    latest_received = None
    latest_bar_ms = None
    for r in payload.get("bars") or []:
        if not isinstance(r, dict):
            continue
        try:
            t = _to_ms(r.get("bar_open_ms") if r.get("bar_open_ms") is not None else r.get("t"))
            close_t = _to_ms(r.get("bar_close_ms") if r.get("bar_close_ms") is not None else r.get("close_t"))
            o = float(r.get("open") if r.get("open") is not None else r.get("o"))
            h = float(r.get("high") if r.get("high") is not None else r.get("h"))
            l = float(r.get("low") if r.get("low") is not None else r.get("l"))
            c = float(r.get("close") if r.get("close") is not None else r.get("c"))
        except Exception:
            continue
        if t is None:
            continue
        recv = _parse_dt(r.get("received_at_utc"))
        if recv and (latest_received is None or recv > latest_received):
            latest_received = recv
        latest_bar_ms = t if latest_bar_ms is None else max(latest_bar_ms, t)
        bars.append({
            "t": t,
            "close_t": close_t,
            "o": o,
            "h": h,
            "l": l,
            "c": c,
            "v": r.get("volume") if r.get("volume") is not None else r.get("v"),
            "source": payload.get("source") or r.get("source") or "twelve",
            "market": mkt,
            "tf": payload.get("timeframe") or suffix,
        })

    if not bars:
        return None
    bars.sort(key=lambda b: b["t"])
    bars = bars[-max(50, int(limit)):]

    now = datetime.now(timezone.utc)
    age = (now - latest_received).total_seconds() if latest_received else None
    # The original writer updates all active series frequently, even on 1H/4H.
    # 3 minutes is intentionally generous enough to tolerate sync/commit lag.
    stale = age is None or age > 180
    ticker = payload.get("ticker") or ""
    tickerid = payload.get("tickerid") or ""
    exchange = payload.get("exchange") or ""
    freshness = "STALE" if stale else "LIVE"
    age_txt = "?" if age is None else (f"{int(age)}s" if age < 120 else f"{int(age // 60)}m")

    return {
        "bars": bars,
        "db": str(path) if path else None,
        "table": None,
        # Keep source null so the existing UI uses note verbatim instead of
        # automatically appending the misleading 'lokaler Cache' suffix.
        "source": None,
        "feed": "original_twelve",
        "provider": payload.get("source") or "twelve",
        "ticker": ticker,
        "tickerid": tickerid,
        "exchange": exchange,
        "last_received_at_utc": latest_received.isoformat() if latest_received else None,
        "last_bar_utc": datetime.fromtimestamp(latest_bar_ms / 1000.0, tz=timezone.utc).isoformat() if latest_bar_ms else None,
        "age_seconds": age,
        "stale": stale,
        "note": f"twelve · {tickerid or ticker or mkt} · {freshness} · age {age_txt}",
    }


def _latest_ms(result):
    try:
        bars = result.get("bars") or []
        if not bars:
            return -1
        return max(_to_ms(b.get("t")) or -1 for b in bars)
    except Exception:
        return -1


def original_query_bars(market="NQ", tf="1H", limit=500, source=None):
    # First choice: exactly the Twelve live-series mirror used by Studio 4.6.
    original = _load_twelve_file(market, tf, limit)

    # Second choice: the original local SQLite cache. This preserves old
    # workspaces that predate the GitHub live mirror and provides continuity if
    # the mirror is temporarily missing.
    local = _LOCAL_SQLITE_QUERY(market, tf, limit, source)
    local = dict(local or {})

    if original and original.get("bars"):
        # Prefer the original Twelve mirror. If SQLite is materially newer,
        # use it instead because it is likely the same writer before sync lag.
        if local.get("bars") and _latest_ms(local) > _latest_ms(original):
            src = local.get("source") or "local"
            local["feed"] = "original_sqlite"
            local["note"] = f"{src} · original local feed"
            return local
        return original

    if local.get("bars"):
        src = local.get("source") or "local"
        local["feed"] = "original_sqlite"
        local["note"] = f"{src} · original local feed"
        return local

    return {
        "bars": [],
        "db": None,
        "table": None,
        "source": None,
        "feed": "original_twelve",
        "stale": True,
        "note": "Kein Original-Livefeed gefunden · Twelve writer/Sync prüfen",
    }


# /api/bars and /api/pd resolve this symbol in server.py at request time.
core.query_bars = original_query_bars
core.APP_VERSION = "0.9.3-beta-original-pipeline"


if __name__ == "__main__":
    core.PID_FILE.write_text(str(core.os.getpid()), encoding="utf-8")
    print("TMBT Next", core.APP_VERSION)
    print("Workspace:", core.WORKSPACE)
    print("Chart feed: ORIGINAL TMBT 4.6 pipeline (Twelve mirror -> local SQLite fallback)")
    print("No Yahoo/GC proxy fallback enabled.")
    print("Open: http://127.0.0.1:%s" % core.PORT)
    try:
        core.ThreadingHTTPServer(("127.0.0.1", core.PORT), core.Handler).serve_forever()
    finally:
        try:
            core.PID_FILE.unlink(missing_ok=True)
        except Exception:
            pass
