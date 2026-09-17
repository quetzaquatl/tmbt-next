from __future__ import annotations

import json
import os
import runpy
import subprocess
import sys
import time
from pathlib import Path


def workspace() -> Path:
    return Path(os.environ.get("TMBT_WORKSPACE", r"D:\Projekt model\Trading_Model_Backtest_Studio_WORKSPACE")).resolve()


def collector_dir() -> Path:
    return Path(os.environ.get("TMBT_TWELVE_DIR", r"D:\Projekt model\Trading_Model_Backtest_Studio_v3_7_DEV")).resolve()


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
                capture_output=True,
                text=True,
                timeout=4,
            )
            return str(pid) in (r.stdout or "") and "No tasks" not in (r.stdout or "")
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def collector_status_path() -> Path:
    return workspace() / "live_data" / "twelve_status.json"


def current_collector() -> dict:
    st = read_json(collector_status_path())
    st["pid_alive"] = pid_alive(st.get("pid"))
    return st


def choose_python(app_dir: Path) -> Path:
    candidates = [
        app_dir / "venv" / "Scripts" / "python.exe",
        app_dir / ".venv" / "Scripts" / "python.exe",
    ]
    for p in candidates:
        if p.exists():
            return p
    return Path(sys.executable)


def start_original_twelve_collector() -> None:
    ws = workspace()
    app_dir = collector_dir()
    script = app_dir / "twelve_live.py"
    status_path = collector_status_path()

    print("Original Twelve collector:")
    print("  app:", app_dir)
    print("  status:", status_path)

    if not script.exists():
        print("  ERROR: twelve_live.py not found. Set TMBT_TWELVE_DIR if the old studio moved.")
        return

    st = current_collector()
    if st.get("pid_alive") and st.get("running") is not False:
        print("  already running · PID", st.get("pid"), "· state", st.get("state") or "unknown")
        return

    py = choose_python(app_dir)
    env = os.environ.copy()
    env["TMBT_WORKSPACE"] = str(ws)
    log_dir = ws / "live_data"
    log_dir.mkdir(parents=True, exist_ok=True)
    boot_log = log_dir / "twelve_boot.log"

    kwargs = {
        "cwd": str(app_dir),
        "env": env,
        "stdin": subprocess.DEVNULL,
        "stdout": open(boot_log, "a", encoding="utf-8", buffering=1),
        "stderr": subprocess.STDOUT,
    }
    if os.name == "nt":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    else:
        kwargs["start_new_session"] = True

    try:
        proc = subprocess.Popen([str(py), str(script), "--run"], **kwargs)
    except Exception as exc:
        print("  ERROR starting collector:", exc)
        return

    print("  started · PID", proc.pid, "· python", py)
    print("  log:", boot_log)

    # Wait briefly for twelve_live.py to publish its own status. This gives a
    # useful startup diagnosis without blocking the desk for long.
    deadline = time.time() + 12
    last = {}
    while time.time() < deadline:
        time.sleep(0.75)
        last = current_collector()
        state = str(last.get("state") or "").lower()
        if last.get("connected") or state in {"polling", "backfill", "error", "quota_pause", "rate_limit_pause"}:
            break

    if last:
        print(
            "  state:", last.get("state") or "unknown",
            "· connected:", bool(last.get("connected")),
            "· PID:", last.get("pid") or proc.pid,
        )
        if last.get("last_error"):
            print("  last_error:", str(last.get("last_error"))[:500])
    else:
        print("  waiting for collector status update ...")


start_original_twelve_collector()

# Start the new UI server after the original data writer has been ensured.
runpy.run_module("server_desk", run_name="__main__")
