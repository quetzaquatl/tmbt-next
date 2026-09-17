from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
import os
import re
import sqlite3
import threading
import time
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

import server_original as original

core = original.core
_base_to_ms = original._to_ms
_DIRECT_CACHE = {}
_DIRECT_ERRORS = {}
_KEY_UNSET = object()
_KEY_CACHE = _KEY_UNSET


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


def _name_tokens(name):
    return {x for x in re.split(r"[^A-Z0-9]+", str(name).upper()) if x}


def _table_market_hint(table, aliases):
    """Only trust market-less tables when the table name identifies the market.

    The previous implementation accepted every OHLC table that did not contain a
    market column. That allowed the freshest ES table to be returned for NQ (and
    vice versa). This is the exact class of bug that produced swapped NQ/ES quotes.
    """
    tokens = _name_tokens(table)
    hints = set()
    for alias in aliases:
        a = str(alias).upper()
        hints.update(x for x in re.split(r"[^A-Z0-9]+", a) if x and x not in {"F"})
    return bool(tokens & hints)


def _table_tf_hint(table, ntf):
    tokens = _name_tokens(table)
    mp = {
        "5m": {"5M", "5MIN"},
        "15m": {"15M", "15MIN"},
        "30m": {"30M", "30MIN"},
        "1h": {"1H", "H1", "60M", "60MIN"},
        "4h": {"4H", "H4", "240M", "240MIN"},
        "1d": {"1D", "D1", "DAY", "DAILY"},
    }
    return bool(tokens & mp.get(ntf, {ntf.upper()}))


def _freshest_local(market="NQ", tf="1H", limit=500, source=None):
    aliases = [x.upper() for x in core.MARKET_ALIASES.get(str(market).upper(), [market])]
    ntf = core.normalize_tf(tf)
    best = None
    best_ms = -1

    for db in core.sqlite_candidates():
        con = None
        try:
            con = sqlite3.connect(str(db))
            con.row_factory = sqlite3.Row
            tables = [r[0] for r in con.execute("select name from sqlite_master where type='table'").fetchall()]

            for table in tables:
                safe = table.replace('"', '""')
                try:
                    cols = [r[1] for r in con.execute(f'pragma table_info("{safe}")').fetchall()]
                except Exception:
                    continue

                o = core.pick_col(cols, ["open"], ["open"])
                h = core.pick_col(cols, ["high"], ["high"])
                l = core.pick_col(cols, ["low"], ["low"])
                c = core.pick_col(cols, ["close"], ["close"])
                ts = core.pick_col(cols, ["bar_open_ms", "timestamp", "datetime", "time", "ts", "open_time"], ["time"])
                close_ts = core.pick_col(cols, ["bar_close_ms", "close_time"], ["close_ms", "close_time"])
                if not all([o, h, l, c, ts]):
                    continue

                mcol = core.pick_col(cols, ["market", "symbol", "ticker", "instrument"], ["market", "symbol", "ticker"])
                tfcol = core.pick_col(cols, ["timeframe", "interval", "tf"], ["timeframe", "interval"])
                scol = core.pick_col(cols, ["source"], ["source"])
                vol = core.pick_col(cols, ["volume", "vol"], ["volume"])

                # Never accept an anonymous OHLC table for every market/timeframe.
                # If identifying columns are absent, require explicit table-name hints.
                if not mcol and not _table_market_hint(table, aliases):
                    continue
                if not tfcol and not _table_tf_hint(table, ntf):
                    continue

                where = []
                params = []
                if mcol:
                    where.append('upper(cast("%s" as text)) in (%s)' % (mcol, ",".join("?" for _ in aliases)))
                    params += aliases
                if tfcol:
                    tf_values = list(dict.fromkeys([ntf, str(tf).lower()]))
                    where.append('lower(cast("%s" as text)) in (%s)' % (tfcol, ",".join("?" for _ in tf_values)))
                    params += tf_values
                if source and scol:
                    where.append('lower(cast("%s" as text))=?' % scol)
                    params.append(str(source).lower())

                fields = [
                    f'"{ts}" as t', f'"{o}" as o', f'"{h}" as h', f'"{l}" as l', f'"{c}" as c',
                    f'"{close_ts}" as close_t' if close_ts else "null as close_t",
                    f'"{scol}" as source' if scol else "null as source",
                    f'"{mcol}" as market' if mcol else "null as market",
                    f'"{tfcol}" as tf' if tfcol else "null as tf",
                    f'"{vol}" as volume' if vol else "null as volume",
                ]
                query = "select " + ",".join(fields) + f' from "{safe}"'
                if where:
                    query += " where " + " and ".join(where)
                query += f' order by "{ts}" desc limit ?'
                params.append(int(limit))

                try:
                    rows = con.execute(query, params).fetchall()
                except Exception:
                    rows = []
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
                    best = {
                        "bars": bars, "db": str(db), "table": table, "source": last.get("source"),
                        "resolved_market": str(market).upper(), "resolved_tf": ntf,
                    }
        except Exception:
            pass
        finally:
            if con:
                try:
                    con.close()
                except Exception:
                    pass

    return best or {
        "bars": [], "db": None, "table": None, "source": None,
        "note": "Keine eindeutig zuordenbare lokale OHLC-Serie gefunden.",
    }


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
        "note": "Kein eindeutig zuordenbarer Original-Livefeed gefunden · Collector/Writer prüfen",
    }


