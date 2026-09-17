from __future__ import annotations

import server_live as live

core = live.core

# Yahoo does not expose a reliable XAU/USD spot symbol here. Use GC=F only as a
# temporary movement proxy, then shift the whole series by the basis versus the
# last known local XAU spot candle so the chart remains roughly aligned with
# the existing XAU model levels. This is chart-only and not suitable for model
# execution or order placement.
live.LIVE_SYMBOLS["XAU"] = "GC=F"

_base_query = live.live_query_bars


def _xau_proxy_bars(tf="5m", limit=1500, source=None):
    raw = live._fetch_yahoo("XAU", tf, limit)
    bars = [dict(b) for b in (raw.get("bars") or [])]
    local = live._LOCAL_QUERY_BARS("XAU", tf, limit, source) or {}
    local_bars = local.get("bars") or []

    basis = 0.0
    anchor_age = None
    if bars and local_bars:
        last_local = local_bars[-1]
        lt = live._to_ms(last_local.get("t"))
        if lt is not None:
            anchor = min(bars, key=lambda b: abs((live._to_ms(b.get("t")) or 0) - lt))
            at = live._to_ms(anchor.get("t"))
            if at is not None:
                anchor_age = abs(at - lt) / 1000.0
                try:
                    basis = float(last_local.get("c")) - float(anchor.get("c"))
                except Exception:
                    basis = 0.0

    if basis:
        for b in bars:
            for k in ("o", "h", "l", "c"):
                try:
                    b[k] = float(b[k]) + basis
                except Exception:
                    pass

    raw = dict(raw)
    raw["bars"] = bars
    raw["feed"] = "temporary_xau_gc_basis_proxy"
    raw["symbol"] = "GC=F"
    raw["proxy"] = True
    raw["basis_adjustment"] = basis
    raw["source"] = None
    anchor_txt = f" · basis {basis:+.2f}" if basis else ""
    if anchor_age is not None:
        anchor_txt += f" · anchor Δt {anchor_age/60:.0f}m"
    raw["note"] = f"XAU proxy via GC=F{anchor_txt} · TEMP LIVE · chart only"
    return raw


def query_bars_all(market="NQ", tf="1H", limit=500, source=None):
    mkt = str(market).upper()
    if mkt == "XAU":
        try:
            return _xau_proxy_bars(tf, limit, source)
        except Exception as exc:
            local = live._LOCAL_QUERY_BARS(market, tf, limit, source)
            local = dict(local or {})
            old_source = local.get("source") or "local"
            local["source"] = None
            local["feed"] = "stale_local_fallback"
            local["live_fallback_error"] = str(exc)
            local["note"] = f"XAU STALE · {old_source} local cache · live proxy error: {exc}"
            return local
    return _base_query(market, tf, limit, source)


core.query_bars = query_bars_all
core.APP_VERSION = "0.9.3-beta-live-all"

if __name__ == "__main__":
    core.PID_FILE.write_text(str(core.os.getpid()), encoding="utf-8")
    print("TMBT Next", core.APP_VERSION)
    print("Workspace:", core.WORKSPACE)
    print("Chart feed: TEMP LIVE NQ/ES + XAU basis-adjusted GC proxy; local cache remains fallback")
    print("Open: http://127.0.0.1:%s" % core.PORT)
    try:
        core.ThreadingHTTPServer(("127.0.0.1", core.PORT), core.Handler).serve_forever()
    finally:
        try:
            core.PID_FILE.unlink(missing_ok=True)
        except Exception:
            pass
