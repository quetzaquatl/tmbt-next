from __future__ import annotations

from dataclasses import dataclass
from typing import Any


TF_LABELS = ("15m", "30m", "1H")


def _f(v: Any, default: float | None = None) -> float | None:
    try:
        return float(v)
    except Exception:
        return default


def _touch(bar: dict[str, Any], level: float) -> bool:
    lo = _f(bar.get("l"))
    hi = _f(bar.get("h"))
    return lo is not None and hi is not None and lo <= level <= hi


def _fmt_tf(tf: str) -> str:
    z = str(tf or "").lower()
    if z == "1h":
        return "1H"
    return z


def _classify_signal(prev: dict[str, Any], ebp: dict[str, Any]):
    po, pc = _f(prev.get("o")), _f(prev.get("c"))
    pl, ph = _f(prev.get("l")), _f(prev.get("h"))
    eo, ec = _f(ebp.get("o")), _f(ebp.get("c"))
    el, eh = _f(ebp.get("l")), _f(ebp.get("h"))
    if None in (po, pc, pl, ph, eo, ec, el, eh):
        return None
    rng = eh - el
    if rng <= 0:
        return None

    bull = el < pl and ec > max(po, pc)
    bear = eh > ph and ec < min(po, pc)
    if not bull and not bear:
        return None

    side = "Long" if bull else "Short"
    if bull:
        retrace_pct = max(0.0, min(100.0, (eh - ec) / rng * 100.0))
    else:
        retrace_pct = max(0.0, min(100.0, (ec - el) / rng * 100.0))

    if retrace_pct <= 15.0:
        close_class = "Strong"
        if bull:
            entry = eh - 0.25 * rng
            stop = eh - 0.75 * rng
        else:
            entry = el + 0.25 * rng
            stop = el + 0.75 * rng
        entry_mode = "25% limit"
        stop_mode = "75% fib"
    elif retrace_pct <= 50.0:
        close_class = "Indecisive"
        entry = (eh + el) / 2.0
        stop = el if bull else eh
        entry_mode = "50% limit"
        stop_mode = "EBP origin"
    else:
        close_class = "Very indecisive"
        entry = ec
        stop = el if bull else eh
        entry_mode = "market after confirmed close"
        stop_mode = "EBP origin"

    risk = (entry - stop) if bull else (stop - entry)
    if risk <= 0:
        return None
    target = entry + 2.0 * risk if bull else entry - 2.0 * risk
    return {
        "side": side,
        "bull": bull,
        "retrace_pct": retrace_pct,
        "close_class": close_class,
        "entry": entry,
        "stop": stop,
        "target": target,
        "entry_mode": entry_mode,
        "stop_mode": stop_mode,
        "prev": prev,
        "ebp": ebp,
    }


