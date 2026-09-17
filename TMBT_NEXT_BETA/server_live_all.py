from __future__ import annotations

import server_live as live

# Extend the temporary chart-only near-live fallback to XAU spot as well.
# Keep GC=F out of XAU because COMEX gold futures can differ materially from
# XAU/USD spot and would misalign existing XAU model levels/overlays.
live.LIVE_SYMBOLS["XAU"] = "XAUUSD=X"

core = live.core
core.APP_VERSION = "0.9.2-beta-live-all"

if __name__ == "__main__":
    core.PID_FILE.write_text(str(core.os.getpid()), encoding="utf-8")
    print("TMBT Next", core.APP_VERSION)
    print("Workspace:", core.WORKSPACE)
    print("Chart feed: TEMP LIVE NQ/ES/XAU fallback (Yahoo Finance); local cache remains fallback")
    print("Open: http://127.0.0.1:%s" % core.PORT)
    try:
        core.ThreadingHTTPServer(("127.0.0.1", core.PORT), core.Handler).serve_forever()
    finally:
        try:
            core.PID_FILE.unlink(missing_ok=True)
        except Exception:
            pass
