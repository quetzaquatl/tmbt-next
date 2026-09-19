from __future__ import annotations

import importlib
import json
import zipfile
import math
import os
import sqlite3
import sys
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd

import historical_store
import ttfm_engine
import legacy_runtime

WORKSPACE = Path(os.environ.get("TMBT_WORKSPACE", r"D:\Projekt model\Trading_Model_Backtest_Studio_WORKSPACE")).resolve()
HERE = Path(__file__).resolve().parent

# These are explicit formalized legacy-model mappings to the true futures history.
# XAUUSD is deliberately NOT mapped to GC: spot gold and GC are not the same instrument.
FUTURES_MARKETS = {
    "NQ": "NQ",
    "ES": "ES",
    "GC": "GC",
}

_PATCHED = False
_MODULES: dict[str, Any] = {}


STRICT_REQUIREMENTS = {
    "development_expectancy_min_r": 0.10,
    "development_profit_factor_min": 1.20,
    "validation_expectancy_min_r": 0.08,
    "validation_profit_factor_min": 1.20,
    "validation_net_r_min": 10.0,
    "expectancy_retention_min": 0.50,
    "validation_recovery_factor_min": 1.50,
    "validation_max_drawdown_r": 25.0,
}


def _finite(value: Any, default: float = 0.0) -> float:
    try:
        x = float(value)
        return x if math.isfinite(x) else default
    except Exception:
        return default


def strict_validation_verdict(dev: dict[str, Any], val: dict[str, Any], min_val_trades: int) -> dict[str, Any]:
    req = dict(STRICT_REQUIREMENTS)
    d_exp = _finite(dev.get("expectancy_r"))
    d_pf = _finite(dev.get("profit_factor_r"))
    v_exp = _finite(val.get("expectancy_r"))
    v_pf = _finite(val.get("profit_factor_r"))
    v_net = _finite(val.get("net_r"))
    v_dd = max(0.0, _finite(val.get("max_drawdown_r")))
    v_trades = int(val.get("trades") or 0)
    retention = (v_exp / d_exp) if d_exp > 0 else None
    recovery = (v_net / v_dd) if v_dd > 0 else (float("inf") if v_net > 0 else 0.0)
    gates = {
        "development_expectancy_ge_0_10R": d_exp >= req["development_expectancy_min_r"],
        "development_profit_factor_ge_1_20": d_pf >= req["development_profit_factor_min"],
        "validation_expectancy_ge_0_08R": v_exp >= req["validation_expectancy_min_r"],
        "validation_profit_factor_ge_1_20": v_pf >= req["validation_profit_factor_min"],
        "validation_min_trades": v_trades >= int(min_val_trades),
        "validation_net_r_ge_10": v_net >= req["validation_net_r_min"],
        "expectancy_retention_ge_50pct": bool(retention is not None and retention >= req["expectancy_retention_min"]),
        "validation_recovery_factor_ge_1_50": recovery >= req["validation_recovery_factor_min"],
        "validation_max_drawdown_le_25R": v_dd <= req["validation_max_drawdown_r"],
    }
    passed = sum(bool(x) for x in gates.values())
    all_pass = passed == len(gates)
    core = (
        v_exp > 0
        and v_pf > 1.0
        and v_trades >= int(min_val_trades)
        and v_net > 0
    )
    verdict = "PASS" if all_pass else ("WEAK" if core else "FAIL")
    return {
        "verdict": verdict,
        "gates": gates,
        "requirements": req,
        "min_val_trades": int(min_val_trades),
        "expectancy_retention": retention,
        "validation_recovery_factor": recovery,
        "passed_gates": passed,
        "total_gates": len(gates),
        "gate_version": "strict-live-v2",
    }


def _db_ready() -> bool:
    return historical_store.db_path(WORKSPACE).exists()


def _available_dates(root: str) -> list[date]:
    return historical_store.available_dates(root, workspace=WORKSPACE)


def _databento_index(market: str) -> dict[date, str]:
    root = FUTURES_MARKETS.get(str(market).upper())
    if not root or not _db_ready():
        return {}
    p = str(historical_store.db_path(WORKSPACE))
    return {d: p for d in _available_dates(root)}


