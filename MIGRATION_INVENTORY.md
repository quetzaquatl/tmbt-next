# Old Studio → TMBT Next migration inventory

Source inventory: 70 files from the audited v3_7_DEV bundle.

Status legend:
- **NATIVE** — implemented directly in TMBT Next.
- **MIGRATED RUNTIME** — runs from the self-contained audited source bundle under the TMBT workspace; old Studio directory is not required.
- **DATA COMPAT** — TMBT Next reads the existing canonical workspace state/output.
- **PENDING UI** — backend capability is preserved/available, but the old Streamlit control surface has not yet been reproduced in the new UI.
- **RETIRE** — old maintenance-only utility that should not remain a long-term runtime dependency.

| Old component | Purpose | Current TMBT Next status |
|---|---|---|
| bt_core.py | Backtest/model engine | MIGRATED RUNTIME + Databento adapter |
| research_jobs.py | Backtest/optimizer jobs | MIGRATED RUNTIME + Research tab |
| research_autopilot.py | Dev/validation optimizer pipeline | MIGRATED RUNTIME + native TMBT wrapper |
| github_sync.py | Remote bounded research channel | MIGRATED RUNTIME + self-healing TMBT wrapper |
| studio_bridge.py | Workspace/manifests/runs | MIGRATED RUNTIME; historical NQ/ES intercepted by Databento adapter |
| twelve_live.py | Twelve live collector | MIGRATED RUNTIME + feed guardian |
| tradingview_live.py | legacy live cache/relay helpers | MIGRATED RUNTIME; PENDING UI where still useful |
| live_signal_agent.py | legacy signal agent | DATA COMPAT / PENDING parity review |
| signal_outcomes.py | outcome tracking | DATA COMPAT; current TMBT UI reads outcomes |
| paper_trader.py | paper execution | DATA COMPAT / PENDING full controls |
| capital_live.py | Capital live provider | MIGRATED RUNTIME / PENDING UI; optional provider |
| yahoo_futures.py | Yahoo prototype provider | MIGRATED RUNTIME / PENDING UI; optional provider |
| readonly_api.py | legacy remote HTTP bridge | PENDING parity review; TMBT Next has its own HTTP API |
| github_setup.py | setup helper | RETIRE after remote sync migration verified |
| bridge_launcher.py | old bridge launcher | RETIRE after parity verified |
| folder_cleanup.py | old cleanup helper | RETIRE; replaced by workspace_cleanup.py |
| dev_patch_agent.py | old patch workflow | RETIRE; repo updater is canonical |
| theme_manager.py/themes | old Streamlit themes | PENDING UI only if still useful |
| app.py | old Streamlit UI | RETIRE after UI parity gate |
| presets/* | formal strategy presets | MIGRATED RUNTIME; NQ/ES true-futures EBP presets added |
| docs/* | historical behavior/reference | MIGRATED in audit bundle; reference only |

## Data canonicalization

Canonical runtime data homes:
- live_data/
- historical/
- research_jobs/
- research_autopilot/
- live_signals/
- paper_account/
- migration/
- _legacy_archive/

The GitHub research checkout remains a transport/integration checkout, not a market-data source. Its old live mirror publishing is disabled by TMBT Next so live bars have one canonical local home under live_data/.

## Retirement gate

Do not delete the old Studio directory until VERIFY_STUDIO_MIGRATION.bat reports the migration ready and live feed + remote research have been tested after a restart.
