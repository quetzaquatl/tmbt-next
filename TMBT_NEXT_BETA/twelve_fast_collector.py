from __future__ import annotations

import importlib
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import legacy_runtime

WORKSPACE = Path(
    os.environ.get(
        "TMBT_WORKSPACE",
        r"D:\Projekt model\Trading_Model_Backtest_Studio_WORKSPACE",
    )
).resolve()


def _load_legacy():
    root = legacy_runtime.activate()
    mod = sys.modules.get("twelve_live")
    if mod is not None:
        f = str(getattr(mod, "__file__", ""))
        if f and str(root) not in f:
            sys.modules.pop("twelve_live", None)
    return importlib.import_module("twelve_live")


def _read_json(path: Path) -> dict[str, Any]:
    import json
    try:
        x = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
        return x if isinstance(x, dict) else {}
    except Exception:
        return {}


def _cache_ready(subs: list[dict[str, Any]]) -> bool:
    root = WORKSPACE / "live_data" / "twelve"
    if not root.exists():
        return False
    for sub in subs:
        alias = str(sub.get("alias") or sub.get("symbol") or "DATA").upper()
        p = root / f"{alias}_5m.json"
        x = _read_json(p)
        if not isinstance(x.get("bars"), list) or not x.get("bars"):
            return False
    return True


