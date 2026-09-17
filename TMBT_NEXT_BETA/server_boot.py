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
    interesting_ext = {".env", ".toml", ".json", ".yaml", ".yml", ".ini", ".cfg", ".py", ".bat", ".ps1", ".txt"}
    interesting_words = ("twelve", "secret", "config", "setting", "credential", "live", "data", "feed", "env")
    seen = set()
    count = 0
    for p in root.rglob("*"):
        if count >= 350:
            break
        try:
            if not p.is_file() or p in seen or p.stat().st_size > 700_000:
                continue
        except Exception:
            continue
        name = p.name.lower()
        suffix = p.suffix.lower()
        is_env = name.startswith(".env")
        if not is_env and suffix not in interesting_ext:
            continue
        if not is_env and not any(w in name for w in interesting_words):
            parent = str(p.parent).lower()
            if suffix not in {".py", ".bat", ".ps1"} or not any(w in parent for w in ("live", "data", "feed", "twelve", "collector")):
                continue
        seen.add(p)
        count += 1
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
