from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

import historical_store
import seasonality_context

NY = ZoneInfo("America/New_York")
WORKSPACE = Path(
    os.environ.get(
        "TMBT_WORKSPACE",
        r"D:\\Projekt model\\Trading_Model_Backtest_Studio_WORKSPACE",
    )
).resolve()

ANALYSIS_VERSION = "model-context-ablation-v1"
_CACHE: dict[tuple[str, int, int], dict[str, Any]] = {}


def _num(v: Any, default: float = 0.0) -> float:
    try:
        x = float(v)
        return x if math.isfinite(x) else default
    except Exception:
        return default


def _run_dir(run_id: str, workspace: Path | None = None) -> Path:
    return (workspace or WORKSPACE) / "runs" / str(run_id)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        x = json.loads(path.read_text(encoding="utf-8"))
        return x if isinstance(x, dict) else {}
    except Exception:
        return {}


def _season_market(market: str) -> tuple[str | None, bool]:
    m = str(market or "").upper()
    if m in {"NQ", "ES", "GC"}:
        return m, False
    if m in {"XAU", "XAUUSD"}:
        return "GC", True
    return None, False


def _max_drawdown_r(values: list[float]) -> float:
    equity = 0.0
    peak = 0.0
    max_dd = 0.0
    for x in values:
        equity += float(x)
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
    return float(max_dd)


def _stats(frame: pd.DataFrame) -> dict[str, Any]:
    if frame is None or frame.empty or "r" not in frame.columns:
        return {"trades": 0}
    r = pd.to_numeric(frame["r"], errors="coerce").dropna().astype(float)
    if r.empty:
        return {"trades": 0}
    gp = float(r[r > 0].sum())
    gl = float(-r[r < 0].sum())
    return {
        "trades": int(len(r)),
        "wins": int((r > 0).sum()),
        "losses": int((r < 0).sum()),
        "winrate_pct": round(float((r > 0).mean() * 100.0), 4),
        "net_r": round(float(r.sum()), 6),
        "expectancy_r": round(float(r.mean()), 6),
        "profit_factor_r": round(gp / gl, 6) if gl > 0 else None,
        "max_drawdown_r": round(_max_drawdown_r(r.tolist()), 6),
    }


def _group_stats(frame: pd.DataFrame, col: str) -> list[dict[str, Any]]:
    if col not in frame.columns or frame.empty:
        return []
    out: list[dict[str, Any]] = []
    for key, group in frame.groupby(col, dropna=False):
        row = {"value": None if pd.isna(key) else str(key)}
        row.update(_stats(group))
        out.append(row)
    out.sort(key=lambda x: str(x.get("value") or ""))
    return out


def _alignment(side: Any, seasonal_label: str) -> str:
    s = str(side or "").strip().upper()
    label = str(seasonal_label or "").upper()
    if label not in {"BULLISH", "BEARISH"}:
        return "NEUTRAL_OR_MIXED"
    if (s == "LONG" and label == "BULLISH") or (s == "SHORT" and label == "BEARISH"):
        return "ALIGNED"
    if (s == "LONG" and label == "BEARISH") or (s == "SHORT" and label == "BULLISH"):
        return "OPPOSED"
    return "NEUTRAL_OR_MIXED"


def _trade_dates(frame: pd.DataFrame) -> pd.Series:
    if "entry_time" in frame.columns:
        dt = pd.to_datetime(frame["entry_time"], utc=True, errors="coerce")
        return dt.apply(
            lambda x: seasonality_context._trading_date(int(x.timestamp() * 1000))
            if not pd.isna(x) else pd.NaT
        )
    if "date" in frame.columns:
        return pd.to_datetime(frame["date"], errors="coerce").dt.date
    return pd.Series([pd.NaT] * len(frame), index=frame.index)