def _discover_twelve_key():
    global _KEY_CACHE
    if _KEY_CACHE is not _KEY_UNSET:
        return _KEY_CACHE

    for name in ("TWELVE_DATA_API_KEY", "TWELVEDATA_API_KEY", "TWELVE_API_KEY", "TWELVEDATA_KEY"):
        v = os.environ.get(name)
        if v and len(v.strip()) >= 8:
            _KEY_CACHE = v.strip()
            return _KEY_CACHE

    candidates = []
    roots = [
        core.WORKSPACE, core.WORKSPACE.parent, core.WORKSPACE / "live_data",
        core.WORKSPACE / ".streamlit", core.WORKSPACE.parent / ".streamlit",
    ]
    for root in roots:
        for name in (".env", "secrets.toml", "config.json", "settings.json", "twelve.env", "twelve_config.json"):
            p = root / name
            if p.exists() and p.is_file() and p not in candidates:
                candidates.append(p)

    pats = [
        r"(?im)^\s*(?:TWELVE_DATA_API_KEY|TWELVEDATA_API_KEY|TWELVE_API_KEY|TWELVEDATA_KEY)\s*[:=]\s*[\"']?([^\"'\s#]+)",
        r"(?im)^\s*(?:twelve_data_api_key|twelvedata_api_key|twelve_api_key)\s*[:=]\s*[\"']?([^\"'\s#]+)",
    ]
    for p in candidates:
        try:
            txt = p.read_text(encoding="utf-8", errors="ignore")[:200000]
        except Exception:
            continue
        for pat in pats:
            m = re.search(pat, txt)
            if m and len(m.group(1).strip()) >= 8:
                _KEY_CACHE = m.group(1).strip()
                return _KEY_CACHE
        try:
            obj = json.loads(txt)
            stack = [obj]
            while stack:
                cur = stack.pop()
                if isinstance(cur, dict):
                    for k, v in cur.items():
                        kl = str(k).lower()
                        if "twelve" in kl and "key" in kl and isinstance(v, str) and len(v.strip()) >= 8:
                            _KEY_CACHE = v.strip()
                            return _KEY_CACHE
                        if isinstance(v, (dict, list)):
                            stack.append(v)
                elif isinstance(cur, list):
                    stack.extend(x for x in cur if isinstance(x, (dict, list)))
        except Exception:
            pass

    _KEY_CACHE = None
    return None


def _tf_spec(tf):
    return {
        "5m": ("5min", 300), "15m": ("15min", 900), "30m": ("30min", 1800),
        "1h": ("1h", 3600), "4h": ("4h", 14400), "1d": ("1day", 86400),
    }.get(core.normalize_tf(tf))


