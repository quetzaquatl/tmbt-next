from __future__ import annotations

from urllib.parse import urlparse

import ebp_parallel
import server_desk as desk

core = desk.core
_base_normalize_models = core.normalize_models


def _is_legacy_index_ebp(m: dict) -> bool:
    name = str(m.get("name") or "").upper()
    market = str(m.get("market") or "").upper()
    return market in {"NQ", "ES"} and "EBP" in name


def ready_models():
    """Expose exactly six NQ/ES EBP instances (15m/30m/1H).

    Old H1 monitor rows are replaced by the generalized evaluator so the Radar,
    Signals tab and Inspector all consume one coherent rule implementation.
    QQQ/SPY remain explicitly proxy-gated by feed_gate_patch.js until a true
    futures mirror is attached.
    """
    base = [m for m in (_base_normalize_models() or []) if not _is_legacy_index_ebp(m)]
    derived = ebp_parallel.build_parallel_models(desk.desk_query_bars)
    return base + derived


core.normalize_models = ready_models
core.APP_VERSION = "0.9.12-beta-ebp-matrix"


def preflight():
    report = ebp_parallel.preflight_report(desk.desk_query_bars)
    report["version"] = core.APP_VERSION
    report["rules"] = {
        "markets": ["NQ", "ES"],
        "timeframes": ["15m", "30m", "1H"],
        "closed_bar_only": True,
        "entry_valid_bars": 4,
        "target_rr": 2.0,
        "proxy_execution_blocked": True,
    }
    return report


def ready_diagnostics():
    d = desk.diagnostics_with_30m()
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
        "detail": "Echte Futures frisch" if pf.get("live_ready") else "Engine bereit, aber QQQ/SPY Proxy bzw. stale Feed blockiert Live-Alerts",
    })
    d["preflight"] = pf
    d["version"] = core.APP_VERSION
    return d


class Handler(desk.Handler):
    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/api/preflight":
            return self.json(preflight())
        if u.path == "/api/diagnostics":
            return self.json(ready_diagnostics())
        return super().do_GET()


if __name__ == "__main__":
    core.PID_FILE.write_text(str(core.os.getpid()), encoding="utf-8")
    print("TMBT Next", core.APP_VERSION)
    print("Workspace:", core.WORKSPACE)
    print("EBP matrix: NQ/ES x 15m/30m/1H · closed-bar evaluator active")
    print("Safety: QQQ/SPY proxy data remains monitoring-only; live alerts are blocked until true futures are attached")
    print("Preflight: http://127.0.0.1:%s/api/preflight" % core.PORT)
    print("Open: http://127.0.0.1:%s" % core.PORT)
    try:
        core.ThreadingHTTPServer(("127.0.0.1", core.PORT), Handler).serve_forever()
    finally:
        try:
            core.PID_FILE.unlink(missing_ok=True)
        except Exception:
            pass
