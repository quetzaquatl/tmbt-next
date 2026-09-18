from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import legacy_runtime

WORKSPACE = Path(os.environ.get("TMBT_WORKSPACE", r"D:\\Projekt model\\Trading_Model_Backtest_Studio_WORKSPACE")).resolve()
HERE = Path(__file__).resolve().parent
STATUS = WORKSPACE / "live_data" / "tmbt_feed_guardian_status.json"
TWELVE_STATUS = WORKSPACE / "live_data" / "twelve_status.json"
DATA_SETTINGS = WORKSPACE / "live_data" / "tmbt_data_settings.json"
PID_FILE = HERE / "feed_guardian.pid"
MASSIVE_PID = HERE / "massive_futures.pid"
CHECK_SECONDS = max(15, int(os.environ.get("TMBT_FEED_GUARDIAN_SECONDS", "30")))
RESTART_COOLDOWN = max(60, int(os.environ.get("TMBT_FEED_RESTART_COOLDOWN", "120")))
DISCONNECTED_GRACE = max(60, int(os.environ.get("TMBT_FEED_DISCONNECTED_GRACE", "180")))
GUARDIAN_GENERATION = "feed-watchdog-v2"

_last_twelve_start = 0.0
_last_massive_start = 0.0
_disconnected_since: float | None = None


def win_no_window() -> int:
    return getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_iso(value: Any) -> datetime | None:
    try:
        if not value:
            return None
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def write_status(**kwargs) -> None:
    cur = read_json(STATUS)
    cur.update(kwargs)
    cur["updated_at_utc"] = now_iso()
    write_json(STATUS, cur)


def secret_env() -> dict[str, str]:
    s = read_json(DATA_SETTINGS)
    out: dict[str, str] = {}
    twelve = str(s.get("twelve_api_key") or "").strip()
    massive = str(s.get("massive_api_key") or "").strip()
    if twelve:
        # Support the common names used by Twelve collectors without exposing
        # the key in the UI or Git repository.
        for name in ("TWELVE_API_KEY", "TWELVEDATA_API_KEY", "TWELVE_DATA_API_KEY", "TMBT_TWELVE_API_KEY"):
            out[name] = twelve
    if massive:
        out["MASSIVE_API_KEY"] = massive
    return out


def pid_alive(pid: Any) -> bool:
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
                creationflags=win_no_window(),
            )
            return str(pid).encode("ascii") in (r.stdout or b"")
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def prevent_duplicate() -> None:
    try:
        old = int(PID_FILE.read_text(encoding="utf-8").strip())
    except Exception:
        old = 0
    if old and old != os.getpid() and pid_alive(old):
        raise SystemExit(f"feed guardian already running as PID {old}")
    PID_FILE.write_text(str(os.getpid()), encoding="utf-8")


def _candidate_from_status(st: dict[str, Any]) -> Path | None:
    for key in ("script", "path", "launcher", "collector", "collector_path"):
        raw = st.get(key)
        if not raw:
            continue
        try:
            p = Path(str(raw).strip('"')).expanduser()
            if p.exists() and p.is_file():
                return p.resolve()
        except Exception:
            pass
    return None


def _score_candidate(path: Path) -> int:
    name = path.name.lower()
    score = 0
    if "twelve" in name:
        score += 8
    if any(x in name for x in ("collector", "writer", "live", "sync", "stream")):
        score += 4
    if name.startswith(("start", "run")):
        score += 2
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")[:120000].lower()
    except Exception:
        text = ""
    if "twelve_status.json" in text:
        score += 12
    if "live_data" in text and "twelve" in text:
        score += 8
    if "api.twelvedata.com" in text or "twelvedata" in text:
        score += 5
    if "tmbt_feed_guardian" in text:
        score -= 50
    return score


