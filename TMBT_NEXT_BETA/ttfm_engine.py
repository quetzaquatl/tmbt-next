from __future__ import annotations

"""
Deterministic, point-in-time implementation of the PUBLIC TTrades Fractal Model
material used by TMBT Next research.

This is not the proprietary TradingView indicator and does not claim to reproduce
private T-Spot / hidden indicator internals. Every hard rule below is either:
  1) directly supported by public TTrades education, or
  2) explicitly labelled as a TMBT execution convention needed to make the
     public narrative testable without lookahead.

Public sources:
- Candle 2 closures:
  https://ttrades.com/understanding-candle-2-closures-within-the-fractal-model/
- Candle 3 closures:
  https://ttrades.com/candle-3-closure-a-complete-guide-to-identifying-continuations-and-reversals/
- CISD / protected swings:
  https://ttrades.com/how-change-in-the-state-of-delivery-cisd-confirms-swing-points/
- D1 -> H1 -> M5 playbook:
  https://ttrades.com/fractal-model-playbook-aligning-daily-hourly-and-5-minute-charts/
- D1 -> H4 -> M15:
  https://ttrades.com/the-best-timeframes-for-ttrades-fractal-model-simple/
- H1 -> M15 -> M1 scalping:
  https://ttrades.com/ttrades-scalping-model-simple-day-trading-strategy/
- POI hierarchy:
  https://ttrades.com/the-only-points-of-interest-that-actually-matter-for-trading/

TMBT public-core conventions (not claimed as proprietary TTrades rules):
- CISD "series" is made deterministic as the contiguous opposing-candle series
  leading into a confirmed pivot. The reference is the origin/open of that series.
- Entry is the next 1-minute bar open after the lowest-timeframe CISD closes.
- Initial research target is fixed >=2R; protected swing is the stop.
- Historical research requires closed candles only. No "Early C2 CISD".
"""

import math
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any, Optional
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd


PUBLIC_RULE_VERSION = "ttfm-public-core-v1"

PROFILE_SPECS: dict[str, dict[str, Any]] = {
    "TTFM D1-H1-M5": {
        "anchor_tf": "1D",
        "confirm_tf": "1H",
        "entry_tf": "5m",
        "mode": "daily_expansion",
        "requires_daily_context": False,
        "label": "TTFM · D1 → H1 → M5",
    },
    "TTFM D1-H4-M15": {
        "anchor_tf": "1D",
        "confirm_tf": "4H",
        "entry_tf": "15m",
        "mode": "daily_expansion",
        "requires_daily_context": False,
        "label": "TTFM · D1 → H4 → M15",
    },
    "TTFM H1-M15-M1": {
        "anchor_tf": "1H",
        "confirm_tf": "15m",
        "entry_tf": "1m",
        "mode": "scalp",
        "requires_daily_context": True,
        "label": "TTFM Scalping · H1 → M15 → M1",
    },
}

_TF_MINUTES = {
    "1m": 1,
    "5m": 5,
    "15m": 15,
    "30m": 30,
    "1H": 60,
    "4H": 240,
    "1D": 1440,
}


@dataclass
class ClosureEvent:
    side: str
    kind: str
    close_time: pd.Timestamp
    candle_open_time: pd.Timestamp
    swing_price: float
    poi_type: str
    poi_level: float
    c1_low: float
    c1_high: float
    c2_low: float
    c2_high: float
    range_eq: float
    source_variant: str


@dataclass
class CISDEvent:
    side: str
    pivot_time: pd.Timestamp
    confirm_time: pd.Timestamp
    protected_swing: float
    reference: float
    poi_type: str
    poi_level: float
    series_start_time: pd.Timestamp
    series_bars: int
    displacement_points: float


def profile_spec(model_type: str) -> Optional[dict[str, Any]]:
    return PROFILE_SPECS.get(str(model_type))


def _ohlc(row: pd.Series) -> tuple[float, float, float, float]:
    return (
        float(row["mid_open"]),
        float(row["mid_high"]),
        float(row["mid_low"]),
        float(row["mid_close"]),
    )


