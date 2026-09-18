from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
WORKSPACE = Path(os.environ.get("TMBT_WORKSPACE", r"D:\Projekt model\Trading_Model_Backtest_Studio_WORKSPACE")).resolve()
CONFIG = WORKSPACE / "github_sync_config.json"
STATUS = WORKSPACE / "github_sync_status.json"
DEFAULT_REPO = WORKSPACE / "github_research_repo"


def _win_no_window() -> int:
    return getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0


def _read_json(path: Path) -> dict[str, Any]:
    try:
        x = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
        return x if isinstance(x, dict) else {}
    except Exception:
        return {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    os.replace(tmp, path)


def _pid_alive(pid: Any) -> bool:
    try:
        pid = int(pid)
    except Exception:
        return False
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            cp = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=5,
                creationflags=_win_no_window(),
            )
            return str(pid).encode("ascii") in (cp.stdout or b"")
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def _git(repo: Path, *args: str) -> str:
    try:
        cp = subprocess.run(
            ["git", "-C", str(repo), *args],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, timeout=8, creationflags=_win_no_window(),
        )
        return (cp.stdout or "").strip() if cp.returncode == 0 else ""
    except Exception:
        return ""


def ensure_config() -> dict[str, Any]:
    cfg = _read_json(CONFIG)
    repo = Path(str(cfg.get("repo_dir") or DEFAULT_REPO)).expanduser().resolve()
    remote = _git(repo, "remote", "get-url", "origin") if (repo / ".git").exists() else ""

    # The user explicitly requested migration of the old remote research
    # capability. If the known old research clone exists, enable its daemon.
    if not cfg and (repo / ".git").exists():
        cfg = {
            "enabled": True,
            "repo_dir": str(repo),
            "branch": "main",
            "poll_seconds": 30,
            "heartbeat_seconds": 120,
            "auto_pull": True,
            "auto_push": True,
            "accept_commands": True,
            "publish_runs": True,
            "publish_live": False,
            "live_source": "twelve",
            "live_markets": ["NQ", "ES", "XAU"],
            "live_timeframes": ["5m", "15m", "1H", "4H", "1D"],
            "live_limit": 300,
            "migrated_to_tmbt_next": True,
        }
        _write_json(CONFIG, cfg)
    elif cfg:
        changed = False
        if "repo_dir" not in cfg:
            cfg["repo_dir"] = str(repo); changed = True
        # Stop duplicating live bars into the research Git clone. Live data now
        # has one canonical home: workspace/live_data.
        if cfg.get("publish_live", True):
            cfg["publish_live"] = False; changed = True
        if cfg.get("enabled") is not True and (repo / ".git").exists() and "tmbt-research-sync" in remote:
            cfg["enabled"] = True; changed = True
        if changed:
            cfg["migrated_to_tmbt_next"] = True
            cfg["updated_at_utc"] = datetime.now(timezone.utc).isoformat()
            _write_json(CONFIG, cfg)
    return cfg


def status() -> dict[str, Any]:
    cfg = ensure_config()
    st = _read_json(STATUS)
    repo = Path(str(cfg.get("repo_dir") or DEFAULT_REPO)).expanduser().resolve()
    pid = int(st.get("pid") or 0)
    heartbeat = {}
    try:
        heartbeat = _read_json(repo / "state" / "heartbeat.json")
    except Exception:
        pass
    st.update({
        "running": bool(st.get("running") and _pid_alive(pid)),
        "pid": pid or None,
        "enabled": bool(cfg.get("enabled")),
        "repo_dir": str(repo),
        "repo_exists": (repo / ".git").exists(),
        "remote": _git(repo, "remote", "get-url", "origin"),
        "branch": str(cfg.get("branch") or "main"),
        "accept_commands": bool(cfg.get("accept_commands", True)),
        "publish_live": bool(cfg.get("publish_live", False)),
        "heartbeat": heartbeat,
        "worker": str(HERE / "legacy_github_sync_worker.py"),
    })
    return st


def start() -> dict[str, Any]:
    cfg = ensure_config()
    st = status()
    if st.get("running"):
        return {"started": False, "reason": "already_running", "status": st}
    if not cfg.get("enabled"):
        return {"started": False, "reason": "sync_disabled", "status": st}
    repo = Path(str(cfg.get("repo_dir") or DEFAULT_REPO)).expanduser().resolve()
    if not (repo / ".git").exists():
        return {"started": False, "reason": f"research_sync_repo_missing:{repo}", "status": st}

    flags = _win_no_window()
    log = open(WORKSPACE / "github_sync.log", "a", encoding="utf-8", buffering=1)
    try:
        proc = subprocess.Popen(
            [sys.executable, str(HERE / "legacy_github_sync_worker.py")],
            cwd=str(HERE),
            env={**os.environ.copy(), "TMBT_WORKSPACE": str(WORKSPACE)},
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            creationflags=flags,
        )
    except Exception:
        log.close()
        raise
    base = _read_json(STATUS)
    base.update({
        "pid": proc.pid,
        "running": True,
        "state": "starting",
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "last_error": "",
    })
    _write_json(STATUS, base)
    return {"started": True, "pid": proc.pid, "status": status()}


def stop() -> dict[str, Any]:
    st = status()
    pid = int(st.get("pid") or 0)
    if pid and _pid_alive(pid):
        try:
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], timeout=10, creationflags=_win_no_window())
            else:
                os.kill(pid, 15)
        except Exception as exc:
            return {"stopped": False, "error": str(exc), "status": status()}
    base = _read_json(STATUS)
    base.update({"running": False, "state": "stopped", "stopped_at_utc": datetime.now(timezone.utc).isoformat()})
    _write_json(STATUS, base)
    return {"stopped": True, "status": status()}


if __name__ == "__main__":
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("action",choices=["status","start","stop"],nargs="?",default="status")
    a=p.parse_args()
    out = start() if a.action=="start" else stop() if a.action=="stop" else status()
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
