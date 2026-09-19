from __future__ import annotations

from copy import deepcopy
from typing import Any

import ict_core_knowledge

# Source-aware rule registry for TMBT.
#
# Evidence classes:
#   A = explicit ICT Core Content rule/definition.
#   B = deterministic software interpretation assembled from A-rules.
#   C = source text is not sufficient for exact chart geometry; visual audit required.
#   D = TMBT research assumption / later-ICT convention, not an ICT 2016/17 Core rule.
#
# This module deliberately contains provenance and software-facing semantics only.
# It does not claim profitability and it does not auto-promote any model to live.

EVIDENCE_CLASSES = {
    "A": "EXPLICIT_CORE",
    "B": "DERIVED_CORE",
    "C": "VISUAL_CONFIRMATION_REQUIRED",
    "D": "TMBT_RESEARCH_OR_LATER_ICT",
}

EXECUTABLE_TO_KNOWLEDGE = {
    "ICT_CORE_OTE_ZONE": "CORE_OTE",
    "ICT_CORE_FVG_3_CANDLE": "CORE_FAIR_VALUE_GAP",
    "ICT_CORE_LIQUIDITY_OLD_EXTREMES": "CORE_LIQUIDITY_OLD_HIGHS_LOWS",
    "ICT_CORE_ORDER_BLOCK": "CORE_ORDER_BLOCK",
    "ICT_CORE_INDEX_OPENING_RANGE": "CORE_INDEX_OPENING_RANGE",
    "ICT_CORE_INDEX_AM_SESSION": "CORE_INDEX_AM_RELATIVE_HILO",
    "ICT_CORE_INDEX_SMT": "CORE_INDEX_SMT_BASKET",
    "ICT_CORE_MULTI_TF_PORTABILITY": "CORE_TIMEFRAME_HIERARCHY",
}

