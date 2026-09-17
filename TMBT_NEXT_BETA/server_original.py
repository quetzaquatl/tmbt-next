from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import server as core

# Compatibility layer for the original TMBT 4.6 live-data architecture.
# No Yahoo/GC proxy or other external fallback is used here. TMBT Next reads
# the same Twelve-generated live JSON mirror used by the original Studio and
# falls back to the local SQLite cache when it is newer or the mirror is absent.

_LOCAL_SQLITE_QUERY = core.query_bars

_TF_FILE = {
    "5m": "5m",
    "15m": "15m",
    "1h": "1H",
    "4h": "4H",
    "1d": "1D",
}

_STALE_AFTER = {
    "5m": 20 * 60,
    "15m": 45 * 60,
    "1h": 3 * 60 * 60,
    "4h": 9 * 60 * 60,
    "1d": 48 * 60 * 60,
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


def _age_text(age):
    if age is None:
        return "?"
    age = max(0.0, float(age))
    if age < 120:
        return f"{int(age)}s"
    if age < 7200:
        return f"{int(age // 60)}m"
    if age < 172800:
        return f"{age / 3600:.1f}h"
    return f"{age / 86400:.1f}d"


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
    stale = age is None or age > 180
    ticker = payload.get("ticker") or ""
    tickerid = payload.get("tickerid") or ""
    exchange = payload.get("exchange") or ""
    freshness = "STALE" if stale else "LIVE"

    return {
        "bars": bars,
        "db": str(path) if path else None,
        "table": None,
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
        "note": f"twelve · {tickerid or ticker or mkt} · {freshness} · age {_age_text(age)}",
    }


def _latest_ms(result):
    try:
        bars = result.get("bars") or []
        if not bars:
            return -1
        return max(_to_ms(b.get("t")) or -1 for b in bars)
    except Exception:
        return -1


def _decorate_local(local, market="NQ", tf="1H"):
    local = dict(local or {})
    bars = local.get("bars") or []
    if not bars:
        return local

    ntf = core.normalize_tf(tf)
    last = bars[-1]
    last_ms = _to_ms(last.get("close_t")) or _to_ms(last.get("t"))
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    bar_age = max(0.0, (now_ms - last_ms) / 1000.0) if last_ms else None

    file_age = None
    db = local.get("db")
    try:
        if db:
            file_age = max(0.0, datetime.now(timezone.utc).timestamp() - Path(db).stat().st_mtime)
    except Exception:
        file_age = None

    stale_after = _STALE_AFTER.get(ntf, 3 * 60 * 60)
    stale = bar_age is None or bar_age > stale_after
    src = local.get("source") or last.get("source") or "local"
    ticker = last.get("market") or str(market).upper()
    local["feed"] = "original_sqlite"
    local["provider"] = src
    local["ticker"] = ticker
    local["tickerid"] = ticker
    local["source"] = None
    local["last_bar_utc"] = datetime.fromtimestamp(last_ms / 1000.0, tz=timezone.utc).isoformat() if last_ms else None
    local["age_seconds"] = bar_age
    local["file_age_seconds"] = file_age
    local["stale"] = stale
    local["note"] = f"{src} · {ticker} · original local feed · {'STALE' if stale else 'LIVE'} · bar age {_age_text(bar_age)}"
    return local


def original_query_bars(market="NQ", tf="1H", limit=500, source=None):
    original = _load_twelve_file(market, tf, limit)
    local = _decorate_local(_LOCAL_SQLITE_QUERY(market, tf, limit, source), market, tf)

    if original and original.get("bars"):
        if local.get("bars") and _latest_ms(local) > _latest_ms(original):
            return local
        return original

    if local.get("bars"):
        return local

    return {
        "bars": [],
        "db": None,
        "table": None,
        "source": None,
        "feed": "original_twelve",
        "stale": True,
        "age_seconds": None,
        "note": "Kein Original-Livefeed gefunden · Twelve writer/Sync prüfen",
    }


def _feed_one(market, tf="5m"):
    x = original_query_bars(market, tf, 40, None)
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
        "file_age_seconds": x.get("file_age_seconds"),
        "stale": bool(x.get("stale", not bool(bars))),
        "note": x.get("note"),
        "path": x.get("db"),
    }


def feed_status():
    return {
        "generated_at_utc": core.now_iso(),
        "markets": {m: _feed_one(m, "5m") for m in ("NQ", "ES", "XAU")},
    }


