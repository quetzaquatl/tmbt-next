from __future__ import annotations

import htf_filter
import server_ready as ready

core = ready.core
_base_ready_models = ready.ready_models


def filtered_models():
    """Apply a conservative closed-bar 1H direction gate to iFVG models.

    The raw model engine remains unchanged; contradictory or neutral-HTF iFVG
    setups are surfaced as BLOCKED and therefore cannot enter Active Now.
    """
    return htf_filter.apply_htf_filter(_base_ready_models(), ready.ready_query)


core.normalize_models = filtered_models
core.APP_VERSION = "0.9.16-beta-htf-gate"
Handler = ready.Handler


if __name__ == "__main__":
    core.PID_FILE.write_text(str(core.os.getpid()), encoding="utf-8")
    print("TMBT Next", core.APP_VERSION)
    print("Workspace:", core.WORKSPACE)
    print("Desk: compact Active Now queue + Background Monitor + notification history")
    print("HTF gate: iFVG models require closed 1H EMA20/50 direction alignment")
    print("HTF safety: opposite-side or neutral/stale HTF iFVG setups are BLOCKED")
    print("EBP matrix: NQ/ES x 15m/30m/1H · closed-bar evaluator active")
    print("Feed priority: TRUE FUTURES mirror -> QQQ/SPY monitoring-only fallback")
    print("Safety: proxy/stale/out-of-session models cannot enter Active Now")
    print("Preflight: http://127.0.0.1:%s/api/preflight" % core.PORT)
    print("Open: http://127.0.0.1:%s" % core.PORT)
    try:
        core.ThreadingHTTPServer(("127.0.0.1", core.PORT), Handler).serve_forever()
    finally:
        try:
            core.PID_FILE.unlink(missing_ok=True)
        except Exception:
            pass
