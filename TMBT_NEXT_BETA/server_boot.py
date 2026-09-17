from __future__ import annotations

import os
import re
import runpy
from pathlib import Path


def _workspace() -> Path:
    return Path(os.environ.get("TMBT_WORKSPACE", r"D:\Projekt model\Trading_Model_Backtest_Studio_WORKSPACE"))


def _valid(value: str | None) -> str | None:
    if not value:
        return None
    v = value.strip().strip("\"'")
    if not (8 <= len(v) <= 160):
        return None
    if any(x in v.lower() for x in ("your_key", "api_key_here", "changeme", "example", "placeholder")):
        return None
    return v


def _from_env() -> tuple[str | None, str | None]:
    for name in ("TWELVE_DATA_API_KEY", "TWELVEDATA_API_KEY", "TWELVE_API_KEY", "TWELVEDATA_KEY"):
        v = _valid(os.environ.get(name))
        if v:
            return v, f"environment:{name}"
    return None, None


def _candidate_files(root: Path):
    if not root.exists():
        return
    allowed = {".env", ".toml", ".json", ".yaml", ".yml", ".ini", ".cfg", ".py", ".bat", ".ps1", ".txt"}
    words = ("twelve", "secret", "config", "setting", "credential", "live", "data", "feed", "env", "collector")
    skip_dirs = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", ".next", ".vite"}
    root = root.resolve()
    emitted = 0
    for dirpath, dirnames, filenames in os.walk(root):
        base = Path(dirpath)
        try:
            depth = len(base.relative_to(root).parts)
        except Exception:
            depth = 0
        dirnames[:] = [d for d in dirnames if d.lower() not in skip_dirs and depth < 6]
        if depth > 6:
            continue
        parent_text = str(base).lower()
        for filename in filenames:
            if emitted >= 350:
                return
            p = base / filename
            name = filename.lower()
            suffix = p.suffix.lower()
            is_env = name.startswith(".env")
            if not is_env and suffix not in allowed:
                continue
            if not is_env and not any(w in name for w in words):
                if suffix not in {".py", ".bat", ".ps1"} or not any(w in parent_text for w in ("live", "data", "feed", "twelve", "collector")):
                    continue
            try:
                if p.stat().st_size > 700_000:
                    continue
            except Exception:
                continue
            emitted += 1
            yield p


def _extract(text: str, twelve_context: bool) -> str | None:
    explicit = [
        r"(?im)^\s*(?:TWELVE_DATA_API_KEY|TWELVEDATA_API_KEY|TWELVE_API_KEY|TWELVEDATA_KEY)\s*[:=]\s*[\"']?([^\"'\s#;]+)",
        r"(?im)[\"']?(?:twelve_data_api_key|twelvedata_api_key|twelve_api_key)[\"']?\s*[:=]\s*[\"']([^\"']+)",
    ]
    for pat in explicit:
        m = re.search(pat, text)
        if m:
            v = _valid(m.group(1))
            if v:
                return v
    if twelve_context:
        for pat in (
            r"(?im)^\s*(?:API_KEY|APIKEY)\s*[:=]\s*[\"']([^\"']+)[\"']",
            r"(?im)[\"']apikey[\"']\s*:\s*[\"']([^\"']+)[\"']",
        ):
            m = re.search(pat, text)
            if m:
                v = _valid(m.group(1))
                if v:
                    return v
    return None


def discover_existing_twelve_key() -> tuple[str | None, str | None]:
    v, src = _from_env()
    if v:
        return v, src
    ws = _workspace()
    checked = set()
    for root in (ws, ws.parent):
        for p in _candidate_files(root):
            if p in checked:
                continue
            checked.add(p)
            try:
                text = p.read_text(encoding="utf-8", errors="ignore")[:700_000]
            except Exception:
                continue
            context = "twelve" in p.name.lower() or "twelve" in str(p.parent).lower() or "twelve" in text[:20_000].lower()
            value = _extract(text, context)
            if value:
                return value, str(p)
    return None, None


key, source = discover_existing_twelve_key()
if key:
    os.environ.setdefault("TWELVE_DATA_API_KEY", key)
    print("Twelve credentials: FOUND (source:", source, ")")
else:
    print("Twelve credentials: NOT FOUND in existing workspace/config files")

runpy.run_module("server_desk", run_name="__main__")