CORE_RULES: dict[str, dict[str, Any]] = {
    "ICT_CORE_OTE_ZONE": {
        "concept": "OTE / Premium-Discount",
        "human_rule": "Inside a relevant impulse/dealing range, 50% is equilibrium and the Core explicitly names 62%, 70.5% and 79% as the Optimal Trade Entry retracement references, with 70.5% the sweet spot.",
        "machine_interpretation": {
            "equilibrium_pct": 50.0,
            "ote_zone_min_pct": 62.0,
            "ote_reference_pct": 70.5,
            "ote_zone_max_pct": 79.0,
            "exact_ote_geometry_locked": False,
            "active_range_selection_is_contextual": True,
        },
        "timeframe_scope": "multi-timeframe",
        "session_scope": "context dependent",
        "source_month": 1,
        "source_lesson": "4, 5",
        "source_timestamp": "L4 24:09-24:22; 29:19-29:45; L5 11:25-11:47",
        "evidence_class": "A",
    },
    "ICT_CORE_FVG_3_CANDLE": {
        "concept": "Fair Value Gap",
        "human_rule": "The Core explicitly frames a three-candle one-sided delivery pocket by the untraded range between candle one and candle three around the displacement candle; the bullish case is the mirrored geometry.",
        "machine_interpretation": {
            "bullish": "high[t-1] < low[t+1]",
            "bearish": "low[t-1] > high[t+1]",
            "canonical_geometry_locked": False,
            "touch_or_full_traversal_is_not_automatic_invalidation": True,
        },
        "timeframe_scope": "multi-timeframe",
        "session_scope": "none",
        "source_month": 4,
        "source_lesson": 36,
        "source_timestamp": "01:44-06:24; especially 03:29-04:54 and 05:48-06:24",
        "evidence_class": "B",
    },
    "ICT_CORE_LIQUIDITY_OLD_EXTREMES": {
        "concept": "Liquidity",
        "human_rule": "Old highs and old lows are primary structural liquidity references.",
        "machine_interpretation": {
            "buy_side_reference": "old/confirmed high",
            "sell_side_reference": "old/confirmed low",
        },
        "timeframe_scope": "multi-timeframe",
        "session_scope": "context dependent",
        "source_month": 1,
        "source_lesson": 7,
        "source_timestamp": "05:38+",
        "evidence_class": "A",
    },
    "ICT_CORE_ORDER_BLOCK": {
        "concept": "Order Block",
        "human_rule": "Order Blocks are selected and validated in structural context; a simplistic 'last opposite candle before every displacement' is not source-equivalent.",
        "machine_interpretation": {
            "strict_mode": "requires source-faithful candle selection + validation + location context",
            "simplified_mode": "TMBT research approximation only",
        },
        "timeframe_scope": "multi-timeframe",
        "session_scope": "context dependent",
        "source_month": 4,
        "source_lesson": 27,
        "source_timestamp": "lesson-wide; chart geometry partly visual",
        "evidence_class": "C",
    },
    "ICT_CORE_INDEX_OPENING_RANGE": {
        "concept": "Index Futures Opening Range",
        "human_rule": "For index futures, the opening range is 09:30-10:30 New York time.",
        "machine_interpretation": {
            "timezone": "America/New_York",
            "start": "09:30",
            "end": "10:30",
        },
        "timeframe_scope": "index futures",
        "session_scope": "RTH",
        "source_month": 10,
        "source_lesson": 98,
        "source_timestamp": "lesson-wide",
        "evidence_class": "A",
    },
    "ICT_CORE_INDEX_AM_SESSION": {
        "concept": "Index Futures AM Session",
        "human_rule": "The AM index-futures session is framed as 09:30-12:00 New York time; the early RTH hour is an important day-extreme window.",
        "machine_interpretation": {
            "timezone": "America/New_York",
            "start": "09:30",
            "end": "12:00",
            "early_extreme_window_start": "09:30",
            "early_extreme_window_end": "10:30",
        },
        "timeframe_scope": "index futures",
        "session_scope": "RTH",
        "source_month": 10,
        "source_lesson": 99,
        "source_timestamp": "lesson-wide",
        "evidence_class": "A",
    },
    "ICT_CORE_INDEX_SMT": {
        "concept": "Index SMT",
        "human_rule": "Compare relative highs/lows across correlated equity indices; non-confirmation of a corresponding extreme is meaningful divergence.",
        "machine_interpretation": {
            "preferred_assets": ["ES", "NQ", "YM"],
            "bullish": "one market raids a reference low while a correlated peer does not",
            "bearish": "one market raids a reference high while a correlated peer does not",
        },
        "timeframe_scope": "index futures",
        "session_scope": "pre-open and RTH context",
        "source_month": 10,
        "source_lesson": "99, 102",
        "source_timestamp": "lesson-wide",
        "evidence_class": "B",
    },
    "ICT_CORE_MULTI_TF_PORTABILITY": {
        "concept": "Timeframe portability",
        "human_rule": "The structural patterns are taught as observable across multiple timeframes; that does not imply identical bar-count parameters across timeframes.",
        "machine_interpretation": {
            "keep_structural_geometry": True,
            "do_not_assume_fixed_bar_count_portability": True,
            "prefer_clock_or_event_scope_for_sessions_and_expiry": True,
        },
        "timeframe_scope": "monthly to intraday",
        "session_scope": "model dependent",
        "source_month": 12,
        "source_lesson": 115,
        "source_timestamp": "lesson-wide",
        "evidence_class": "B",
    },
}

# TMBT/later-model assumptions that must never be silently presented as Core rules.
NON_CORE_ASSUMPTIONS = {
    "IFVG_INVERSION": {
        "concept": "Inversion FVG",
        "evidence_class": "D",
        "reason": "Not established as a standalone 2016/17 Core model in the audited corpus.",
    },
    "IFVG_CE_ENTRY": {
        "concept": "50% / CE entry on an inversion FVG",
        "evidence_class": "D",
        "reason": "Treat as later-ICT/TMBT convention unless separately sourced.",
    },
    "IFVG_FIXED_BAR_EXPIRY": {
        "concept": "Fixed iFVG lookback/inversion/retest bar counts",
        "evidence_class": "D",
        "reason": "Values such as 18/12/12 are TMBT research assumptions, not audited Core constants.",
    },
    "SILVER_BULLET_MODEL": {
        "concept": "Silver Bullet",
        "evidence_class": "D",
        "reason": "Concrete Silver Bullet model is not defined in the audited 2016/17 Core corpus.",
    },
    "TMBT_BOS_BOOLEAN": {
        "concept": "Current TMBT BOS boolean",
        "evidence_class": "D",
        "reason": "Market structure is taught in Core, but the current exact TMBT boolean is our quantification.",
    },
    "TTFM_STATE_MACHINE": {
        "concept": "Current TTFM D1/H1/M5 etc. state machine",
        "evidence_class": "D",
        "reason": "Top-down hierarchy is Core-compatible; the exact TMBT state machine is our implementation.",
    },
    "EBP_MODEL": {
        "concept": "EBP",
        "evidence_class": "D",
        "reason": "EBP is a formalized TMBT model, not a named ICT 2016/17 Core model.",
    },
}


