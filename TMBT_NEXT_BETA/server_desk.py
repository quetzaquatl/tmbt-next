from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urlparse

import server_original as original

core = original.core
_base_to_ms = original._to_ms


def _robust_to_ms(v):
    """Accept numeric epochs and ISO timestamp strings."""
    x = _base_to_ms(v)
    if x is not None:
        return x
    try:
        if v is None:
            return None
        z = str(v).strip().replace("Z", "+00:00")
        if not z:
            return None
        dt = datetime.fromisoformat(z)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.astimezone(timezone.utc).timestamp() * 1000)
    except Exception:
        return None


original._to_ms = _robust_to_ms
original._STALE_AFTER["30m"] = 75 * 60

_EXPECTED_IDENTITY = {
    "NQ": "QQQ",
    "ES": "SPY",
    "XAU": "XAU/USD",
}


def _aggregate_30m(bars):
    """Build deterministic 30m candles from the canonical 15m series."""
    out = []
    cur = None
    width = 30 * 60 * 1000
    for row in bars or []:
        t = _robust_to_ms(row.get("t"))
        if t is None:
            continue
        bucket = (t // width) * width
        try:
            o = float(row.get("o"))
            h = float(row.get("h"))
            l = float(row.get("l"))
            c = float(row.get("c"))
        except Exception:
            continue
        if cur is None or cur["t"] != bucket:
            if cur is not None:
                out.append(cur)
            cur = {
                "t": bucket,
                "close_t": bucket + width,
                "o": o,
                "h": h,
                "l": l,
                "c": c,
                "v": float(row.get("v") or 0),
                "source": row.get("source"),
                "market": row.get("market"),
                "tf": "30m",
            }
        else:
            cur["h"] = max(cur["h"], h)
            cur["l"] = min(cur["l"], l)
            cur["c"] = c
            try:
                cur["v"] += float(row.get("v") or 0)
            except Exception:
                pass
    if cur is not None:
        out.append(cur)
    return out


def _identity_matches(market: str, result: dict) -> bool:
    """Reject a mirror that explicitly identifies as the wrong instrument.

    Empty identity fields are tolerated because older mirror files did not always
    populate ticker/tickerid. If an identity is present, however, it must match
    the prototype scale used by the live models.
    """
    expected = _EXPECTED_IDENTITY.get(str(market).upper())
    if not expected:
        return True
    identity = str(result.get("tickerid") or result.get("ticker") or "").upper().replace(" ", "")
    if not identity:
        return True
    if expected == "XAU/USD":
        return "XAU/USD" in identity or "XAUUSD" in identity
    return expected in identity


def _canonical_mirror(market="NQ", tf="1H", limit=500):
    """Read exactly the same Twelve mirror the old Studio publishes.

    NQ/ES are the old Studio's QQQ/SPY prototypes. Keeping this as the only chart
    source is important because the live model engine uses the same price scale.
    """
    result = original._load_twelve_file(market, tf, limit)
    if not result or not result.get("bars"):
        return None

    ntf = core.normalize_tf(tf)
    age = result.get("age_seconds")
    stale_after = original._STALE_AFTER.get(ntf, 3 * 60 * 60)
    result["stale"] = age is None or float(age) > stale_after
    result["canonical"] = True
    result["identity_ok"] = _identity_matches(str(market).upper(), result)

    identity = result.get("tickerid") or result.get("ticker") or str(market).upper()
    if not result["identity_ok"]:
        result["stale"] = True
        result["note"] = (
            f"MODEL/CHART FEED MISMATCH · expected {_EXPECTED_IDENTITY.get(str(market).upper())} "
            f"· got {identity} · chart blocked"
        )
        result["bars"] = []
        return result

    state = "STALE" if result["stale"] else "LIVE"
    result["note"] = f"twelve · {identity} · {state} · age {original._age_text(age)}"
    return result


def _canonical_query(market="NQ", tf="1H", limit=500, source=None):
    mirror = _canonical_mirror(market, tf, limit)
    if mirror:
        return mirror

    # Deliberately do not fall back to anonymous/local futures tables here.
    # A fresh NQ future (~30k) beside a QQQ-based model (~700) is worse than a
    # clearly unavailable chart because Entry/SL/TP would be plotted on the wrong
    # price scale. Old Studio Twelve mirror is therefore the sole chart source.
    return {
        "bars": [],
        "db": None,
        "table": None,
        "source": None,
        "feed": "canonical_twelve_only",
        "provider": None,
        "ticker": None,
        "tickerid": None,
        "stale": True,
        "age_seconds": None,
        "canonical": True,
        "identity_ok": None,
        "note": "Kanonischer Twelve-Mirror fehlt · kein Cross-Scale-Fallback erlaubt · Old Studio/Sync prüfen",
    }


def desk_query_bars(market="NQ", tf="1H", limit=500, source=None):
    ntf = core.normalize_tf(tf)
    if ntf != "30m":
        return _canonical_query(market, tf, limit, source)

    base = dict(_canonical_query(market, "15m", max(100, int(limit) * 2), source) or {})
    bars = _aggregate_30m(base.get("bars") or [])
    base["bars"] = bars[-max(50, int(limit)):]
    base["derived_from"] = "15m"
    base["tf"] = "30m"
    if bars:
        last = bars[-1]
        last_ms = _robust_to_ms(last.get("close_t")) or _robust_to_ms(last.get("t"))
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        age = max(0.0, (now_ms - last_ms) / 1000.0) if last_ms else None
        source_stale = bool(base.get("stale"))
        bar_stale = age is None or age > original._STALE_AFTER["30m"]
        base["age_seconds"] = age
        base["stale"] = source_stale or bar_stale
        base["last_bar_utc"] = (
            datetime.fromtimestamp(last_ms / 1000.0, tz=timezone.utc).isoformat()
            if last_ms else None
        )
        state = "STALE" if base["stale"] else "LIVE"
        base["note"] = f"{base.get('provider') or 'twelve'} · 30m aus kanonischem 15m · {state} · age {original._age_text(age)}"
    return base


original.original_query_bars = desk_query_bars
core.query_bars = desk_query_bars
core.APP_VERSION = "0.9.11-beta-canonical-strict"


def _feed_one(market, tf="5m"):
    x = desk_query_bars(market, tf, 80, None)
    bars = x.get("bars") or []
    last = bars[-1] if bars else {}
    return {
        "market": market,
        "tf": tf,
        "ok": bool(bars),
        "price": last.get("c"),
        "bars": len(bars),
        "feed": x.get("feed"),
        "provider": x.get("provider"),
        "ticker": x.get("ticker"),
        "tickerid": x.get("tickerid"),
        "last_bar_utc": x.get("last_bar_utc"),
        "last_received_at_utc": x.get("last_received_at_utc"),
        "age_seconds": x.get("age_seconds"),
        "stale": bool(x.get("stale", not bool(bars))),
        "note": x.get("note"),
        "path": x.get("db"),
        "canonical": bool(x.get("canonical")),
        "identity_ok": x.get("identity_ok"),
    }


def desk_feed_status():
    markets = {}
    for market in ("NQ", "ES", "XAU"):
        tfs = {tf: _feed_one(market, tf) for tf in ("5m", "15m", "30m", "1H")}
        summary = dict(tfs["5m"])
        summary["timeframes"] = tfs
        markets[market] = summary
    return {"generated_at_utc": core.now_iso(), "markets": markets}


def diagnostics_with_30m():
    d = original.diagnostics()
    for market in ("NQ", "ES", "XAU"):
        for tf in ("5m", "15m", "30m", "1H", "4H", "1D"):
            d.setdefault("feeds", {}).setdefault(market, {})[tf] = _feed_one(market, tf)
    d["version"] = core.APP_VERSION
    d["hint"] = (
        "Strict canonical feed mode: NQ=TWELVE:QQQ, ES=TWELVE:SPY, XAU=TWELVE:XAU/USD. "
        "No local futures/Yahoo fallback is allowed because model/chart price scales must match."
    )
    return d


class Handler(original.Handler):
    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/api/feed-status":
            return self.json(desk_feed_status())
        if u.path == "/api/diagnostics":
            return self.json(diagnostics_with_30m())
        return super().do_GET()


if __name__ == "__main__":
    core.PID_FILE.write_text(str(core.os.getpid()), encoding="utf-8")
    print("TMBT Next", core.APP_VERSION)
    print("Workspace:", core.WORKSPACE)
    print("Feed: strict canonical Old-Studio Twelve mirror (single collector owner)")
    print("NQ=QQQ · ES=SPY · XAU=XAU/USD · 30m derived from 15m")
    print("Cross-scale local fallback: DISABLED")
    print("Open: http://127.0.0.1:%s" % core.PORT)
    try:
        core.ThreadingHTTPServer(("127.0.0.1", core.PORT), Handler).serve_forever()
    finally:
        try:
            core.PID_FILE.unlink(missing_ok=True)
        except Exception:
            pass
