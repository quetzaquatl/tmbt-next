from __future__ import annotations

from datetime import datetime, timezone
import sqlite3

import server_original as original

core = original.core
_base_to_ms = original._to_ms


def _robust_to_ms(v):
    """Accept numeric epochs and ISO timestamp strings from local SQLite rows."""
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
            o = float(row.get("o")); h = float(row.get("h")); l = float(row.get("l")); c = float(row.get("c"))
        except Exception:
            continue
        if cur is None or cur["t"] != bucket:
            if cur is not None:
                out.append(cur)
            cur = {
                "t": bucket, "close_t": bucket + width,
                "o": o, "h": h, "l": l, "c": c,
                "v": float(row.get("v") or 0),
                "source": row.get("source"), "market": row.get("market"), "tf": "30m",
            }
        else:
            cur["h"] = max(cur["h"], h); cur["l"] = min(cur["l"], l); cur["c"] = c
            try: cur["v"] += float(row.get("v") or 0)
            except Exception: pass
    if cur is not None:
        out.append(cur)
    return out


def _freshest_local(market="NQ", tf="1H", limit=500, source=None):
    """Search every local OHLC table and return the series with the newest bar.

    The base preview returned the first schema-compatible table. That can leave
    XAU pinned to an old Twelve table while another local source is newer.
    """
    aliases = [x.upper() for x in core.MARKET_ALIASES.get(str(market).upper(), [market])]
    ntf = core.normalize_tf(tf)
    best = None
    best_ms = -1

    for db in core.sqlite_candidates():
        con = None
        try:
            con = sqlite3.connect(str(db)); con.row_factory = sqlite3.Row
            tables = [r[0] for r in con.execute("select name from sqlite_master where type='table'").fetchall()]
            for table in tables:
                safe = table.replace('"', '""')
                try:
                    cols = [r[1] for r in con.execute(f'pragma table_info("{safe}")').fetchall()]
                except Exception:
                    continue
                o = core.pick_col(cols, ["open"], ["open"]); h = core.pick_col(cols, ["high"], ["high"])
                l = core.pick_col(cols, ["low"], ["low"]); c = core.pick_col(cols, ["close"], ["close"])
                ts = core.pick_col(cols, ["bar_open_ms", "timestamp", "datetime", "time", "ts", "open_time"], ["time"])
                close_ts = core.pick_col(cols, ["bar_close_ms", "close_time"], ["close_ms", "close_time"])
                if not all([o, h, l, c, ts]):
                    continue
                mcol = core.pick_col(cols, ["market", "symbol", "ticker", "instrument"], ["market", "symbol", "ticker"])
                tfcol = core.pick_col(cols, ["timeframe", "interval", "tf"], ["timeframe", "interval"])
                scol = core.pick_col(cols, ["source"], ["source"])
                vol = core.pick_col(cols, ["volume", "vol"], ["volume"])
                where = []; params = []
                if mcol:
                    where.append('upper(cast("%s" as text)) in (%s)' % (mcol, ",".join("?" for _ in aliases)))
                    params += aliases
                if tfcol:
                    tf_values = list(dict.fromkeys([ntf, str(tf).lower()]))
                    where.append('lower(cast("%s" as text)) in (%s)' % (tfcol, ",".join("?" for _ in tf_values)))
                    params += tf_values
                if source and scol:
                    where.append('lower(cast("%s" as text))=?' % scol); params.append(str(source).lower())
                fields = [
                    f'"{ts}" as t', f'"{o}" as o', f'"{h}" as h', f'"{l}" as l', f'"{c}" as c',
                    f'"{close_ts}" as close_t' if close_ts else "null as close_t",
                    f'"{scol}" as source' if scol else "null as source",
                    f'"{mcol}" as market' if mcol else "null as market",
                    f'"{tfcol}" as tf' if tfcol else "null as tf",
                    f'"{vol}" as volume' if vol else "null as volume",
                ]
                query = "select " + ",".join(fields) + f' from "{safe}"'
                if where: query += " where " + " and ".join(where)
                query += f' order by "{ts}" desc limit ?'; params.append(int(limit))
                try: rows = con.execute(query, params).fetchall()
                except Exception: rows = []
                if not rows:
                    continue
                bars = []
                for r in reversed(rows):
                    try:
                        bars.append({
                            "t": r["t"], "close_t": r["close_t"],
                            "o": float(r["o"]), "h": float(r["h"]), "l": float(r["l"]), "c": float(r["c"]),
                            "v": r["volume"], "source": r["source"], "market": r["market"], "tf": r["tf"],
                        })
                    except Exception:
                        pass
                if not bars:
                    continue
                last = bars[-1]
                last_ms = _robust_to_ms(last.get("close_t")) or _robust_to_ms(last.get("t")) or -1
                if last_ms > best_ms:
                    best_ms = last_ms
                    best = {"bars": bars, "db": str(db), "table": table, "source": last.get("source")}
        except Exception:
            pass
        finally:
            if con:
                try: con.close()
                except Exception: pass

    return best or {"bars": [], "db": None, "table": None, "source": None, "note": "Keine passende lokale OHLC-Serie gefunden."}


def _best_original_query(market="NQ", tf="1H", limit=500, source=None):
    mirror = original._load_twelve_file(market, tf, limit)
    local = original._decorate_local(_freshest_local(market, tf, limit, source), market, tf)
    if mirror and mirror.get("bars"):
        if local.get("bars") and original._latest_ms(local) > original._latest_ms(mirror):
            return local
        return mirror
    if local.get("bars"):
        return local
    return {
        "bars": [], "db": None, "table": None, "source": None,
        "feed": "original_pipeline", "stale": True, "age_seconds": None,
        "note": "Kein Original-Livefeed gefunden · Collector/Writer prüfen",
    }


def desk_query_bars(market="NQ", tf="1H", limit=500, source=None):
    ntf = core.normalize_tf(tf)
    if ntf != "30m":
        return _best_original_query(market, tf, limit, source)

    # Deterministic 30m bars from the same original 15m stream.
    base = dict(_best_original_query(market, "15m", max(100, int(limit) * 2), source) or {})
    bars = _aggregate_30m(base.get("bars") or [])
    base["bars"] = bars[-max(50, int(limit)):]
    base["derived_from"] = "15m"; base["tf"] = "30m"
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


original.original_query_bars = desk_query_bars
core.query_bars = desk_query_bars
core.APP_VERSION = "0.9.5-beta-live-desk"


def diagnostics_with_30m():
    d = original.diagnostics()
    for market in ("NQ", "ES", "XAU"):
        d.setdefault("feeds", {}).setdefault(market, {})["30m"] = original._feed_one(market, "30m")
    d["version"] = core.APP_VERSION
    d["hint"] = "The desk now chooses the freshest matching local series by bar timestamp. If XAU still shows stale while NQ/ES are live, there is no newer XAU series in the original workspace and the XAU collector/writer must be repaired."
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
    print("Feed: freshest original local/mirror series by market-bar timestamp")
    print("30m: derived from original 15m bars")
    print("Open: http://127.0.0.1:%s" % core.PORT)
    try:
        core.ThreadingHTTPServer(("127.0.0.1", core.PORT), Handler).serve_forever()
    finally:
        try: core.PID_FILE.unlink(missing_ok=True)
        except Exception: pass