def _base_profile(
    *,
    source_family: str,
    source_status: str,
    evidence_class: str,
    core_rules: list[str] | None = None,
    non_core_assumptions: list[str] | None = None,
    notes: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "source_family": source_family,
        "source_status": source_status,
        "evidence_class": evidence_class,
        "evidence_label": EVIDENCE_CLASSES.get(evidence_class, evidence_class),
        "core_rules": list(core_rules or []),
        "non_core_assumptions": list(non_core_assumptions or []),
        "notes": list(notes or []),
        "auto_live_promotion": False,
    }


def profile_provenance(profile_id: str) -> dict[str, Any]:
    p = str(profile_id or "").upper()

    if "_OTE_BOS_" in p:
        return _base_profile(
            source_family="ICT_CORE_2016_17 + TMBT",
            source_status="MIXED",
            evidence_class="B",
            core_rules=[
                "ICT_CORE_OTE_ZONE",
                "ICT_CORE_LIQUIDITY_OLD_EXTREMES",
                "ICT_CORE_MULTI_TF_PORTABILITY",
            ],
            non_core_assumptions=["TMBT_BOS_BOOLEAN"],
            notes=[
                "OTE zone is Core-sourced; exact BOS quantification and several execution thresholds remain TMBT research choices.",
            ],
        )

    if "_SWEEP_IFVG_" in p:
        return _base_profile(
            source_family="ICT_CORE_2016_17 components + later ICT/TMBT",
            source_status="MIXED_NON_CORE_MODEL",
            evidence_class="D",
            core_rules=[
                "ICT_CORE_FVG_3_CANDLE",
                "ICT_CORE_LIQUIDITY_OLD_EXTREMES",
                "ICT_CORE_MULTI_TF_PORTABILITY",
            ],
            non_core_assumptions=[
                "IFVG_INVERSION",
                "IFVG_CE_ENTRY",
                "IFVG_FIXED_BAR_EXPIRY",
            ],
            notes=[
                "Do not label the complete Sweep-iFVG state machine as an ICT 2016/17 Core model.",
                "Fixed bar lookback/expiry values are research parameters, not source constants.",
            ],
        )

    if "_SILVER_BULLET_" in p:
        return _base_profile(
            source_family="later ICT/TMBT",
            source_status="NOT_2016_17_CORE_MODEL",
            evidence_class="D",
            core_rules=[
                "ICT_CORE_FVG_3_CANDLE",
                "ICT_CORE_LIQUIDITY_OLD_EXTREMES",
            ],
            non_core_assumptions=[
                "SILVER_BULLET_MODEL",
                "IFVG_INVERSION",
                "IFVG_CE_ENTRY",
                "IFVG_FIXED_BAR_EXPIRY",
            ],
        )

    if "_TTFM_" in p:
        rules = ["ICT_CORE_MULTI_TF_PORTABILITY"]
        if p.startswith(("NQ_", "ES_")):
            rules += [
                "ICT_CORE_INDEX_OPENING_RANGE",
                "ICT_CORE_INDEX_AM_SESSION",
                "ICT_CORE_INDEX_SMT",
            ]
        return _base_profile(
            source_family="TTRADES_PUBLIC + ICT_CORE_CONTEXT + TMBT",
            source_status="MIXED_EXTERNAL_PUBLIC_MODEL",
            evidence_class="B",
            core_rules=rules,
            non_core_assumptions=["TTFM_STATE_MACHINE"],
            notes=[
                "The named TTFM playbooks come from public TTrades education, not from the ICT 2016/17 Core Content.",
                "ICT Core context such as index-session/SMT may be layered around the model, but exact three-timeframe gates and thresholds remain TMBT implementation choices.",
            ],
        )

    if p.startswith(("NQ_EBP_", "ES_EBP_")):
        return _base_profile(
            source_family="TMBT",
            source_status="TMBT_FORMALIZED_MODEL",
            evidence_class="D",
            core_rules=[],
            non_core_assumptions=["EBP_MODEL"],
        )

    return _base_profile(
        source_family="TMBT/unknown",
        source_status="UNCLASSIFIED",
        evidence_class="D",
    )


