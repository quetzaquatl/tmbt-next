from __future__ import annotations

from dataclasses import replace
from typing import Any, Callable

from context_factors import ContextConfig, DEFAULT_CONFIG, evaluate_bars


# Vendor-agnostic hook for Trading Model Backtest Studio.
# The only missing piece after the historical NQ/ES data is purchased is a loader
# with signature: load_bars(market, timeframe, as_of_ms, limit) -> list[dict].

DEFAULT_BACKTEST_CONTEXT = {
    "enabled": True,
    "smt_enabled": True,
    "smt_hard_veto": True,
    "smt_tf": "30m",
    "smt_pivot_left": 2,
    "smt_pivot_right": 2,
    "smt_lookahead_bars": 6,
    "smt_require_reclaim": True,
    "po3_enabled": True,
    "po3_hard_veto": True,
    "asia_enabled": True,
    "asia_session_ny": "20:00-00:00",
    "midnight_enabled": True,
    "midnight_open_ny": "00:00",
    "store_context_columns": True,
}


def _side(v: Any) -> str:
    z = str(v or "").strip().upper()
    if z in {"BUY", "BULL", "BULLISH", "LONG"}:
        return "LONG"
    if z in {"SELL", "BEAR", "BEARISH", "SHORT"}:
        return "SHORT"
    return ""


def _config_for_market(market: str, overrides: dict[str, Any] | None = None) -> ContextConfig:
    target = str(market or "NQ").upper()
    if target not in {"NQ", "ES"}:
        raise ValueError("Context filter currently supports NQ and ES only")
    peer = "ES" if target == "NQ" else "NQ"
    o = dict(overrides or {})
    return replace(
        DEFAULT_CONFIG,
        target_market=target,
        peer_market=peer,
        smt_tf=str(o.get("smt_tf", DEFAULT_BACKTEST_CONTEXT["smt_tf"])),
        smt_pivot_left=int(o.get("smt_pivot_left", DEFAULT_BACKTEST_CONTEXT["smt_pivot_left"])),
        smt_pivot_right=int(o.get("smt_pivot_right", DEFAULT_BACKTEST_CONTEXT["smt_pivot_right"])),
        smt_lookahead_bars=int(o.get("smt_lookahead_bars", DEFAULT_BACKTEST_CONTEXT["smt_lookahead_bars"])),
        smt_hard_veto=bool(o.get("smt_hard_veto", DEFAULT_BACKTEST_CONTEXT["smt_hard_veto"])),
        po3_hard_veto=bool(o.get("po3_hard_veto", DEFAULT_BACKTEST_CONTEXT["po3_hard_veto"])),
        require_reclaim_for_smt=bool(o.get("smt_require_reclaim", DEFAULT_BACKTEST_CONTEXT["smt_require_reclaim"])),
    )


def context_at(
    load_bars: Callable[[str, str, int, int], list[dict[str, Any]]],
    *,
    market: str,
    as_of_ms: int,
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluate context using only bars closed at or before as_of_ms.

    This function is safe to call inside a historical backtest loop. It never
    needs future bars. Pivot confirmation uses only right-side bars that are
    already closed by as_of_ms.
    """
    cfg = _config_for_market(market, overrides)
    target, peer = cfg.target_market, cfg.peer_market
    target_5m = load_bars(target, "5m", as_of_ms, 1800) or []
    peer_5m = load_bars(peer, "5m", as_of_ms, 1800) or []
    target_smt = load_bars(target, cfg.smt_tf, as_of_ms, 700) or []
    peer_smt = load_bars(peer, cfg.smt_tf, as_of_ms, 700) or []
    return evaluate_bars(
        target_5m,
        peer_5m,
        target_smt,
        peer_smt,
        as_of_ms=as_of_ms,
        cfg=cfg,
    )


def flatten_context(ctx: dict[str, Any], market: str) -> dict[str, Any]:
    market = str(market or "").upper()
    levels = (ctx.get("markets") or {}).get(market, {}) or {}
    smt = ctx.get("smt") or {}
    return {
        "ctx_bias": ctx.get("bias"),
        "ctx_quality": ctx.get("quality"),
        "ctx_allow_long": ctx.get("allow_long"),
        "ctx_allow_short": ctx.get("allow_short"),
        "ctx_veto_reason": ctx.get("veto_reason"),
        "ctx_smt_bias": smt.get("bias"),
        "ctx_smt_state": smt.get("state"),
        "ctx_smt_sweeper": smt.get("sweeper"),
        "ctx_smt_holder": smt.get("holder"),
        "ctx_po3_bias": levels.get("po3_bias"),
        "ctx_po3_phase": levels.get("po3_phase"),
        "ctx_asia_high": levels.get("asia_high"),
        "ctx_asia_low": levels.get("asia_low"),
        "ctx_asia_first_sweep": levels.get("asia_first_sweep"),
        "ctx_asia_low_swept": levels.get("asia_low_swept"),
        "ctx_asia_high_swept": levels.get("asia_high_swept"),
        "ctx_midnight_open": levels.get("midnight_open"),
        "ctx_midnight_position": levels.get("midnight_position"),
        "ctx_midnight_bull_reclaim": levels.get("midnight_bull_reclaim"),
        "ctx_midnight_bear_reclaim": levels.get("midnight_bear_reclaim"),
    }


def apply_candidate_filter(
    candidate: dict[str, Any],
    load_bars: Callable[[str, str, int, int], list[dict[str, Any]]],
    *,
    event_time_ms: int,
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Backtest-Studio hook: enrich a candidate and hard-veto counter-bias entries."""
    out = dict(candidate)
    market = str(out.get("market") or out.get("symbol") or "").upper()
    if market not in {"NQ", "ES"}:
        return out

    options = dict(DEFAULT_BACKTEST_CONTEXT)
    options.update(overrides or {})
    if not options.get("enabled", True):
        out["context_filter_allowed"] = True
        return out

    ctx = context_at(load_bars, market=market, as_of_ms=event_time_ms, overrides=options)
    flat = flatten_context(ctx, market)
    if options.get("store_context_columns", True):
        out.update(flat)

    side = _side(out.get("side"))
    allowed = True
    if side == "LONG":
        allowed = bool(ctx.get("allow_long", True))
    elif side == "SHORT":
        allowed = bool(ctx.get("allow_short", True))

    out["context_filter_allowed"] = allowed
    out["context_filter_reason"] = None if allowed else (ctx.get("veto_reason") or "context veto")
    out["context_filter"] = {
        "bias": ctx.get("bias"),
        "quality": ctx.get("quality"),
        "SMT": (ctx.get("smt") or {}).get("bias"),
        "PO3": ((ctx.get("markets") or {}).get(market, {}) or {}).get("po3_bias"),
        "PO3_phase": ((ctx.get("markets") or {}).get(market, {}) or {}).get("po3_phase"),
        "allowed": allowed,
    }
    return out
