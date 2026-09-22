from __future__ import annotations

import py_compile
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
NY = ZoneInfo("America/New_York")

# Syntax smoke test for the source-audit integration.
for name in (
    "ict_core_rules.py",
    "ict_core_knowledge.py",
    "ict_core_knowledge_export.py",
    "ict_rule_engine.py",
    "ict_research_snapshot.py",
    "legacy_research_adapter.py",
    "research_scheduler.py",
    "context_factors.py",
    "backtest_context_adapter.py",
    "historical_store.py",
    "databento_history_import.py",
    "seasonality_context.py",
    "model_context_analysis.py",
):
    py_compile.compile(str(HERE / name), doraise=True)

from ict_core_rules import profile_provenance, profile_variant_metadata, knowledge_coverage, EXECUTABLE_TO_KNOWLEDGE, CORE_RULES, core_rule_gate
import ict_core_knowledge
from ict_rule_engine import PIPELINE_VERSION, normalize_closed_bars, fair_value_gaps, confirmed_swings, liquidity_raids, profile_pipeline_contract, snapshot
from context_factors import DEFAULT_CONFIG, _session_context
from databento_history_import import OUTRIGHT_RE
import research_scheduler
import seasonality_context

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
assert "CORE_SEASONALITY_CONTEXT_ONLY" in ote["knowledge_context_rules"]
assert "CORE_SEASONALITY_CONTEXT_ONLY" in silver["knowledge_context_rules"]
assert "CORE_SEASONALITY_CONTEXT_ONLY" in profile_provenance("NQ_EBP_H1")["knowledge_context_rules"]

assert profile_variant_metadata("XAU_OTE_BOS_M15")["variant_status"] == "CANONICAL_FORMALIZED"
assert profile_variant_metadata("XAU_OTE_BOS_H1")["variant_status"] == "GENERATED_RESEARCH_VARIANT"
assert profile_variant_metadata("NQ_TTFM_D1_H1_M5")["variant_status"] == "DOCUMENTED_PUBLIC_MODEL_VARIANT"
assert OUTRIGHT_RE.fullmatch("YMU26")
assert len(research_scheduler.DEFAULT_CONFIG["profiles"]) == 15
assert research_scheduler.DEFAULT_CONFIG["source_audited_matrix_enabled"] is True
assert research_scheduler.DEFAULT_CONFIG["experimental_timeframe_matrix_enabled"] is False

coverage = knowledge_coverage()
assert coverage["knowledge_version"] == "ict-core-knowledge-v2"
assert PIPELINE_VERSION == "ict-source-pipeline-v2"
assert coverage["lecture_count"] == 115
assert coverage["expected_lecture_count"] == 115
assert coverage["all_lectures_indexed"] is True
assert coverage["structured_knowledge_complete"] is True
assert coverage["completion"]["structured_knowledge_base"] == "COMPLETE"
assert coverage["source_rule_audit_complete"] is True
assert coverage["fully_rule_audited"] is True
assert coverage["frame_by_frame_visual_audit_complete"] is False
assert coverage["visual_locked_rule_count"] == 0
assert coverage["visual_locked_rules"] == []
assert coverage["completion"]["source_rule_audit"] == "COMPLETE"
assert coverage["completion"]["frame_by_frame_visual_audit"] == "NOT_CLAIMED"
assert coverage["completion"]["full_rule_audit"] == "COMPLETE"
assert coverage["focus_indexed"] == 115
assert coverage["rule_catalog_count"] == 88
assert coverage["rule_mapped_lecture_count"] == 115
assert coverage["unmapped_lessons"] == []
assert coverage["knowledge_linked_executable_rules"] == len(EXECUTABLE_TO_KNOWLEDGE)
assert len(ict_core_knowledge.LESSON_FOCUS) == 115
assert len(ict_core_knowledge.LESSON_KNOWLEDGE) == 115
assert coverage["lesson_knowledge_count"] == 115
assert coverage["lesson_knowledge_complete"] is True
assert ict_core_knowledge.lecture(1)["month"] == 1
assert ict_core_knowledge.lecture(115)["month"] == 12
assert "CORE_FAIR_VALUE_GAP" in ict_core_knowledge.RULE_CATALOG
assert "CORE_CBDR" in ict_core_knowledge.RULE_CATALOG
assert "CORE_INDEX_SMT_BASKET" in ict_core_knowledge.RULE_CATALOG
assert ict_core_knowledge.RULE_CATALOG["CORE_ORDER_BLOCK"]["machine_status"] == "PARTIAL"