def profile_knowledge_links(profile_id: str) -> list[str]:
    """Broader Core knowledge relevant to a profile without claiming model origin."""
    p = str(profile_id or "").upper()
    if "_OTE_BOS_" in p:
        return [
            "CORE_OTE",
            "CORE_EQUILIBRIUM_PREMIUM_DISCOUNT",
            "CORE_LIQUIDITY_OLD_HIGHS_LOWS",
            "CORE_TIMEFRAME_HIERARCHY",
            "CORE_INSTITUTIONAL_SWING_POINTS",
            "CORE_PD_ARRAY_MATRIX",
        ]
    if "_SWEEP_IFVG_" in p:
        return [
            "CORE_FAIR_VALUE_GAP",
            "CORE_LIQUIDITY_OLD_HIGHS_LOWS",
            "CORE_TIMEFRAME_HIERARCHY",
            "CORE_TIME_OF_DAY",
        ]
    if "_SILVER_BULLET_" in p:
        links = [
            "CORE_FAIR_VALUE_GAP",
            "CORE_LIQUIDITY_OLD_HIGHS_LOWS",
            "CORE_TIME_OF_DAY",
        ]
        if p.startswith(("NQ_", "ES_")):
            links += [
                "CORE_INDEX_OPENING_RANGE",
                "CORE_INDEX_AM_RELATIVE_HILO",
                "CORE_INDEX_PM_SESSION",
                "CORE_INDEX_SMT_BASKET",
            ]
        return links
    if "_TTFM_" in p:
        links = ["CORE_TIMEFRAME_HIERARCHY", "CORE_DAYTRADE_HTF_ALIGNMENT"]
        if p.startswith(("NQ_", "ES_")):
            links += [
                "CORE_INDEX_OPENING_RANGE",
                "CORE_INDEX_AM_RELATIVE_HILO",
                "CORE_INDEX_PM_SESSION",
                "CORE_INDEX_SMT_BASKET",
            ]
        return links
    return []


def profile_variant_metadata(profile_id: str) -> dict[str, Any]:
    """Separate original/formalized profiles from generated timeframe clones."""
    p = str(profile_id or "").upper()

    canonical = {
        "NQ_EBP_H1": ("H1", "formalized TMBT EBP timeframe"),
        "ES_EBP_H1": ("H1", "formalized TMBT EBP timeframe"),
        "XAU_OTE_BOS_M15": ("M15", "audited migrated OTE baseline"),
        "XAU_SWEEP_IFVG_M5": ("M5", "migrated London Sweep iFVG baseline"),
        "NQ_SILVER_BULLET_M1": ("M1", "migrated Silver Bullet baseline mapped to NQ futures"),
        "ES_SILVER_BULLET_M1": ("M1", "migrated Silver Bullet baseline mapped to ES futures"),
    }
    if p in canonical:
        tf, note = canonical[p]
        return {
            "variant_status": "CANONICAL_FORMALIZED",
            "canonical_timeframe": tf,
            "generated_timeframe_variant": False,
            "variant_note": note,
        }

    if "_TTFM_" in p:
        return {
            "variant_status": "DOCUMENTED_PUBLIC_MODEL_VARIANT",
            "canonical_timeframe": None,
            "generated_timeframe_variant": False,
            "variant_note": "Explicit public TTrades playbook mapping; exact TMBT mechanics remain implementation conventions.",
        }

    generated_prefixes = (
        "NQ_EBP_", "ES_EBP_",
        "XAU_OTE_BOS_", "GC_OTE_BOS_",
        "XAU_SWEEP_IFVG_", "GC_SWEEP_IFVG_",
        "NQ_SILVER_BULLET_", "ES_SILVER_BULLET_",
    )
    if any(p.startswith(x) for x in generated_prefixes):
        return {
            "variant_status": "GENERATED_RESEARCH_VARIANT",
            "canonical_timeframe": None,
            "generated_timeframe_variant": True,
            "variant_note": "Generated for discovery; not a separately sourced/canonical strategy definition.",
        }

    return {
        "variant_status": "UNCLASSIFIED",
        "canonical_timeframe": None,
        "generated_timeframe_variant": False,
        "variant_note": "",
    }


