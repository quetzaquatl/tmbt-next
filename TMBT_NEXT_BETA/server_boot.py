from __future__ import annotations

import json
import os
import re
import runpy
import subprocess
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


def _valid_key(v) -> str | None:
    if not isinstance(v, str):
        return None
    v = v.strip().strip("\"'")
    if len(v) < 8 or len(v) > 256:
        return None
    bad = ("your_key", "api_key_here", "changeme", "placeholder", "example")
    return None if any(x in v.lower() for x in bad) else v


def _walk_for_key(obj, allow_generic=False):
    if isinstance(obj, dict):
        # Old Twelve config versions used a plain api_key field.
        preferred = ("TWELVE_API_KEY", "TWELVE_DATA_API_KEY", "twelve_api_key", "twelve_data_api_key")
        for k in preferred:
            if k in obj:
                v = _valid_key(obj.get(k))
                if v:
                    return v
        if allow_generic:
            for k in ("api_key", "apikey", "key"):
                if k in obj:
                    v = _valid_key(obj.get(k))
                    if v:
                        return v
        for k, v in obj.items():
            kl = str(k).lower()
            if "twelve" in kl and "key" in kl:
                vv = _valid_key(v)
                if vv:
                    return vv
            if isinstance(v, (dict, list)):
                vv = _walk_for_key(v, allow_generic=(allow_generic or "twelve" in kl))
                if vv:
                    return vv
    elif isinstance(obj, list):
        for x in obj:
            vv = _walk_for_key(x, allow_generic=allow_generic)
            if vv:
                return vv
    return None


def _key_from_file(path: Path):
    try:
        if not path.exists() or not path.is_file() or path.stat().st_size > 2_000_000:
            return None
        txt = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return None

    lower_path = str(path).lower()
    twelve_specific = "twelve" in lower_path

    if path.suffix.lower() == ".json":
        try:
            obj = json.loads(txt)
            v = _walk_for_key(obj, allow_generic=twelve_specific)
            if v:
                return v
        except Exception:
            pass

    patterns = [
        r"(?im)^\s*(?:TWELVE_API_KEY|TWELVE_DATA_API_KEY|TWELVEDATA_API_KEY|TWELVEDATA_KEY)\s*[:=]\s*[\"']?([^\"'\s#;]+)",
        r"(?im)[\"']?(?:twelve_api_key|twelve_data_api_key|twelvedata_api_key)[\"']?\s*[:=]\s*[\"']([^\"'\r\n]+)",
    ]
    if twelve_specific:
        patterns += [
            r"(?im)^\s*(?:api_key|apikey)\s*[:=]\s*[\"']([^\"']+)[\"']",
            r"(?im)[\"'](?:api_key|apikey)[\"']\s*:\s*[\"']([^\"']+)[\"']",
        ]
    for pat in patterns:
        m = re.search(pat, txt)
        if m:
            v = _valid_key(m.group(1))
            if v:
                return v
    return None


def discover_legacy_twelve_key():
    # 1) inherited environment
    for name in ("TWELVE_API_KEY", "TWELVE_DATA_API_KEY", "TWELVEDATA_API_KEY", "TWELVEDATA_KEY"):
        v = _valid_key(os.environ.get(name))
        if v:
            return v, f"environment:{name}"

    ws = workspace()
    app = collector_dir()
    project_root = ws.parent
    old_roots = [
        app,
        project_root / "Trading_Model_Backtest_Studio_v3_6",
        project_root / "Trading_Model_Backtest_Studio_v3_7_DEV",
        project_root / "Trading_Model_Backtest_Studio_v3_7",
        ws,
    ]

    # 2) exact legacy locations first. This is where the old UI/connector stored
    # or read the credential; do not print the secret itself.
    candidates = [
        ws / "live_data" / "twelve_config.json",
        ws / "twelve_config.json",
    ]
    for root in old_roots:
        candidates += [
            root / "live_data" / "twelve_config.json",
            root / "twelve_config.json",
            root / ".env",
            root / ".env.local",
            root / ".streamlit" / "secrets.toml",
            root / "secrets.toml",
            root / "config.json",
            root / "settings.json",
        ]

    seen = set()
    for p in candidates:
        try:
            rp = p.resolve()
        except Exception:
            rp = p
        if rp in seen:
            continue
        seen.add(rp)
        v = _key_from_file(p)
        if v:
            return v, str(p)

    # 3) focused scan only inside the old v3.6/v3.7 app dirs. No huge workspace
    # backup scan and no secret value is ever logged.
    for root in old_roots[:4]:
        if not root.exists():
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            base = Path(dirpath)
            try:
                depth = len(base.relative_to(root).parts)
            except Exception:
                depth = 0
            if depth > 4:
                dirnames[:] = []
                continue
            dirnames[:] = [d for d in dirnames if d.lower() not in {".git", "node_modules", "venv", ".venv", "__pycache__", "dist", "build"}]
            for fn in filenames:
                low = fn.lower()
                if not ("twelve" in low or low.startswith(".env") or low == "secrets.toml"):
                    continue
                p = base / fn
                v = _key_from_file(p)
                if v:
                    return v, str(p)
    return None, None


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


