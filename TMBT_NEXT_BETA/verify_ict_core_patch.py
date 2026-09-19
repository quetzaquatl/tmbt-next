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
    "legacy_research_adapter.py",
    "research_scheduler.py",
    "context_factors.py",
    "backtest_context_adapter.py",
):
    py_compile.compile(str(HERE / name), doraise=True)

from ict_core_rules import profile_provenance
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