def discover_twelve_launcher() -> Path | None:
    # Prefer the native TMBT fast warm-start collector. It reuses the migrated
    # Twelve helpers but avoids a full multi-timeframe REST backfill on every
    # restart once local mirrors already exist.
    fast = HERE / "twelve_fast_collector.py"
    if fast.exists():
        return fast.resolve()

    # Fallback to the self-contained migration runtime.
    try:
        native = legacy_runtime.script("twelve_live.py")
        if native.exists():
            return native.resolve()
    except Exception:
        pass

    explicit = os.environ.get("TMBT_TWELVE_COLLECTOR_PATH", "").strip().strip('"')
    if explicit:
        p = Path(explicit)
        if p.exists() and p.is_file():
            return p.resolve()

    st = read_json(TWELVE_STATUS)
    from_status = _candidate_from_status(st)
    if from_status:
        return from_status

    patterns = (
        "*twelve*collector*.py", "*twelve*writer*.py", "*twelve*live*.py", "*twelve*sync*.py",
        "*Twelve*Collector*.py", "*Twelve*Writer*.py", "*Twelve*Live*.py",
        "*twelve*.bat", "*Twelve*.bat", "*twelve*.cmd", "*Twelve*.cmd", "*twelve*.ps1", "*Twelve*.ps1",
    )
    found: dict[Path, int] = {}
    for pat in patterns:
        try:
            for p in WORKSPACE.rglob(pat):
                if not p.is_file():
                    continue
                # Never recurse into this repo's own helper scripts as a collector candidate.
                if HERE in p.resolve().parents:
                    continue
                s = _score_candidate(p)
                if s > 0:
                    found[p.resolve()] = max(found.get(p.resolve(), -999), s)
        except Exception:
            continue
    # Fallback for older Studio builds whose collector has a generic filename.
    # Scan script contents only when the strong filename search found nothing.
    if not found:
        scanned = 0
        for root in (WORKSPACE, WORKSPACE / "github_research_repo"):
            if not root.exists():
                continue
            for pat in ("*.py", "*.bat", "*.cmd", "*.ps1"):
                try:
                    for p in root.rglob(pat):
                        scanned += 1
                        if scanned > 3000:
                            break
                        if not p.is_file():
                            continue
                        try:
                            rp = p.resolve()
                        except Exception:
                            continue
                        if HERE in rp.parents:
                            continue
                        s = _score_candidate(rp)
                        # Generic filenames need strong content evidence before
                        # they are trusted as a restart target.
                        if s >= 12:
                            found[rp] = max(found.get(rp, -999), s)
                    if scanned > 3000:
                        break
                except Exception:
                    continue
            if scanned > 3000:
                break
    if not found:
        return None
    return max(found.items(), key=lambda kv: kv[1])[0]


def _spawn_file(path: Path) -> subprocess.Popen:
    ext = path.suffix.lower()
    env = os.environ.copy()
    env.update(secret_env())
    env["TMBT_WORKSPACE"] = str(WORKSPACE)
    flags = win_no_window()
    if ext in {".bat", ".cmd"}:
        cmd = ["cmd.exe", "/c", str(path)]
    elif ext == ".ps1":
        cmd = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(path)]
    elif ext == ".py":
        cmd = [sys.executable, str(path)]
        if path.name.lower() == "twelve_live.py":
            cmd.append("--run")
    else:
        raise RuntimeError(f"unsupported collector launcher: {path}")
    return subprocess.Popen(
        cmd,
        cwd=str(path.parent),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=flags,
    )


def start_twelve_collector(reason: str) -> dict[str, Any]:
    global _last_twelve_start
    now = time.time()
    if now - _last_twelve_start < RESTART_COOLDOWN:
        return {"started": False, "reason": "cooldown"}
    _last_twelve_start = now

    explicit_cmd = os.environ.get("TMBT_TWELVE_COLLECTOR_CMD", "").strip()
    try:
        if explicit_cmd:
            env = os.environ.copy()
            env.update(secret_env())
            env["TMBT_WORKSPACE"] = str(WORKSPACE)
            flags = win_no_window()
            p = subprocess.Popen(
                explicit_cmd,
                cwd=str(WORKSPACE),
                env=env,
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=flags,
            )
            return {"started": True, "pid": p.pid, "launcher": "TMBT_TWELVE_COLLECTOR_CMD", "reason": reason}

        launcher = discover_twelve_launcher()
        if not launcher:
            return {
                "started": False,
                "reason": "collector launcher not found",
                "hint": "Run AUDIT_OLD_STUDIO.bat once so TMBT Next can use its self-contained migration runtime.",
            }
        p = _spawn_file(launcher)
        return {"started": True, "pid": p.pid, "launcher": str(launcher), "reason": reason}
    except Exception as exc:
        return {"started": False, "reason": f"start failed: {exc}"}


