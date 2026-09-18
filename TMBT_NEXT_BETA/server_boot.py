from __future__ import annotations

import json
import os
import runpy
import subprocess
import sys
from pathlib import Path


def workspace() -> Path:
    return Path(os.environ.get("TMBT_WORKSPACE", r"D:\Projekt model\Trading_Model_Backtest_Studio_WORKSPACE")).resolve()


def read_json(path: Path) -> dict:
    try:
        x = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
        return x if isinstance(x, dict) else {}
    except Exception:
        return {}


def pid_alive(pid) -> bool:
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
            )
            return str(pid).encode("ascii") in (r.stdout or b"")
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def collector_status_path() -> Path:
    return workspace() / "live_data" / "twelve_status.json"


def guardian_status_path() -> Path:
    return workspace() / "live_data" / "tmbt_feed_guardian_status.json"


def start_feed_guardian() -> None:
    script = Path(__file__).resolve().parent / "feed_guardian.py"
    if not script.exists():
        print("Feed guardian: missing", script)
        return
    try:
        subprocess.Popen(
            [sys.executable, str(script)],
            cwd=str(script.parent),
            env=os.environ.copy(),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) if os.name == "nt" else 0,
        )
        print("Feed guardian: start requested")
    except Exception as exc:
        print("Feed guardian: start failed:", exc)


def print_collector_status() -> None:
    st = read_json(collector_status_path())
    print("Original Twelve collector (owned by Old Studio):")
    print("  status:", collector_status_path())
    if not st:
        print("  state: no status file")
        return
    alive = pid_alive(st.get("pid"))
    print(
        "  state:", st.get("state") or "unknown",
        "· connected:", bool(st.get("connected")),
        "· running PID:", st.get("pid") if alive else "no",
    )
    if st.get("last_error") and not st.get("connected"):
        print("  last_error:", str(st.get("last_error"))[:500])
    print("  note: Feed Guardian will restart the existing collector when needed.")


print("========================================")
print("TMBT NEXT · ACTIVE DESK")
print("========================================")
print("Workspace:", workspace())
start_feed_guardian()
print_collector_status()
print("Guardian status:", guardian_status_path())
print("Starting focused live desk + 6-instance EBP matrix: NQ/ES x 15m/30m/1H")
print("QQQ/SPY proxy feeds remain monitoring-only until true futures data is attached.")

runpy.run_module("server_active", run_name="__main__")
