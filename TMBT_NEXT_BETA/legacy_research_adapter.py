from __future__ import annotations

import importlib
import math
import os
import sqlite3
import sys
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd

import historical_store
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

    # Add the true-futures presets beside the migrated legacy presets so every
    # original profile remains usable from the compatibility runtime.
    preset_dir = root / "presets"
    preset_dir.mkdir(parents=True, exist_ok=True)
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

    futures_presets = {}
    for market in ("NQ", "ES"):
        for tf, suffix in (("15m", "M15"), ("30m", "M30"), ("1H", "H1")):
            futures_presets[f"EBP_{suffix}_{market}_FUTURES.json"] = _ebp_preset(market, tf)
    import json
    for name, payload in futures_presets.items():
        p = preset_dir / name
        if not p.exists():
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

    # Replace the migrated permissive validation gate. A merely positive net
    # result is explicitly NOT enough to become a live-review candidate.
    research_autopilot._validation_verdict = strict_validation_verdict


    _MODULES = {
        "root": root,
        "studio_bridge": studio_bridge,
        "bt_core": bt_core,
        "research_jobs": research_jobs,
        "research_autopilot": research_autopilot,
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