def _fast_run(tl) -> None:
    api_key = os.environ.get("TWELVE_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("TWELVE_API_KEY missing")

    cfg = tl.load_twelve_config(WORKSPACE)
    subs = [x for x in list(cfg.get("subscriptions") or []) if str(x.get("symbol") or "").strip()]
    resolutions = [x for x in list(cfg.get("resolutions") or []) if x in tl.INTERVAL_TO_TF]
    if "5min" not in resolutions:
        resolutions = ["5min"] + resolutions

    # First-ever setup still uses the audited legacy full backfill. Once a local
    # mirror exists, restarts use only three 5m catch-up requests and rebuild
    # higher TFs locally. This avoids 15-request startup backfills every reboot.
    if not _cache_ready(subs):
        tl._run_connector(WORKSPACE)
        return

    poll_seconds = int(cfg.get("poll_seconds", 420))
    daily_budget = int(cfg.get("daily_budget", 720))
    catchup_bars = max(12, min(int(cfg.get("backfill_bars", 300)), 120))

    tl._write_status(
        WORKSPACE,
        {
            "pid": os.getpid(),
            "running": True,
            "connected": False,
            "state": "catchup",
            "provider": "Twelve Data",
            "poll_seconds": poll_seconds,
            "daily_budget": daily_budget,
            "startup_mode": "fast_5m_catchup",
            "subscriptions": subs,
        },
    )

    request_count = 0
    day_key = datetime.now(timezone.utc).date().isoformat()
    credits_left: str | None = None
    latest_quotes: dict[str, Any] = {}

    for sub in subs:
        alias = str(sub.get("alias") or sub.get("symbol") or "DATA").upper()
        symbol = str(sub.get("symbol") or "").strip()
        try:
            data, hdr = tl._fetch_series(
                api_key,
                symbol=symbol,
                interval="5min",
                outputsize=catchup_bars,
            )
            request_count += 1
            credits_left = hdr.get("api_credits_left") or credits_left
            n = tl._ingest_time_series(
                WORKSPACE,
                alias=alias,
                symbol=symbol,
                interval="5min",
                response=data,
            )
            tl._refresh_aggregates_from_5m(
                WORKSPACE,
                alias,
                symbol,
                resolutions,
            )
            vals = list(data.get("values") or [])
            if vals:
                newest = max(vals, key=lambda x: str(x.get("datetime") or ""))
                latest_quotes[alias] = {
                    "symbol": symbol,
                    "price": newest.get("close"),
                    "datetime": newest.get("datetime"),
                }
            tl._write_status(
                WORKSPACE,
                {
                    "connected": True,
                    "state": "catchup",
                    "requests_today": request_count,
                    "credits_left": credits_left,
                    "last_bar": {
                        "market": alias,
                        "symbol": symbol,
                        "tf": "5m",
                        "bars_received": n,
                    },
                    "quotes": latest_quotes,
                    "last_error": "",
                },
            )
        except Exception as exc:
            msg = str(exc)
            tl._write_status(
                WORKSPACE,
                {
                    "connected": False,
                    "state": "catchup_error",
                    "requests_today": request_count,
                    "last_error": f"{symbol}: {msg[:500]}",
                },
            )
            if "429" in msg or "Too Many Requests" in msg:
                time.sleep(65)
            else:
                time.sleep(8)
        else:
            time.sleep(8)

    tl._write_status(
        WORKSPACE,
        {
            "connected": True,
            "state": "polling",
            "startup_mode": "fast_5m_catchup",
            "quotes": latest_quotes,
            "last_error": "",
        },
    )

    while True:
        now_day = datetime.now(timezone.utc).date().isoformat()
        if now_day != day_key:
            day_key = now_day
            request_count = 0

        if request_count >= daily_budget:
            tl._write_status(
                WORKSPACE,
                {
                    "connected": True,
                    "state": "quota_pause",
                    "requests_today": request_count,
                },
            )
            tl._sleep_interruptible(300)
            continue

        cycle_errors: list[str] = []
        for sub in subs:
            alias = str(sub.get("alias") or sub.get("symbol") or "DATA").upper()
            symbol = str(sub.get("symbol") or "").strip()
            if request_count >= daily_budget:
                break
            try:
                data, hdr = tl._fetch_series(
                    api_key,
                    symbol=symbol,
                    interval="5min",
                    outputsize=4,
                )
                request_count += 1
                credits_left = hdr.get("api_credits_left") or credits_left
                n = tl._ingest_time_series(
                    WORKSPACE,
                    alias=alias,
                    symbol=symbol,
                    interval="5min",
                    response=data,
                )
                tl._refresh_aggregates_from_5m(
                    WORKSPACE,
                    alias,
                    symbol,
                    resolutions,
                )
                vals = list(data.get("values") or [])
                if vals:
                    newest = max(vals, key=lambda x: str(x.get("datetime") or ""))
                    latest_quotes[alias] = {
                        "symbol": symbol,
                        "price": newest.get("close"),
                        "datetime": newest.get("datetime"),
                    }
                tl._write_status(
                    WORKSPACE,
                    {
                        "connected": True,
                        "state": "polling",
                        "startup_mode": "fast_5m_catchup",
                        "requests_today": request_count,
                        "credits_left": credits_left,
                        "quotes": latest_quotes,
                        "last_bar": {
                            "market": alias,
                            "symbol": symbol,
                            "tf": "5m",
                            "bars_received": n,
                        },
                        "last_error": "",
                    },
                )
            except Exception as exc:
                cycle_errors.append(f"{symbol}: {str(exc)[:240]}")
                request_count += 1
                tl._write_status(
                    WORKSPACE,
                    {
                        "connected": False,
                        "state": "poll_error",
                        "startup_mode": "fast_5m_catchup",
                        "requests_today": request_count,
                        "credits_left": credits_left,
                        "last_error": " | ".join(cycle_errors)[-700:],
                    },
                )

        if not cycle_errors:
            tl._write_status(
                WORKSPACE,
                {
                    "connected": True,
                    "state": "polling",
                    "startup_mode": "fast_5m_catchup",
                },
            )
        tl._sleep_interruptible(poll_seconds)


def main() -> None:
    tl = _load_legacy()
    tl._write_status(
        WORKSPACE,
        {
            "pid": os.getpid(),
            "running": True,
            "connected": False,
            "state": "starting",
            "startup_mode": "tmbt_fast_collector",
        },
    )
    try:
        _fast_run(tl)
    except KeyboardInterrupt:
        pass
    except Exception as exc:
        tl._write_status(
            WORKSPACE,
            {
                "connected": False,
                "state": "error",
                "last_error": str(exc)[:700],
            },
        )
        raise
    finally:
        tl._write_status(
            WORKSPACE,
            {
                "running": False,
                "connected": False,
                "state": "stopped",
            },
        )


if __name__ == "__main__":
    main()
