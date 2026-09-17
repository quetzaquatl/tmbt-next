from __future__ import annotations

import json
import os
import runpy
import subprocess
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
            # Keep this byte-based. Windows tasklist output is not guaranteed to
            # use the Python process' active text codepage and previously caused
            # repeated UnicodeDecodeError reader-thread failures.
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


def show_collector_status() -> None:
    status_path = workspace() / "live_data" / "twelve_status.json"
    st = read_json(status_path)
    print("Original Twelve collector:")
    print("  status:", status_path)
    if not st:
        print("  state: no status file")
        return
    alive = pid_alive(st.get("pid"))
    print(
        "  state:", st.get("state") or "unknown",
        "· connected:", bool(st.get("connected")),
        "· running PID:", st.get("pid") if alive else "no",
    )
    if st.get("last_error"):
        print("  last_error:", str(st.get("last_error"))[:500])
    if not alive:
        print("  note: collector is NOT auto-started by TMBT Next. UI startup must never mutate the market-data pipeline.")


show_collector_status()

# Start only the UI server. Market-data collectors are deliberately managed
# separately so a missing credential or old collector cannot corrupt/replace
# otherwise working NQ/ES feeds when the desk is opened.
runpy.run_module("server_desk", run_name="__main__")
