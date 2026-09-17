from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


WORKSPACE = Path(os.environ.get("TMBT_WORKSPACE", r"D:\Projekt model\Trading_Model_Backtest_Studio_WORKSPACE")).resolve()
OUT_DIR = WORKSPACE / "live_data" / "futures"
STATUS = WORKSPACE / "live_data" / "massive_futures_status.json"
PID_FILE = Path(__file__).resolve().parent / "massive_futures.pid"
POLL_SECONDS = max(10, int(os.environ.get("TMBT_MASSIVE_POLL_SECONDS", "20")))
LOOKBACK_DAYS = max(2, int(os.environ.get("TMBT_MASSIVE_LOOKBACK_DAYS", "5")))

# On 2026-09-17 the December contracts are already the liquid roll contracts.
# Keep environment overrides so the bridge remains explicit and rollover-safe.
CONTRACTS = {
    "NQ": os.environ.get("TMBT_NQ_CONTRACT", "NQZ6").strip().upper(),
    "ES": os.environ.get("TMBT_ES_CONTRACT", "ESZ6").strip().upper(),
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def write_status(**kwargs) -> None:
    current = {}
    try:
        current = json.loads(STATUS.read_text(encoding="utf-8")) if STATUS.exists() else {}
    except Exception:
        current = {}
    current.update(kwargs)
    current["updated_at_utc"] = now_iso()
    write_json(STATUS, current)


def pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            r = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"], capture_output=True, timeout=4)
            return str(pid).encode("ascii") in (r.stdout or b"")
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def prevent_duplicate() -> None:
    try:
        pid = int(PID_FILE.read_text(encoding="utf-8").strip())
    except Exception:
        pid = 0
    if pid and pid != os.getpid() and pid_alive(pid):
        raise SystemExit(f"Massive futures bridge already running as PID {pid}")
    PID_FILE.write_text(str(os.getpid()), encoding="utf-8")


def obj_get(x: Any, name: str, default=None):
    if isinstance(x, dict):
        return x.get(name, default)
    return getattr(x, name, default)


def ns_to_ms(v: Any) -> int | None:
    try:
        n = int(v)
    except Exception:
        return None
    if n > 10**17:  # nanoseconds
        return n // 1_000_000
    if n > 10**14:  # microseconds
        return n // 1_000
    if n > 10**11:  # milliseconds
        return n
    return n * 1000


def fetch_5m(client, alias: str, ticker: str) -> dict[str, Any]:
    start = (datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)).date().isoformat()
    rows = list(client.list_futures_aggregates(
        ticker=ticker,
        resolution="5min",
        window_start_gte=start,
        sort="window_start.asc",
        limit=5000,
    ))
    received = now_iso()
    bars = []
    for a in rows:
        t = ns_to_ms(obj_get(a, "window_start"))
        if t is None:
            continue
        try:
            o = float(obj_get(a, "open"))
            h = float(obj_get(a, "high"))
            l = float(obj_get(a, "low"))
            c = float(obj_get(a, "close"))
        except Exception:
            continue
        bars.append({
            "bar_open_ms": t,
            "bar_close_ms": t + 5 * 60 * 1000,
            "open": o,
            "high": h,
            "low": l,
            "close": c,
            "volume": obj_get(a, "volume"),
            "received_at_utc": received,
        })
    bars.sort(key=lambda x: x["bar_open_ms"])
    if not bars:
        raise RuntimeError(f"Massive returned no 5m bars for {ticker}")
    return {
        "source": "massive",
        "market": alias,
        "ticker": ticker,
        "tickerid": f"MASSIVE:{ticker}",
        "exchange": "CME",
        "timeframe": "5m",
        "generated_at_utc": received,
        "bars": bars[-1500:],
    }


def main() -> None:
    prevent_duplicate()
    api_key = os.environ.get("MASSIVE_API_KEY", "").strip()
    if not api_key:
        write_status(running=False, connected=False, state="error", last_error="MASSIVE_API_KEY missing", contracts=CONTRACTS)
        raise SystemExit("MASSIVE_API_KEY missing")
    try:
        from massive import RESTClient
    except Exception:
        msg = "Python package missing: pip install -U massive-api-client"
        write_status(running=False, connected=False, state="error", last_error=msg, contracts=CONTRACTS)
        raise SystemExit(msg)

    client = RESTClient(api_key, pagination=True)
    write_status(pid=os.getpid(), running=True, connected=False, state="starting", provider="Massive", contracts=CONTRACTS, poll_seconds=POLL_SECONDS, last_error="")
    try:
        while True:
            cycle = {}
            errors = []
            for alias, ticker in CONTRACTS.items():
                try:
                    payload = fetch_5m(client, alias, ticker)
                    write_json(OUT_DIR / f"{alias}_5m.json", payload)
                    last = payload["bars"][-1]
                    cycle[alias] = {
                        "ticker": ticker,
                        "bars": len(payload["bars"]),
                        "last_bar_open_ms": last["bar_open_ms"],
                        "last_bar_close_ms": last["bar_close_ms"],
                        "price": last["close"],
                    }
                except Exception as exc:
                    errors.append(f"{alias}/{ticker}: {exc}")
            ok = len(cycle) == len(CONTRACTS)
            write_status(
                pid=os.getpid(), running=True, connected=ok, state="polling" if ok else "degraded",
                provider="Massive", contracts=CONTRACTS, quotes=cycle,
                last_error=" | ".join(errors)[:1000], poll_seconds=POLL_SECONDS,
            )
            time.sleep(POLL_SECONDS)
    finally:
        try:
            PID_FILE.unlink(missing_ok=True)
        except Exception:
            pass
        write_status(running=False, connected=False, state="stopped")


if __name__ == "__main__":
    main()