def _aggregate(df: pd.DataFrame, tf: str, tz_name: str) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    tf = str(tf)
    if tf == "1m":
        return df.copy()
    rules = {
        "5m": "5min",
        "15m": "15min",
        "30m": "30min",
        "1H": "1h",
        "4H": "4h",
        "1D": "1D",
    }
    rule = rules.get(tf)
    if not rule:
        return pd.DataFrame()
    local = df.tz_convert(tz_name)
    agg = {}
    for pfx in ("mid", "bid", "ask"):
        agg[f"{pfx}_open"] = "first"
        agg[f"{pfx}_high"] = "max"
        agg[f"{pfx}_low"] = "min"
        agg[f"{pfx}_close"] = "last"
    for col, fn in (
        ("tick_count", "sum"),
        ("ask_volume", "sum"),
        ("bid_volume", "sum"),
        ("spread_median", "median"),
        ("spread_close", "last"),
    ):
        if col in local.columns:
            agg[col] = fn
    if tf == "1D":
        # CME/COMEX Globex trading day: 18:00 ET -> 17:00 ET, with the
        # maintenance hour left empty. Offset keeps Daily closures aligned to
        # the futures session instead of arbitrary midnight calendar bars.
        out = local.resample(rule, label="left", closed="left", offset="18h").agg(agg)
    else:
        out = local.resample(rule, label="left", closed="left").agg(agg)
    marker = "tick_count" if "tick_count" in out.columns else "mid_close"
    out = out[out[marker].notna()].copy()
    if marker == "tick_count":
        out = out[out[marker] > 0]
    out.index = out.index.tz_convert("UTC")
    return out


def _load_trading_day(bt_core, file_index, cache_root: Path, market: str, d: date, tz_name: str) -> pd.DataFrame:
    """Load one Globex trading day ending on local date d at 18:00 ET.

    Session convention for NQ/ES/GC research:
    previous calendar day 18:00 ET -> current calendar day 18:00 ET.
    The 17:00-18:00 ET maintenance gap simply contains no bars.
    """
    tz = ZoneInfo(tz_name)
    start_local = pd.Timestamp(datetime.combine(d - timedelta(days=1), time(18, 0), tzinfo=tz))
    end_local = pd.Timestamp(datetime.combine(d, time(18, 0), tzinfo=tz))
    pieces = []
    for cal_d in (d - timedelta(days=1), d):
        x = bt_core.load_local_day_1m(file_index, cache_root, market, cal_d, tz_name)
        if x is not None and not x.empty:
            pieces.append(x)
    if not pieces:
        return pd.DataFrame()
    x = pd.concat(pieces).sort_index()
    return x[(x.index >= start_local.tz_convert("UTC")) & (x.index < end_local.tz_convert("UTC"))].copy()


def _previous_trading_days(bt_core, file_index, cache_root: Path, market: str, d: date, tz_name: str, count: int = 8) -> list[pd.DataFrame]:
    frames: list[pd.DataFrame] = []
    cursor = d - timedelta(days=1)
    attempts = 0
    while len(frames) < count and attempts < 24:
        x = _load_trading_day(bt_core, file_index, cache_root, market, cursor, tz_name)
        if x is not None and not x.empty:
            frames.append(x)
        cursor -= timedelta(days=1)
        attempts += 1
    frames.reverse()
    return frames

def _pivot_indices(bars: pd.DataFrame, kind: str, left: int = 2, right: int = 2) -> list[int]:
    if bars is None or len(bars) < left + right + 1:
        return []
    vals = bars["mid_low"].to_numpy(float) if kind == "low" else bars["mid_high"].to_numpy(float)
    out = []
    for i in range(left, len(vals) - right):
        before = vals[i-left:i]
        after = vals[i+1:i+right+1]
        if kind == "low":
            ok = vals[i] < np.min(before) and vals[i] <= np.min(after)
        else:
            ok = vals[i] > np.max(before) and vals[i] >= np.max(after)
        if ok:
            out.append(i)
    return out


