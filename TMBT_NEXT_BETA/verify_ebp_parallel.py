from __future__ import annotations

import argparse
import os
import time
from datetime import date
from pathlib import Path

import pandas as pd

import legacy_research_adapter


def _canonical(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    cols = [
        c for c in (
            "entry_time", "exit_time", "side", "entry", "stop", "target",
            "r_multiple", "outcome", "model", "setup", "reason",
        )
        if c in df.columns
    ]
    out = df[cols].copy() if cols else df.copy()
    if "entry_time" in out.columns:
        out = out.sort_values(["entry_time"] + (["exit_time"] if "exit_time" in out.columns else []))
    return out.reset_index(drop=True)


def _run(workers: int, start: date, end: date):
    mods = legacy_research_adapter.activate()
    root = Path(mods["root"])
    jobs = mods["research_jobs"]
    studio = mods["studio_bridge"]
    bt = mods["bt_core"]
    request = {
        "preset": "EBP_H1_NQ_FUTURES",
        "start": start.isoformat(),
        "end": end.isoformat(),
        "dataset_role": "Performance Regression",
        "overrides": {"execution_mode": "Bar conservative"},
    }
    cfg = jobs._load_config(root, legacy_research_adapter.WORKSPACE, request)
    file_index = studio.load_file_index(legacy_research_adapter.WORKSPACE, cfg.market, True)
    cache_root = legacy_research_adapter.WORKSPACE / "cache"
    old = os.environ.get("TMBT_EBP_WORKERS")
    os.environ["TMBT_EBP_WORKERS"] = str(workers)
    try:
        t0 = time.perf_counter()
        df = bt.backtest(
            file_index,
            cache_root,
            cfg,
            start,
            end,
            news_df=pd.DataFrame(),
            progress_cb=None,
        )
        elapsed = time.perf_counter() - t0
    finally:
        if old is None:
            os.environ.pop("TMBT_EBP_WORKERS", None)
        else:
            os.environ["TMBT_EBP_WORKERS"] = old
    return _canonical(df), elapsed


def main() -> int:
    p = argparse.ArgumentParser(description="Verify deterministic EBP parallel speedup.")
    p.add_argument("--start", default="2020-01-01")
    p.add_argument("--end", default="2020-06-30")
    p.add_argument("--workers", type=int, default=4)
    args = p.parse_args()

    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)
    parallel_workers = max(2, min(8, int(args.workers)))

    serial, serial_s = _run(1, start, end)
    parallel, parallel_s = _run(parallel_workers, start, end)

    try:
        pd.testing.assert_frame_equal(
            serial,
            parallel,
            check_dtype=False,
            check_exact=False,
            rtol=1e-12,
            atol=1e-12,
        )
    except AssertionError as exc:
        print("EBP PARALLEL REGRESSION: FAIL")
        print(str(exc))
        return 2

    speedup = serial_s / parallel_s if parallel_s > 0 else 0.0
    print("EBP PARALLEL REGRESSION: PASS")
    print(f"range: {start} -> {end}")
    print(f"trades: {len(serial)}")
    print(f"serial:   {serial_s:.2f}s")
    print(f"parallel: {parallel_s:.2f}s ({parallel_workers} workers)")
    print(f"speedup:  {speedup:.2f}x")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