def core_rule_gate(rule_id: str) -> dict[str, Any]:
    """Return whether a Core rule may participate in deterministic execution.

    A/B provenance alone is not enough when the broader knowledge record has a
    locked visual audit gap. C/D rules are always non-executable.
    """
    rid = str(rule_id or "")
    rule = CORE_RULES.get(rid) or {}
    knowledge_id = EXECUTABLE_TO_KNOWLEDGE.get(rid)
    knowledge = ict_core_knowledge.RULE_CATALOG.get(knowledge_id or "") or {}
    visual_gap = ict_core_knowledge.VISUAL_AUDIT_GAPS.get(knowledge_id or "")
    visual_locked = bool(
        visual_gap and str(visual_gap.get("status") or "").upper() == "LOCKED"
    )
    evidence = str(rule.get("evidence_class") or "")
    machine_status = str(knowledge.get("machine_status") or "")
    executable = bool(
        rule
        and evidence in {"A", "B"}
        and not visual_locked
        and machine_status == "READY"
    )
    return {
        "rule_id": rid,
        "knowledge_rule_id": knowledge_id,
        "evidence_class": evidence or None,
        "machine_status": knowledge.get("machine_status"),
        "visual_audit_status": (visual_gap or {}).get("status"),
        "visual_locked": visual_locked,
        "execution_allowed": executable,
        "reason": (
            "source-certified deterministic primitive"
            if executable
            else "locked: rule is not READY, has unresolved visual/source geometry, or uses a non-executable evidence class"
        ),
    }


def production_safe_core_rules(rule_ids: list[str] | None = None) -> list[str]:
    ids = list(rule_ids or CORE_RULES.keys())
    return [rid for rid in ids if core_rule_gate(rid)["execution_allowed"]]


def knowledge_coverage() -> dict[str, Any]:
    """Expose the full Core knowledge-base audit separately from executable rules."""
    coverage = dict(ict_core_knowledge.coverage_report())
    coverage["executable_rule_count"] = len(CORE_RULES)
    coverage["knowledge_linked_executable_rules"] = sum(
        1 for rid in CORE_RULES if rid in EXECUTABLE_TO_KNOWLEDGE
    )
    coverage["knowledge_version"] = ict_core_knowledge.KNOWLEDGE_VERSION
    return coverage


def expanded_provenance(profile_id: str) -> dict[str, Any]:
    """Return profile provenance plus referenced executable + knowledge rules."""
    p = profile_provenance(profile_id)
    p.update(profile_variant_metadata(profile_id))
    p["knowledge_version"] = ict_core_knowledge.KNOWLEDGE_VERSION
    p["knowledge_context_rules"] = profile_knowledge_links(profile_id)
    p["knowledge_context_details"] = {
        rid: deepcopy(ict_core_knowledge.RULE_CATALOG[rid])
        for rid in p["knowledge_context_rules"]
        if rid in ict_core_knowledge.RULE_CATALOG
    }
    p["core_rule_details"] = {
        rid: deepcopy(CORE_RULES[rid])
        for rid in p.get("core_rules") or []
        if rid in CORE_RULES
    }
    p["knowledge_rule_details"] = {
        EXECUTABLE_TO_KNOWLEDGE[rid]: deepcopy(
            ict_core_knowledge.RULE_CATALOG[EXECUTABLE_TO_KNOWLEDGE[rid]]
        )
        for rid in p.get("core_rules") or []
        if rid in EXECUTABLE_TO_KNOWLEDGE
        and EXECUTABLE_TO_KNOWLEDGE[rid] in ict_core_knowledge.RULE_CATALOG
    }
    p["non_core_details"] = {
        rid: deepcopy(NON_CORE_ASSUMPTIONS[rid])
        for rid in p.get("non_core_assumptions") or []
        if rid in NON_CORE_ASSUMPTIONS
    }
    return p


def annotate_profile(profile_id: str, profile: dict[str, Any]) -> dict[str, Any]:
    out = dict(profile)
    out["provenance"] = expanded_provenance(profile_id)
    return out
