from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_OLD = Path(r"D:\Projekt model\Trading_Model_Backtest_Studio_v3_7_DEV")
DEFAULT_WS = Path(r"D:\Projekt model\Trading_Model_Backtest_Studio_WORKSPACE")
SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", ".pytest_cache", ".mypy_cache", "node_modules"}
SOURCE_EXTS = {".py", ".json", ".md", ".txt", ".toml", ".yaml", ".yml", ".bat", ".cmd", ".ps1"}
SENSITIVE_HINTS = {"api_key", "secret", "token", "password", ".env", "credentials"}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_rel(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except Exception:
        return str(path)


def should_skip(path: Path) -> bool:
    return any(part.lower() in {x.lower() for x in SKIP_DIRS} for part in path.parts)


def looks_sensitive(path: Path) -> bool:
    s = path.name.lower()
    return any(h in s for h in SENSITIVE_HINTS)


def imports_for(path: Path) -> list[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return []
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for n in node.names:
                out.add(n.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            out.add(node.module.split(".")[0])
    return sorted(out)


def sha256(path: Path) -> str | None:
    try:
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return None


def dir_stats(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"exists": False, "files": 0, "bytes": 0}
    files = 0
    size = 0
    try:
        for p in path.rglob("*"):
            if p.is_file():
                files += 1
                try:
                    size += p.stat().st_size
                except Exception:
                    pass
    except Exception:
        pass
    return {"exists": True, "files": files, "bytes": size}


def audit(old_root: Path, workspace: Path) -> dict[str, Any]:
    source_files = []
    local_modules = set()
    for p in old_root.rglob("*"):
        if not p.is_file() or should_skip(p):
            continue
        if p.suffix.lower() not in SOURCE_EXTS:
            continue
        if looks_sensitive(p):
            continue
        rel = safe_rel(p, old_root)
        row = {
            "path": rel,
            "size": p.stat().st_size,
            "sha256": sha256(p),
        }
        if p.suffix.lower() == ".py":
            row["imports"] = imports_for(p)
            local_modules.add(p.stem)
        source_files.append(row)

    py_imports = sorted({
        imp
        for row in source_files
        for imp in row.get("imports", [])
        if imp in local_modules
    })

    data_roots = {
        "canonical_live_data": workspace / "live_data",
        "legacy_live": workspace / "live",
        "legacy_github_live": workspace / "github_research_repo" / "live",
        "historical": workspace / "historical",
        "research_jobs": workspace / "research_jobs",
        "research_autopilot": workspace / "research_autopilot",
        "live_signals": workspace / "live_signals",
        "paper_account": workspace / "paper_account",
    }

    return {
        "generated_at_utc": now_iso(),
        "old_studio_root": str(old_root),
        "workspace": str(workspace),
        "old_studio_exists": old_root.exists(),
        "source_file_count": len(source_files),
        "source_files": source_files,
        "local_python_dependencies": py_imports,
        "data_roots": {k: {"path": str(v), **dir_stats(v)} for k, v in data_roots.items()},
        "canonical_workspace_layout": {
            "live_data": "single canonical home for live feeds, statuses and provider mirrors",
            "historical": "single canonical home for Databento/raw historical DBs",
            "research_jobs": "research/backtest job state and results",
            "research_autopilot": "autopilot status/report/logs",
            "live_signals": "signal history/outcomes/snapshots",
            "paper_account": "paper execution state",
            "_legacy_archive": "verified legacy duplicates moved here, never deleted automatically",
        },
    }


def build_bundle(old_root: Path, output: Path) -> dict[str, Any]:
    output.parent.mkdir(parents=True, exist_ok=True)
    included = []
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for p in old_root.rglob("*"):
            if not p.is_file() or should_skip(p):
                continue
            if p.suffix.lower() not in SOURCE_EXTS:
                continue
            if looks_sensitive(p):
                continue
            rel = safe_rel(p, old_root)
            # Keep source/config/presets/docs; exclude obvious runtime/data artifacts.
            low = rel.lower().replace("\\", "/")
            if any(x in low for x in ["/cache/", "/data/", "/live/", "/logs/", "/runs/", "/research_jobs/"]):
                continue
            zf.write(p, arcname=rel)
            included.append(rel)
    return {"bundle": str(output), "files": len(included), "included": included}


def main() -> int:
    ap = argparse.ArgumentParser(description="Audit old Studio and prepare migration bundle.")
    ap.add_argument("--old-root", default=os.environ.get("TMBT_OLD_STUDIO_ROOT", str(DEFAULT_OLD)))
    ap.add_argument("--workspace", default=os.environ.get("TMBT_WORKSPACE", str(DEFAULT_WS)))
    ap.add_argument("--bundle", action="store_true")
    args = ap.parse_args()

    old_root = Path(args.old_root).resolve()
    workspace = Path(args.workspace).resolve()
    out_root = workspace / "migration"
    out_root.mkdir(parents=True, exist_ok=True)

    report = audit(old_root, workspace)
    report_path = out_root / "old_studio_audit.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Audit:", report_path)
    print("Source files:", report["source_file_count"])
    print("Local module dependencies:", ", ".join(report["local_python_dependencies"][:80]))

    if args.bundle:
        bundle = build_bundle(old_root, out_root / "old_studio_source_bundle.zip")
        bundle_path = out_root / "old_studio_bundle_manifest.json"
        bundle_path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
        print("Bundle:", bundle["bundle"])
        print("Bundled files:", bundle["files"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