def _fetch_direct_xau(tf="5m", limit=500, force=False):
    spec = _tf_spec(tf)
    if not spec:
        return None
    interval, seconds = spec
    ntf = core.normalize_tf(tf)
    key = _discover_twelve_key()
    if not key:
        _DIRECT_ERRORS[ntf] = "TWELVE_API_KEY missing"
        return None

    now = time.time()
    cached = _DIRECT_CACHE.get(ntf)
    ttl = 20 if ntf in {"5m", "15m", "30m"} else 45
    if not force and cached and now - cached.get("fetched", 0) < ttl:
        return cached.get("result")

    params = {
        "symbol": "XAU/USD", "interval": interval,
        "outputsize": min(max(int(limit), 100), 5000),
        "timezone": "UTC", "format": "JSON", "apikey": key,
    }
    try:
        req = Request(
            "https://api.twelvedata.com/time_series?" + urlencode(params),
            headers={"User-Agent": "TMBT-Next/0.9.8"},
        )
        with urlopen(req, timeout=12) as r:
            payload = json.loads(r.read().decode("utf-8", errors="ignore"))
        if payload.get("status") == "error" or not isinstance(payload.get("values"), list):
            raise RuntimeError(payload.get("message") or "Twelve returned no values")

        bars = []
        for row in reversed(payload.get("values") or []):
            try:
                dt = datetime.fromisoformat(str(row.get("datetime"))).replace(tzinfo=timezone.utc)
                t = int(dt.timestamp() * 1000)
                bars.append({
                    "t": t, "close_t": t + seconds * 1000,
                    "o": float(row["open"]), "h": float(row["high"]), "l": float(row["low"]), "c": float(row["close"]),
                    "v": float(row["volume"]) if row.get("volume") not in (None, "") else None,
                    "source": "twelve", "market": "XAU", "tf": ntf,
                })
            except Exception:
                pass
        if not bars:
            raise RuntimeError("No parseable XAU bars")

        last = bars[-1]
        close_ms = _robust_to_ms(last.get("close_t")) or _robust_to_ms(last.get("t"))
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        age = max(0.0, (now_ms - close_ms) / 1000.0) if close_ms else None
        stale = age is None or age > original._STALE_AFTER.get(ntf, 10800)
        result = {
            "bars": bars[-max(50, int(limit)):], "db": None, "table": None, "source": None,
            "feed": "twelve_direct", "provider": "twelve", "ticker": "XAU/USD", "tickerid": "TWELVE:XAU/USD",
            "last_bar_utc": datetime.fromtimestamp(close_ms / 1000.0, tz=timezone.utc).isoformat() if close_ms else None,
            "age_seconds": age, "stale": stale,
            "note": f"twelve · XAU/USD direct · {'STALE' if stale else 'LIVE'} · age {original._age_text(age)}",
        }
        _DIRECT_CACHE[ntf] = {"fetched": now, "result": result}
        _DIRECT_ERRORS.pop(ntf, None)
        return result
    except Exception as exc:
        _DIRECT_ERRORS[ntf] = str(exc)
        return cached.get("result") if cached else None


def _latest_ms(result):
    try:
        return max((_robust_to_ms(x.get("t")) or -1) for x in (result.get("bars") or []))
    except Exception:
        return -1