def feature_checks():
    checks = []

    def add(name, status, detail, count=None):
        row = {"name": name, "status": status, "detail": detail}
        if count is not None:
            row["count"] = count
        checks.append(row)

    try:
        models = core.normalize_models()
        st = core.signal_status() or {}
        running = st.get("running") is not False
        add("Live models", "PASS" if models and running else ("WARN" if models else "FAIL"), f"{len(models)} Modelle · monitor {st.get('state') or ('running' if running else 'stopped')}", len(models))
    except Exception as exc:
        add("Live models", "FAIL", str(exc))

    try:
        rows = core.archive_rows(500)
        snap_dir = core.WORKSPACE / "live_signals" / "snapshots"
        snaps = len(list(snap_dir.glob("*.json"))) if snap_dir.exists() else 0
        add("Archive + snapshots", "PASS" if rows else "WARN", f"{len(rows)} Archiveinträge · {snaps} Snapshots", len(rows))
    except Exception as exc:
        add("Archive + snapshots", "FAIL", str(exc))

    try:
        outs = core.outcome_summary()
        add("Outcomes", "PASS" if outs else "WARN", f"{len(outs)} Modell-Summaries", len(outs))
    except Exception as exc:
        add("Outcomes", "FAIL", str(exc))

    try:
        paper = core.paper_payload()
        ps = paper.get("status") or {}
        pstate = paper.get("state") or {}
        present = bool(ps or pstate)
        add("Paper account", "PASS" if present else "WARN", f"agent {ps.get('state') or '—'} · open {len(pstate.get('open_positions') or [])}")
    except Exception as exc:
        add("Paper account", "FAIL", str(exc))

    try:
        jobs = core.research_jobs(20)
        add("Research jobs", "PASS" if jobs else "WARN", f"{len(jobs)} Jobs sichtbar", len(jobs))
    except Exception as exc:
        add("Research jobs", "FAIL", str(exc))

    try:
        pd_ok = 0
        for m in ("NQ", "ES", "XAU"):
            x = original_query_bars(m, "1H", 3000, None)
            levels = core.previous_period_level(x.get("bars") or [], m)
            if levels.get("PDH") is not None and levels.get("PDL") is not None:
                pd_ok += 1
        add("PD/PW/PM arrays", "PASS" if pd_ok == 3 else ("WARN" if pd_ok else "FAIL"), f"{pd_ok}/3 Märkte mit Previous-Day Levels")
    except Exception as exc:
        add("PD/PW/PM arrays", "FAIL", str(exc))

    return checks


def diagnostics():
    feeds = {}
    for m in ("NQ", "ES", "XAU"):
        feeds[m] = {tf: _feed_one(m, tf) for tf in ("5m", "15m", "1H", "4H", "1D")}
    components = {}
    for name in ("live_data", "live_signals", "paper_account", "research_jobs", "github_research_repo"):
        p = core.WORKSPACE / name
        try:
            mtime = datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc).isoformat() if p.exists() else None
        except Exception:
            mtime = None
        components[name] = {"exists": p.exists(), "path": str(p), "mtime_utc": mtime}
    return {
        "version": core.APP_VERSION,
        "generated_at_utc": core.now_iso(),
        "workspace": str(core.WORKSPACE),
        "components": components,
        "feeds": feeds,
        "features": feature_checks(),
        "hint": "Wenn nur XAU stale ist, läuft die UI korrekt; dann den ursprünglichen Twelve/XAU-Writer im Workspace prüfen.",
    }


core.query_bars = original_query_bars
core.APP_VERSION = "0.9.4-beta-original-pipeline"


class Handler(core.Handler):
    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/api/feed-status":
            return self.json(feed_status())
        if u.path == "/api/diagnostics":
            return self.json(diagnostics())
        return super().do_GET()


if __name__ == "__main__":
    core.PID_FILE.write_text(str(core.os.getpid()), encoding="utf-8")
    print("TMBT Next", core.APP_VERSION)
    print("Workspace:", core.WORKSPACE)
    print("Chart feed: ORIGINAL TMBT 4.6 pipeline (Twelve mirror -> local SQLite fallback)")
    print("No Yahoo/GC proxy fallback enabled.")
    print("Open: http://127.0.0.1:%s" % core.PORT)
    try:
        core.ThreadingHTTPServer(("127.0.0.1", core.PORT), Handler).serve_forever()
    finally:
        try:
            core.PID_FILE.unlink(missing_ok=True)
        except Exception:
            pass
