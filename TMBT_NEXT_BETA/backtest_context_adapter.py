from __future__ import annotations

from dataclasses import replace
from typing import Any, Callable

from context_factors import ContextConfig, DEFAULT_CONFIG, evaluate_bars, normalize_bars, _swing_state, _target_smt
import smt_trade_management
import ict_rule_engine


def load_local_databento_bars(market: str, timeframe: str, as_of_ms: int, limit: int) -> list[dict[str, Any]]:
    """Use the locally imported Databento NQ/ES/YM/GC store.

    This keeps the historical engine point-in-time safe: historical_store only
    returns bars that were fully closed at or before as_of_ms.
    """
    from historical_store import load_bars

    return load_bars(market, timeframe, as_of_ms, limit)


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
    "index_smt_ym_enabled": True,
    "po3_enabled": True,
    "po3_hard_veto": True,
    "asia_enabled": True,
    "asia_session_ny": "20:00-00:00",
    "midnight_enabled": True,
    "midnight_open_ny": "00:00",
    "store_context_columns": True,
    "smt_profit_take_enabled": True,
    "smt_profit_take_raw_enabled": True,
    "smt_profit_take_partial_min_r": 1.0,
    "smt_profit_take_partial_fraction": 0.5,
    "smt_profit_take_confirmed_exit_review": True,
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
    ctx = evaluate_bars(
        target_5m,
        peer_5m,
        target_smt,
        peer_smt,
        as_of_ms=as_of_ms,
        cfg=cfg,
    )
    ctx["symmetric_smt"] = smt_trade_management.symmetric_smt(ctx)
    ctx["ict_source_snapshot"] = ict_rule_engine.snapshot(
        target_5m,
        market=target,
        timeframe="5m",
        as_of_ms=as_of_ms,
        max_events=6,
    )

    # Month-10 Index SMT uses ES/NQ/YM as a correlated basket. Keep the
    # existing NQ/ES gate unchanged for backwards compatibility, but add a
    # descriptive target-vs-YM comparison whenever YM history is available.
    # It is intentionally advisory until the three-index correspondence rules
    # have their own locked validation pass.
    options = dict(DEFAULT_BACKTEST_CONTEXT)
    options.update(overrides or {})
    if options.get("index_smt_ym_enabled", True) and target in {"NQ", "ES"}:
        try:
            ym_rows = load_bars("YM", cfg.smt_tf, as_of_ms, 700) or []
        except Exception:
            ym_rows = []
        if ym_rows:
            ts = normalize_bars(target_smt, as_of_ms)
            ys = normalize_bars(ym_rows, as_of_ms)
            target_state = _swing_state(ts, cfg)
            ym_state = _swing_state(ys, cfg)
            pair = _target_smt(
                target,
                "YM",
                target_state,
                ym_state,
                cfg,
            )
            ctx["smt_ym"] = pair
            ctx["symmetric_smt_ym"] = smt_trade_management.symmetric_smt({"smt": pair})
        else:
            ctx["smt_ym"] = {
                "bias": "UNAVAILABLE",
                "state": "UNAVAILABLE",
                "reason": "YM history unavailable; NQ/ES SMT remains active",
                "target": target,
                "peer": "YM",
            }
            ctx["symmetric_smt_ym"] = {
                "bias": "UNAVAILABLE",
                "raw_bias": "UNAVAILABLE",
                "state": "UNAVAILABLE",
                "reason": "YM history unavailable",
                "target": target,
                "peer": "YM",
            }
    return ctx


