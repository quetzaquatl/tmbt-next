from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import historical_store
import ict_rule_engine


def _latest_as_of_ms(market: str, workspace: Path) -> int:
    p = historical_store.db_path(workspace)
    if not p.exists():
        raise RuntimeError(f"historical store not found: {p}")
    con = sqlite3.connect(f"file:{p.as_posix()}?mode=ro", uri=True)
    try:
        row = con.execute(
            "SELECT MAX(t) FROM bars_1m WHERE root=?",
            (market.upper(),),
        ).fetchone()
    finally:
        con.close()
    if not row or row[0] is None:
        raise RuntimeError(f"no historical bars for {market}")
    # Make the latest 1m candle closed for load_bars' cutoff semantics.
    return int(row[0]) + 60_000


def build_snapshot(
    *,
    market: str,
    timeframe: str,
    workspace: Path,
    as_of_ms: int | None = None,
    limit: int = 1500,
) -> dict[str, Any]:
    market = market.upper()
    as_of = int(as_of_ms) if as_of_ms is not None else _latest_as_of_ms(market, workspace)
    rows = historical_store.load_bars(
        market,
        timeframe,
        as_of,
        limit,
        workspace=workspace,
    )
    snap = ict_rule_engine.snapshot(
        rows,
        market=market,
        timeframe=timeframe,
        as_of_ms=as_of,
        max_events=50,
    )
    snap["research_only"] = True
    snap["execution_enabled"] = False
    snap["workspace"] = str(workspace)
    snap["as_of_utc"] = datetime.fromtimestamp(as_of / 1000.0, tz=timezone.utc).isoformat()
    return snap


def main() -> int:
    p = argparse.ArgumentParser(
        description="Read-only ICT Core CONTEXT/EVENT snapshot from local Databento history."
    )
    p.add_argument("--market", default="NQ", choices=["NQ", "ES", "YM", "GC"])
    p.add_argument("--tf", default="5m", choices=["1m", "5m", "15m", "30m", "1H"])
    p.add_argument("--limit", type=int, default=1500)
    p.add_argument("--as-of-ms", type=int, default=None)
    p.add_argument(
        "--workspace",
        default=r"D:\Projekt model\Trading_Model_Backtest_Studio_WORKSPACE",
    )
    p.add_argument("--output", default="")
    args = p.parse_args()

    snap = build_snapshot(
        market=args.market,
        timeframe=args.tf,
        workspace=Path(args.workspace).resolve(),
        as_of_ms=args.as_of_ms,
        limit=max(50, args.limit),
    )
    text = json.dumps(snap, ensure_ascii=False, indent=2)
    if args.output:
        out = Path(args.output).resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        print(out)
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
