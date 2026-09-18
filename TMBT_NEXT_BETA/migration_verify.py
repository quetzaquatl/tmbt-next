from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import historical_store
import legacy_runtime
import research_autopilot_bridge
import research_sync_bridge

WORKSPACE = Path(
    os.environ.get(
        "TMBT_WORKSPACE",
        r"D:\Projekt model\Trading_Model_Backtest_Studio_WORKSPACE",
    )
).resolve()
OLD_ROOT = Path(
    os.environ.get(
        "TMBT_OLD_STUDIO_ROOT",
        r"D:\Projekt model\Trading_Model_Backtest_Studio_v3_7_DEV",
    )
).resolve()


def _win_no_window() -> int:
    return getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0


def _old_processes() -> list[dict[str, Any]]:
    if os.name != "nt":
        return []

    # Pass OLD_ROOT through the environment instead of embedding it into the
    # PowerShell command line. That prevents the verifier from matching its own
    # helper process merely because the searched path appears in -Command.
    ps = (
        "$old=$env:TMBT_VERIFY_OLD_ROOT; "
        "Get-CimInstance Win32_Process | "
        "Where-Object { "
        "$_.CommandLine -and "
        "$_.CommandLine -like ('*' + $old + '*') -and "
        "$_.Name -match '^(python|pythonw|streamlit|cmd)\\.exe$' "
        "} | "
        "Select-Object ProcessId,Name,CommandLine | ConvertTo-Json -Compress"
    )
    env = os.environ.copy()
    env["TMBT_VERIFY_OLD_ROOT"] = str(OLD_ROOT)

    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            capture_output=True,
            text=True,
            timeout=10,
            env=env,
            creationflags=_win_no_window(),
        )
        raw = (r.stdout or "").strip()
        if not raw:
            return []
        x = json.loads(raw)
        return x if isinstance(x, list) else [x]
    except Exception:
        return []


def _workspace_refs() -> list[str]:
    needle = str(OLD_ROOT).lower()
    hits: list[str] = []
    for p in WORKSPACE.rglob("*"):
        try:
            if not p.is_file() or p.stat().st_size > 5_000_000:
                continue
        except Exception:
            continue
        if p.suffix.lower() not in {".json", ".txt", ".md", ".cmd", ".bat", ".ps1"}:
            continue
        try:
            txt = p.read_text(encoding="utf-8", errors="ignore").lower()
        except Exception:
            continue
        if needle in txt:
            hits.append(str(p))
    return hits[:500]


def main() -> int:
    runtime: dict[str, Any] = {}
    runtime_error = ""
    try:
        legacy_runtime.ensure_runtime()
        runtime = legacy_runtime.status()
    except Exception as exc:
        runtime_error = f"{type(exc).__name__}: {exc}"

    hist = historical_store.status(WORKSPACE)
    research = research_autopilot_bridge.status()
    remote_sync = research_sync_bridge.status()
    old_processes = _old_processes()
    refs = _workspace_refs()

    profiles = research.get("available_profiles") or {}
    checks = {
        "migration_bundle_available": bool(runtime.get("bundle_exists")),
        "compatibility_runtime_ready": bool(runtime.get("runtime_exists")),
        "databento_db_ready": bool(hist.get("db_exists")),
        "research_profiles_ready": "NQ_EBP_H1" in profiles and "ES_EBP_H1" in profiles,
        "remote_research_sync_ready": bool(
            remote_sync.get("repo_exists") and remote_sync.get("accept_commands")
        ),
        "no_running_old_studio_processes": len(old_processes) == 0,
        "no_workspace_config_references_to_old_root": len(refs) == 0,
    }
    ready_to_archive_old_source = all(checks.values())

    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "workspace": str(WORKSPACE),
        "old_root": str(OLD_ROOT),
        "old_root_exists": OLD_ROOT.exists(),
        "checks": checks,
        "ready_to_archive_old_source": ready_to_archive_old_source,
        "runtime": runtime,
        "runtime_error": runtime_error,
        "historical": hist,
        "research": {
            "running": research.get("running"),
            "state": research.get("state"),
            "available_profiles": profiles,
        },
        "remote_research_sync": remote_sync,
        "old_root_processes": old_processes,
        "workspace_old_root_references": refs,
    }

    out = WORKSPACE / "migration" / "migration_verification.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    print("Migration verification:", out)
    for key, value in checks.items():
        print(("PASS" if value else "WARN"), key)
    print("Ready to archive old Studio source:", ready_to_archive_old_source)

    if refs:
        print("Workspace references still pointing at old Studio:")
        for p in refs[:20]:
            print(" -", p)
    if old_processes:
        print("Old Studio processes still running:", len(old_processes))
        for proc in old_processes[:10]:
            print(
                " - PID",
                proc.get("ProcessId"),
                proc.get("Name"),
                str(proc.get("CommandLine") or "")[:500],
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