assert ict_core_knowledge.RULE_CATALOG["CORE_OTE"]["evidence_class"] == "A"
assert ict_core_knowledge.RULE_CATALOG["CORE_OTE"]["machine_status"] == "READY"
assert ict_core_knowledge.RULE_CATALOG["CORE_FAIR_VALUE_GAP"]["evidence_class"] == "A"
assert ict_core_knowledge.RULE_CATALOG["CORE_FAIR_VALUE_GAP"]["machine_status"] == "READY"
assert core_rule_gate("ICT_CORE_OTE_ZONE")["execution_allowed"] is True
assert core_rule_gate("ICT_CORE_FVG_3_CANDLE")["execution_allowed"] is True
assert core_rule_gate("ICT_CORE_INDEX_OPENING_RANGE")["execution_allowed"] is True
assert core_rule_gate("ICT_CORE_ORDER_BLOCK")["execution_allowed"] is False
assert CORE_RULES["ICT_CORE_OTE_ZONE"]["machine_interpretation"]["ote_zone_min_pct"] == 62.0
assert CORE_RULES["ICT_CORE_OTE_ZONE"]["machine_interpretation"]["ote_reference_pct"] == 70.5
assert CORE_RULES["ICT_CORE_OTE_ZONE"]["machine_interpretation"]["ote_zone_max_pct"] == 79.0
assert ict_core_knowledge.SOURCE_AUDIT_STATUS["CORE_OTE"]["status"] == "TEXT_CERTIFIED_NUMERIC"
assert ict_core_knowledge.SOURCE_AUDIT_STATUS["CORE_FAIR_VALUE_GAP"]["status"] == "TEXT_CERTIFIED_GEOMETRY"
assert ict_core_knowledge.VISUAL_AUDIT_GAPS is ict_core_knowledge.SOURCE_AUDIT_STATUS
assert all(str(x.get("status") or "").upper() != "LOCKED" for x in ict_core_knowledge.SOURCE_AUDIT_STATUS.values())

pipe = profile_pipeline_contract("XAU_SWEEP_IFVG_H1")
assert pipe["context"]["status"] == "SOURCE_AWARE"
assert "ICT_CORE_FVG_3_CANDLE" not in pipe["context"]["locked_core_rules"]
assert "ICT_CORE_FVG_3_CANDLE" in pipe["context"]["production_safe_core_rules"]
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
assert gaps[-1]["evidence_class"] == "B"
assert gaps[-1]["geometry_status"] == "SOURCE_CERTIFIED"
assert gaps[-1]["primitive_usable"] is True

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
assert snap["audit"]["fvg_geometry_locked"] is False
assert snap["audit"]["ote_geometry_locked"] is False

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


# Leakage-safe seasonal context: future rows must not affect a historical trade.
season_rows = [
    {"date": date(2021, 1, 12), "return_pct": 1.0, "range_pct": 2.0},
    {"date": date(2022, 1, 11), "return_pct": 1.5, "range_pct": 2.0},
    {"date": date(2023, 1, 10), "return_pct": 0.5, "range_pct": 2.0},
    {"date": date(2025, 1, 7), "return_pct": -99.0, "range_pct": 2.0},
]
season = seasonality_context.point_in_time_consensus_from_rows(
    season_rows, date(2024, 1, 9), bucket="iso_week", min_samples=3
)
assert season["label"] == "BULLISH"
assert season["point_in_time_safe"] is True
assert all(
    row.get("history_last") is None or row["history_last"] < "2024-01-09"
    for row in season["windows"].values()
)
print("ICT Core source-audit verification: PASS")
print("  OTE provenance:", ote["source_status"], ote["evidence_label"])
print("  iFVG provenance:", ifvg["source_status"], ifvg["evidence_label"])
print("  Index OR:", ctx["index_or_low"], "->", ctx["index_or_high"], ctx["index_session_phase"])
print("  Rule pipeline:", pipe["pipeline_version"], "· setup", pipe["setup"]["status"])
print("  Primitive tests: FVG + liquidity raid PASS")
print("  Seasonality: point-in-time leakage guard PASS")
print("  Canonical matrix: 15 profiles · generated TF variants opt-in")
print("  YM importer matcher: PASS")
print("  Core knowledge:", coverage["lecture_count"], "lectures ·", coverage["lesson_knowledge_count"], "lesson notes ·", coverage["rule_catalog_count"], "rule groups")
print("  Rule mapping:", coverage["rule_mapped_lecture_count"], "/115 lectures · unmapped", coverage["unmapped_lessons"])
print("  Source-rule audit: COMPLETE · unresolved locked rules:", coverage["visual_locked_rule_count"])
print("  Frame-by-frame 53h video audit: NOT CLAIMED · contextual/reference rules remain non-executable")
