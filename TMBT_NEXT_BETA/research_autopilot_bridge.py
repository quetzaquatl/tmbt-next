from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import legacy_runtime
import legacy_research_adapter

HERE = Path(__file__).resolve().parent


def _win_no_window() -> int:
    return getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0


def workspace() -> Path:
    return Path(os.environ.get("TMBT_WORKSPACE", r"D:\Projekt model\Trading_Model_Backtest_Studio_WORKSPACE")).resolve()


def root() -> Path:
    return workspace() / "research_autopilot"


def status_path() -> Path:
    return root() / "status.json"


def request_path() -> Path:
    return root() / "request.json"


def cancel_path() -> Path:
    return root() / "cancel.requested"


def log_path() -> Path:
    return root() / "autopilot.log"


def _read_json(path: Path) -> dict[str, Any]:
    try:
        d = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
        return d if isinstance(d, dict) else {}
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


def profiles() -> dict[str, Any]:
    try:
        from legacy_research_adapter import activate
        mods = activate()
        return mods["research_autopilot"].profiles()
    except Exception as exc:
        return {"_error": {"label": f"{type(exc).__name__}: {exc}"}}


def latest_report() -> dict[str, Any]:
    return _read_json(root() / "latest_report.json")


def research_requirements(profile: str) -> dict[str, int]:
    p = str(profile).upper()
    if p.startswith("NQ_EBP_") or p.startswith("ES_EBP_"):
        return {"min_dev_trades": 250, "min_val_trades": 100}
    if "_TTFM_" in p:
        return {"min_dev_trades": 200, "min_val_trades": 80}
    if p.startswith(("NQ_SILVER_BULLET_", "ES_SILVER_BULLET_", "GC_")):
        return {"min_dev_trades": 200, "min_val_trades": 80}
    if p.startswith("XAU_"):
        return {"min_dev_trades": 100, "min_val_trades": 40}
    return {"min_dev_trades": 100, "min_val_trades": 50}


def status() -> dict[str, Any]:
    st = _read_json(status_path())
    pid = int(st.get("pid") or 0)
    st["running"] = bool(st.get("running") and _pid_alive(pid))
    st["pid"] = pid or None
    st["workspace"] = str(workspace())
    st["runtime"] = legacy_runtime.status()
    st["worker"] = str(HERE / "legacy_autopilot_worker.py")
    st["available_profiles"] = profiles()
    st["latest_report"] = latest_report()
    return st


def start(
    profile: str,
    *,
    test_news: bool = True,
    tick_audit: bool = False,
    optimizer_overrides: list[dict[str, Any]] | None = None,
    cycle_round: int | None = None,
    requested_by: str = "TMBT Next",
) -> dict[str, Any]:
    st = status()
    if st.get("running"):
        return {"started": False, "reason": "already_running", "status": st}

    available = profiles()
    if profile not in available or profile == "_error":
        return {"started": False, "reason": f"unknown_profile:{profile}", "profiles": available}

    legacy_runtime.ensure_runtime()
    root().mkdir(parents=True, exist_ok=True)
    cancel_path().unlink(missing_ok=True)
    news = legacy_research_adapter.news_status()
    effective_test_news = bool(test_news and news.get("ready"))
    requirements = research_requirements(profile)
    request = {
        "profile": profile,
        "test_news_requested": bool(test_news),
        "test_news": effective_test_news,
        "news_status": news,
        "min_dev_trades": requirements["min_dev_trades"],
        "min_val_trades": requirements["min_val_trades"],
        "review_gate_version": "strict-live-v2",
        "history_split_mode": "full-history-70-15-15-v1",
        # Databento purchase is OHLCV-1m. Do not claim tick-exact validation.
        "tick_audit": bool(tick_audit),
        "requested_at_utc": datetime.now(timezone.utc).isoformat(),
        "requested_by": requested_by,
        "cycle_round": cycle_round,
        "optimizer_overrides": optimizer_overrides or [],
    }
    _write_json(request_path(), request)

    flags = _win_no_window()
    log = open(log_path(), "a", encoding="utf-8", buffering=1)
    try:
        proc = subprocess.Popen(
            [sys.executable, str(HERE / "legacy_autopilot_worker.py")],
            cwd=str(HERE),
            env={**os.environ.copy(), "TMBT_WORKSPACE": str(workspace())},
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            creationflags=flags,
        )
    except Exception:
        log.close()
        raise
    _write_json(
        status_path(),
        {
            "pid": proc.pid,
            "running": True,
            "state": "STARTING",
            "profile": profile,
            "started_at_utc": datetime.now(timezone.utc).isoformat(),
            "message": "TMBT Next Research Autopilot startet",
        },
    )
    return {"started": True, "pid": proc.pid, "profile": profile, "status": status()}


def stop() -> dict[str, Any]:
    root().mkdir(parents=True, exist_ok=True)
    cancel_path().write_text(datetime.now(timezone.utc).isoformat(), encoding="utf-8")
    st = _read_json(status_path())
    st["cancel_requested"] = True
    st["state"] = "CANCELLING" if st.get("running") else st.get("state", "STOPPED")
    _write_json(status_path(), st)
    return {"cancel_requested": True, "status": status()}


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("action", choices=["status", "start", "stop", "profiles"], nargs="?", default="status")
    p.add_argument("--profile", default="NQ_EBP_H1")
    args = p.parse_args()
    if args.action == "start":
        value = start(args.profile)
    elif args.action == "stop":
        value = stop()
    elif args.action == "profiles":
        value = profiles()
    else:
        value = status()
    print(json.dumps(value, ensure_ascii=False, indent=2, default=str))
