from __future__ import annotations

"""Live monitor for the public TTFM research models.

Safety:
- Uses TRUE futures mirrors only. QQQ/SPY/XAU spot are never substituted.
- Emits monitor states only (WATCH/FORMING/READY/BLOCKED/IDLE).
- Never emits SIGNAL/TRIGGERED and therefore cannot enter paper/live trades.
- READY means the public-core entry confirmation exists; promotion to execution
  remains blocked until the corresponding research profile passes review.
"""

from datetime import datetime, timezone
from typing import Any
import time

import pandas as pd

import futures_mirror
import ttfm_engine


_CACHE: dict[str, Any] = {"at": 0.0, "models": []}
CACHE_SECONDS = 15.0

PROFILE_MATRIX = (
    ("D1_H1_M5", "TTFM D1-H1-M5", "D1 → H1 → M5", "5m"),
    ("D1_H4_M15", "TTFM D1-H4-M15", "D1 → H4 → M15", "15m"),
    ("H1_M15_M1", "TTFM H1-M15-M1", "H1 → M15 → M1 Scalping", "1m"),
)


def _ms(v: Any) -> int | None:
    try:
        n = float(v)
        return int(n if n > 1e12 else n * 1000)
    except Exception:
        return None


def _df(bars: list[dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for b in bars or []:
        t = _ms(b.get("t") if b.get("t") is not None else b.get("bar_open_ms"))
        if t is None:
            continue
        try:
            o, h, l, c = (float(b[k]) for k in ("o", "h", "l", "c"))
        except Exception:
            try:
                o = float(b["open"]); h = float(b["high"]); l = float(b["low"]); c = float(b["close"])
            except Exception:
                continue
        rows.append({
            "t": pd.to_datetime(t, unit="ms", utc=True),
            "mid_open": o, "mid_high": h, "mid_low": l, "mid_close": c,
            "bid_open": o, "bid_high": h, "bid_low": l, "bid_close": c,
            "ask_open": o, "ask_high": h, "ask_low": l, "ask_close": c,
            "tick_count": float(b.get("v") or 1.0),
        })
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).set_index("t").sort_index()


def _crit(label: str, status: str, detail: str) -> dict[str, str]:
    return {"label": label, "status": status, "detail": detail}


def _base_logic(spec: dict[str, Any]) -> dict[str, Any]:
    return {
        "engine": ttfm_engine.PUBLIC_RULE_VERSION,
        "mode": "MONITOR_ONLY_UNTIL_REVIEW",
        "anchor_tf": spec["anchor_tf"],
        "confirm_tf": spec["confirm_tf"],
        "entry_tf": spec["entry_tf"],
        "closure": "C2 reversal close; C3 public fallback",
        "confirmation": "lower-TF CISD + protected swing",
        "poi_priority": "FVG -> prior swing; CISD confirms",
        "lookahead": "closed bars only; no Early C2 CISD",
        "execution": "blocked until research profile passes manual review",
        "feed_rule": "true futures only; no QQQ/SPY/XAU substitution",
    }


def _blocked(market: str, suffix: str, label: str, spec: dict[str, Any], reason: str, *, stale=False) -> dict[str, Any]:
    return {
        "id": f"{market.lower()}_ttfm_{suffix.lower()}",
        "name": f"{market} · TTFM {label}",
        "market": market,
        "tf": spec["entry_tf"],
        "status": "BLOCKED",
        "side": "—",
        "entry": None, "sl": None, "tp": None, "rr": None,
        "message": reason,
        "validity": {"status": "INVALID", "still_valid": False, "reason": reason},
        "criteria": [_crit("True Futures Feed", "FAIL", reason)],
        "logic": _base_logic(spec),
        "arrays": {},
        "event": {},
        "setup_key": None,
        "proxy": True,
        "feed_stale": bool(stale),
        "research_only": True,
        "live_trade_allowed": False,
    }


def _find_confirm(segment: pd.DataFrame, side: str) -> Any:
    return ttfm_engine._find_cisd(
        segment,
        side,
        pivot_left=2,
        pivot_right=2,
        max_confirm_bars=12,
        require_local_poi=False,
    )


def _find_entry(segment: pd.DataFrame, side: str) -> Any:
    return ttfm_engine._find_cisd(
        segment,
        side,
        pivot_left=2,
        pivot_right=2,
        max_confirm_bars=8,
        require_local_poi=True,
    )


def _daily_model(market: str, suffix: str, label: str, spec: dict[str, Any], base: pd.DataFrame, source: str) -> dict[str, Any]:
    daily = ttfm_engine._aggregate(base, "1D", "America/New_York")
    if len(daily) < 3:
        return _blocked(market, suffix, label, spec, "Zu wenig True-Futures-Historie für bestätigte Daily TTFM-Struktur.")

    # Only completed Globex Daily candles may become anchors.
    now = pd.Timestamp.now(tz="UTC")
    daily = daily[(daily.index + pd.Timedelta(days=1)) <= now]
    anchor = ttfm_engine.latest_closure_event(daily, 2, 2)
    if not anchor:
        return {
            **_blocked(market, suffix, label, spec, "Kein bestätigter Daily C2/C3-Fractal vorhanden."),
            "status": "IDLE", "proxy": False,
            "criteria": [
                _crit("True Futures Feed", "PASS", source),
                _crit("Daily C2/C3 Closure", "PENDING", "Wartet auf abgeschlossene Fractal-Closure."),
            ],
        }

    side = anchor.side
    confirm_all = ttfm_engine._aggregate(base, spec["confirm_tf"], "America/New_York")
    confirm_segment = ttfm_engine._filter_between(confirm_all, anchor.candle_open_time, anchor.close_time)
    confirm = _find_confirm(confirm_segment, side)

    common = {
        "id": f"{market.lower()}_ttfm_{suffix.lower()}",
        "name": f"{market} · TTFM {label}",
        "market": market,
        "tf": spec["entry_tf"],
        "side": side,
        "source": source,
        "rr": 2.0,
        "proxy": False,
        "feed_stale": False,
        "research_only": True,
        "live_trade_allowed": False,
        "logic": _base_logic(spec),
        "setup_key": f"{market}:{suffix}:{int(anchor.candle_open_time.timestamp())}:{side}",
        "event": {"event_ms": int(anchor.candle_open_time.timestamp() * 1000)},
    }

    if not confirm:
        return {
            **common,
            "status": "WATCH",
            "entry": None, "sl": None, "tp": None,
            "message": f"{side} Daily {anchor.kind} bestätigt · wartet auf {spec['confirm_tf']} CISD.",
            "validity": {"status": "VALID", "still_valid": True, "reason": "HTF closure confirmed; confirmation TF pending"},
            "criteria": [
                _crit("True Futures Feed", "PASS", source),
                _crit(f"Daily {anchor.kind} Closure", "PASS", f"{side} · POI {anchor.poi_type} @ {anchor.poi_level:.2f}"),
                _crit(f"{spec['confirm_tf']} CISD", "PENDING", "Noch keine bestätigte CISD in der Anchor-Candle."),
            ],
            "arrays": {"anchor_poi": anchor.poi_level, "range_eq": anchor.range_eq},
        }

    # Entry structure must form after the completed Daily anchor, i.e. current
    # Globex session. Use all bars after anchor close, never bars from the future.
    entry_all = ttfm_engine._aggregate(base, spec["entry_tf"], "America/New_York")
    entry_segment = entry_all[entry_all.index >= anchor.close_time].copy()
    entry = _find_entry(entry_segment, side)

    if not entry:
        return {
            **common,
            "status": "ARMED",
            "entry": None,
            "sl": confirm.protected_swing,
            "tp": None,
            "message": f"{side} {spec['confirm_tf']} CISD bestätigt · wartet auf {spec['entry_tf']} CISD/POI.",
            "validity": {"status": "VALID", "still_valid": True, "reason": "HTF + confirmation TF complete; entry TF pending"},
            "criteria": [
                _crit("True Futures Feed", "PASS", source),
                _crit(f"Daily {anchor.kind} Closure", "PASS", f"{side} · {anchor.source_variant}"),
                _crit(f"{spec['confirm_tf']} CISD", "PASS", f"Protected swing {confirm.protected_swing:.2f}"),
                _crit(f"{spec['entry_tf']} CISD + POI", "PENDING", "Entry-Fractal noch nicht bestätigt."),
            ],
            "arrays": {
                "anchor_poi": anchor.poi_level,
                "range_eq": anchor.range_eq,
                "confirm_cisd_ref": confirm.reference,
                "confirm_protected_swing": confirm.protected_swing,
            },
        }

    # Public-core confirmation exists. Keep it READY, never SIGNAL, until the
    # research profile passes manual promotion.
    entry_level = entry.reference
    stop = entry.protected_swing
    risk = abs(entry_level - stop)
    target = entry_level + 2.0 * risk if side == "Long" else entry_level - 2.0 * risk
    return {
        **common,
        "status": "READY",
        "entry": entry_level,
        "sl": stop,
        "tp": target,
        "message": f"{side} TTFM vollständig bestätigt · RESEARCH-ONLY, keine Paper/Live-Ausführung.",
        "validity": {"status": "VALID", "still_valid": True, "reason": "public-core confirmation complete; execution locked by review gate"},
        "criteria": [
            _crit("True Futures Feed", "PASS", source),
            _crit(f"Daily {anchor.kind} Closure", "PASS", f"{side} · POI {anchor.poi_type}"),
            _crit(f"{spec['confirm_tf']} CISD", "PASS", f"Ref {confirm.reference:.2f}"),
            _crit(f"{spec['entry_tf']} CISD + POI", "PASS", f"{entry.poi_type} · Ref {entry.reference:.2f}"),
            _crit("Live/Paper Freigabe", "PENDING", "Research-Validation + manueller Review noch erforderlich."),
        ],
        "arrays": {
            "entry": entry_level, "stop": stop, "target": target,
            "anchor_poi": anchor.poi_level, "range_eq": anchor.range_eq,
            "confirm_cisd_ref": confirm.reference,
            "entry_cisd_ref": entry.reference,
        },
    }


def _scalp_model(market: str, suffix: str, label: str, spec: dict[str, Any], base5: pd.DataFrame, base1: pd.DataFrame | None, source: str) -> dict[str, Any]:
    if base1 is None or base1.empty:
        return _blocked(
            market, suffix, label, spec,
            "TTFM H1→M15→M1 benötigt einen echten 1m-Futures-Feed; 5m wird nicht künstlich zu M1 interpoliert."
        )

    merged = base1
    daily = ttfm_engine._aggregate(merged, "1D", "America/New_York")
    context = ttfm_engine._daily_direction_context(daily.iloc[:-1] if len(daily) > 1 else daily)
    if not context:
        model = _blocked(market, suffix, label, spec, "Kein eindeutiger Daily Context für das Scalping-Fractal.")
        model["status"] = "IDLE"; model["proxy"] = False
        model["criteria"] = [
            _crit("True 1m Futures Feed", "PASS", source),
            _crit("Daily Context", "PENDING", "Keine bestätigte Direction."),
        ]
        return model

    h1 = ttfm_engine._aggregate(merged, "1H", "America/New_York")
    anchor = ttfm_engine.latest_closure_event(h1, 2, 2)
    if not anchor or anchor.side != context:
        model = _blocked(market, suffix, label, spec, f"Daily {context} · wartet auf passende H1 C2/C3 Closure.")
        model["status"] = "WATCH"; model["proxy"] = False; model["side"] = context
        model["criteria"] = [
            _crit("True 1m Futures Feed", "PASS", source),
            _crit("Daily Context", "PASS", context),
            _crit("H1 C2/C3", "PENDING", "Passende H1 Closure fehlt."),
        ]
        return model

    m15 = ttfm_engine._aggregate(merged, "15m", "America/New_York")
    confirm = _find_confirm(ttfm_engine._filter_between(m15, anchor.candle_open_time, anchor.close_time), context)
    if not confirm:
        model = _blocked(market, suffix, label, spec, f"{context} H1 Closure · wartet auf M15 CISD.")
        model["status"] = "FORMING"; model["proxy"] = False; model["side"] = context
        model["criteria"] = [
            _crit("True 1m Futures Feed", "PASS", source),
            _crit("Daily Context", "PASS", context),
            _crit(f"H1 {anchor.kind}", "PASS", anchor.source_variant),
            _crit("M15 CISD", "PENDING", "Bestätigung fehlt."),
        ]
        return model

    next_h1_end = anchor.close_time + pd.Timedelta(hours=1)
    m1seg = ttfm_engine._filter_between(merged, anchor.close_time, next_h1_end)
    entry = _find_entry(m1seg, context)
    if not entry:
        model = _blocked(market, suffix, label, spec, f"{context} H1+M15 bestätigt · wartet auf M1 CISD/POI.")
        model["status"] = "ARMED"; model["proxy"] = False; model["side"] = context
        model["sl"] = confirm.protected_swing
        model["criteria"] = [
            _crit("True 1m Futures Feed", "PASS", source),
            _crit("Daily Context", "PASS", context),
            _crit(f"H1 {anchor.kind}", "PASS", anchor.source_variant),
            _crit("M15 CISD", "PASS", f"Protected swing {confirm.protected_swing:.2f}"),
            _crit("M1 CISD + POI", "PENDING", "Entry-Fractal fehlt."),
        ]
        return model

    entry_level = entry.reference
    stop = entry.protected_swing
    risk = abs(entry_level - stop)
    target = entry_level + 2.0 * risk if context == "Long" else entry_level - 2.0 * risk
    return {
        "id": f"{market.lower()}_ttfm_{suffix.lower()}",
        "name": f"{market} · TTFM {label}",
        "market": market, "tf": "1m", "status": "READY", "side": context,
        "entry": entry_level, "sl": stop, "tp": target, "rr": 2.0,
        "message": f"{context} TTFM Scalping vollständig bestätigt · RESEARCH-ONLY.",
        "validity": {"status": "VALID", "still_valid": True, "reason": "public-core scalp confirmation complete; execution locked by review gate"},
        "criteria": [
            _crit("True 1m Futures Feed", "PASS", source),
            _crit("Daily Context", "PASS", context),
            _crit(f"H1 {anchor.kind}", "PASS", anchor.source_variant),
            _crit("M15 CISD", "PASS", f"Ref {confirm.reference:.2f}"),
            _crit("M1 CISD + POI", "PASS", f"{entry.poi_type} · Ref {entry.reference:.2f}"),
            _crit("Live/Paper Freigabe", "PENDING", "Research-Validation + manueller Review noch erforderlich."),
        ],
        "logic": _base_logic(spec),
        "arrays": {"entry": entry_level, "stop": stop, "target": target},
        "event": {"event_ms": int(entry.confirm_time.timestamp() * 1000)},
        "setup_key": f"{market}:{suffix}:{int(anchor.candle_open_time.timestamp())}:{context}",
        "proxy": False, "feed_stale": False, "research_only": True, "live_trade_allowed": False,
        "source": source,
    }


def _market_models(workspace, market: str) -> list[dict[str, Any]]:
    q5 = futures_mirror.query(workspace, market, "5m", 5000)
    if not q5 or not q5.get("bars"):
        return [
            _blocked(market, suffix, label, ttfm_engine.profile_spec(model_type),
                     "Kein echter Futures-Livefeed vorhanden. TTFM verwendet absichtlich keinen Proxy.")
            for suffix, model_type, label, _entry_tf in PROFILE_MATRIX
        ]

    source = str(q5.get("note") or q5.get("provider") or "true futures")
    if bool(q5.get("stale", True)):
        return [
            _blocked(market, suffix, label, ttfm_engine.profile_spec(model_type),
                     f"True-Futures-Feed ist stale: {source}", stale=True)
            for suffix, model_type, label, _entry_tf in PROFILE_MATRIX
        ]

    base5 = _df(q5.get("bars") or [])
    q1 = futures_mirror.query(workspace, market, "1m", 8000)
    base1 = _df(q1.get("bars") or []) if q1 and q1.get("bars") and not q1.get("stale") else None

    out = []
    for suffix, model_type, label, _entry_tf in PROFILE_MATRIX:
        spec = ttfm_engine.profile_spec(model_type)
        if spec["mode"] == "scalp":
            out.append(_scalp_model(market, suffix, label, spec, base5, base1, source))
        else:
            out.append(_daily_model(market, suffix, label, spec, base5, source))
    return out


def build_monitor_models(workspace) -> list[dict[str, Any]]:
    now = time.monotonic()
    if now - float(_CACHE.get("at") or 0.0) < CACHE_SECONDS:
        return list(_CACHE.get("models") or [])

    models: list[dict[str, Any]] = []
    for market in ("NQ", "ES", "GC"):
        try:
            models.extend(_market_models(workspace, market))
        except Exception as exc:
            for suffix, model_type, label, _entry_tf in PROFILE_MATRIX:
                spec = ttfm_engine.profile_spec(model_type)
                models.append(_blocked(
                    market, suffix, label, spec,
                    f"TTFM Monitor Fehler: {type(exc).__name__}: {exc}"
                ))

    _CACHE["at"] = now
    _CACHE["models"] = models
    return list(models)
