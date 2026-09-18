from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any

TF = {
    "1m": ("bars_1m", 60_000),
    "5m": ("bars_5m", 5 * 60_000),
    "15m": ("bars_15m", 15 * 60_000),
    "30m": ("bars_30m", 30 * 60_000),
    "1h": ("bars_1h", 60 * 60_000),
}


def _workspace() -> Path:
    return Path(
        os.environ.get(
            "TMBT_WORKSPACE",
            r"D:\Projekt model\Trading_Model_Backtest_Studio_WORKSPACE",
        )
    ).resolve()


def _norm_tf(tf: str) -> str:
    z = str(tf or "").strip().lower()
    return {"60m": "1h", "h1": "1h", "1hr": "1h"}.get(z, z)


def _norm_market(market: str) -> str:
    z = str(market or "").strip().upper()
    if z not in {"NQ", "ES", "GC"}:
        raise ValueError(f"Historical Databento store supports NQ/ES/GC, got {market!r}")
    return z


def db_path(workspace: Path | None = None) -> Path:
    root = (workspace or _workspace()).resolve()
    return root / "historical" / "databento" / "tmbt_futures_history.sqlite"


def load_bars(
    market: str,
    timeframe: str,
    as_of_ms: int,
    limit: int,
    *,
    workspace: Path | None = None,
    path: Path | None = None,
) -> list[dict[str, Any]]:
    """Return only bars fully closed at or before as_of_ms.

    Signature intentionally matches backtest_context_adapter:
      load_bars(market, timeframe, as_of_ms, limit) -> list[dict]
    """
    root = _norm_market(market)
    ntf = _norm_tf(timeframe)
    if ntf not in TF:
        raise ValueError(f"Unsupported historical timeframe: {timeframe!r}")
    table, width_ms = TF[ntf]
    p = (path or db_path(workspace)).resolve()
    if not p.exists():
        return []

    cutoff_open_ms = int(as_of_ms) - width_ms
    lim = max(1, int(limit))
    con = sqlite3.connect(f"file:{p.as_posix()}?mode=ro", uri=True)
    try:
        rows = con.execute(
            f"""
            SELECT t, symbol, o, h, l, c, v
            FROM {table}
            WHERE root=? AND t<=?
            ORDER BY t DESC
            LIMIT ?
            """,
            (root, cutoff_open_ms, lim),
        ).fetchall()
    finally:
        con.close()
    rows.reverse()
    return [
        {
            "t": int(t),
            "bar_open_ms": int(t),
            "close_t": int(t) + width_ms,
            "bar_close_ms": int(t) + width_ms,
            "o": float(o),
            "h": float(h),
            "l": float(l),
            "c": float(c),
            "v": float(v),
            "open": float(o),
            "high": float(h),
            "low": float(l),
            "close": float(c),
            "volume": float(v),
            "market": root,
            "symbol": str(symbol),
            "tf": "1H" if ntf == "1h" else ntf,
            "source": "DATABENTO_HISTORICAL",
        }
        for t, symbol, o, h, l, c, v in rows
    ]


def status(workspace: Path | None = None) -> dict[str, Any]:
    root = (workspace or _workspace()).resolve()
    p = db_path(root)
    status_path = root / "historical" / "databento" / "import_status.json"
    import json

    value: dict[str, Any] = {}
    try:
        x = json.loads(status_path.read_text(encoding="utf-8", errors="ignore"))
        if isinstance(x, dict):
            value = x
    except Exception:
        pass
    value["db"] = str(p)
    value["db_exists"] = p.exists()
    value["db_size_bytes"] = p.stat().st_size if p.exists() else None
    value["import_complete"] = bool(
        p.exists() and str(value.get("state") or "").upper() == "COMPLETE"
    )
    value["ready_for_research"] = value["import_complete"]
    return value


def available_dates(market: str, *, workspace: Path | None = None, path: Path | None = None):
    """Return UTC dates available in the local 1m Databento continuous series."""
    from datetime import date
    root = _norm_market(market)
    p = (path or db_path(workspace)).resolve()
    if not p.exists():
        return []
    con = sqlite3.connect(f"file:{p.as_posix()}?mode=ro", uri=True)
    try:
        rows = con.execute(
            """
            SELECT DISTINCT strftime('%Y-%m-%d', t / 1000, 'unixepoch')
            FROM bars_1m
            WHERE root=?
            ORDER BY 1
            """,
            (root,),
        ).fetchall()
    finally:
        con.close()
    out = []
    for (ds,) in rows:
        try:
            out.append(date.fromisoformat(str(ds)))
        except Exception:
            pass
    return out


def load_utc_day_1m(
    market: str,
    utc_date,
    *,
    workspace: Path | None = None,
    path: Path | None = None,
) -> list[dict[str, Any]]:
    """Load one UTC day of 1m bars for research/backtest compatibility."""
    from datetime import datetime, time, timedelta, timezone
    root = _norm_market(market)
    if isinstance(utc_date, str):
        from datetime import date
        utc_date = date.fromisoformat(utc_date)
    start = datetime.combine(utc_date, time.min, tzinfo=timezone.utc)
    end = start + timedelta(days=1)
    a = int(start.timestamp() * 1000)
    b = int(end.timestamp() * 1000)
    p = (path or db_path(workspace)).resolve()
    if not p.exists():
        return []
    con = sqlite3.connect(f"file:{p.as_posix()}?mode=ro", uri=True)
    try:
        rows = con.execute(
            """
            SELECT t, symbol, o, h, l, c, v
            FROM bars_1m
            WHERE root=? AND t>=? AND t<?
            ORDER BY t
            """,
            (root, a, b),
        ).fetchall()
    finally:
        con.close()
    return [
        {
            "t": int(t),
            "symbol": str(symbol),
            "o": float(o),
            "h": float(h),
            "l": float(l),
            "c": float(c),
            "v": float(v),
        }
        for t, symbol, o, h, l, c, v in rows
    ]
