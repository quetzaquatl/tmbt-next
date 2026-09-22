from __future__ import annotations

import importlib
import os
import subprocess
from pathlib import Path

import legacy_research_adapter
import research_autopilot_bridge
import historical_store
import seasonality_context


def _read_json_file(path: Path):
    import json
    try:
        value = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def _read_scheduler_state(workspace: Path):
    status = _read_json_file(workspace / "research_scheduler" / "status.json")
    profiles = _read_json_file(workspace / "research_scheduler" / "profiles.json")
    config = _read_json_file(workspace / "research_scheduler" / "config.json")
    return {
        "status": status,
        "profiles": profiles.get("profiles", {}),
        "config": config,
    }


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

    # The migrated daemon polls Git every few seconds. In a detached Windows
    # process, plain subprocess.run() can flash a console window. Keep every Git
    # command hidden while preserving the original behavior and return object.
    if os.name == "nt":
        def hidden_run_git(repo, args, timeout=60, check=True):
            git = github_sync._git_executable()
            if not git:
                raise RuntimeError("git_not_found")

            def run_git(inner_args, inner_timeout=None):
                return subprocess.run(
                    [git, "-C", str(repo), *inner_args],
                    capture_output=True,
                    text=True,
                    timeout=inner_timeout or timeout,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )

            def reconcile(branch):
                # First try the clean history-preserving path.
                run_git(["fetch", "origin", branch], 90)
                cp_pull = run_git(["pull", "--rebase", "--autostash", "origin", branch], 120)
                if cp_pull.returncode == 0:
                    return cp_pull

                # Generated state files can conflict if TMBT and the remote
                # command channel both moved main. Abort the rebase and merge
                # instead, keeping the current local generated state on content
                # conflicts while still importing new remote commands/files.
                run_git(["rebase", "--abort"])
                cp_pull = run_git(
                    ["pull", "--no-rebase", "--autostash", "-X", "ours", "origin", branch],
                    120,
                )
                return cp_pull

            cp = run_git(args)

            is_push = bool(args and str(args[0]).lower() == "push")
            err_text = ((cp.stderr or "") + "\n" + (cp.stdout or "")).lower()
            if is_push and cp.returncode != 0 and (
                "non-fast-forward" in err_text
                or "[rejected]" in err_text
                or "fetch first" in err_text
                or "behind its remote counterpart" in err_text
            ):
                branch_cp = run_git(["rev-parse", "--abbrev-ref", "HEAD"])
                branch = (branch_cp.stdout or "main").strip() or "main"
                pull = reconcile(branch)
                if pull.returncode == 0:
                    cp = run_git(args)

            if check and cp.returncode != 0:
                msg = (cp.stderr or cp.stdout or "git command failed").strip()[:1500]
                raise RuntimeError(msg)
            return cp

        def robust_pull(repo, branch):
            cp = hidden_run_git(
                repo,
                ["pull", "--rebase", "--autostash", "origin", branch],
                timeout=120,
                check=False,
            )
            if cp.returncode == 0:
                return
            hidden_run_git(repo, ["rebase", "--abort"], timeout=30, check=False)
            cp = hidden_run_git(
                repo,
                ["pull", "--no-rebase", "--autostash", "-X", "ours", "origin", branch],
                timeout=120,
                check=False,
            )
            if cp.returncode != 0:
                msg = (cp.stderr or cp.stdout or "git pull failed").strip()[:1500]
                raise RuntimeError(msg)

        github_sync._run_git = hidden_run_git
        github_sync._pull = robust_pull

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

    # Publish compact TMBT Next-only state so ChatGPT can evaluate current
    # Databento readiness and automated research without raw market data.
    original_publish_state = github_sync._publish_state

    def publish_state_with_tmbt_next(repo):
        changed = original_publish_state(repo)
        changed |= github_sync._write_if_changed(
            repo / "state" / "historical.json",
            historical_store.status(github_sync.WORKSPACE),
        )
        changed |= github_sync._write_if_changed(
            repo / "state" / "research_scheduler.json",
            _read_scheduler_state(github_sync.WORKSPACE),
        )
        seasonal = seasonality_context.load_cache(github_sync.WORKSPACE)
        if seasonal:
            changed |= github_sync._write_if_changed(
                repo / "state" / "seasonality.json",
                seasonal,
            )
        latest = _read_json_file(github_sync.WORKSPACE / "research_reports" / "latest.json")
        if latest:
            changed |= github_sync._write_if_changed(repo / "reports" / "latest.json", latest)
            analysis = latest.get("analysis") or {}
            profile = str(analysis.get("profile") or "").strip()
            if profile:
                changed |= github_sync._write_if_changed(
                    repo / "reports" / f"{profile}_latest.json",
                    latest,
                )
        return changed

    github_sync._publish_state = publish_state_with_tmbt_next
    github_sync.daemon()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
