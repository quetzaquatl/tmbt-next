# TMBT Next migration master plan

Goal: TMBT Next becomes the only Studio. The old Streamlit Studio is a temporary migration source, not a permanent runtime dependency.

## Canonical workspace layout

Keep the existing TMBT Next roots as the canonical layout to avoid another migration:

- `live_data/` — live provider mirrors, feed status, provider settings
- `historical/` — Databento raw downloads and local historical databases
- `research_jobs/` — backtest/optimizer jobs and results
- `research_autopilot/` — autopilot request/status/report/log
- `live_signals/` — signal history, outcomes, snapshots
- `paper_account/` — paper trading state
- `migration/` — temporary audit/migration reports only
- `_legacy_archive/` — verified legacy duplicates; never auto-deleted

Legacy live roots such as `live/` and `github_research_repo/live/` are migration inputs only.

## Function migration order

1. Historical data: Databento NQ/ES/GC store and point-in-time loaders.
2. Live feeds: Twelve/true futures provider adapters, self-healing guardian.
3. Research core: backtest engine, presets, job manager, optimizer, autopilot.
4. Signal/model engine: all model types, setup archive, outcomes and snapshots.
5. Paper execution and trade management.
6. Configuration/API keys/provider settings.
7. Remaining Old Studio utilities and diagnostics.
8. Verify parity and archive Old Studio.

## Decommission gate

The Old Studio can be retired only when:

- no TMBT Next process imports or launches code from the old Studio directory;
- every old preset/model used in production exists in the new repo;
- research/backtest/optimizer/autopilot run natively from TMBT Next;
- live feeds restart without Old Studio;
- data readers use only canonical workspace roots;
- a migration audit reports no required old module;
- old data roots have been checksum-merged and archived.

## Safety rule

Workspace cleanup is never destructive on first pass. `workspace_cleanup.py` performs a dry run by default. In apply mode it checksum-verifies copied files and moves legacy roots into `_legacy_archive/`; it does not delete them.
