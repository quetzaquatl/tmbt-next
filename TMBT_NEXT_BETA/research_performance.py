from __future__ import annotations

import math
import os
from pathlib import Path
from typing import Any

import pandas as pd

import model_context_analysis

WORKSPACE = Path(
    os.environ.get(
        "TMBT_WORKSPACE",
        r"D:\Projekt model\Trading_Model_Backtest_Studio_WORKSPACE",
    )
).resolve()

DEFAULT_START_BALANCE_EUR = float(os.environ.get("TMBT_BACKTEST_START_BALANCE_EUR", "10000"))
DEFAULT_RISK_PCT = float(os.environ.get("TMBT_BACKTEST_RISK_PCT", "1.0"))

_CACHE: dict[tuple[str, float, float, float], dict[str, Any]] = {}


def _num(value: Any, default: float = 0.0) -> float:
    try:
        x = float(value)
        return x if math.isfinite(x) else default
    except Exception:
        return default


def _run_dir(run_id: str) -> Path:
    return WORKSPACE / "runs" / str(run_id)


def _streak(values: list[float], positive: bool) -> int:
    best = cur = 0
    for x in values:
        ok = x > 0 if positive else x < 0
        if ok:
            cur += 1
            best = max(best, cur)
        else:
            cur = 0
    return best


def _side_stats(frame: pd.DataFrame, side: str) -> dict[str, Any]:
    if "side" not in frame.columns:
        return {"side": side, "trades": 0}
    x = frame[frame["side"].astype(str).str.lower() == side.lower()].copy()
    if x.empty:
        return {"side": side, "trades": 0}
    r = pd.to_numeric(x["r"], errors="coerce").dropna()
    return {
        "side": side,
        "trades": int(len(r)),
        "wins": int((r > 0).sum()),
        "losses": int((r < 0).sum()),
        "winrate_pct": float((r > 0).mean() * 100.0) if len(r) else 0.0,
        "net_r": float(r.sum()) if len(r) else 0.0,
        "expectancy_r": float(r.mean()) if len(r) else 0.0,
    }


def _exit_stats(frame: pd.DataFrame) -> list[dict[str, Any]]:
    if "exit_reason" not in frame.columns or frame.empty:
        return []
    rows = []
    for reason, group in frame.groupby(frame["exit_reason"].fillna("UNKNOWN").astype(str), dropna=False):
        r = pd.to_numeric(group["r"], errors="coerce").dropna()
        rows.append(
            {
                "reason": str(reason),
                "trades": int(len(r)),
                "net_r": float(r.sum()) if len(r) else 0.0,
                "winrate_pct": float((r > 0).mean() * 100.0) if len(r) else 0.0,
            }
        )
    rows.sort(key=lambda x: x["trades"], reverse=True)
    return rows


def _monthly_stats(frame: pd.DataFrame) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    x = frame.copy()
    if "month" not in x.columns:
        time_col = "exit_time" if "exit_time" in x.columns else "entry_time" if "entry_time" in x.columns else None
        if time_col:
            dt = pd.to_datetime(x[time_col], utc=True, errors="coerce")
            x["month"] = dt.dt.strftime("%Y-%m")
        else:
            return []
    x["r"] = pd.to_numeric(x["r"], errors="coerce")
    rows = []
    for month, group in x.dropna(subset=["r"]).groupby("month", dropna=False):
        r = group["r"]
        rows.append(
            {
                "month": str(month),
                "trades": int(len(r)),
                "net_r": float(r.sum()),
                "expectancy_r": float(r.mean()),
                "winrate_pct": float((r > 0).mean() * 100.0),
            }
        )
    rows.sort(key=lambda x: x["month"])
    return rows


def _trade_label(row: pd.Series) -> dict[str, Any]:
    when = row.get("exit_time") if "exit_time" in row else row.get("entry_time")
    return {
        "r": _num(row.get("r")),
        "side": str(row.get("side") or ""),
        "entry_time": str(row.get("entry_time") or ""),
        "exit_time": str(row.get("exit_time") or when or ""),
        "exit_reason": str(row.get("exit_reason") or ""),
        "entry_price": _num(row.get("entry_price")),
        "exit_price": _num(row.get("exit_price")),
        "planned_rr": _num(row.get("planned_rr")),
        "mfe_r": _num(row.get("mfe_r")),
        "mae_r": _num(row.get("mae_r")),
        "hold_minutes": _num(row.get("hold_minutes")),
    }