def evaluate_ebp(
    market: str,
    tf: str,
    bars: list[dict[str, Any]],
    *,
    source: str = "",
    ticker: str = "",
    stale: bool = False,
) -> dict[str, Any]:
    tf = _fmt_tf(tf)
    clean = [b for b in (bars or []) if all(_f(b.get(k)) is not None for k in ("o", "h", "l", "c"))]
    enough = len(clean) >= 20
    proxy = str(ticker or "").upper().replace(" ", "") in {"QQQ", "TWELVE:QQQ", "SPY", "TWELVE:SPY"}
    identity = "QQQ proxy" if market == "NQ" and proxy else "SPY proxy" if market == "ES" and proxy else market
    model_id = f"{market.lower()}_ebp_{tf.lower()}"
    label = f"{market} ({identity}) · EBP {tf}" if proxy else f"{market} · EBP {tf}"

    base_logic = {
        "timeframe": tf,
        "bullish": f"sweep previous {tf} low and close above max(previous open, previous close)",
        "bearish": f"sweep previous {tf} high and close below min(previous open, previous close)",
        "same_colour_allowed": True,
        "strong_close_pct": 15.0,
        "strong": "25% limit, 75% stop",
        "indecisive": "50% limit, EBP origin stop",
        "very_indecisive": ">50% retrace => market after confirmed candle close",
        "limit_valid_bars": 4,
        "target_rr": 2.0,
        "breakeven": f"after new HH/LL beyond EBP candle extreme; effective next {tf} bar in OHLC monitor",
        "lookahead_rule": f"only confirmed/closed {tf} candles can create a setup",
        "engine": "TMBT Next parallel EBP v1",
        "execution_gate": "PROXY_DELAYED" if proxy else ("DATA_STALE" if stale else "LIVE_ELIGIBLE"),
    }

    if not enough:
        return {
            "id": model_id,
            "name": label,
            "market": market,
            "tf": tf,
            "source": source,
            "status": "IDLE",
            "side": "—",
            "entry": None,
            "sl": None,
            "tp": None,
            "rr": None,
            "message": f"Zu wenige geschlossene {tf}-Bars für EBP-Auswertung.",
            "validity": {"status": "INVALID", "still_valid": False, "reason": "insufficient_bars"},
            "criteria": [{"label": f"Genügend {tf}-Bars", "status": "FAIL", "detail": f"{len(clean)} Bars geladen; mindestens 20 benötigt."}],
            "logic": base_logic,
            "arrays": {},
            "event": {},
            "setup_key": None,
            "preflight": True,
            "proxy": proxy,
            "feed_stale": stale,
        }

    # Find the most recent qualifying EBP pair. We keep expired setups visible so
    # the UI proves the engine is evaluating the full lifecycle rather than only
    # surfacing current signals.
    found = None
    found_i = None
    start = max(1, len(clean) - 120)
    for i in range(len(clean) - 1, start - 1, -1):
        sig = _classify_signal(clean[i - 1], clean[i])
        if sig:
            found, found_i = sig, i
            break

    if found is None:
        last = clean[-1]
        return {
            "id": model_id,
            "name": label,
            "market": market,
            "tf": tf,
            "source": source,
            "status": "IDLE",
            "side": "—",
            "entry": None,
            "sl": None,
            "tp": None,
            "rr": None,
            "message": f"Kein bestätigtes EBP-Paar in den letzten {min(120, len(clean)-1)} {tf}-Bars.",
            "validity": {"status": "VALID", "still_valid": False, "reason": "no_setup"},
            "criteria": [
                {"label": f"Genügend {tf}-Bars", "status": "PASS", "detail": f"{len(clean)} geschlossene Bars geladen."},
                {"label": f"Previous {tf} Liquidity Sweep + Engulf Close", "status": "PENDING", "detail": "Noch kein gültiges Paar gefunden."},
            ],
            "logic": base_logic,
            "arrays": {},
            "event": {"event_ms": last.get("t")},
            "setup_key": None,
            "preflight": True,
            "proxy": proxy,
            "feed_stale": stale,
        }

    ebp = found["ebp"]
    prev = found["prev"]
    after = clean[found_i + 1 : found_i + 5]
    bars_elapsed = len(clean) - 1 - found_i
    immediate = found["close_class"] == "Very indecisive"
    entry_touched = immediate
    stop_before_entry = False
    touch_bar = None
    if not immediate:
        for b in after:
            stop_hit = _touch(b, found["stop"])
            ent_hit = _touch(b, found["entry"])
            if stop_hit and not ent_hit:
                stop_before_entry = True
                touch_bar = b
                break
            if ent_hit:
                entry_touched = True
                touch_bar = b
                break

    if entry_touched:
        stage = "SIGNAL"
        validity = {"status": "VALID", "still_valid": True, "reason": "EBP entry triggered", "bars_remaining": max(0, 4 - min(4, bars_elapsed))}
        msg = f"{found['side']} EBP {found['close_class']} · {found['entry_mode']} getriggert"
    elif stop_before_entry:
        stage = "EXPIRED"
        validity = {"status": "INVALID", "still_valid": False, "reason": "Stop/Origin vor Entry-Retest verletzt", "bars_remaining": 0}
        msg = f"{found['side']} EBP ungültig vor Entry-Retest"
    elif bars_elapsed >= 4:
        stage = "EXPIRED"
        validity = {"status": "EXPIRED", "still_valid": False, "reason": f"Entry-Retest nicht innerhalb 4 {tf}-Bars", "bars_remaining": 0}
        msg = f"{found['side']} EBP abgelaufen · kein Retest innerhalb 4 Bars"
    else:
        stage = "ARMED"
        validity = {"status": "VALID", "still_valid": True, "reason": "EBP bestätigt; Retest-Fenster offen", "bars_remaining": max(0, 4 - bars_elapsed)}
        msg = f"{found['side']} EBP bestätigt · wartet auf {found['entry_mode']}"

    if proxy:
        msg += " · PROXY/DELAYED: live execution blocked"
    elif stale:
        msg += " · DATA STALE: live execution blocked"

    prev_body_lo = min(_f(prev["o"], 0.0), _f(prev["c"], 0.0))
    prev_body_hi = max(_f(prev["o"], 0.0), _f(prev["c"], 0.0))
    retrace = found["retrace_pct"]
    side = found["side"]
    criteria = [
        {"label": f"Bestätigte {tf}-Paare", "status": "PASS", "detail": f"Previous {tf} + geschlossene EBP-{tf} vorhanden; {len(clean)} Bars geladen."},
        {"label": f"Previous {tf} Liquidity Sweep", "status": "PASS", "detail": f"{side}: {'Low' if side == 'Long' else 'High'} des Previous-{tf} wurde genommen."},
        {"label": "Engulf-Close über gegenüberliegende Body-Seite", "status": "PASS", "detail": f"Previous body {prev_body_lo:.4f}–{prev_body_hi:.4f}."},
        {"label": "Same-colour erlaubt", "status": "PASS", "detail": "Kerzenfarbe ist für die EBP-Kernbedingung kein Filter."},
        {"label": "Close-Stärke", "status": "PASS", "detail": f"Retrace vom EBP-Extrem {retrace:.1f}% → {found['close_class']}."},
        {"label": f"Entry-Retest innerhalb 4 {tf}-Bars", "status": "PASS" if entry_touched else ("FAIL" if stage == "EXPIRED" else "PENDING"), "detail": f"Entry {found['entry']:.4f}; {validity.get('bars_remaining', 0)} Bars Rest."},
        {"label": "Stop", "status": "PASS", "detail": f"{found['stop_mode']} = {found['stop']:.4f}."},
        {"label": "Target", "status": "PASS", "detail": f"2R = {found['target']:.4f}."},
    ]
    setup_key = f"{side}:{int(_f(ebp.get('t'), 0) or 0)}:{tf}"
    arrays = {
        "entry": found["entry"],
        "stop": found["stop"],
        "target": found["target"],
        "prev_high": _f(prev.get("h")),
        "prev_low": _f(prev.get("l")),
        "prev_body_high": prev_body_hi,
        "prev_body_low": prev_body_lo,
        "signal_high": _f(ebp.get("h")),
        "signal_low": _f(ebp.get("l")),
    }
    return {
        "id": model_id,
        "name": label,
        "market": market,
        "tf": tf,
        "source": source,
        "status": stage,
        "side": side,
        "entry": found["entry"],
        "sl": found["stop"],
        "tp": found["target"],
        "rr": 2.0,
        "message": msg,
        "validity": validity,
        "criteria": criteria,
        "logic": base_logic,
        "arrays": arrays,
        "event": {"event_ms": ebp.get("t"), "touch_ms": touch_bar.get("t") if touch_bar else None},
        "setup_key": setup_key,
        "preflight": True,
        "proxy": proxy,
        "feed_stale": stale,
        "close_class": found["close_class"],
        "retrace_pct": retrace,
    }


