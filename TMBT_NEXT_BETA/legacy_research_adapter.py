from __future__ import annotations

import importlib
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
    futures_presets = {
        "EBP_H1_NQ_FUTURES.json": {
            "market": "NQ", "model_type": "EBP H1 Indices", "calendar_tz": "America/New_York",
            "signal_tf": "1H", "session_name": "EBP H1 NQ Futures · All Day NY",
            "session_start": "00:00", "session_end": "23:59", "session_tz": "America/New_York",
            "side_mode": "Both", "bias_mode": "Off", "sweep_min_points": 0.0,
            "target_mode": "Fixed RR", "target_rr": 2.0, "min_target_rr": 0.0,
            "max_trades_per_day": 0, "execution_mode": "Bar conservative", "news_mode": "Ignore",
            "ebp_close_mode": "Previous body", "ebp_opposite_color_required": False,
            "ebp_strong_close_pct": 15.0, "ebp_strong_entry_pct": 25.0, "ebp_strong_stop_pct": 75.0,
            "ebp_indecisive_entry_pct": 50.0, "ebp_market_close_pct": 50.0,
            "ebp_very_indecisive_mode": "Market", "ebp_entry_valid_bars": 4,
            "ebp_min_range_atr": 0.0, "ebp_move_be_after_extreme": True, "force_exit_at_session_end": True,
        },
        "EBP_H1_ES_FUTURES.json": {
            "market": "ES", "model_type": "EBP H1 Indices", "calendar_tz": "America/New_York",
            "signal_tf": "1H", "session_name": "EBP H1 ES Futures · All Day NY",
            "session_start": "00:00", "session_end": "23:59", "session_tz": "America/New_York",
            "side_mode": "Both", "bias_mode": "Off", "sweep_min_points": 0.0,
            "target_mode": "Fixed RR", "target_rr": 2.0, "min_target_rr": 0.0,
            "max_trades_per_day": 0, "execution_mode": "Bar conservative", "news_mode": "Ignore",
            "ebp_close_mode": "Previous body", "ebp_opposite_color_required": False,
            "ebp_strong_close_pct": 15.0, "ebp_strong_entry_pct": 25.0, "ebp_strong_stop_pct": 75.0,
            "ebp_indecisive_entry_pct": 50.0, "ebp_market_close_pct": 50.0,
            "ebp_very_indecisive_mode": "Market", "ebp_entry_valid_bars": 4,
            "ebp_min_range_atr": 0.0, "ebp_move_be_after_extreme": True, "force_exit_at_session_end": True,
        },
    }
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
    research_autopilot.PROFILES.update({
        "NQ_EBP_H1": {
            "label": "NQ Futures · EBP H1",
            "preset": "EBP_H1_NQ_FUTURES",
            "market": "NQ",
            "optimizers": [
                {"name": "Close strength × limit expiry", "param1": "ebp_strong_close_pct", "values1": [10.0, 15.0, 20.0], "param2": "ebp_entry_valid_bars", "values2": [2, 4, 6, 8]},
                {"name": "Strong entry × stop", "param1": "ebp_strong_entry_pct", "values1": [20.0, 25.0, 30.0], "param2": "ebp_strong_stop_pct", "values2": [70.0, 75.0, 80.0]},
                {"name": "Indecisive entry × target", "param1": "ebp_indecisive_entry_pct", "values1": [40.0, 50.0, 60.0], "param2": "target_rr", "values2": [1.5, 2.0, 2.5, 3.0]},
            ],
        },
        "ES_EBP_H1": {
            "label": "ES Futures · EBP H1",
            "preset": "EBP_H1_ES_FUTURES",
            "market": "ES",
            "optimizers": [
                {"name": "Close strength × limit expiry", "param1": "ebp_strong_close_pct", "values1": [10.0, 15.0, 20.0], "param2": "ebp_entry_valid_bars", "values2": [2, 4, 6, 8]},
                {"name": "Strong entry × stop", "param1": "ebp_strong_entry_pct", "values1": [20.0, 25.0, 30.0], "param2": "ebp_strong_stop_pct", "values2": [70.0, 75.0, 80.0]},
                {"name": "Indecisive entry × target", "param1": "ebp_indecisive_entry_pct", "values1": [40.0, 50.0, 60.0], "param2": "target_rr", "values2": [1.5, 2.0, 2.5, 3.0]},
            ],
        },
    })

    _MODULES = {
        "root": root,
        "studio_bridge": studio_bridge,
        "bt_core": bt_core,
        "research_jobs": research_jobs,
        "research_autopilot": research_autopilot,
    }
    _PATCHED = True
    return _MODULES