def context_for_run(
    run_id: str | None,
    *,
    workspace: Path | None = None,
    write_file: bool = True,
) -> dict[str, Any]:
    if not run_id:
        return {}
    root = workspace or WORKSPACE
    run_dir = _run_dir(str(run_id), root)
    trades_path = run_dir / "trades.csv"
    config_path = run_dir / "config.json"
    if not trades_path.exists():
        return {"run_id": str(run_id), "available": False, "reason": "trades.csv missing"}

    db = historical_store.db_path(root)
    key = (
        str(run_id),
        int(trades_path.stat().st_mtime_ns),
        int(db.stat().st_mtime_ns if db.exists() else 0),
    )
    if key in _CACHE:
        return _CACHE[key]

    try:
        frame = pd.read_csv(trades_path)
    except Exception as exc:
        return {"run_id": str(run_id), "available": False, "reason": f"{type(exc).__name__}: {exc}"}
    if frame.empty or "r" not in frame.columns:
        return {"run_id": str(run_id), "available": False, "reason": "no trade R data"}

    config = _read_json(config_path)
    market = str(config.get("market") or (frame["market"].iloc[0] if "market" in frame.columns and len(frame) else ""))
    season_market, proxy = _season_market(market)

    x = frame.copy()
    x["r"] = pd.to_numeric(x["r"], errors="coerce")
    x = x.dropna(subset=["r"]).reset_index(drop=True)
    if x.empty:
        return {"run_id": str(run_id), "available": False, "reason": "no numeric R data"}

    x["_trade_date"] = _trade_dates(x)
    x = x[x["_trade_date"].notna()].copy()
    if x.empty:
        return {"run_id": str(run_id), "available": False, "reason": "trade dates unavailable"}

    x["month_of_year"] = [d.month for d in x["_trade_date"]]
    x["quarter"] = [((d.month - 1) // 3) + 1 for d in x["_trade_date"]]
    x["iso_week"] = [d.isocalendar().week for d in x["_trade_date"]]
    x["weekday"] = [d.strftime("%A") for d in x["_trade_date"]]

    seasonal_note = "No supported market seasonality mapping."
    if season_market:
        daily = seasonality_context._daily(season_market, root)
        cache: dict[Any, tuple[dict[str, Any], dict[str, Any]]] = {}
        for d in sorted(set(x["_trade_date"].tolist())):
            cache[d] = (
                seasonality_context.point_in_time_consensus(
                    season_market, d, workspace=root, bucket="iso_week", rows=daily
                ),
                seasonality_context.point_in_time_consensus(
                    season_market, d, workspace=root, bucket="month", rows=daily
                ),
            )
        x["season_week_label"] = [cache[d][0].get("label") for d in x["_trade_date"]]
        x["season_week_score"] = [cache[d][0].get("score") for d in x["_trade_date"]]
        x["season_month_label"] = [cache[d][1].get("label") for d in x["_trade_date"]]
        x["season_month_score"] = [cache[d][1].get("score") for d in x["_trade_date"]]
        x["season_alignment"] = [
            _alignment(side, label)
            for side, label in zip(x.get("side", pd.Series([""] * len(x))), x["season_week_label"])
        ]
        seasonal_note = (
            "Point-in-time safe: each trade uses only earlier Databento dates. "
            "XAU uses GC futures as an explicit proxy." if proxy else
            "Point-in-time safe: each trade uses only earlier Databento dates."
        )
    else:
        x["season_week_label"] = "UNAVAILABLE"
        x["season_month_label"] = "UNAVAILABLE"
        x["season_alignment"] = "NEUTRAL_OR_MIXED"

    baseline = _stats(x)
    alignment_rows = _group_stats(x, "season_alignment")
    aligned = next((z for z in alignment_rows if z.get("value") == "ALIGNED"), None)
    opposed = next((z for z in alignment_rows if z.get("value") == "OPPOSED"), None)
    lift = None
    retention = None
    if aligned and baseline.get("trades"):
        lift = round(_num(aligned.get("expectancy_r")) - _num(baseline.get("expectancy_r")), 6)
        retention = round(100.0 * int(aligned.get("trades") or 0) / int(baseline.get("trades") or 1), 2)

    result = {
        "version": ANALYSIS_VERSION,
        "run_id": str(run_id),
        "available": True,
        "market": market,
        "seasonality_market": season_market,
        "seasonality_proxy": bool(proxy),
        "source": "TMBT Databento history + completed trade ledger",
        "point_in_time_safe": True,
        "automatic_trade_filtering": False,
        "usage": "research_ablation_only",
        "notes": [
            seasonal_note,
            "Calendar/model buckets are descriptive discovery. Confirm any discovered effect on locked Validation before using it as a rule.",
            "External MRCI charts remain an independent reference and are not numerically copied into the strategy engine.",
        ],
        "baseline": baseline,
        "calendar": {
            "month_of_year": _group_stats(x, "month_of_year"),
            "weekday": _group_stats(x, "weekday"),
            "quarter": _group_stats(x, "quarter"),
            "iso_week": _group_stats(x, "iso_week"),
        },
        "market_seasonality": {
            "week_consensus": _group_stats(x, "season_week_label"),
            "month_consensus": _group_stats(x, "season_month_label"),
            "side_alignment": alignment_rows,
            "aligned_expectancy_lift_r": lift,
            "aligned_trade_retention_pct": retention,
            "opposed_summary": opposed,
        },
    }

    if write_file:
        try:
            out = run_dir / "context_analysis.json"
            tmp = out.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
            tmp.replace(out)
        except Exception:
            pass

    _CACHE[key] = result
    while len(_CACHE) > 64:
        _CACHE.pop(next(iter(_CACHE)))
    return result


__all__ = ["ANALYSIS_VERSION", "context_for_run"]