def performance_for_run(
    run_id: str | None,
    *,
    start_balance_eur: float = DEFAULT_START_BALANCE_EUR,
    risk_pct: float = DEFAULT_RISK_PCT,
) -> dict[str, Any]:
    if not run_id:
        return {}
    run_dir = _run_dir(str(run_id))
    trades_path = run_dir / "trades.csv"
    if not trades_path.exists():
        return {"run_id": str(run_id), "available": False, "reason": "trades.csv missing"}

    mtime = trades_path.stat().st_mtime
    key = (str(run_id), float(start_balance_eur), float(risk_pct), float(mtime))
    cached = _CACHE.get(key)
    if cached is not None:
        return cached

    try:
        frame = pd.read_csv(trades_path)
    except Exception as exc:
        return {"run_id": str(run_id), "available": False, "reason": f"{type(exc).__name__}: {exc}"}

    if frame.empty or "r" not in frame.columns:
        return {"run_id": str(run_id), "available": False, "reason": "no trade R data"}

    frame = frame.copy()
    frame["r"] = pd.to_numeric(frame["r"], errors="coerce")
    frame = frame.dropna(subset=["r"]).reset_index(drop=True)
    if frame.empty:
        return {"run_id": str(run_id), "available": False, "reason": "no numeric R data"}

    if "exit_time" in frame.columns:
        frame["_sort_time"] = pd.to_datetime(frame["exit_time"], utc=True, errors="coerce")
    elif "entry_time" in frame.columns:
        frame["_sort_time"] = pd.to_datetime(frame["entry_time"], utc=True, errors="coerce")
    else:
        frame["_sort_time"] = pd.NaT
    frame = frame.sort_values(["_sort_time"], kind="stable", na_position="last").reset_index(drop=True)

    rvals = frame["r"].astype(float).tolist()
    gross_win_r = float(frame.loc[frame["r"] > 0, "r"].sum())
    gross_loss_r = float(-frame.loc[frame["r"] < 0, "r"].sum())
    profit_factor = gross_win_r / gross_loss_r if gross_loss_r > 0 else None

    balance = float(start_balance_eur)
    peak = balance
    max_dd_eur = 0.0
    max_dd_pct = 0.0
    gross_profit_eur = 0.0
    gross_loss_eur = 0.0
    curve = [{
        "i": 0,
        "balance_eur": round(balance, 2),
        "drawdown_eur": 0.0,
        "drawdown_pct": 0.0,
        "r": 0.0,
        "time": "",
    }]
    pnl_eur_values: list[float] = []

    for i, row in frame.iterrows():
        rr = float(row["r"])
        risk_eur = max(0.0, balance * float(risk_pct) / 100.0)
        pnl_eur = rr * risk_eur
        balance += pnl_eur
        peak = max(peak, balance)
        dd_eur = max(0.0, peak - balance)
        dd_pct = (dd_eur / peak * 100.0) if peak > 0 else 0.0
        max_dd_eur = max(max_dd_eur, dd_eur)
        max_dd_pct = max(max_dd_pct, dd_pct)
        if pnl_eur > 0:
            gross_profit_eur += pnl_eur
        elif pnl_eur < 0:
            gross_loss_eur += -pnl_eur
        pnl_eur_values.append(float(pnl_eur))
        t = row.get("exit_time") if "exit_time" in frame.columns else row.get("entry_time")
        curve.append(
            {
                "i": int(i + 1),
                "balance_eur": round(balance, 2),
                "drawdown_eur": round(dd_eur, 2),
                "drawdown_pct": round(dd_pct, 4),
                "r": round(rr, 6),
                "time": str(t or ""),
            }
        )

    wins = frame[frame["r"] > 0]
    losses = frame[frame["r"] < 0]
    best_idx = frame["r"].idxmax()
    worst_idx = frame["r"].idxmin()
    best_trade = _trade_label(frame.loc[best_idx])
    worst_trade = _trade_label(frame.loc[worst_idx])
    best_trade["pnl_eur"] = round(pnl_eur_values[int(best_idx)], 2)
    worst_trade["pnl_eur"] = round(pnl_eur_values[int(worst_idx)], 2)

    avg_hold = _num(pd.to_numeric(frame.get("hold_minutes"), errors="coerce").mean()) if "hold_minutes" in frame.columns else 0.0
    avg_mfe = _num(pd.to_numeric(frame.get("mfe_r"), errors="coerce").mean()) if "mfe_r" in frame.columns else 0.0
    avg_mae = _num(pd.to_numeric(frame.get("mae_r"), errors="coerce").mean()) if "mae_r" in frame.columns else 0.0
    avg_rr = _num(pd.to_numeric(frame.get("planned_rr"), errors="coerce").mean()) if "planned_rr" in frame.columns else 0.0

    net_profit_eur = balance - float(start_balance_eur)
    return_pct = (net_profit_eur / float(start_balance_eur) * 100.0) if start_balance_eur else 0.0
    expectancy_r = float(frame["r"].mean())
    recovery_factor = (net_profit_eur / max_dd_eur) if max_dd_eur > 0 else None

    result = {
        "run_id": str(run_id),
        "available": True,
        "accounting": {
            "start_balance_eur": round(float(start_balance_eur), 2),
            "risk_pct_per_r": round(float(risk_pct), 4),
            "method": "reporting simulation: 1R equals configured percent of current equity; compounded",
            "affects_strategy_logic": False,
        },
        "metrics": {
            "trades": int(len(frame)),
            "wins": int(len(wins)),
            "losses": int(len(losses)),
            "breakeven": int((frame["r"] == 0).sum()),
            "winrate_pct": float((frame["r"] > 0).mean() * 100.0),
            "net_r": float(frame["r"].sum()),
            "expectancy_r": expectancy_r,
            "median_r": float(frame["r"].median()),
            "avg_win_r": float(wins["r"].mean()) if len(wins) else 0.0,
            "avg_loss_r": float(losses["r"].mean()) if len(losses) else 0.0,
            "gross_profit_r": gross_win_r,
            "gross_loss_r": gross_loss_r,
            "profit_factor": profit_factor,
            "max_consecutive_wins": _streak(rvals, True),
            "max_consecutive_losses": _streak(rvals, False),
            "avg_planned_rr": avg_rr,
            "avg_hold_minutes": avg_hold,
            "avg_mfe_r": avg_mfe,
            "avg_mae_r": avg_mae,
            "start_balance_eur": round(float(start_balance_eur), 2),
            "end_balance_eur": round(balance, 2),
            "net_profit_eur": round(net_profit_eur, 2),
            "return_pct": round(return_pct, 4),
            "gross_profit_eur": round(gross_profit_eur, 2),
            "gross_loss_eur": round(gross_loss_eur, 2),
            "max_drawdown_eur": round(max_dd_eur, 2),
            "max_drawdown_pct": round(max_dd_pct, 4),
            "recovery_factor": recovery_factor,
        },
        "best_trade": best_trade,
        "worst_trade": worst_trade,
        "sides": [_side_stats(frame, "Long"), _side_stats(frame, "Short")],
        "exit_reasons": _exit_stats(frame),
        "monthly": _monthly_stats(frame),
        "context_analysis": model_context_analysis.context_for_run(str(run_id), workspace=WORKSPACE),
        "equity_curve": curve,
    }
    _CACHE[key] = result
    while len(_CACHE) > 32:
        _CACHE.pop(next(iter(_CACHE)))
    return result


def _stage(report: dict[str, Any], name: str) -> dict[str, Any]:
    for row in report.get("stages") or []:
        if isinstance(row, dict) and row.get("name") == name:
            return row
    return {}


def performance_bundle(report: dict[str, Any]) -> dict[str, Any]:
    baseline = _stage(report, "development_baseline")
    candidate = _stage(report, "optimized_development_candidate")
    news = _stage(report, "forex_factory_selection")
    validation = _stage(report, "validation")
    full_history = _stage(report, "full_history_diagnostic")

    selected_news = (news.get("selected") or {}) if news else {}
    development_run = selected_news.get("run_id") or candidate.get("run_id")

    return {
        "accounting": {
            "start_balance_eur": round(DEFAULT_START_BALANCE_EUR, 2),
            "risk_pct_per_r": round(DEFAULT_RISK_PCT, 4),
            "affects_strategy_logic": False,
        },
        "baseline": performance_for_run(baseline.get("run_id")),
        "development": performance_for_run(development_run),
        "validation": performance_for_run(validation.get("run_id")),
        "full_history": performance_for_run(full_history.get("run_id")),
    }
