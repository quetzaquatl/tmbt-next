from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any


STALE_AFTER = {
    "1m": 3 * 60,
    "5m": 8 * 60,
    "15m": 18 * 60,
    "30m": 35 * 60,
    "1h": 65 * 60,
    "4h": 4 * 60 * 60 + 20 * 60,
}


def _ms(v):
    try:
        n = float(v)
        return int(n if n > 1e12 else n * 1000)
    except Exception:
        return None


def _parse_iso(v):
    try:
        if not v:
            return None
        d = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d.astimezone(timezone.utc)
    except Exception:
        return None


def _tf(tf: str) -> str:
    z = str(tf or "").strip().lower()
    return {"h1": "1h", "60m": "1h", "1hr": "1h"}.get(z, z)


def _suffix(tf: str) -> str:
    z = _tf(tf)
    return {"1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m", "1h": "1H", "4h": "4H"}.get(z, tf)


def _roots(workspace: Path):
    return [
        workspace / "live_data" / "futures",
        workspace / "live" / "futures",
        workspace / "github_research_repo" / "live" / "futures",
    ]


def _read_json(path: Path):
    try:
        import json
        x = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
        return x if isinstance(x, dict) else {}
    except Exception:
        return {}


def _normalize_payload(payload: dict[str, Any], market: str, tf: str):
    bars = []
    latest_received = None
    for r in payload.get("bars") or []:
        if not isinstance(r, dict):
            continue
        t = _ms(r.get("bar_open_ms") if r.get("bar_open_ms") is not None else r.get("t"))
        close_t = _ms(r.get("bar_close_ms") if r.get("bar_close_ms") is not None else r.get("close_t"))
        try:
            o = float(r.get("open") if r.get("open") is not None else r.get("o"))
            h = float(r.get("high") if r.get("high") is not None else r.get("h"))
            l = float(r.get("low") if r.get("low") is not None else r.get("l"))
            c = float(r.get("close") if r.get("close") is not None else r.get("c"))
        except Exception:
            continue
        if t is None:
            continue
        recv = _parse_iso(r.get("received_at_utc"))
        if recv and (latest_received is None or recv > latest_received):
            latest_received = recv
        bars.append({
            "t": t,
            "close_t": close_t,
            "o": o,
            "h": h,
            "l": l,
            "c": c,
            "v": r.get("volume") if r.get("volume") is not None else r.get("v"),
            "source": payload.get("source") or r.get("source") or "futures",
            "market": market,
            "tf": tf,
        })
    bars.sort(key=lambda b: b["t"])
    return bars, latest_received


def _aggregate(bars, minutes: int):
    width = minutes * 60 * 1000
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    out = []
    cur = None
    for r in bars or []:
        t = _ms(r.get("t"))
        if t is None:
            continue
        bucket = (t // width) * width
        if cur is None or cur["t"] != bucket:
            if cur is not None and cur["close_t"] <= now_ms:
                out.append(cur)
            cur = {
                "t": bucket,
                "close_t": bucket + width,
                "o": float(r["o"]),
                "h": float(r["h"]),
                "l": float(r["l"]),
                "c": float(r["c"]),
                "v": float(r.get("v") or 0),
                "source": r.get("source"),
                "market": r.get("market"),
                "tf": f"{minutes}m" if minutes != 60 else "1H",
            }
        else:
            cur["h"] = max(cur["h"], float(r["h"]))
            cur["l"] = min(cur["l"], float(r["l"]))
            cur["c"] = float(r["c"])
            try:
                cur["v"] += float(r.get("v") or 0)
            except Exception:
                pass
    if cur is not None and cur["close_t"] <= now_ms:
        out.append(cur)
    return out


def query(workspace: Path, market: str, tf: str, limit: int = 500):
    market = str(market).upper()
    if market not in {"NQ", "ES", "GC"}:
        return None
    ntf = _tf(tf)

    direct = None
    direct_path = None
    for root in _roots(workspace):
        p = root / f"{market}_{_suffix(ntf)}.json"
        x = _read_json(p)
        if x.get("bars"):
            direct, direct_path = x, p
            break

    payload = direct
    bars = []
    latest_received = None
    derived_from = None

    if payload:
        bars, latest_received = _normalize_payload(payload, market, _suffix(ntf))
    elif ntf in {"15m", "30m", "1h", "4h"}:
        base_payload = None
        base_path = None
        for root in _roots(workspace):
            p = root / f"{market}_5m.json"
            x = _read_json(p)
            if x.get("bars"):
                base_payload, base_path = x, p
                break
        if not base_payload:
            return None
        base, latest_received = _normalize_payload(base_payload, market, "5m")
        mins = {"15m": 15, "30m": 30, "1h": 60, "4h": 240}[ntf]
        bars = _aggregate(base, mins)
        payload = base_payload
        direct_path = base_path
        derived_from = "5m"
    else:
        return None

    if not bars:
        return None
    bars = bars[-max(50, int(limit)):]
    last = bars[-1]
    now = datetime.now(timezone.utc)
    last_close = _ms(last.get("close_t")) or _ms(last.get("t"))
    bar_age = max(0.0, (now.timestamp() * 1000 - last_close) / 1000.0) if last_close else None
    recv_age = max(0.0, (now - latest_received).total_seconds()) if latest_received else None
    age = recv_age if recv_age is not None else bar_age
    stale_after = STALE_AFTER.get(ntf, 65 * 60)
    stale = age is None or age > stale_after
    ticker = str(payload.get("ticker") or payload.get("tickerid") or "")
    provider = str(payload.get("source") or "futures")
    return {
        "bars": bars,
        "db": str(direct_path) if direct_path else None,
        "table": None,
        "source": None,
        "feed": "true_futures_mirror",
        "provider": provider,
        "ticker": ticker,
        "tickerid": str(payload.get("tickerid") or ticker),
        "exchange": str(payload.get("exchange") or ("COMEX" if market == "GC" else "CME")),
        "last_received_at_utc": latest_received.isoformat() if latest_received else None,
        "last_bar_utc": datetime.fromtimestamp(last_close / 1000.0, tz=timezone.utc).isoformat() if last_close else None,
        "age_seconds": age,
        "stale": stale,
        "canonical": True,
        "identity_ok": True,
        "derived_from": derived_from,
        "note": f"{provider} · {ticker or market} · TRUE FUTURES · {'STALE' if stale else 'LIVE'}",
    }
