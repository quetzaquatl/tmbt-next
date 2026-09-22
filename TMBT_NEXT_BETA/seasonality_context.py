from __future__ import annotations

import argparse
import json
import math
import statistics
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import historical_store

NY = ZoneInfo("America/New_York")
SUPPORTED_MARKETS = ("NQ", "ES", "GC")
CACHE_VERSION = "market-seasonality-v1"


def _workspace() -> Path:
    return historical_store._workspace()


def _trading_date(ts_ms: int) -> date:
    """Map a futures bar to the CME trading date using 18:00 New York rollover."""
    local = datetime.fromtimestamp(int(ts_ms) / 1000.0, tz=timezone.utc).astimezone(NY)
    d = local.date()
    if local.hour >= 18:
        d += timedelta(days=1)
    return d


def _load_hourly(market: str, workspace: Path | None = None) -> list[tuple[int, float, float, float, float, float]]:
    root = str(market).upper()
    if root not in SUPPORTED_MARKETS:
        raise ValueError(f"Unsupported seasonality market: {market!r}")
    p = historical_store.db_path(workspace or _workspace())
    if not p.exists():
        return []
    con = historical_store._ro_connection(p)
    return [
        (int(t), float(o), float(h), float(l), float(c), float(v))
        for t, o, h, l, c, v in con.execute(
            """
            SELECT t, o, h, l, c, v
            FROM bars_1h
            WHERE root=?
            ORDER BY t
            """,
            (root,),
        ).fetchall()
    ]


def _daily(market: str, workspace: Path | None = None) -> list[dict[str, Any]]:
    rows = _load_hourly(market, workspace)
    by_day: dict[date, dict[str, Any]] = {}
    for t, o, h, l, c, v in rows:
        d = _trading_date(t)
        item = by_day.get(d)
        if item is None:
            by_day[d] = {
                "date": d,
                "first_t": t,
                "last_t": t,
                "open": o,
                "high": h,
                "low": l,
                "close": c,
                "volume": v,
            }
            continue
        item["high"] = max(float(item["high"]), h)
        item["low"] = min(float(item["low"]), l)
        item["volume"] = float(item["volume"]) + v
        if t < int(item["first_t"]):
            item["first_t"] = t
            item["open"] = o
        if t >= int(item["last_t"]):
            item["last_t"] = t
            item["close"] = c

    out = []
    for d in sorted(by_day):
        x = by_day[d]
        o = float(x["open"])
        h = float(x["high"])
        l = float(x["low"])
        c = float(x["close"])
        if o <= 0:
            continue
        out.append({
            "date": d,
            "open": o,
            "high": h,
            "low": l,
            "close": c,
            "return_pct": (c / o - 1.0) * 100.0,
            "range_pct": ((h - l) / o) * 100.0,
            "volume": float(x["volume"]),
        })
    return out


def _metric(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"n": 0}
    rets = [float(x["return_pct"]) for x in rows]
    ranges = [float(x["range_pct"]) for x in rows]
    return {
        "n": len(rows),
        "mean_return_pct": round(statistics.fmean(rets), 6),
        "median_return_pct": round(statistics.median(rets), 6),
        "positive_pct": round(100.0 * sum(1 for x in rets if x > 0) / len(rets), 2),
        "negative_pct": round(100.0 * sum(1 for x in rets if x < 0) / len(rets), 2),
        "mean_range_pct": round(statistics.fmean(ranges), 6),
    }


def _bucket(rows: list[dict[str, Any]], key_fn) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[str(key_fn(row["date"]))].append(row)
    return {k: _metric(v) for k, v in sorted(groups.items(), key=lambda kv: kv[0])}


def _window_rows(rows: list[dict[str, Any]], years: int | None) -> list[dict[str, Any]]:
    if not rows or years is None:
        return list(rows)
    last = rows[-1]["date"]
    cutoff = date(last.year - int(years) + 1, 1, 1)
    return [x for x in rows if x["date"] >= cutoff]


def build_market(market: str, workspace: Path | None = None) -> dict[str, Any]:
    rows = _daily(market, workspace)
    if not rows:
        return {"version": CACHE_VERSION, "market": market, "days": 0, "windows": {}}

    result: dict[str, Any] = {
        "version": CACHE_VERSION,
        "market": market,
        "source": "Databento continuous futures 1h aggregated to CME trading date",
        "trading_date_roll": "18:00 America/New_York",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "first_date": rows[0]["date"].isoformat(),
        "last_date": rows[-1]["date"].isoformat(),
        "days": len(rows),
        "windows": {},
    }
    for label, years in (("5y", 5), ("15y", 15), ("all", None)):
        sample = _window_rows(rows, years)
        result["windows"][label] = {
            "first_date": sample[0]["date"].isoformat() if sample else None,
            "last_date": sample[-1]["date"].isoformat() if sample else None,
            "days": len(sample),
            "overall": _metric(sample),
            "month": _bucket(sample, lambda d: d.month),
            "iso_week": _bucket(sample, lambda d: d.isocalendar().week),
            "weekday": _bucket(sample, lambda d: d.weekday()),
            "quarter": _bucket(sample, lambda d: (d.month - 1) // 3 + 1),
            "day_of_month": _bucket(sample, lambda d: d.day),
        }
    return result


def build_all(workspace: Path | None = None) -> dict[str, Any]:
    root = workspace or _workspace()
    payload = {
        "version": CACHE_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "markets": {m: build_market(m, root) for m in SUPPORTED_MARKETS},
        "usage_note": (
            "Seasonality is context only, not a standalone signal. Compare 5y/15y/all "
            "windows and validate model-specific expectancy before using any filter."
        ),
    }
    out = root / "research_context" / "seasonality" / "market_seasonality.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(out)
    payload["path"] = str(out)
    return payload


def load_cache(workspace: Path | None = None) -> dict[str, Any]:
    p = (workspace or _workspace()) / "research_context" / "seasonality" / "market_seasonality.json"
    try:
        x = json.loads(p.read_text(encoding="utf-8"))
        return x if isinstance(x, dict) else {}
    except Exception:
        return {}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--market", choices=list(SUPPORTED_MARKETS))
    args = ap.parse_args()
    if args.market:
        print(json.dumps(build_market(args.market), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(build_all(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
