from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_WS = Path(r"D:\Projekt model\Trading_Model_Backtest_Studio_WORKSPACE")


def now_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def copy_verified(src: Path, dst: Path) -> dict[str, Any]:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        if src.stat().st_size == dst.stat().st_size and sha256(src) == sha256(dst):
            return {"action": "identical", "src": str(src), "dst": str(dst)}
        # Never overwrite a conflicting canonical file.
        suffix = src.parent.name.replace(" ", "_")
        candidate = dst.with_name(f"{dst.stem}__legacy_{suffix}{dst.suffix}")
        n = 2
        while candidate.exists():
            candidate = dst.with_name(f"{dst.stem}__legacy_{suffix}_{n}{dst.suffix}")
            n += 1
        dst = candidate
    shutil.copy2(src, dst)
    if src.stat().st_size != dst.stat().st_size or sha256(src) != sha256(dst):
        raise RuntimeError(f"verification_failed:{src}->{dst}")
    return {"action": "copied", "src": str(src), "dst": str(dst)}


def merge_tree(src_root: Path, dst_root: Path, apply: bool) -> list[dict[str, Any]]:
    rows = []
    if not src_root.exists():
        return rows
    for src in src_root.rglob("*"):
        if not src.is_file():
            continue
        rel = src.relative_to(src_root)
        dst = dst_root / rel
        if apply:
            rows.append(copy_verified(src, dst))
        else:
            rows.append({"action": "would_copy_or_verify", "src": str(src), "dst": str(dst)})
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description="Consolidate legacy TMBT data roots safely.")
    ap.add_argument("--workspace", default=os.environ.get("TMBT_WORKSPACE", str(DEFAULT_WS)))
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    ws = Path(args.workspace).resolve()

    mappings = [
        (ws / "live" / "twelve", ws / "live_data" / "twelve"),
        (ws / "github_research_repo" / "live" / "twelve", ws / "live_data" / "twelve"),
        (ws / "live" / "futures", ws / "live_data" / "futures"),
        (ws / "github_research_repo" / "live" / "futures", ws / "live_data" / "futures"),
    ]

    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "workspace": str(ws),
        "mode": "apply" if args.apply else "dry_run",
        "operations": [],
        "archives": [],
    }

    sources_to_archive = []
    for src, dst in mappings:
        rows = merge_tree(src, dst, args.apply)
        report["operations"].extend(rows)
        if rows and src.exists():
            sources_to_archive.append(src)

    if args.apply:
        archive_root = ws / "_legacy_archive" / now_stamp()
        for src in sorted(set(sources_to_archive), key=lambda p: len(p.parts), reverse=True):
            if not src.exists():
                continue
            rel = src.relative_to(ws)
            target = archive_root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(target))
            report["archives"].append({"src": str(src), "archived_to": str(target)})

    out = ws / "migration" / ("workspace_cleanup_apply.json" if args.apply else "workspace_cleanup_dry_run.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("Mode:", report["mode"])
    print("Report:", out)
    print("Operations:", len(report["operations"]))
    print("Archived roots:", len(report["archives"]))
    if not args.apply:
        print("Nothing changed. Re-run with --apply after reviewing the report.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
