from __future__ import annotations

import json
import os
import runpy
import socket
import threading
import time
import webbrowser
import subprocess
import sys
from pathlib import Path

import research_autopilot_bridge
import legacy_runtime
import research_sync_bridge
import research_scheduler
import feed_guardian


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
        st = read_json(guardian_status_path())
        old_pid = int(st.get("pid") or 0)
        old_generation = str(st.get("guardian_generation") or "")
        expected_generation = str(feed_guardian.GUARDIAN_GENERATION)

        if old_pid and pid_alive(old_pid) and old_generation == expected_generation:
            print("Feed guardian: already current · PID", old_pid)
            return

        if old_pid and pid_alive(old_pid) and old_generation != expected_generation:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/PID", str(old_pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=8,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
            else:
                os.kill(old_pid, 15)

        subprocess.Popen(
            [sys.executable, str(script)],
            cwd=str(script.parent),
            env=os.environ.copy(),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0,
        )
        print("Feed guardian: start requested · generation", expected_generation)
    except Exception as exc:
        print("Feed guardian: start failed:", exc)


def prepare_legacy_runtime() -> None:
    try:
        root = legacy_runtime.ensure_runtime()
        print("Migration runtime:", root)
        print("Old Studio directory dependency: none")
    except Exception as exc:
        print("Migration runtime unavailable:", exc)


def _start_migrated_worker(script_name: str, status_rel: str, args: list[str], *, force_restart: bool = False) -> dict:
    status_path = workspace() / status_rel
    try:
        st = read_json(status_path)
        pid = int(st.get("pid") or 0)
        if pid and pid_alive(pid) and not force_restart:
            return {
                "ok": True,
                "started": False,
                "pid": pid,
                "state": st.get("state") or "running",
                "status": str(status_path),
            }
        if pid and pid_alive(pid) and force_restart:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/PID", str(pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=8,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
            else:
                os.kill(pid, 15)

        script = legacy_runtime.script(script_name)
        cmd = [sys.executable, str(script), *args]
        proc = subprocess.Popen(
            cmd,
            cwd=str(script.parent),
            env=os.environ.copy(),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0,
        )
        return {
            "ok": True,
            "started": True,
            "pid": proc.pid,
            "state": "start_requested",
            "status": str(status_path),
            "script": str(script),
        }
    except Exception as exc:
        return {
            "ok": False,
            "started": False,
            "state": "error",
            "error": f"{type(exc).__name__}: {exc}",
            "status": str(status_path),
        }


def start_migrated_live_workers() -> None:
    signal = _start_migrated_worker(
        "live_signal_agent.py",
        r"live_signals\agent_status.json",
        ["--run"],
        force_restart=True,
    )
    paper = _start_migrated_worker(
        "paper_trader.py",
        r"paper_account\agent_status.json",
        ["--run"],
    )
    print(
        "Live signal agent:",
        signal.get("state"),
        "· PID:", signal.get("pid") or "—",
        "· started:", bool(signal.get("started")),
    )
    if signal.get("error"):
        print("  error:", signal.get("error"))
    print(
        "Paper trader:",
        paper.get("state"),
        "· PID:", paper.get("pid") or "—",
        "· started:", bool(paper.get("started")),
    )
    if paper.get("error"):
        print("  error:", paper.get("error"))


def start_research_sync() -> None:
    try:
        result = research_sync_bridge.start()
        st = result.get("status") or {}
        print(
            "Research remote sync:",
            st.get("state") or result.get("reason") or "unknown",
            "· running:", bool(st.get("running")),
            "· remote:", st.get("remote") or "—",
        )
    except Exception as exc:
        print("Research remote sync start failed:", exc)


def start_research_scheduler() -> None:
    try:
        result = research_scheduler.start_background()
        st = result.get("status") or {}
        print(
            "Research scheduler:",
            st.get("state") or result.get("reason") or "unknown",
            "· running:", bool(st.get("running")),
        )
    except Exception as exc:
        print("Research scheduler start failed:", exc)


def print_research_status() -> None:
    try:
        st = research_autopilot_bridge.status()
        print("Research autopilot:", st.get("state") or "idle", "· running:", bool(st.get("running")))
    except Exception as exc:
        print("Research autopilot status failed:", exc)


def start_browser_after_server_ready() -> None:
    """Open the Studio only after the HTTP server is actually reachable.

    The old launcher opened the URL before server_active had bound the port.
    During Windows logon this could create a failed/ignored browser launch.
    """
    if str(os.environ.get("TMBT_AUTO_OPEN_BROWSER", "1")).strip().lower() in {"0", "false", "no", "off"}:
        print("Browser auto-open: disabled by TMBT_AUTO_OPEN_BROWSER")
        return

    try:
        port = int(os.environ.get("TMBT_NEXT_PORT", "8510"))
    except Exception:
        port = 8510

    url = f"http://127.0.0.1:{port}/?v=0964"

    def worker() -> None:
        deadline = time.monotonic() + 75.0
        ready = False
        while time.monotonic() < deadline:
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                    ready = True
                    break
            except OSError:
                time.sleep(0.5)

        if not ready:
            print("Browser auto-open: server did not become reachable within 75s")
            return

        print("Browser auto-open:", url)
        try:
            if os.name == "nt" and hasattr(os, "startfile"):
                os.startfile(url)  # type: ignore[attr-defined]
                return
        except Exception:
            pass

        try:
            if webbrowser.open(url, new=2):
                return
        except Exception:
            pass

        if os.name == "nt":
            try:
                subprocess.Popen(
                    ["cmd", "/c", "start", "", url],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
            except Exception as exc:
                print("Browser auto-open failed:", exc)

    threading.Thread(target=worker, name="tmbt-browser-opener", daemon=True).start()
    print("Browser auto-open: waiting for server on port", port)


def print_collector_status() -> None:
    st = read_json(collector_status_path())
    print("Twelve collector (TMBT migration runtime):")
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
    print("  note: Feed Guardian restarts the migrated collector when needed.")


print("========================================")
print("TMBT NEXT · ACTIVE DESK")
print("========================================")
print("Workspace:", workspace())
prepare_legacy_runtime()
start_feed_guardian()
start_migrated_live_workers()
start_research_sync()
start_research_scheduler()
print_research_status()
print_collector_status()
print("Guardian status:", guardian_status_path())
print("Starting focused live desk + 6-instance EBP matrix: NQ/ES x 15m/30m/1H")
print("QQQ/SPY proxy feeds remain monitoring-only until true futures data is attached.")
start_browser_after_server_ready()

runpy.run_module("server_active", run_name="__main__")