def status_path() -> Path:
    return workspace() / "live_data" / "twelve_status.json"


def choose_python(app: Path) -> Path:
    for p in (app / "venv" / "Scripts" / "python.exe", app / ".venv" / "Scripts" / "python.exe"):
        if p.exists():
            return p
    return Path(os.sys.executable)


def ensure_original_collector(key: str | None) -> dict:
    st = read_json(status_path())
    alive = pid_alive(st.get("pid"))
    if alive:
        return st
    if not key:
        return st

    app = collector_dir()
    script = app / "twelve_live.py"
    if not script.exists():
        print("Original Twelve collector: twelve_live.py not found:", script)
        return st

    env = os.environ.copy()
    env["TMBT_WORKSPACE"] = str(workspace())
    # The old connector specifically expects TWELVE_API_KEY.
    env["TWELVE_API_KEY"] = key
    env.setdefault("TWELVE_DATA_API_KEY", key)

    logdir = workspace() / "live_data"
    logdir.mkdir(parents=True, exist_ok=True)
    logfile = logdir / "twelve_boot.log"
    log = open(logfile, "ab", buffering=0)
    kwargs = {
        "cwd": str(app), "env": env, "stdin": subprocess.DEVNULL,
        "stdout": log, "stderr": subprocess.STDOUT,
    }
    if os.name == "nt":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    else:
        kwargs["start_new_session"] = True
    try:
        proc = subprocess.Popen([str(choose_python(app)), str(script), "--run"], **kwargs)
        print("Original Twelve collector: started PID", proc.pid, "· log", logfile)
    except Exception as exc:
        print("Original Twelve collector: start failed:", exc)
        return st

    deadline = time.time() + 10
    while time.time() < deadline:
        time.sleep(0.75)
        st = read_json(status_path())
        state = str(st.get("state") or "").lower()
        if st.get("connected") or state in {"backfill", "polling", "error", "quota_pause", "rate_limit_pause"}:
            break
    return st


def print_status(st: dict, key_source: str | None):
    print("Legacy Twelve credential bridge:")
    print("  key:", "FOUND" if key_source else "NOT FOUND")
    if key_source:
        print("  source:", key_source)
    print("Original Twelve collector:")
    print("  status:", status_path())
    if not st:
        print("  state: no status file")
        return
    alive = pid_alive(st.get("pid"))
    print("  state:", st.get("state") or "unknown", "· connected:", bool(st.get("connected")), "· running PID:", st.get("pid") if alive else "no")
    if st.get("last_error") and not st.get("connected"):
        print("  last_error:", str(st.get("last_error"))[:500])


key, key_source = discover_legacy_twelve_key()
if key:
    # Make the same legacy credential available to server_desk's XAU recovery.
    os.environ["TWELVE_API_KEY"] = key
    os.environ.setdefault("TWELVE_DATA_API_KEY", key)

collector_state = ensure_original_collector(key)
print_status(collector_state, key_source)

# Start the UI after the legacy credential/collector bridge is prepared.
runpy.run_module("server_desk", run_name="__main__")