def ensure_twelve() -> dict[str, Any]:
    global _disconnected_since
    st = read_json(TWELVE_STATUS)
    alive = pid_alive(st.get("pid"))
    connected = bool(st.get("connected"))
    state = str(st.get("state") or "unknown")
    updated = parse_iso(st.get("updated_at_utc"))
    heartbeat_age = (
        max(0.0, (datetime.now(timezone.utc) - updated).total_seconds())
        if updated else None
    )
    try:
        poll_seconds = max(300, int(st.get("poll_seconds") or 420))
    except Exception:
        poll_seconds = 420
    heartbeat_limit = max(900, (poll_seconds * 2) + 120)

    # "connected" alone is insufficient: a wedged collector process can stay
    # alive forever while no longer polling. Quota pause is intentional and
    # must not trigger a restart loop.
    heartbeat_stale = (
        alive
        and connected
        and state != "quota_pause"
        and (heartbeat_age is None or heartbeat_age > heartbeat_limit)
    )
    if heartbeat_stale:
        if os.name == "nt":
            try:
                subprocess.run(
                    ["taskkill", "/PID", str(int(st.get("pid"))), "/T", "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=8,
                    creationflags=win_no_window(),
                )
                time.sleep(1)
            except Exception:
                pass
        launch = start_twelve_collector("collector heartbeat stale")
        return {
            "ok": False,
            "alive": False,
            "connected": False,
            "state": state,
            "heartbeat_age_seconds": heartbeat_age,
            "heartbeat_limit_seconds": heartbeat_limit,
            "restart": launch,
        }

    if alive and connected:
        _disconnected_since = None
        return {
            "ok": True,
            "alive": True,
            "connected": True,
            "state": state,
            "pid": st.get("pid"),
            "heartbeat_age_seconds": heartbeat_age,
            "heartbeat_limit_seconds": heartbeat_limit,
        }

    if alive and not connected:
        if _disconnected_since is None:
            _disconnected_since = time.time()
        age = time.time() - _disconnected_since
        if age < DISCONNECTED_GRACE:
            return {
                "ok": False, "alive": True, "connected": False, "state": state,
                "pid": st.get("pid"), "waiting_seconds": int(DISCONNECTED_GRACE - age),
                "last_error": st.get("last_error"),
            }
        # A live but disconnected collector may be wedged. Kill only the PID published
        # by its own status file, then start the same collector again.
        if os.name == "nt":
            try:
                subprocess.run(["taskkill", "/PID", str(int(st.get("pid"))), "/T", "/F"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=8,
                               creationflags=win_no_window())
                time.sleep(1)
            except Exception:
                pass
        _disconnected_since = None
        launch = start_twelve_collector("published collector disconnected beyond grace")
        return {"ok": False, "alive": False, "connected": False, "state": state, "restart": launch}

    _disconnected_since = None
    launch = start_twelve_collector("collector missing or dead")
    return {"ok": False, "alive": False, "connected": False, "state": state, "restart": launch}


def ensure_massive() -> dict[str, Any]:
    global _last_massive_start
    saved = secret_env()
    api_key = (saved.get("MASSIVE_API_KEY") or os.environ.get("MASSIVE_API_KEY", "")).strip()
    if not api_key:
        return {"enabled": False, "reason": "MASSIVE_API_KEY not set"}
    try:
        pid = int(MASSIVE_PID.read_text(encoding="utf-8").strip())
    except Exception:
        pid = 0
    if pid and pid_alive(pid):
        return {"enabled": True, "running": True, "pid": pid}
    if time.time() - _last_massive_start < RESTART_COOLDOWN:
        return {"enabled": True, "running": False, "reason": "cooldown"}
    _last_massive_start = time.time()
    script = HERE / "massive_futures_bridge.py"
    try:
        flags = win_no_window()
        p = subprocess.Popen(
            [sys.executable, str(script)],
            cwd=str(HERE),
            env={**os.environ.copy(), **secret_env()},
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=flags,
        )
        return {"enabled": True, "running": True, "pid": p.pid, "started": True}
    except Exception as exc:
        return {"enabled": True, "running": False, "reason": str(exc)}


def main() -> None:
    prevent_duplicate()
    write_status(
        pid=os.getpid(),
        running=True,
        state="starting",
        workspace=str(WORKSPACE),
        guardian_generation=GUARDIAN_GENERATION,
    )
    try:
        while True:
            twelve = ensure_twelve()
            massive = ensure_massive()
            overall = "healthy" if twelve.get("ok") else "recovering"
            write_status(
                pid=os.getpid(),
                running=True,
                state=overall,
                twelve=twelve,
                massive=massive,
                check_seconds=CHECK_SECONDS,
                guardian_generation=GUARDIAN_GENERATION,
            )
            time.sleep(CHECK_SECONDS)
    finally:
        try:
            PID_FILE.unlink(missing_ok=True)
        except Exception:
            pass
        write_status(running=False, state="stopped")


if __name__ == "__main__":
    main()