def _write_xau_mirror(result, tf):
    suffix = {"5m": "5m", "15m": "15m", "1h": "1H"}.get(core.normalize_tf(tf))
    if not suffix or not result or not result.get("bars"):
        return False
    now = datetime.now(timezone.utc).isoformat()
    rows = []
    for b in result.get("bars") or []:
        rows.append({
            "source": "twelve", "schema_version": 1, "event": "bar_update",
            "market": "XAU", "ticker": "XAU/USD", "tickerid": "TWELVE:XAU/USD", "exchange": "TWELVE",
            "timeframe": suffix, "chart_timeframe": "",
            "bar_open_ms": _robust_to_ms(b.get("t")), "bar_close_ms": _robust_to_ms(b.get("close_t")),
            "open": b.get("o"), "high": b.get("h"), "low": b.get("l"), "close": b.get("c"), "volume": b.get("v"),
            "sent_at_ms": None, "received_at_utc": now, "remote_addr": "direct-twelve-recovery",
        })
    payload = {
        "source": "twelve", "market": "XAU", "timeframe": suffix,
        "ticker": "XAU/USD", "tickerid": "TWELVE:XAU/USD", "bars": rows,
    }
    try:
        root = core.WORKSPACE / "github_research_repo" / "live" / "twelve"
        root.mkdir(parents=True, exist_ok=True)
        p = root / f"XAU_{suffix}.json"
        tmp = p.with_suffix(p.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(p)
        return True
    except Exception as exc:
        _DIRECT_ERRORS[f"mirror:{tf}"] = str(exc)
        return False


def _xau_recovery_loop():
    while True:
        for tf in ("5m", "15m", "1H"):
            r = _fetch_direct_xau(tf, 800, force=True)
            if r and not r.get("stale"):
                _write_xau_mirror(r, tf)
            time.sleep(4)
        time.sleep(35)


def _start_xau_recovery():
    if _discover_twelve_key():
        threading.Thread(target=_xau_recovery_loop, name="tmbt-xau-recovery", daemon=True).start()


def desk_query_bars(market="NQ", tf="1H", limit=500, source=None):
    ntf = core.normalize_tf(tf)
    if ntf == "30m":
        base = dict(desk_query_bars(market, "15m", max(100, int(limit) * 2), source) or {})
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

    base = _best_original_query(market, tf, limit, source)
    if str(market).upper() == "XAU":
        direct = _fetch_direct_xau(tf, limit, force=False)
        if direct and direct.get("bars") and (not base.get("bars") or base.get("stale") or _latest_ms(direct) >= _latest_ms(base)):
            return direct
    return base


original.original_query_bars = desk_query_bars
core.query_bars = desk_query_bars
core.APP_VERSION = "0.9.8-beta-stable-feed"


def _feed_one(market, tf="5m"):
    x = desk_query_bars(market, tf, 60, None)
    bars = x.get("bars") or []
    last = bars[-1] if bars else {}
    return {
        "market": market, "tf": tf, "ok": bool(bars), "price": last.get("c"), "bars": len(bars),
        "feed": x.get("feed"), "provider": x.get("provider"), "ticker": x.get("ticker"), "tickerid": x.get("tickerid"),
        "last_bar_utc": x.get("last_bar_utc"), "age_seconds": x.get("age_seconds"),
        "stale": bool(x.get("stale", not bool(bars))), "note": x.get("note"), "path": x.get("db"),
        "table": x.get("table"), "resolved_market": x.get("resolved_market"), "resolved_tf": x.get("resolved_tf"),
    }


def desk_feed_status():
    markets = {}
    for m in ("NQ", "ES", "XAU"):
        tfs = {tf: _feed_one(m, tf) for tf in ("5m", "15m", "30m", "1H")}
        summary = dict(tfs["5m"])
        summary["timeframes"] = tfs
        markets[m] = summary
    return {
        "generated_at_utc": core.now_iso(), "markets": markets,
        "xau_direct": {"key_found": bool(_discover_twelve_key()), "errors": dict(_DIRECT_ERRORS)},
    }


def diagnostics_with_30m():
    d = original.diagnostics()
    for market in ("NQ", "ES", "XAU"):
        for tf in ("5m", "15m", "30m", "1H", "4H", "1D"):
            d.setdefault("feeds", {}).setdefault(market, {})[tf] = _feed_one(market, tf)
    d["version"] = core.APP_VERSION
    d["xau_direct"] = {"key_found": bool(_discover_twelve_key()), "errors": dict(_DIRECT_ERRORS)}
    d["hint"] = "Feed selection is market-isolated. Anonymous SQLite OHLC tables are ignored unless table names identify both market and timeframe. XAU direct recovery activates only when a Twelve API key actually exists."
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
    _start_xau_recovery()
    core.PID_FILE.write_text(str(core.os.getpid()), encoding="utf-8")
    print("TMBT Next", core.APP_VERSION)
    print("Workspace:", core.WORKSPACE)
    print("Feed: market-isolated local/original feeds")
    print("XAU direct Twelve key found:", bool(_discover_twelve_key()))
    print("30m: derived from original 15m bars")
    print("Open: http://127.0.0.1:%s" % core.PORT)
    try:
        core.ThreadingHTTPServer(("127.0.0.1", core.PORT), Handler).serve_forever()
    finally:
        try:
            core.PID_FILE.unlink(missing_ok=True)
        except Exception:
            pass
