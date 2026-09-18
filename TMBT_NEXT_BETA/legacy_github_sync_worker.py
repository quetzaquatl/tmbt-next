from __future__ import annotations

import importlib
from pathlib import Path

import legacy_research_adapter
import research_autopilot_bridge


def main() -> int:
    mods = legacy_research_adapter.activate()
    runtime = Path(mods["root"])
    github_sync = importlib.import_module("github_sync")

    # Keep all runtime state in the canonical workspace while executing migrated
    # source from the self-contained compatibility bundle.
    github_sync.APP_DIR = runtime
    github_sync.WORKSPACE = research_autopilot_bridge.workspace()
    github_sync.CONFIG_PATH = github_sync.WORKSPACE / "github_sync_config.json"
    github_sync.STATUS_PATH = github_sync.WORKSPACE / "github_sync_status.json"
    github_sync.LOG_PATH = github_sync.WORKSPACE / "github_sync.log"

    # Old github_sync used research_autopilot.start_process(), which would spawn
    # the legacy script without our Databento adapter. Route remote autopilot
    # commands through TMBT Next's native wrapper instead.
    def start_autopilot(req, app_dir=None, workspace=None):
        profile = str((req or {}).get("profile") or "NQ_EBP_H1")
        return research_autopilot_bridge.start(
            profile,
            test_news=bool((req or {}).get("test_news", True)),
            tick_audit=bool((req or {}).get("tick_audit", False)),
        )

    def stop_autopilot(workspace=None):
        return research_autopilot_bridge.stop()

    github_sync.start_autopilot_process = start_autopilot
    github_sync.stop_autopilot_process = stop_autopilot
    github_sync.read_autopilot_status = lambda workspace=None: research_autopilot_bridge.status()
    github_sync.autopilot_latest_report = lambda workspace=None: research_autopilot_bridge.latest_report()
    github_sync.autopilot_profiles = lambda: research_autopilot_bridge.profiles()

    github_sync.daemon()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