def _fvg_zones(bars: pd.DataFrame, upto: int) -> list[dict[str, Any]]:
    zones: list[dict[str, Any]] = []
    stop = min(max(0, int(upto)), len(bars))
    for i in range(2, stop):
        a = bars.iloc[i - 2]
        c = bars.iloc[i]
        # ICT-style 3-candle imbalance; used only as the public POI primitive.
        if float(c["mid_low"]) > float(a["mid_high"]):
            zones.append({
                "kind": "bullish_fvg",
                "low": float(a["mid_high"]),
                "high": float(c["mid_low"]),
                "time": bars.index[i],
            })
        if float(c["mid_high"]) < float(a["mid_low"]):
            zones.append({
                "kind": "bearish_fvg",
                "low": float(c["mid_high"]),
                "high": float(a["mid_low"]),
                "time": bars.index[i],
            })
    return zones


def _poi_interaction(bars: pd.DataFrame, i: int, side: str, pivot_left: int = 2, pivot_right: int = 2) -> Optional[dict[str, Any]]:
    """POI priority: FVG -> prior swing. CISD itself is confirmation, not invented as a pre-pivot level."""
    if i <= 0 or i >= len(bars):
        return None
    row = bars.iloc[i]
    lo, hi = float(row["mid_low"]), float(row["mid_high"])

    # First: most recent FVG that the candidate swing candle actually touches.
    zones = _fvg_zones(bars, i)
    for z in reversed(zones[-30:]):
        if hi >= z["low"] and lo <= z["high"]:
            if side == "Long" and z["kind"] == "bullish_fvg":
                return {"type": "FVG", "level": (z["low"] + z["high"]) / 2.0, "zone": z}
            if side == "Short" and z["kind"] == "bearish_fvg":
                return {"type": "FVG", "level": (z["low"] + z["high"]) / 2.0, "zone": z}

    # Second: prior confirmed swing high/low that is raided/touched.
    kind = "low" if side == "Long" else "high"
    pivots = _pivot_indices(bars.iloc[:i], kind, pivot_left, pivot_right)
    if pivots:
        p = pivots[-1]
        level = float(bars.iloc[p]["mid_low"] if side == "Long" else bars.iloc[p]["mid_high"])
        if (side == "Long" and lo <= level) or (side == "Short" and hi >= level):
            return {"type": "SWING", "level": level, "pivot_time": bars.index[p]}

    return None