def _to_legacy_frame(root: str, utc_date: date) -> pd.DataFrame:
    rows = historical_store.load_utc_day_1m(root, utc_date, workspace=WORKSPACE)
    if not rows:
        return pd.DataFrame()
    x = pd.DataFrame(rows)
    idx = pd.to_datetime(x["t"], unit="ms", utc=True)
    out = pd.DataFrame(index=idx)
    out.index.name = "dt"
    for pfx in ("mid", "bid", "ask"):
        out[f"{pfx}_open"] = x["o"].astype(float).to_numpy()
        out[f"{pfx}_high"] = x["h"].astype(float).to_numpy()
        out[f"{pfx}_low"] = x["l"].astype(float).to_numpy()
        out[f"{pfx}_close"] = x["c"].astype(float).to_numpy()
    volume = pd.to_numeric(x.get("v", 0.0), errors="coerce").fillna(0.0).astype(float).to_numpy()
    out["tick_count"] = 1
    out["ask_volume"] = volume
    out["bid_volume"] = volume
    out["spread_median"] = 0.0
    out["spread_close"] = 0.0
    return out.sort_index()


def activate() -> dict[str, Any]:
    global _PATCHED, _MODULES
    if _PATCHED:
        return _MODULES

    root = legacy_runtime.activate()

    # Ensure imports come from the extracted compatibility runtime, not from a
    # retired old Studio path.
    for name in ("research_autopilot", "research_jobs", "studio_bridge", "bt_core"):
        mod = sys.modules.get(name)
        if mod is not None:
            f = str(getattr(mod, "__file__", ""))
            if f and str(root) not in f:
                sys.modules.pop(name, None)

    studio_bridge = importlib.import_module("studio_bridge")
    bt_core = importlib.import_module("bt_core")

    original_load_file_index = studio_bridge.load_file_index
    original_load_cached = bt_core._load_cached_utc_date

    def backtest_ebp_multitimeframe(file_index, cache_root: Path, cfg, start_date: date, end_date: date, news_df=None, progress_cb=None):
        """Run the already-formalized EBP model on 15m, 30m, or 1H bars.

        Signal logic is unchanged. The only intentional extension is timeframe:
        signal confirmation, previous-bar liquidity, and entry-valid duration are
        expressed in the selected signal timeframe.
        """
        tf = str(cfg.signal_tf)
        tf_minutes = int(bt_core.TF_MINUTES.get(tf, 0) or 0)
        if tf not in {"15m", "30m", "1H"} or tf_minutes <= 0:
            return pd.DataFrame()
        news = bt_core._filter_news(news_df if news_df is not None else pd.DataFrame(), cfg)
        trades = []
        dates = pd.date_range(start_date, end_date, freq="D").date
        total = len(dates)

        for di, d in enumerate(dates, 1):
            if d.weekday() not in cfg.weekdays:
                if progress_cb:
                    progress_cb(di, total, d, len(trades))
                continue
            day = bt_core.load_local_day_1m(file_index, cache_root, cfg.market, d, cfg.calendar_tz)
            if day.empty:
                if progress_cb:
                    progress_cb(di, total, d, len(trades))
                continue
            _prev_d, prev = bt_core._find_prev_nonempty_day(file_index, cache_root, cfg.market, d, cfg.calendar_tz)
            warm_bars = max(180, int(180 * 60 / tf_minutes))
            warm = pd.concat([prev.tail(warm_bars) if not prev.empty else prev, day]).sort_index()
            sig = bt_core._apply_indicators(bt_core._aggregate_1m(warm, tf, cfg.calendar_tz), cfg)
            if len(sig) < 2:
                if progress_cb:
                    progress_cb(di, total, d, len(trades))
                continue

            sess_start, sess_end = bt_core._session_bounds(d, cfg.session_start, cfg.session_end, cfg.session_tz)
            candidates = []
            for i in range(1, len(sig)):
                signal_open = sig.index[i]
                signal_close = signal_open + pd.Timedelta(minutes=tf_minutes)
                if not (sess_start <= signal_close < sess_end):
                    continue
                setup = bt_core._ebp_signal_from_pair(sig.iloc[i - 1], sig.iloc[i], cfg)
                if not setup:
                    continue
                if cfg.side_mode == "Long only" and setup["side"] != "Long":
                    continue
                if cfg.side_mode == "Short only" and setup["side"] != "Short":
                    continue
                setup.update({"signal_i": i, "signal_open_time": signal_open, "signal_close_time": signal_close})
                candidates.append(setup)

            count = 0
            last_exit = pd.Timestamp.min.tz_localize("UTC")
            for setup in candidates:
                if cfg.max_trades_per_day > 0 and count >= cfg.max_trades_per_day:
                    break
                ready = pd.Timestamp(setup["signal_close_time"])
                if ready <= last_exit or ready >= sess_end:
                    continue
                expiry = min(
                    sess_end,
                    ready + pd.Timedelta(minutes=tf_minutes * max(1, int(cfg.ebp_entry_valid_bars))),
                )
                result = bt_core._ebp_execute(file_index, day, ready, expiry, sess_end, setup, cfg, news)
                if not result or pd.Timestamp(result["entry_time"]) <= last_exit:
                    continue
                tf_label = tf.upper()
                rec = bt_core._make_model_trade_record(
                    cfg,
                    d,
                    setup["side"],
                    "EBP",
                    result,
                    f"{tf_label} EBP · {setup['variant']}",
                    liquidity_source=f"Previous {tf_label} Low" if setup["side"] == "Long" else f"Previous {tf_label} High",
                    liquidity_level=setup["swept_level"],
                    sweep_time=setup["signal_open_time"],
                    protected_swing=setup["stop"],
                    meta={
                        "ebp_variant": setup["variant"],
                        "ebp_order_type": setup["order_type"],
                        "ebp_signal_tf": tf,
                        "ebp_signal_time": setup["signal_close_time"],
                        "ebp_close_retrace_pct": setup["close_retrace_pct"],
                        "ebp_prev_open": setup["prev_open"],
                        "ebp_prev_high": setup["prev_high"],
                        "ebp_prev_low": setup["prev_low"],
                        "ebp_prev_close": setup["prev_close"],
                        "ebp_signal_open": setup["signal_open"],
                        "ebp_signal_high": setup["signal_high"],
                        "ebp_signal_low": setup["signal_low"],
                        "ebp_signal_close": setup["signal_close"],
                        "ebp_fib15": setup["fib15"],
                        "ebp_fib25": setup["fib25"],
                        "ebp_fib50": setup["fib50"],
                        "ebp_fib75": setup["fib75"],
                        "ebp_be_trigger": setup["be_trigger"],
                        "ebp_be_enabled": bool(cfg.ebp_move_be_after_extreme),
                        "ebp_be_time": result.get("be_time"),
                        "ebp_range_atr": (
                            setup["range"] / setup["atr"]
                            if setup.get("atr")
                            and not bt_core.np.isnan(setup["atr"])
                            and setup["atr"] > 0
                            else bt_core.np.nan
                        ),
                    },
                )
                trades.append(rec)
                last_exit = pd.Timestamp(result["exit_time"])
                count += 1
            if progress_cb:
                progress_cb(di, total, d, len(trades))
        return pd.DataFrame(trades).sort_values("entry_time").reset_index(drop=True) if trades else pd.DataFrame()

    bt_core._backtest_ebp_h1_indices = backtest_ebp_multitimeframe

    original_backtest = bt_core.backtest

    def backtest_dispatch(file_index, cache_root: Path, cfg, start_date: date, end_date: date, news_df=None, progress_cb=None):
        if ttfm_engine.profile_spec(str(cfg.model_type)):
            return ttfm_engine.backtest(
                bt_core,
                file_index,
                cache_root,
                cfg,
                start_date,
                end_date,
                news_df,
                progress_cb,
            )
        return original_backtest(
            file_index,
            cache_root,
            cfg,
            start_date,
            end_date,
            news_df,
            progress_cb,
        )

    bt_core.backtest = backtest_dispatch

    def load_file_index(workspace: Path, market: str, validate_exists: bool = True):
        idx = _databento_index(market)
        if idx:
            return idx
        return original_load_file_index(workspace, market, validate_exists)

    def load_cached_utc_date(file_index, cache_root: Path, market: str, d: date):
        root_symbol = FUTURES_MARKETS.get(str(market).upper())
        if root_symbol and _db_ready():
            return _to_legacy_frame(root_symbol, d)
        return original_load_cached(file_index, cache_root, market, d)

    studio_bridge.load_file_index = load_file_index
    bt_core._load_cached_utc_date = load_cached_utc_date

    research_jobs = importlib.import_module("research_jobs")
    original_load_config = research_jobs._load_config

    def load_config(app_dir: Path, workspace: Path, request: dict[str, Any]):
        cfg = original_load_config(app_dir, workspace, request)
        # Databento purchase is OHLCV-1m, not tick/quote data. Keep the old
        # conservative bar simulator, but never pretend this source is tick exact.
        if str(cfg.market).upper() in FUTURES_MARKETS and cfg.execution_mode == "Tick exact":
            cfg.execution_mode = "Bar conservative"
        return cfg

    research_jobs._load_config = load_config

    research_autopilot = importlib.import_module("research_autopilot")

    def full_history_splits(file_index):
        """Use the complete available market history without hard-coded calendar years.

        70% development / 15% locked validation / 15% untouched holdout, split
        by actual available trading dates. This keeps point-in-time research
        discipline while allowing old history (e.g. 2010+) to participate.
        """
        if not file_index:
            raise ValueError("no_market_data")
        dates = sorted(file_index)
        n = len(dates)
        if n < 60:
            raise ValueError("not_enough_days_for_autopilot")
        i70 = max(1, min(n - 2, int(n * 0.70)))
        i85 = max(i70 + 1, min(n - 1, int(n * 0.85)))
        return {
            "full_start": dates[0].isoformat(),
            "full_end": dates[-1].isoformat(),
            "development_start": dates[0].isoformat(),
            "development_end": dates[i70 - 1].isoformat(),
            "validation_start": dates[i70].isoformat(),
            "validation_end": dates[i85 - 1].isoformat(),
            "holdout_start": dates[i85].isoformat() if i85 < n else None,
            "holdout_end": dates[-1].isoformat() if i85 < n else None,
            "split_mode": "full-history-70-15-15-v1",
        }

    research_autopilot._default_splits = full_history_splits

    # Add the true-futures presets beside the migrated legacy presets so every
    # original profile remains usable from the compatibility runtime.
    preset_dir = root / "presets"
    preset_dir.mkdir(parents=True, exist_ok=True)

    def _builtin_runtime_preset(stem: str) -> dict[str, Any]:
        # Audited baseline presets from the migrated Old Studio source bundle.
        # Used only if both extracted runtime and local migration zip lack them.
        common_ifvg = {
            "side_mode": "Both",
            "bias_mode": "Off",
            "sweep_min_points": 0.0,
            "ifvg_inversion_max_bars": 12,
            "ifvg_min_points": 0.0,
            "ifvg_entry_depth_pct": 50.0,
            "ifvg_displacement_atr_mult": 0.0,
            "ifvg_require_sweep_reclaim": False,
            "stop_buffer_points": 0.0,
            "min_target_rr": 1.0,
            "max_trades_per_day": 1,
            "execution_mode": "Tick exact",
            "news_mode": "Ignore",
        }
        presets = {
            "OTE_BOS_XAU_15m_AUDIT": {
                "market": "XAUUSD",
                "model_type": "OTE Pure",
                "calendar_tz": "Europe/Berlin",
                "signal_tf": "15m",
                "session_name": "OTE BOS XAU ALL DAY",
                "session_start": "00:00",
                "session_end": "23:59",
                "session_tz": "Europe/Berlin",
                "side_mode": "Both",
                "bias_mode": "Off",
                "ote_pivot_left": 2,
                "ote_pivot_right": 2,
                "ote_swing_mode": "BOS-confirmed impulse",
                "ote_stop_anchor": "Executable side",
                "ote_min_impulse_atr": 1.0,
                "ote_entry_pct": 70.5,
                "ote_zone_min_pct": 62.0,
                "ote_zone_max_pct": 79.0,
                "ote_retest_max_bars": 24,
                "ote_target_mode": "Swing extreme",
                "stop_buffer_points": 0.0,
                "min_target_rr": 1.0,
                "max_trades_per_day": 0,
                "execution_mode": "Tick exact",
                "news_mode": "Ignore",
            },
            "XAU_LONDON_SWEEP_iFVG_15_17": {
                **common_ifvg,
                "market": "XAUUSD",
                "model_type": "XAU Range Sweep iFVG",
                "calendar_tz": "Europe/Berlin",
                "signal_tf": "5m",
                "session_name": "XAU London Sweep iFVG 15-17 DE",
                "session_start": "15:00",
                "session_end": "17:00",
                "session_tz": "Europe/Berlin",
                "reference_name": "London 08-11",
                "reference_start": "08:00",
                "reference_end": "11:00",
                "reference_tz": "Europe/Berlin",
                "ifvg_lookback_bars": 18,
                "ifvg_retest_max_bars": 12,
            },
            "SILVER_BULLET_USA500_iFVG": {
                **common_ifvg,
                "market": "USA500IDXUSD",
                "model_type": "Silver Bullet iFVG",
                "calendar_tz": "America/New_York",
                "signal_tf": "1m",
                "session_name": "AM Silver Bullet iFVG 10-11 NY",
                "session_start": "10:00",
                "session_end": "11:00",
                "session_tz": "America/New_York",
                "reference_name": "9AM Range",
                "reference_start": "09:00",
                "reference_end": "10:00",
                "reference_tz": "America/New_York",
                "ifvg_lookback_bars": 20,
                "ifvg_retest_max_bars": 20,
            },
            "SILVER_BULLET_USATECH_iFVG": {
                **common_ifvg,
                "market": "USATECHIDXUSD",
                "model_type": "Silver Bullet iFVG",
                "calendar_tz": "America/New_York",
                "signal_tf": "1m",
                "session_name": "AM Silver Bullet iFVG 10-11 NY",
                "session_start": "10:00",
                "session_end": "11:00",
                "session_tz": "America/New_York",
                "reference_name": "9AM Range",
                "reference_start": "09:00",
                "reference_end": "10:00",
                "reference_tz": "America/New_York",
                "ifvg_lookback_bars": 20,
                "ifvg_retest_max_bars": 20,
            },
        }
        return dict(presets.get(stem) or {})

    def _read_runtime_preset(stem: str) -> dict[str, Any]:
        p = preset_dir / f"{stem}.json"
        try:
            x = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(x, dict):
                return dict(x)
        except Exception:
            pass

        # Self-heal from the immutable migration bundle if an extracted preset
        # is missing/corrupt. This keeps the compatibility runtime reproducible
        # and avoids requiring the retired Old Studio directory.
        try:
            bundle = legacy_runtime.bundle_path()
            member = f"presets/{stem}.json"
            if bundle.exists():
                with zipfile.ZipFile(bundle, "r") as zf:
                    raw = zf.read(member).decode("utf-8")
                x = json.loads(raw)
                if isinstance(x, dict):
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_text(json.dumps(x, ensure_ascii=False, indent=2), encoding="utf-8")
                    return dict(x)
        except Exception:
            pass
        fallback = _builtin_runtime_preset(stem)
        if fallback:
            try:
                p.write_text(json.dumps(fallback, ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception:
                pass
        return fallback

    def _clone_preset(stem: str, *, market: str, tf: str, name: str | None = None) -> dict[str, Any]:
        payload = _read_runtime_preset(stem)
        if not payload:
            raise RuntimeError(f"missing runtime preset: {stem}")
        payload["market"] = market
        payload["signal_tf"] = tf
        payload["execution_mode"] = "Bar conservative"
        payload["news_mode"] = "Ignore"
        if market in FUTURES_MARKETS:
            payload["calendar_tz"] = "America/New_York"
        if name:
            payload["session_name"] = name
        return payload
    def _ebp_preset(market: str, tf: str) -> dict[str, Any]:
        label = tf.upper()
        return {
            "market": market,
            "model_type": "EBP H1 Indices",
            "calendar_tz": "America/New_York",
            "signal_tf": tf,
            "session_name": f"EBP {label} {market} Futures · All Day NY",
            "session_start": "00:00",
            "session_end": "23:59",
            "session_tz": "America/New_York",
            "side_mode": "Both",
            "bias_mode": "Off",
            "sweep_min_points": 0.0,
            "target_mode": "Fixed RR",
            "target_rr": 2.0,
            "min_target_rr": 0.0,
            "max_trades_per_day": 0,
            "execution_mode": "Bar conservative",
            "news_mode": "Ignore",
            "ebp_close_mode": "Previous body",
            "ebp_opposite_color_required": False,
            "ebp_strong_close_pct": 15.0,
            "ebp_strong_entry_pct": 25.0,
            "ebp_strong_stop_pct": 75.0,
            "ebp_indecisive_entry_pct": 50.0,
            "ebp_market_close_pct": 50.0,
            "ebp_very_indecisive_mode": "Market",
            "ebp_entry_valid_bars": 4,
            "ebp_min_range_atr": 0.0,
            "ebp_move_be_after_extreme": True,
            "force_exit_at_session_end": True,
        }

    def _ttfm_preset(market: str, model_type: str, entry_tf: str) -> dict[str, Any]:
        return {
            "market": market,
            "model_type": model_type,
            "calendar_tz": "America/New_York",
            "signal_tf": entry_tf,
            "session_name": f"{model_type} · {market} Futures · All Day NY",
            "session_start": "00:00",
            "session_end": "23:59",
            "session_tz": "America/New_York",
            "side_mode": "Both",
            "bias_mode": "Off",
            "target_mode": "Fixed RR",
            "target_rr": 2.0,
            "min_target_rr": 2.0,
            "max_trades_per_day": 1,
            "execution_mode": "Bar conservative",
            "news_mode": "Ignore",
            "cisd_lookback": 8,
            "cisd_max_bars": 6,
            "ote_pivot_left": 2,
            "ote_pivot_right": 2,
            "stop_buffer_points": 0.0,
            "force_exit_at_session_end": True,
        }

    futures_presets = {}
    for market in ("NQ", "ES"):
        for tf, suffix in (("15m", "M15"), ("30m", "M30"), ("1H", "H1")):
            futures_presets[f"EBP_{suffix}_{market}_FUTURES.json"] = _ebp_preset(market, tf)

    ttfm_preset_specs = (
        ("D1_H1_M5", "TTFM D1-H1-M5", "5m"),
        ("D1_H4_M15", "TTFM D1-H4-M15", "15m"),
        ("H1_M15_M1", "TTFM H1-M15-M1", "1m"),
    )
    for market in ("NQ", "ES", "GC"):
        for suffix, model_type, entry_tf in ttfm_preset_specs:
            futures_presets[f"TTFM_{suffix}_{market}_FUTURES.json"] = _ttfm_preset(
                market, model_type, entry_tf
            )

    # Full research matrix for the currently formalized non-TTFM models.
    # "All timeframes" means every timeframe that is technically meaningful for
    # that model engine. Session-bound iFVG models stop at 1H because a 4H candle
    # cannot be resolved inside the 1-2h execution window without changing the model.
    ote_tf_specs = (("5m", "M5"), ("15m", "M15"), ("30m", "M30"), ("1H", "H1"), ("4H", "H4"))
    ifvg_tf_specs = (("1m", "M1"), ("3m", "M3"), ("5m", "M5"), ("15m", "M15"), ("30m", "M30"), ("1H", "H1"))

    for market, tag in (("XAUUSD", "XAU"), ("GC", "GC")):
        for tf, suffix in ote_tf_specs:
            futures_presets[f"OTE_BOS_{tag}_{suffix}.json"] = _clone_preset(
                "OTE_BOS_XAU_15m_AUDIT",
                market=market,
                tf=tf,
                name=f"OTE BOS {tag} {suffix} · All Day",
            )
        for tf, suffix in ifvg_tf_specs:
            futures_presets[f"LONDON_SWEEP_IFVG_{tag}_{suffix}.json"] = _clone_preset(
                "XAU_LONDON_SWEEP_iFVG_15_17",
                market=market,
                tf=tf,
                name=f"{tag} London Sweep iFVG {suffix}",
            )

    for market, source_stem in (("NQ", "SILVER_BULLET_USATECH_iFVG"), ("ES", "SILVER_BULLET_USA500_iFVG")):
        for tf, suffix in ifvg_tf_specs:
            futures_presets[f"SILVER_BULLET_{market}_{suffix}.json"] = _clone_preset(
                source_stem,
                market=market,
                tf=tf,
                name=f"{market} Silver Bullet iFVG {suffix} · 10-11 NY",
            )

    for name, payload in futures_presets.items():
        p = preset_dir / name
        p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    research_autopilot.APP_DIR = root
    research_autopilot.WORKSPACE = WORKSPACE
    research_autopilot.ROOT = WORKSPACE / "research_autopilot"
    research_autopilot.STATUS_PATH = research_autopilot.ROOT / "status.json"
    research_autopilot.REQUEST_PATH = research_autopilot.ROOT / "request.json"
    research_autopilot.REPORT_PATH = research_autopilot.ROOT / "latest_report.json"
    research_autopilot.LOG_PATH = research_autopilot.ROOT / "autopilot.log"
    research_autopilot.CANCEL_PATH = research_autopilot.ROOT / "cancel.requested"

    # Native futures versions of the old, already-formalized EBP model.
    # This ports an existing formal model to actual NQ/ES history; it does not
    # turn discretionary Trader Observations into criteria.
    ebp_optimizers = [
        {"name": "Close strength × limit expiry", "param1": "ebp_strong_close_pct", "values1": [10.0, 15.0, 20.0], "param2": "ebp_entry_valid_bars", "values2": [2, 4, 6, 8]},
        {"name": "Strong entry × stop", "param1": "ebp_strong_entry_pct", "values1": [20.0, 25.0, 30.0], "param2": "ebp_strong_stop_pct", "values2": [70.0, 75.0, 80.0]},
        {"name": "Indecisive entry × target", "param1": "ebp_indecisive_entry_pct", "values1": [40.0, 50.0, 60.0], "param2": "target_rr", "values2": [1.5, 2.0, 2.5, 3.0]},
    ]
    for market in ("NQ", "ES"):
        for tf, suffix in (("15m", "M15"), ("30m", "M30"), ("1H", "H1")):
            research_autopilot.PROFILES[f"{market}_EBP_{suffix}"] = {
                "label": f"{market} Futures · EBP {suffix}",
                "preset": f"EBP_{suffix}_{market}_FUTURES",
                "market": market,
                "optimizers": [dict(x) for x in ebp_optimizers],
            }

    # Full timeframe research for the currently formalized OTE / iFVG models.
    ote_optimizers = [
        {
            "name": "OTE depth × impulse",
            "param1": "ote_entry_pct",
            "values1": [62.0, 66.0, 70.5, 75.0, 79.0],
            "param2": "ote_min_impulse_atr",
            "values2": [0.75, 1.0, 1.25, 1.5],
        },
        {
            "name": "Pivot confirmation",
            "param1": "ote_pivot_left",
            "values1": [1, 2, 3, 4],
            "param2": "ote_pivot_right",
            "values2": [1, 2, 3, 4],
        },
    ]
    ifvg_optimizers = [
        {
            "name": "iFVG depth × lookback",
            "param1": "ifvg_entry_depth_pct",
            "values1": [25.0, 50.0, 75.0],
            "param2": "ifvg_lookback_bars",
            "values2": [12, 18, 24, 36],
        },
        {
            "name": "Inversion × retest window",
            "param1": "ifvg_inversion_max_bars",
            "values1": [6, 12, 18],
            "param2": "ifvg_retest_max_bars",
            "values2": [6, 12, 18, 24],
        },
    ]

    ote_tf_specs = (("5m", "M5"), ("15m", "M15"), ("30m", "M30"), ("1H", "H1"), ("4H", "H4"))
    ifvg_tf_specs = (("1m", "M1"), ("3m", "M3"), ("5m", "M5"), ("15m", "M15"), ("30m", "M30"), ("1H", "H1"))

    for market, tag, market_label in (
        ("XAUUSD", "XAU", "XAU Spot"),
        ("GC", "GC", "Gold Futures (GC)"),
    ):
        for _tf, suffix in ote_tf_specs:
            research_autopilot.PROFILES[f"{tag}_OTE_BOS_{suffix}"] = {
                "label": f"{market_label} · OTE BOS {suffix}",
                "preset": f"OTE_BOS_{tag}_{suffix}",
                "market": market,
                "optimizers": [dict(x) for x in ote_optimizers],
            }
        for _tf, suffix in ifvg_tf_specs:
            research_autopilot.PROFILES[f"{tag}_SWEEP_IFVG_{suffix}"] = {
                "label": f"{market_label} · London Sweep iFVG {suffix}",
                "preset": f"LONDON_SWEEP_IFVG_{tag}_{suffix}",
                "market": market,
                "optimizers": [dict(x) for x in ifvg_optimizers],
            }

    for market in ("NQ", "ES"):
        for _tf, suffix in ifvg_tf_specs:
            research_autopilot.PROFILES[f"{market}_SILVER_BULLET_{suffix}"] = {
                "label": f"{market} Futures · Silver Bullet iFVG {suffix}",
                "preset": f"SILVER_BULLET_{market}_{suffix}",
                "market": market,
                "optimizers": [dict(x) for x in ifvg_optimizers],
            }

    # TTFM public-core research. We only optimize the explicit TMBT
    # implementation conventions, not undocumented/private indicator rules.
    ttfm_optimizers = [
        {
            "name": "Protected-swing pivot confirmation",
            "param1": "ote_pivot_left",
            "values1": [1, 2, 3],
            "param2": "ote_pivot_right",
            "values2": [1, 2, 3],
        },
        {
            "name": "CISD confirmation window × target",
            "param1": "cisd_max_bars",
            "values1": [4, 6, 8, 12],
            "param2": "target_rr",
            "values2": [2.0, 2.5, 3.0],
        },
    ]
    ttfm_profiles = (
        ("D1_H1_M5", "D1 → H1 → M5"),
        ("D1_H4_M15", "D1 → H4 → M15"),
        ("H1_M15_M1", "H1 → M15 → M1 Scalping"),
    )
    for market in ("NQ", "ES", "GC"):
        market_label = "Gold Futures (GC)" if market == "GC" else f"{market} Futures"
        for suffix, label in ttfm_profiles:
            research_autopilot.PROFILES[f"{market}_TTFM_{suffix}"] = {
                "label": f"{market_label} · TTFM {label}",
                "preset": f"TTFM_{suffix}_{market}_FUTURES",
                "market": market,
                "optimizers": [dict(x) for x in ttfm_optimizers],
            }

    # Replace the migrated permissive validation gate. A merely positive net
    # result is explicitly NOT enough to become a live-review candidate.
    research_autopilot._validation_verdict = strict_validation_verdict

    original_autopilot_run = research_autopilot.run

    def run_with_full_history_audit(request: dict[str, Any]):
        report = original_autopilot_run(request)
        try:
            profile_id = str(report.get("profile") or request.get("profile") or "")
            profile = research_autopilot.PROFILES.get(profile_id) or {}
            splits = report.get("splits") or {}
            full_start = str(
                splits.get("full_start")
                or splits.get("development_start")
                or ""
            )
            full_end = str(
                splits.get("full_end")
                or splits.get("holdout_end")
                or splits.get("validation_end")
                or ""
            )
            if profile and full_start and full_end:
                research_autopilot._status(
                    state="RUNNING",
                    profile=profile_id,
                    stage="full_history_audit",
                    message="Full-history diagnostic · locked parameters",
                )
                locked = dict(report.get("selected_overrides") or {})
                locked["execution_mode"] = "Bar conservative"
                audit = research_autopilot._run_backtest(
                    profile,
                    full_start,
                    full_end,
                    "Full History Diagnostic",
                    locked,
                    "Autopilot: full-history diagnostic (reporting only)",
                )
                summary = audit.get("summary") or {}
                research_autopilot._record_stage(
                    report,
                    "full_history_diagnostic",
                    {
                        "job_id": audit.get("job_id"),
                        "run_id": audit.get("run_id"),
                        "summary": summary,
                        "overrides": locked,
                        "start": full_start,
                        "end": full_end,
                        "reporting_only": True,
                        "used_for_optimizer": False,
                        "used_for_live_gate": False,
                    },
                )
                report["full_history_summary"] = summary
                report["full_history_diagnostic"] = {
                    "start": full_start,
                    "end": full_end,
                    "reporting_only": True,
                    "used_for_optimizer": False,
                    "used_for_live_gate": False,
                }
                report["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
                research_autopilot.REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
                tmp = research_autopilot.REPORT_PATH.with_suffix(".tmp")
                tmp.write_text(
                    json.dumps(report, ensure_ascii=False, indent=2, default=str),
                    encoding="utf-8",
                )
                os.replace(tmp, research_autopilot.REPORT_PATH)
        except Exception as exc:
            report["full_history_audit_error"] = f"{type(exc).__name__}: {exc}"
        return report

    research_autopilot.run = run_with_full_history_audit


    _MODULES = {
        "root": root,
        "studio_bridge": studio_bridge,
        "bt_core": bt_core,
        "research_jobs": research_jobs,
        "research_autopilot": research_autopilot,
        "ttfm_engine": ttfm_engine,
    }
    _PATCHED = True
    return _MODULES


def news_status() -> dict[str, Any]:
    """Describe the historical news dataset actually used by backtests."""
    try:
        mods = activate()
        studio_bridge = mods["studio_bridge"]
        bt_core = mods["bt_core"]
        settings = studio_bridge.load_settings(WORKSPACE)
        raw = str(settings.get("news_path") or "").strip()
        if not raw:
            return {
                "configured": False,
                "ready": False,
                "path": "",
                "rows": 0,
                "reason": "news_path_not_configured",
            }
        path = Path(raw).expanduser()
        if path.is_dir():
            candidate = path / "forex_factory_usd_high_impact.csv"
            if candidate.exists():
                path = candidate
        frame = bt_core.load_news(path)
        if frame is None or frame.empty:
            return {
                "configured": True,
                "ready": False,
                "path": str(path),
                "exists": path.exists(),
                "rows": 0,
                "reason": "news_file_missing_or_invalid",
            }
        dt = frame.get("datetime_utc")
        first = str(dt.min()) if dt is not None else None
        last = str(dt.max()) if dt is not None else None
        return {
            "configured": True,
            "ready": True,
            "path": str(path),
            "exists": path.exists(),
            "rows": int(len(frame)),
            "first_utc": first,
            "last_utc": last,
            "reason": "",
        }
    except Exception as exc:
        return {
            "configured": False,
            "ready": False,
            "path": "",
            "rows": 0,
            "reason": f"{type(exc).__name__}: {exc}",
        }