def flatten_context(ctx: dict[str, Any], market: str) -> dict[str, Any]:
    market = str(market or "").upper()
    levels = (ctx.get("markets") or {}).get(market, {}) or {}
    smt = ctx.get("smt") or {}
    symmetric = ctx.get("symmetric_smt") or smt_trade_management.symmetric_smt(ctx)
    symmetric_ym = ctx.get("symmetric_smt_ym") or {}
    source = ctx.get("ict_source_snapshot") or {}
    layers = source.get("layers") or {}
    source_ctx = layers.get("context") or {}
    source_evt = layers.get("event") or {}
    dr = source_ctx.get("dealing_range") or {}
    latest_fvg = source_evt.get("latest_fvg") or {}
    latest_raid = source_evt.get("latest_liquidity_raid") or {}
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
        "ctx_smt_symmetric_bias": symmetric.get("bias"),
        "ctx_smt_raw_bias": symmetric.get("raw_bias"),
        "ctx_smt_raw_sweeper": symmetric.get("raw_sweeper"),
        "ctx_smt_raw_holder": symmetric.get("raw_holder"),
        "ctx_smt_ym_bias": symmetric_ym.get("bias"),
        "ctx_smt_ym_raw_bias": symmetric_ym.get("raw_bias"),
        "ctx_smt_ym_state": symmetric_ym.get("state"),
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
        "ctx_index_session_phase": levels.get("index_session_phase"),
        "ctx_index_or_high": levels.get("index_or_high"),
        "ctx_index_or_low": levels.get("index_or_low"),
        "ctx_index_or_complete": levels.get("index_or_complete"),
        "ctx_index_am_active": levels.get("index_am_active"),
        "ctx_index_pm_active": levels.get("index_pm_active"),
        "ctx_ict_dealing_location": dr.get("location"),
        "ctx_ict_equilibrium": dr.get("equilibrium"),
        "ctx_ict_latest_fvg_side": latest_fvg.get("side"),
        "ctx_ict_latest_fvg_ce": latest_fvg.get("ce"),
        "ctx_ict_latest_raid_side": latest_raid.get("liquidity_side"),
        "ctx_ict_latest_raid_reference": latest_raid.get("reference_price"),
        "ctx_ict_pipeline_version": source.get("pipeline_version"),
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

    # Symmetric SMT: direction does not depend on which correlated index raids
    # liquidity. High divergence is bearish, low divergence bullish.
    symmetric = ctx.get("symmetric_smt") or {}
    sbias = symmetric.get("bias")
    if options.get("smt_hard_veto", True):
        if side == "LONG" and sbias in {"BEARISH", "CONFLICT"}:
            allowed = False
        elif side == "SHORT" and sbias in {"BULLISH", "CONFLICT"}:
            allowed = False

    out["context_filter_allowed"] = allowed
    out["context_filter_reason"] = None if allowed else (symmetric.get("reason") or ctx.get("veto_reason") or "context veto")
    out["context_filter"] = {
        "bias": ctx.get("bias"),
        "quality": ctx.get("quality"),
        "SMT": (ctx.get("smt") or {}).get("bias"),
        "SMT_symmetric": symmetric.get("bias"),
        "SMT_raw": symmetric.get("raw_bias"),
        "SMT_YM": (ctx.get("symmetric_smt_ym") or {}).get("bias"),
        "SMT_YM_raw": (ctx.get("symmetric_smt_ym") or {}).get("raw_bias"),
        "PO3": ((ctx.get("markets") or {}).get(market, {}) or {}).get("po3_bias"),
        "PO3_phase": ((ctx.get("markets") or {}).get(market, {}) or {}).get("po3_phase"),
        "allowed": allowed,
    }
    return out


def manage_open_trade(
    trade: dict[str, Any],
    load_bars: Callable[[str, str, int, int], list[dict[str, Any]]],
    *,
    as_of_ms: int,
    current_price: float | None = None,
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Backtest/paper hook for SMT-based profit taking after entry.

    Raw opposite SMT is deliberately earlier than the entry veto: it fires on the
    liquidity raid itself and can therefore protect open profit before a reclaim
    confirms the reversal. Confirmed opposite SMT upgrades the state to
    EXIT_REVIEW. The caller decides whether TAKE_PARTIAL means 25%, 50%, etc.;
    the default experiment is 50% once >=1R is available.
    """
    out = dict(trade)
    market = str(out.get("market") or out.get("symbol") or "").upper()
    if market not in {"NQ", "ES"}:
        return out

    options = dict(DEFAULT_BACKTEST_CONTEXT)
    options.update(overrides or {})
    if not options.get("smt_profit_take_enabled", True):
        out["smt_profit_take_action"] = "HOLD"
        return out

    ctx = context_at(load_bars, market=market, as_of_ms=as_of_ms, overrides=options)
    side = _side(out.get("side"))
    if current_price is None:
        rows = load_bars(market, "5m", as_of_ms, 10) or []
        if rows:
            last = rows[-1]
            current_price = last.get("c") if last.get("c") is not None else last.get("close")

    r_now = smt_trade_management.current_r(
        side,
        out.get("entry"),
        out.get("stop") if out.get("stop") is not None else out.get("sl"),
        current_price,
    )
    advice = smt_trade_management.profit_take_advice(
        ctx,
        trade_side=side,
        current_r_value=r_now,
        partial_min_r=float(options.get("smt_profit_take_partial_min_r", 1.0)),
    )

    # Allow A/B tests without changing the detector itself.
    if not options.get("smt_profit_take_raw_enabled", True) and not advice.get("adverse_confirmed"):
        advice["action"] = "HOLD"
        advice["reason"] = "raw SMT profit taking disabled"
    if not options.get("smt_profit_take_confirmed_exit_review", True) and advice.get("action") == "EXIT_REVIEW":
        advice["action"] = "TAKE_PARTIAL"
        advice["reason"] = "confirmed SMT detected; full-exit review disabled"

    advice["partial_fraction"] = float(options.get("smt_profit_take_partial_fraction", 0.5))
    advice["as_of_ms"] = as_of_ms
    advice["current_price"] = current_price
    out["smt_profit_take_action"] = advice.get("action")
    out["smt_profit_take_reason"] = advice.get("reason")
    out["smt_profit_take_current_r"] = r_now
    out["smt_profit_take_fraction"] = advice.get("partial_fraction")
    out["smt_profit_take"] = advice
    if options.get("store_context_columns", True):
        out.update(flatten_context(ctx, market))
    return out
