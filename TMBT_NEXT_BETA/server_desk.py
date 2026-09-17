from __future__ import annotations

from datetime import datetime, timezone

import server_original as original

core = original.core
_base_query = original.original_query_bars
_base_to_ms = original._to_ms


def _robust_to_ms(v):
    """Accept numeric epoch values and ISO timestamps from local SQLite rows."""
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


# server_original resolves this function dynamically inside its freshness code.
original._to_ms = _robust_to_ms
original._STALE_AFTER["30m"] = 75 * 60


def _aggregate_30m(bars):
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


def desk_query_bars(market="NQ", tf="1H", limit=500, source=None):
    ntf = core.normalize_tf(tf)
    if ntf != "30m":
        return _base_query(market, tf, limit, source)

    # 30m is generated deterministically from the original 15m stream. This
    # gives NQ/ES EBP a useful intraday view without inventing another provider.
    base = dict(_base_query(market, "15m", max(100, int(limit) * 2), source) or {})
    bars = _aggregate_30m(base.get("bars") or [])
    base["bars"] = bars[-max(50, int(limit)):]
    base["derived_from"] = "15m"
    base["tf"] = "30m"
    if base["bars"]:
        last = base["bars"][-1]
        last_ms = _robust_to_ms(last.get("close_t")) or _robust_to_ms(last.get("t"))
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        age = max(0.0, (now_ms - last_ms) / 1000.0) if last_ms else None
        base["last_bar_utc"] = datetime.fromtimestamp(last_ms / 1000.0, tz=timezone.utc).isoformat() if last_ms else None
        base["age_seconds"] = age
        base["stale"] = age is None or age > original._STALE_AFTER["30m"]
        base["note"] = f"{base.get('provider') or 'original'} · 30m aus 15m · {'STALE' if base['stale'] else 'LIVE'} · age {original._age_text(age)}"
    return base


# Upgrade every caller, including server_original diagnostics/feed-status.
original.original_query_bars = desk_query_bars
core.query_bars = desk_query_bars
core.APP_VERSION = "0.9.5-beta-live-desk"


def diagnostics_with_30m():
    d = original.diagnostics()
    for market in ("NQ", "ES", "XAU"):
        d.setdefault("feeds", {}).setdefault(market, {})["30m"] = original._feed_one(market, "30m")
    d["version"] = core.APP_VERSION
    d["hint"] = "Feed freshness is based on the newest market bar, not the shared SQLite file mtime. If XAU is stale while NQ/ES are live, repair the XAU collector/writer before trusting XAU model alerts."
    return d


class Handler(original.Handler):
    def do_GET(self):
        from urllib.parse import urlparse
        u = urlparse(self.path)
        if u.path == "/api/diagnostics":
            return self.json(diagnostics_with_30m())
        return super().do_GET()


if __name__ == "__main__":
    core.PID_FILE.write_text(str(core.os.getpid()), encoding="utf-8")
    print("TMBT Next", core.APP_VERSION)
    print("Workspace:", core.WORKSPACE)
    print("Feed: original TMBT pipeline with bar-age freshness checks")
    print("30m: derived from original 15m bars")
    print("Open: http://127.0.0.1:%s" % core.PORT)
    try:
        core.ThreadingHTTPServer(("127.0.0.1", core.PORT), Handler).serve_forever()
    finally:
        try:
            core.PID_FILE.unlink(missing_ok=True)
        except Exception:
            pass