def build_parallel_models(query_fn) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for market in ("NQ", "ES"):
        for tf in TF_LABELS:
            q = query_fn(market, tf, 800, None) or {}
            out.append(
                evaluate_ebp(
                    market,
                    tf,
                    q.get("bars") or [],
                    source=q.get("provider") or q.get("feed") or "",
                    ticker=q.get("tickerid") or q.get("ticker") or "",
                    stale=bool(q.get("stale", True)),
                )
            )
    return out


def preflight_report(query_fn) -> dict[str, Any]:
    models = build_parallel_models(query_fn)
    checks = []
    for m in models:
        checks.append({
            "model": m["name"],
            "market": m["market"],
            "tf": m["tf"],
            "engine_ok": bool(m.get("criteria")),
            "feed_stale": bool(m.get("feed_stale")),
            "proxy": bool(m.get("proxy")),
            "stage": m.get("status"),
            "setup_key": m.get("setup_key"),
            "actionable_now": not bool(m.get("feed_stale")) and not bool(m.get("proxy")),
        })
    return {
        "engine": "TMBT Next parallel EBP v1",
        "models_expected": 6,
        "models_built": len(models),
        "engine_ready": len(models) == 6 and all(x["engine_ok"] for x in checks),
        "live_ready": len(models) == 6 and all(x["actionable_now"] for x in checks),
        "checks": checks,
        "note": "Engine-ready can pass on delayed QQQ/SPY proxy data. live-ready only passes with fresh true NQ/ES futures data.",
    }
