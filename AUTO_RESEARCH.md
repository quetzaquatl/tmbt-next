# Automated Research Lab

TMBT Next runs a bounded research loop for formalized model profiles only.

Default queue:
- NQ_EBP_H1
- ES_EBP_H1
- XAU_OTE_BOS
- XAU_SWEEP_IFVG

Behavior:
- failed/weak candidates are re-tested after 24h with a refined Development optimizer grid;
- passed candidates are re-tested weekly for stability;
- after 3 failed cycles a model is marked REVIEW_REQUIRED instead of being tuned indefinitely;
- PASS becomes READY_FOR_LIVE_REVIEW, never automatic live promotion;
- holdout/OOS stays locked;
- Trader Thinking / Observations are excluded from optimizer inputs.

Reports:
- workspace/research_reports/latest.json
- workspace/research_reports/latest.md
- workspace/research_reports/<PROFILE>/latest.json
- workspace/research_reports/<PROFILE>/latest.md

Remote Research Sync publishes only compact state/results to tmbt-research-sync:
- state/historical.json
- state/research_scheduler.json
- reports/latest.json
- reports/<PROFILE>_latest.json

Raw Databento files and the historical SQLite database remain local.
