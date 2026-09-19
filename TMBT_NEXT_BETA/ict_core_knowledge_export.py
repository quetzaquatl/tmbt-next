from __future__ import annotations

import argparse
import json
from pathlib import Path

import ict_core_knowledge
import ict_core_rules


def payload() -> dict:
    return {
        "knowledge_version": ict_core_knowledge.KNOWLEDGE_VERSION,
        "coverage": ict_core_rules.knowledge_coverage(),
        "evidence_classes": ict_core_knowledge.EVIDENCE,
        "machine_status": ict_core_knowledge.MACHINE_STATUS,
        "lectures": [ict_core_knowledge.lecture(i) for i in range(1, 116)],
        "rule_catalog": {
            rid: {"rule_id": rid, **rule}
            for rid, rule in ict_core_knowledge.RULE_CATALOG.items()
        },
        "source_audit_status": ict_core_knowledge.VISUAL_AUDIT_GAPS,
        "executable_rules": ict_core_rules.CORE_RULES,
        "executable_to_knowledge": ict_core_rules.EXECUTABLE_TO_KNOWLEDGE,
        "non_core_assumptions": ict_core_rules.NON_CORE_ASSUMPTIONS,
        "guardrails": {
            "visual_rules_auto_execute": False,
            "partial_rules_auto_execute": False,
            "reference_rules_auto_execute": False,
            "core_event_auto_creates_trade": False,
            "profitability_claim": False,
            "live_promotion": False,
        },
    }


def main() -> int:
    p = argparse.ArgumentParser(
        description="Export the source-aware ICT Core Content knowledge base as JSON."
    )
    p.add_argument("--output", default="")
    p.add_argument("--compact", action="store_true")
    args = p.parse_args()

    value = payload()
    text = json.dumps(
        value,
        ensure_ascii=False,
        indent=None if args.compact else 2,
        separators=(",", ":") if args.compact else None,
        default=str,
    )
    if args.output:
        path = Path(args.output).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        print(path)
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
