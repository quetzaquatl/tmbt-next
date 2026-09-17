from __future__ import annotations

from urllib.parse import urlparse

import ebp_parallel
import futures_mirror
import server_desk as desk

core = desk.core
_base_normalize_models = core.normalize_models


def _is_legacy_index_ebp(m: dict) -> bool:
    name = str(m.get("name") or "").upper()
    market = str(m.get("market") or "").upper()
    return market in {"NQ", "ES"} and "EBP" in name


def ready_query(market="NQ", tf="1H", limit=500, source=None):
    """Prefer a true NQ/ES futures mirror; fall back to the safe proxy mirror.

    The fallback is deliberately monitoring-only. feed_gate_patch.js blocks proxy
    alerts/signals. As soon as a provider bridge writes NQ/ES futures JSON into
    workspace/live_data/futures (or one of the other supported roots), this
    function switches the chart and all six EBP instances to that same feed.
    """
    mkt = str(market).upper()
    if mkt in {"NQ", "ES"}:
        true_future = futures_mirror.query(core.WORKSPACE, mkt, tf, limit)
        if true_future and true_future.get("bars"):
            return true_future
    return desk.desk_query_bars(market, tf, limit, source)


def ready_models():
    """Expose exactly six NQ/ES EBP instances (15m/30m/1H)."""
    base = [m for m in (_base_normalize_models() or []) if not _is_legacy_index_ebp(m)]
    derived = ebp_parallel.build_parallel_models(ready_query)
    return base + derived


# All handlers that resolve core.query_bars now see the same provider-selecting
# function as the EBP evaluator. This prevents model/chart feed mismatches.
core.query_bars = ready_query
core.normalize_models = ready_models
core.APP_VERSION = "0.9.13-beta-ebp-futures-ready"


def _feed_one(market, tf="5m"):
    x = ready_query(market, tf, 100, None) or {}
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
        "exchange": x.get("exchange"),
        "last_bar_utc": x.get("last_bar_utc"),
        "last_received_at_utc": x.get("last_received_at_utc"),
        "age_seconds": x.get("age_seconds"),
        "stale": bool(x.get("stale", not bool(bars))),
        "note": x.get("note"),
        "path": x.get("db"),
        "canonical": bool(x.get("canonical")),
        "identity_ok": x.get("identity_ok"),
        "derived_from": x.get("derived_from"),
        "true_futures": x.get("feed") == "true_futures_mirror",
    }


def ready_feed_status():
    markets = {}
    for market in ("NQ", "ES", "XAU"):
        tfs = {tf: _feed_one(market, tf) for tf in ("5m", "15m", "30m", "1H")}
        summary = dict(tfs["5m"])
        summary["timeframes"] = tfs
        markets[market] = summary
    return {"generated_at_utc": core.now_iso(), "markets": markets}


def preflight():
    report = ebp_parallel.preflight_report(ready_query)
    report["version"] = core.APP_VERSION
    report["rules"] = {
        "markets": ["NQ", "ES"],
        "timeframes": ["15m", "30m", "1H"],
        "closed_bar_only": True,
        "entry_valid_bars": 4,
        "target_rr": 2.0,
        "proxy_execution_blocked": True,
    }
    report["feed_status"] = ready_feed_status()
    return report


def ready_diagnostics():
    # Start with existing workspace/component checks, then replace the feed rows
    # with the provider-selecting path used by models and charts.
    d = desk.diagnostics_with_30m()
    d["feeds"] = {}
    for market in ("NQ", "ES", "XAU"):
        d["feeds"][market] = {tf: _feed_one(market, tf) for tf in ("5m", "15m", "30m", "1H", "4H", "1D")}
    pf = preflight()
    checks = d.setdefault("features", [])
    checks.append({
        "name": "EBP 6-instance engine",
        "status": "PASS" if pf.get("engine_ready") else "FAIL",
        "detail": f"{pf.get('models_built', 0)}/6 Instanzen gebaut · NQ/ES × 15m/30m/1H",
        "count": pf.get("models_built", 0),
    })
    checks.append({
        "name": "EBP live execution gate",
        "status": "PASS" if pf.get("live_ready") else "WARN",
        "detail": "Echte NQ/ES Futures frisch · 6/6 live-fähig" if pf.get("live_ready") else "Engine bereit; QQQ/SPY Proxy, stale oder fehlender Futures-Feed blockiert Live-Alerts",
    })
    d["preflight"] = pf
    d["version"] = core.APP_VERSION
    d["hint"] = (
        "Provider-ready mode: true NQ/ES futures mirrors are preferred automatically. "
        "Without them, QQQ/SPY remain monitoring-only and cannot fire live alerts."
    )
    return d


class Handler(desk.Handler):
    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/api/preflight":
            return self.json(preflight())
        if u.path == "/api/feed-status":
            return self.json(ready_feed_status())
        if u.path == "/api/diagnostics":
            return self.json(ready_diagnostics())
        return super().do_GET()


if __name__ == "__main__":
    core.PID_FILE.write_text(str(core.os.getpid()), encoding="utf-8")
    print("TMBT Next", core.APP_VERSION)
    print("Workspace:", core.WORKSPACE)
    print("EBP matrix: NQ/ES x 15m/30m/1H · closed-bar evaluator active")
    print("Feed priority: TRUE FUTURES mirror -> QQQ/SPY monitoring-only fallback")
    print("Safety: proxy/stale feeds cannot fire live alerts")
    print("Preflight: http://127.0.0.1:%s/api/preflight" % core.PORT)
    print("Open: http://127.0.0.1:%s" % core.PORT)
    try:
        core.ThreadingHTTPServer(("127.0.0.1", core.PORT), Handler).serve_forever()
    finally:
        try:
            core.PID_FILE.unlink(missing_ok=True)
        except Exception:
            pass
