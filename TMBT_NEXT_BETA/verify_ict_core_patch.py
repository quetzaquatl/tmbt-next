from __future__ import annotations

import py_compile
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
NY = ZoneInfo("America/New_York")

# Syntax smoke test for the source-audit integration.
for name in (
    "ict_core_rules.py",
    "ict_rule_engine.py",
    "legacy_research_adapter.py",
    "research_scheduler.py",
    "context_factors.py",
    "backtest_context_adapter.py",
    "historical_store.py",
    "databento_history_import.py",
):
    py_compile.compile(str(HERE / name), doraise=True)

from ict_core_rules import profile_provenance
from ict_rule_engine import normalize_closed_bars, fair_value_gaps, confirmed_swings, liquidity_raids, profile_pipeline_contract, snapshot
from context_factors import DEFAULT_CONFIG, _session_context

ote = profile_provenance("XAU_OTE_BOS_M15")
assert ote["source_status"] == "MIXED"
assert "ICT_CORE_OTE_ZONE" in ote["core_rules"]
assert "TMBT_BOS_BOOLEAN" in ote["non_core_assumptions"]

ifvg = profile_provenance("XAU_SWEEP_IFVG_H1")
assert ifvg["evidence_class"] == "D"
assert "ICT_CORE_FVG_3_CANDLE" in ifvg["core_rules"]
assert "IFVG_FIXED_BAR_EXPIRY" in ifvg["non_core_assumptions"]

silver = profile_provenance("NQ_SILVER_BULLET_M1")
assert silver["source_status"] == "NOT_2016_17_CORE_MODEL"

pipe = profile_pipeline_contract("XAU_SWEEP_IFVG_H1")
assert pipe["context"]["status"] == "SOURCE_AWARE"
assert pipe["setup"]["status"] == "MODEL_SPECIFIC"
assert pipe["setup"]["auto_infer_from_core_events"] is False
assert "IFVG_FIXED_BAR_EXPIRY" in pipe["setup"]["non_core_assumptions"]

# Pure source-pipeline tests: closed-candle FVG + confirmed-liquidity raid.
base_ms = 1_700_000_000_000
width = 5 * 60_000
fvg_rows = [
    {"t": base_ms + 0 * width, "close_t": base_ms + 1 * width, "o": 100.0, "h": 101.0, "l": 99.0, "c": 100.5},
    {"t": base_ms + 1 * width, "close_t": base_ms + 2 * width, "o": 100.5, "h": 102.0, "l": 100.2, "c": 101.8},
    {"t": base_ms + 2 * width, "close_t": base_ms + 3 * width, "o": 101.8, "h": 103.0, "l": 101.5, "c": 102.7},
]
closed = normalize_closed_bars(fvg_rows, timeframe="5m", as_of_ms=base_ms + 3 * width)
gaps = fair_value_gaps(closed)
assert gaps and gaps[-1]["side"] == "BULLISH"
assert abs(gaps[-1]["low"] - 101.0) < 1e-9
assert abs(gaps[-1]["high"] - 101.5) < 1e-9
assert gaps[-1]["validity_claim"] == "NONE"

raid_rows = [
    {"t": base_ms + 0 * width, "close_t": base_ms + 1 * width, "o": 100.0, "h": 101.0, "l": 99.0, "c": 100.0},
    {"t": base_ms + 1 * width, "close_t": base_ms + 2 * width, "o": 100.0, "h": 103.0, "l": 100.0, "c": 102.0},
    {"t": base_ms + 2 * width, "close_t": base_ms + 3 * width, "o": 102.0, "h": 102.0, "l": 100.5, "c": 101.0},
    {"t": base_ms + 3 * width, "close_t": base_ms + 4 * width, "o": 101.0, "h": 104.0, "l": 101.0, "c": 102.0},
]
raid_bars = normalize_closed_bars(raid_rows, timeframe="5m", as_of_ms=base_ms + 4 * width)
sw = confirmed_swings(raid_bars, left=1, right=1)
raids = liquidity_raids(raid_bars, sw)
assert any(x["liquidity_side"] == "BUY_SIDE" and abs(x["reference_price"] - 103.0) < 1e-9 for x in raids)

snap = snapshot(fvg_rows, market="NQ", timeframe="5m", as_of_ms=base_ms + 3 * width, pivot_left=1, pivot_right=1)
assert snap["layers"]["setup"]["status"] == "LOCKED"
assert snap["layers"]["execution"]["status"] == "LOCKED"
assert snap["layers"]["risk"]["status"] == "LOCKED"

# Point-in-time test for the Month-10 index session features.
day = datetime(2026, 9, 18, 0, 0, tzinfo=NY)
bars = []

# Previous evening Asia range required by the existing context engine.
t = day - timedelta(hours=4)  # previous day 20:00 NY
for i in range(48):
    px = 100.0 + (i % 5) * 0.1
    bars.append({
        "t": int(t.timestamp() * 1000),
        "close_t": int((t + timedelta(minutes=5)).timestamp() * 1000),
        "o": px,
        "h": px + 0.2,
        "l": px - 0.2,
        "c": px + 0.05,
    })
    t += timedelta(minutes=5)

# Opening range 09:30-10:30 NY.
t = day + timedelta(hours=9, minutes=30)
for i in range(12):
    px = 110.0 + i
    bars.append({
        "t": int(t.timestamp() * 1000),
        "close_t": int((t + timedelta(minutes=5)).timestamp() * 1000),
        "o": px,
        "h": px + 0.75,
        "l": px - 0.5,
        "c": px + 0.25,
    })
    t += timedelta(minutes=5)

as_of = day + timedelta(hours=10, minutes=31)
ctx = _session_context(bars, int(as_of.timestamp() * 1000), DEFAULT_CONFIG)
assert ctx["index_or_complete"] is True
assert abs(ctx["index_or_high"] - 121.75) < 1e-9
assert abs(ctx["index_or_low"] - 109.5) < 1e-9
assert ctx["index_session_phase"] == "AM_AFTER_OR"

print("ICT Core source-audit verification: PASS")
print("  OTE provenance:", ote["source_status"], ote["evidence_label"])
print("  iFVG provenance:", ifvg["source_status"], ifvg["evidence_label"])
print("  Index OR:", ctx["index_or_low"], "->", ctx["index_or_high"], ctx["index_session_phase"])
print("  Rule pipeline:", pipe["pipeline_version"], "· setup", pipe["setup"]["status"])
print("  Primitive tests: FVG + liquidity raid PASS")