def _c2_event(bars: pd.DataFrame, i: int) -> Optional[ClosureEvent]:
    if i < 1 or i >= len(bars):
        return None
    c1, c2 = bars.iloc[i - 1], bars.iloc[i]
    o1, h1, l1, c1c = _ohlc(c1)
    o2, h2, l2, c2c = _ohlc(c2)

    bull = l2 < l1 and l1 < c2c <= h1
    bear = h2 > h1 and l1 <= c2c < h1
    if bull and bear:
        return None
    if not bull and not bear:
        return None

    side = "Long" if bull else "Short"
    poi = {"type": "PREVIOUS_LOW" if bull else "PREVIOUS_HIGH", "level": l1 if bull else h1}
    tf_min = 1440 if (bars.index[i] - bars.index[i-1]).total_seconds() >= 20 * 3600 else max(1, int((bars.index[i] - bars.index[i-1]).total_seconds() // 60))
    close_time = bars.index[i] + pd.Timedelta(minutes=tf_min)
    return ClosureEvent(
        side=side,
        kind="C2",
        close_time=close_time,
        candle_open_time=bars.index[i],
        swing_price=l2 if bull else h2,
        poi_type=poi["type"],
        poi_level=float(poi["level"]),
        c1_low=l1,
        c1_high=h1,
        c2_low=l2,
        c2_high=h2,
        range_eq=(l1 + h1) / 2.0,
        source_variant="reversal_sweep_close_inside_previous_range",
    )


def _c3_event(bars: pd.DataFrame, i: int, pivot_left: int = 2, pivot_right: int = 2) -> Optional[ClosureEvent]:
    if i < 2 or i >= len(bars):
        return None
    # A valid C2 already confirmed one bar earlier; C3 closure is the fallback only.
    if _c2_event(bars, i - 1) is not None:
        return None
    c1, c2, c3 = bars.iloc[i - 2], bars.iloc[i - 1], bars.iloc[i]
    o1, h1, l1, c1c = _ohlc(c1)
    o2, h2, l2, c2c = _ohlc(c2)
    o3, h3, l3, c3c = _ohlc(c3)
    body_hi = max(o2, c2c)
    body_lo = min(o2, c2c)

    bull_close = c3c > body_hi and l3 >= l2
    bear_close = c3c < body_lo and h3 <= h2

    # Public descriptions show two C3 paths: C2 may sweep but fail the inside
    # close, or may interact with another POI and C3 then engulfs C2. Support both.
    bull_failed_sweep = l2 < l1 and not (l1 < c2c <= h1)
    bear_failed_sweep = h2 > h1 and not (l1 <= c2c < h1)
    bull_poi = _poi_interaction(bars, i - 1, "Long", pivot_left, pivot_right)
    bear_poi = _poi_interaction(bars, i - 1, "Short", pivot_left, pivot_right)

    if bull_close and (bull_failed_sweep or bull_poi):
        poi = bull_poi or {"type": "PREVIOUS_LOW_FAILED_C2", "level": l1}
        return ClosureEvent(
            side="Long",
            kind="C3",
            close_time=bars.index[i] + (bars.index[i] - bars.index[i-1]),
            candle_open_time=bars.index[i],
            swing_price=l2,
            poi_type=str(poi["type"]),
            poi_level=float(poi["level"]),
            c1_low=l1,
            c1_high=h1,
            c2_low=l2,
            c2_high=h2,
            range_eq=(l2 + h2) / 2.0,
            source_variant="c3_body_engulf_after_failed_c2_or_poi",
        )
    if bear_close and (bear_failed_sweep or bear_poi):
        poi = bear_poi or {"type": "PREVIOUS_HIGH_FAILED_C2", "level": h1}
        return ClosureEvent(
            side="Short",
            kind="C3",
            close_time=bars.index[i] + (bars.index[i] - bars.index[i-1]),
            candle_open_time=bars.index[i],
            swing_price=h2,
            poi_type=str(poi["type"]),
            poi_level=float(poi["level"]),
            c1_low=l1,
            c1_high=h1,
            c2_low=l2,
            c2_high=h2,
            range_eq=(l2 + h2) / 2.0,
            source_variant="c3_body_engulf_after_failed_c2_or_poi",
        )
    return None


def latest_closure_event(bars: pd.DataFrame, pivot_left: int = 2, pivot_right: int = 2) -> Optional[ClosureEvent]:
    if bars is None or len(bars) < 2:
        return None
    i = len(bars) - 1
    return _c2_event(bars, i) or _c3_event(bars, i, pivot_left, pivot_right)


def _daily_direction_context(daily: pd.DataFrame) -> Optional[str]:
    """Broad direction only. Uses the public continuation/reversal closure logic."""
    if daily is None or len(daily) < 2:
        return None
    event = latest_closure_event(daily)
    if event:
        return event.side
    prev, cur = daily.iloc[-2], daily.iloc[-1]
    _, ph, pl, _ = _ohlc(prev)
    _, ch, cl, cc = _ohlc(cur)
    if cl < pl and cc < pl:
        return "Short"  # continuation closure through prior low
    if ch > ph and cc > ph:
        return "Long"   # continuation closure through prior high
    return None


def _opposing_series_origin(bars: pd.DataFrame, pivot_i: int, side: str) -> tuple[int, float]:
    # Deterministic public-core convention: contiguous candles delivering into
    # the pivot. For a bullish turn those are bearish bodies; bearish mirrors.
    j = pivot_i
    def opposing(row):
        o, _, _, c = _ohlc(row)
        return c <= o if side == "Long" else c >= o

    if j >= 0 and not opposing(bars.iloc[j]):
        j -= 1
    if j < 0:
        return max(0, pivot_i - 1), float(bars.iloc[max(0, pivot_i - 1)]["mid_open"])
    start = j
    while start - 1 >= 0 and opposing(bars.iloc[start - 1]):
        start -= 1
    ref = float(bars.iloc[start]["mid_open"])
    return start, ref


def _find_cisd(
    bars: pd.DataFrame,
    side: str,
    *,
    pivot_left: int = 2,
    pivot_right: int = 2,
    max_confirm_bars: int = 12,
    require_local_poi: bool = False,
    min_time: Optional[pd.Timestamp] = None,
) -> Optional[CISDEvent]:
    if bars is None or len(bars) < pivot_left + pivot_right + 3:
        return None
    kind = "low" if side == "Long" else "high"
    pivots = _pivot_indices(bars, kind, pivot_left, pivot_right)
    for p in pivots:
        confirm_pivot_i = p + pivot_right
        if confirm_pivot_i >= len(bars):
            continue
        if min_time is not None and bars.index[confirm_pivot_i] < min_time:
            continue
        poi = _poi_interaction(bars, p, side, pivot_left, pivot_right)
        if require_local_poi and poi is None:
            continue
        start, ref = _opposing_series_origin(bars, p, side)
        last = min(len(bars) - 1, confirm_pivot_i + max(1, int(max_confirm_bars)))
        for j in range(confirm_pivot_i, last + 1):
            close = float(bars.iloc[j]["mid_close"])
            crossed = close > ref if side == "Long" else close < ref
            if not crossed:
                continue
            protected = (
                float(bars.iloc[start:j+1]["mid_low"].min())
                if side == "Long"
                else float(bars.iloc[start:j+1]["mid_high"].max())
            )
            displacement = (close - ref) if side == "Long" else (ref - close)
            return CISDEvent(
                side=side,
                pivot_time=bars.index[p],
                confirm_time=bars.index[j],
                protected_swing=protected,
                reference=ref,
                poi_type=str((poi or {}).get("type") or "HTF_CLOSURE_POI"),
                poi_level=float((poi or {}).get("level") or protected),
                series_start_time=bars.index[start],
                series_bars=max(1, p - start + 1),
                displacement_points=float(displacement),
            )
    return None


def _filter_between(bars: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    if bars is None or bars.empty:
        return pd.DataFrame()
    return bars[(bars.index >= start) & (bars.index < end)].copy()


def _tf_delta(tf: str) -> pd.Timedelta:
    return pd.Timedelta(minutes=_TF_MINUTES[tf])


def _execute_market(
    bt_core,
    day_1m: pd.DataFrame,
    side: str,
    ready_time: pd.Timestamp,
    stop: float,
    cfg,
    news: pd.DataFrame,
    session_end: pd.Timestamp,
) -> Optional[dict[str, Any]]:
    x = day_1m[(day_1m.index >= ready_time) & (day_1m.index < session_end)]
    if x.empty:
        return None
    fill_i = None
    entry = None
    spread = np.nan
    news_ctx = None
    for i, (ts, row) in enumerate(x.iterrows()):
        sp = float(row.get("spread_median", np.nan))
        if cfg.max_spread_points > 0 and not np.isnan(sp) and sp > cfg.max_spread_points:
            continue
        ctx = bt_core._news_context(news, ts, cfg)
        if not ctx.get("allowed", True):
            continue
        entry = float(row["ask_open"] if side == "Long" else row["bid_open"])
        entry += cfg.slippage_points if side == "Long" else -cfg.slippage_points
        fill_i = i
        spread = sp
        news_ctx = ctx
        break
    if fill_i is None or entry is None:
        return None

    stop = float(stop)
    risk = abs(entry - stop)
    if risk <= 0:
        return None
    if side == "Long" and stop >= entry:
        return None
    if side == "Short" and stop <= entry:
        return None
    if cfg.min_risk_points > 0 and risk < cfg.min_risk_points:
        return None
    if cfg.max_risk_points > 0 and risk > cfg.max_risk_points:
        return None

    rr = max(2.0, float(cfg.target_rr))
    target = entry + rr * risk if side == "Long" else entry - rr * risk
    xx = x.iloc[fill_i:]
    exit_time = None
    exit_price = None
    reason = None
    mfe_r = -np.inf
    mae_r = np.inf
    for ts, row in xx.iterrows():
        if side == "Long":
            fav = (float(row["bid_high"]) - entry) / risk
            adv = (float(row["bid_low"]) - entry) / risk
            sl_hit = float(row["bid_low"]) <= stop
            tp_hit = float(row["bid_high"]) >= target
        else:
            fav = (entry - float(row["ask_low"])) / risk
            adv = (entry - float(row["ask_high"])) / risk
            sl_hit = float(row["ask_high"]) >= stop
            tp_hit = float(row["ask_low"]) <= target
        mfe_r = max(mfe_r, fav)
        mae_r = min(mae_r, adv)
        # OHLCV-1m has no intrabar ordering: conservative SL-first.
        if sl_hit:
            exit_time = ts
            exit_price = stop - cfg.slippage_points if side == "Long" else stop + cfg.slippage_points
            reason = "SL"
            break
        if tp_hit:
            exit_time = ts
            exit_price = target
            reason = "TP"
            break

    if exit_time is None:
        row = xx.iloc[-1]
        exit_time = xx.index[-1]
        exit_price = float(row["bid_close"] if side == "Long" else row["ask_close"])
        reason = "TIME"

    return {
        "entry_time": x.index[fill_i],
        "entry_price": float(entry),
        "entry_spread": float(spread),
        "news_ctx": news_ctx,
        "stop": stop,
        "target": float(target),
        "target_name": f"Fixed {rr:g}R",
        "planned_rr": rr,
        "exit_time": exit_time,
        "exit_price": float(exit_price),
        "exit_reason": reason,
        "mfe_r": float(mfe_r),
        "mae_r": float(mae_r),
    }


def _record_trade(bt_core, cfg, d: date, anchor: ClosureEvent, confirm: CISDEvent, entry_cisd: CISDEvent, result: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    rec = bt_core._make_model_trade_record(
        cfg,
        d,
        anchor.side,
        f"{anchor.kind} {anchor.side}",
        result,
        f"{spec['label']} · {anchor.kind}",
        liquidity_source=anchor.poi_type,
        liquidity_level=anchor.poi_level,
        sweep_time=anchor.candle_open_time,
        protected_swing=entry_cisd.protected_swing,
        meta={
            "ttfm_rule_version": PUBLIC_RULE_VERSION,
            "ttfm_anchor_tf": spec["anchor_tf"],
            "ttfm_confirm_tf": spec["confirm_tf"],
            "ttfm_entry_tf": spec["entry_tf"],
            "ttfm_anchor_kind": anchor.kind,
            "ttfm_anchor_variant": anchor.source_variant,
            "ttfm_anchor_close_time": anchor.close_time,
            "ttfm_anchor_poi_type": anchor.poi_type,
            "ttfm_anchor_poi_level": anchor.poi_level,
            "ttfm_range_eq": anchor.range_eq,
            "ttfm_confirm_cisd_time": confirm.confirm_time,
            "ttfm_confirm_cisd_ref": confirm.reference,
            "ttfm_confirm_protected_swing": confirm.protected_swing,
            "ttfm_confirm_poi_type": confirm.poi_type,
            "ttfm_entry_cisd_time": entry_cisd.confirm_time,
            "ttfm_entry_cisd_ref": entry_cisd.reference,
            "ttfm_entry_poi_type": entry_cisd.poi_type,
            "ttfm_entry_poi_level": entry_cisd.poi_level,
            "ttfm_cisd_reference_mode": "opposing_series_origin_open_public_proxy",
            "ttfm_entry_convention": "next_1m_open_after_closed_entry_tf_cisd",
            "ttfm_target_convention": "fixed_min_2R",
            "ttfm_early_cisd_used": False,
        },
    )
    rec["cisd_time"] = pd.Timestamp(entry_cisd.confirm_time)
    rec["cisd_ref"] = float(entry_cisd.reference)
    return rec


def _daily_profile_trade(
    bt_core,
    file_index,
    cache_root: Path,
    cfg,
    d: date,
    day: pd.DataFrame,
    history: pd.DataFrame,
    spec: dict[str, Any],
    news: pd.DataFrame,
) -> Optional[dict[str, Any]]:
    daily = _aggregate(history[history.index < day.index.min()], "1D", cfg.calendar_tz)
    if len(daily) < 3:
        return None
    anchor = latest_closure_event(daily, int(cfg.ote_pivot_left), int(cfg.ote_pivot_right))
    if not anchor:
        return None

    anchor_start = anchor.candle_open_time
    anchor_end = day.index.min()
    anchor.close_time = anchor_end
    confirm_all = _aggregate(history, spec["confirm_tf"], cfg.calendar_tz)
    confirm_segment = _filter_between(confirm_all, anchor_start, anchor_end)
    confirm = _find_cisd(
        confirm_segment,
        anchor.side,
        pivot_left=int(cfg.ote_pivot_left),
        pivot_right=int(cfg.ote_pivot_right),
        max_confirm_bars=max(6, int(cfg.cisd_max_bars) * 2),
        require_local_poi=False,
    )
    if not confirm:
        return None

    # Public playbook specifically warns about range EQ and gives bullish
    # confirmation in the upper half / bearish in the lower half.
    confirm_close_row = confirm_segment.loc[confirm.confirm_time]
    if isinstance(confirm_close_row, pd.DataFrame):
        confirm_close_row = confirm_close_row.iloc[-1]
    confirm_close = float(confirm_close_row["mid_close"])
    if anchor.side == "Long" and confirm_close < anchor.range_eq:
        return None
    if anchor.side == "Short" and confirm_close > anchor.range_eq:
        return None

    entry_bars = _aggregate(day, spec["entry_tf"], cfg.calendar_tz)
    entry_cisd = _find_cisd(
        entry_bars,
        anchor.side,
        pivot_left=int(cfg.ote_pivot_left),
        pivot_right=int(cfg.ote_pivot_right),
        max_confirm_bars=max(4, int(cfg.cisd_max_bars)),
        require_local_poi=True,
    )
    if not entry_cisd:
        return None

    ready = entry_cisd.confirm_time + _tf_delta(spec["entry_tf"])
    session_end = day.index.max() + pd.Timedelta(minutes=1)
    stop = entry_cisd.protected_swing
    if anchor.side == "Long":
        stop -= float(cfg.stop_buffer_points)
    else:
        stop += float(cfg.stop_buffer_points)
    result = _execute_market(bt_core, day, anchor.side, ready, stop, cfg, news, session_end)
    if not result:
        return None
    return _record_trade(bt_core, cfg, d, anchor, confirm, entry_cisd, result, spec)


def _scalp_profile_trade(
    bt_core,
    file_index,
    cache_root: Path,
    cfg,
    d: date,
    day: pd.DataFrame,
    history: pd.DataFrame,
    spec: dict[str, Any],
    news: pd.DataFrame,
) -> Optional[dict[str, Any]]:
    daily = _aggregate(history[history.index < day.index.min()], "1D", cfg.calendar_tz)
    daily_context = _daily_direction_context(daily)
    if not daily_context:
        return None

    h1 = _aggregate(history, "1H", cfg.calendar_tz)
    day_start = day.index.min()
    day_end = day.index.max() + pd.Timedelta(minutes=1)
    # Only H1 candles whose close is known during the current local day.
    for i in range(2, len(h1)):
        open_time = h1.index[i]
        close_time = open_time + pd.Timedelta(hours=1)
        if close_time <= day_start or close_time >= day_end:
            continue
        hist_to_i = h1.iloc[: i + 1]
        anchor = latest_closure_event(hist_to_i, int(cfg.ote_pivot_left), int(cfg.ote_pivot_right))
        if not anchor or anchor.side != daily_context:
            continue
        # H1 close is one hour after its open; do not infer duration from a
        # possible maintenance-gap spacing between neighboring bars.
        anchor.close_time = anchor.candle_open_time + pd.Timedelta(hours=1)

        m15 = _aggregate(history, "15m", cfg.calendar_tz)
        segment = _filter_between(m15, anchor.candle_open_time, anchor.close_time)
        confirm = _find_cisd(
            segment,
            anchor.side,
            pivot_left=int(cfg.ote_pivot_left),
            pivot_right=int(cfg.ote_pivot_right),
            max_confirm_bars=max(4, int(cfg.cisd_max_bars)),
            require_local_poi=False,
        )
        if not confirm:
            continue

        # Execute inside the next H1 expansion candle after the anchor closes.
        next_h1_end = min(day_end, anchor.close_time + pd.Timedelta(hours=1))
        m1_segment = _filter_between(day, anchor.close_time, next_h1_end)
        entry_cisd = _find_cisd(
            m1_segment,
            anchor.side,
            pivot_left=int(cfg.ote_pivot_left),
            pivot_right=int(cfg.ote_pivot_right),
            max_confirm_bars=max(4, int(cfg.cisd_max_bars)),
            require_local_poi=True,
        )
        if not entry_cisd:
            continue
        ready = entry_cisd.confirm_time + pd.Timedelta(minutes=1)
        stop = entry_cisd.protected_swing
        if anchor.side == "Long":
            stop -= float(cfg.stop_buffer_points)
        else:
            stop += float(cfg.stop_buffer_points)
        result = _execute_market(bt_core, day, anchor.side, ready, stop, cfg, news, day_end)
        if result:
            return _record_trade(bt_core, cfg, d, anchor, confirm, entry_cisd, result, spec)
    return None


def backtest(
    bt_core,
    file_index: dict[date, str],
    cache_root: Path,
    cfg,
    start_date: date,
    end_date: date,
    news_df: Optional[pd.DataFrame] = None,
    progress_cb=None,
) -> pd.DataFrame:
    spec = profile_spec(cfg.model_type)
    if not spec:
        return pd.DataFrame()

    news = bt_core._filter_news(news_df if news_df is not None else pd.DataFrame(), cfg)
    dates = pd.date_range(start_date, end_date, freq="D").date
    total = len(dates)
    trades: list[dict[str, Any]] = []

    for di, d in enumerate(dates, 1):
        if d.weekday() not in cfg.weekdays:
            if progress_cb:
                progress_cb(di, total, d, len(trades))
            continue
        day = _load_trading_day(bt_core, file_index, cache_root, cfg.market, d, cfg.calendar_tz)
        if day is None or day.empty:
            if progress_cb:
                progress_cb(di, total, d, len(trades))
            continue

        prev = _previous_trading_days(bt_core, file_index, cache_root, cfg.market, d, cfg.calendar_tz, 8)
        history = pd.concat([*prev, day]).sort_index() if prev else day.copy()

        if spec["mode"] == "daily_expansion":
            rec = _daily_profile_trade(bt_core, file_index, cache_root, cfg, d, day, history, spec, news)
        else:
            rec = _scalp_profile_trade(bt_core, file_index, cache_root, cfg, d, day, history, spec, news)
        if rec is not None:
            trades.append(rec)

        if progress_cb:
            progress_cb(di, total, d, len(trades))

    if not trades:
        return pd.DataFrame()
    return pd.DataFrame(trades).sort_values("entry_time").reset_index(drop=True)
