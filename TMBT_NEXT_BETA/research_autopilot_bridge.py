from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


def workspace() -> Path:
    return Path(os.environ.get("TMBT_WORKSPACE", r"D:\Projekt model\Trading_Model_Backtest_Studio_WORKSPACE")).resolve()


def old_root() -> Path:
    return Path(os.environ.get(
        "TMBT_OLD_STUDIO_ROOT",
        r"D:\Projekt model\Trading_Model_Backtest_Studio_v3_7_DEV",
    )).resolve()


def script_path() -> Path:
    return Path(os.environ.get("TMBT_RESEARCH_AUTOPILOT_PATH", str(old_root() / "research_autopilot.py"))).resolve()


def python_path() -> Path:
    configured = os.environ.get("TMBT_RESEARCH_PYTHON")
    if configured:
        return Path(configured).resolve()
    candidate = old_root() / ".venv" / "Scripts" / "python.exe"
    return candidate if candidate.exists() else Path(sys.executable)


def pid_path() -> Path:
    return workspace() / "research_jobs" / "tmbt_research_autopilot.pid"


def _pid_alive(pid: Any) -> bool:
    try:
        pid = int(pid)
    except Exception:
        return False
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            r = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                timeout=4,
                text=True,
            )
            return str(pid) in (r.stdout or "")
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def _published_pid() -> int | None:
    try:
        pid = int(pid_path().read_text(encoding="utf-8").strip())
        return pid if _pid_alive(pid) else None
    except Exception:
        return None


def _windows_worker_pids() -> list[int]:
    if os.name != "nt":
        return []
    ps = (
        "Get-CimInstance Win32_Process | "
        "Where-Object { $_.CommandLine -match 'research_autopilot\.py' -and $_.CommandLine -match '--worker' } | "
        "Select-Object -ExpandProperty ProcessId"
    )
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=8,
            text=True,
        )
        return [int(x.strip()) for x in (r.stdout or "").splitlines() if x.strip().isdigit()]
    except Exception:
        return []


def worker_pids() -> list[int]:
    pids = _windows_worker_pids()
    published = _published_pid()
    if published and published not in pids:
        pids.append(published)
    return sorted(set(pids))


def legacy_status() -> dict[str, Any]:
    script = script_path()
    py = python_path()
    if not script.exists():
        return {"ok": False, "error": f"missing autopilot script: {script}"}
    try:
        r = subprocess.run(
            [str(py), str(script), "--status"],
            cwd=str(script.parent),
            env={**os.environ.copy(), "TMBT_WORKSPACE": str(workspace())},
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=15,
            text=True,
        )
        return {
            "ok": r.returncode == 0,
            "returncode": r.returncode,
            "output": (r.stdout or "").strip()[-6000:],
        }
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def status() -> dict[str, Any]:
    pids = worker_pids()
    return {
        "running": bool(pids),
        "pids": pids,
        "script": str(script_path()),
        "python": str(python_path()),
        "workspace": str(workspace()),
        "script_exists": script_path().exists(),
        "legacy_status": legacy_status(),
    }


def start() -> dict[str, Any]:
    current = worker_pids()
    if current:
        return {"started": False, "reason": "already_running", "pids": current, "status": status()}

    script = script_path()
    py = python_path()
    if not script.exists():
        return {"started": False, "reason": f"missing script: {script}", "status": status()}

    pid_path().parent.mkdir(parents=True, exist_ok=True)
    flags = 0
    if os.name == "nt":
        flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(subprocess, "DETACHED_PROCESS", 0)
    try:
        proc = subprocess.Popen(
            [str(py), str(script), "--worker"],
            cwd=str(script.parent),
            env={**os.environ.copy(), "TMBT_WORKSPACE": str(workspace())},
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=flags,
        )
        pid_path().write_text(str(proc.pid), encoding="utf-8")
        return {"started": True, "pid": proc.pid, "status": status()}
    except Exception as exc:
        return {"started": False, "reason": f"{type(exc).__name__}: {exc}", "status": status()}


def stop() -> dict[str, Any]:
    pids = worker_pids()
    stopped = []
    errors = []
    for pid in pids:
        try:
            if os.name == "nt":
                r = subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], timeout=8)
                if r.returncode == 0:
                    stopped.append(pid)
                else:
                    errors.append({"pid": pid, "returncode": r.returncode})
            else:
                os.kill(pid, 15)
                stopped.append(pid)
        except Exception as exc:
            errors.append({"pid": pid, "error": str(exc)})
    try:
        pid_path().unlink(missing_ok=True)
    except Exception:
        pass
    return {"stopped": stopped, "errors": errors, "status": status()}


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("action", choices=["status", "start", "stop"], nargs="?", default="status")
    args = p.parse_args()
    result = {"status": status(), "start": start, "stop": stop}
    value = result["status"] if args.action == "status" else result[args.action]()
    print(json.dumps(value, indent=2))
