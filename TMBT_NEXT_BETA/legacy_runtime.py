from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
WORKSPACE = Path(os.environ.get("TMBT_WORKSPACE", r"D:\Projekt model\Trading_Model_Backtest_Studio_WORKSPACE")).resolve()
RUNTIME_BASE = WORKSPACE / "runtime"
RUNTIME_ROOT = RUNTIME_BASE / "old_studio_core"
MARKER = RUNTIME_ROOT / ".bundle.json"


def bundle_path() -> Path:
    explicit = os.environ.get("TMBT_OLD_STUDIO_BUNDLE", "").strip()
    if explicit:
        return Path(explicit).expanduser().resolve()
    return WORKSPACE / "migration" / "old_studio_source_bundle.zip"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        d = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _safe_extract(zf: zipfile.ZipFile, target: Path) -> None:
    target_resolved = target.resolve()
    for info in zf.infolist():
        name = str(info.filename or "").replace("\\", "/").lstrip("/")
        if not name or name.endswith("/"):
            continue
        dst = (target / name).resolve()
        try:
            dst.relative_to(target_resolved)
        except Exception:
            raise RuntimeError(f"unsafe bundle member: {name}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        with zf.open(info, "r") as src, dst.open("wb") as out:
            shutil.copyfileobj(src, out)


def ensure_runtime(force: bool = False) -> Path:
    bundle = bundle_path()
    if not bundle.exists():
        raise FileNotFoundError(
            f"Old Studio migration bundle missing: {bundle}. "
            "Run TMBT_NEXT_BETA\\AUDIT_OLD_STUDIO.bat once before retiring the old Studio."
        )
    digest = _sha256(bundle)
    marker = _read_json(MARKER)
    required = [RUNTIME_ROOT / "bt_core.py", RUNTIME_ROOT / "research_jobs.py", RUNTIME_ROOT / "research_autopilot.py"]
    if not force and marker.get("sha256") == digest and all(p.exists() for p in required):
        return RUNTIME_ROOT

    RUNTIME_BASE.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="old_studio_core_", dir=str(RUNTIME_BASE)))
    try:
        with zipfile.ZipFile(bundle, "r") as zf:
            _safe_extract(zf, tmp)
        (tmp / ".bundle.json").write_text(
            json.dumps(
                {
                    "source": str(bundle),
                    "sha256": digest,
                    "extracted_at_utc": datetime.now(timezone.utc).isoformat(),
                    "mode": "compatibility_runtime",
                    "note": "Source migration runtime. No API keys/secrets are bundled.",
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        if RUNTIME_ROOT.exists():
            archive = WORKSPACE / "_legacy_archive" / "runtime"
            archive.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            old = archive / f"old_studio_core_{stamp}"
            shutil.move(str(RUNTIME_ROOT), str(old))
        os.replace(tmp, RUNTIME_ROOT)
    finally:
        if tmp.exists():
            shutil.rmtree(tmp, ignore_errors=True)
    return RUNTIME_ROOT


def activate(force: bool = False) -> Path:
    root = ensure_runtime(force=force)
    s = str(root)
    if s not in sys.path:
        sys.path.insert(0, s)
    return root


def script(name: str) -> Path:
    return ensure_runtime() / str(name)


def status() -> dict[str, Any]:
    bundle = bundle_path()
    marker = _read_json(MARKER)
    return {
        "bundle": str(bundle),
        "bundle_exists": bundle.exists(),
        "runtime": str(RUNTIME_ROOT),
        "runtime_exists": RUNTIME_ROOT.exists(),
        "bundle_sha256": marker.get("sha256"),
        "extracted_at_utc": marker.get("extracted_at_utc"),
        "old_studio_directory_required": False if RUNTIME_ROOT.exists() else None,
    }
