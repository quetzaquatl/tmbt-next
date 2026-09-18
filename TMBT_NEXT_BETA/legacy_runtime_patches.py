from __future__ import annotations

from pathlib import Path

PATCH_VERSION = "ote-preentry-invalidation-v1"


def apply(root: Path) -> None:
    """Patch extracted migration runtime without mutating the source bundle."""
    path = Path(root) / "live_signal_agent.py"
    if not path.exists():
        return

    text = path.read_text(encoding="utf-8", errors="ignore")
    marker = "# TMBT_NEXT_PATCH: ote-preentry-invalidation-v1"
    if marker in text:
        return

    old = '''        touched_i = None
        if ready_i <= scan_end:
            view = df.iloc[ready_i:scan_end+1]
            hits = view["low"] <= entry if side == "Long" else view["high"] >= entry
            if hits.any():
                touched_i = int(view.index[np.flatnonzero(hits.to_numpy())[0]])

        if touched_i is not None:
'''

    new = '''        # TMBT_NEXT_PATCH: ote-preentry-invalidation-v1
        # If the intended impulse target is consumed BEFORE the 70.5% limit
        # entry, the trade idea is no longer executable and must not remain
        # ARMED. Same-bar Entry+Target is ambiguous on 15m OHLC, so reject it
        # conservatively instead of inventing intrabar ordering.
        touched_i = None
        preentry_target_i = None
        ambiguous_i = None
        if ready_i <= scan_end:
            view = df.iloc[ready_i:scan_end+1]
            entry_hits = view["low"] <= entry if side == "Long" else view["high"] >= entry
            target_hits = view["high"] >= target if side == "Long" else view["low"] <= target

            entry_pos = int(np.flatnonzero(entry_hits.to_numpy())[0]) if entry_hits.any() else None
            target_pos = int(np.flatnonzero(target_hits.to_numpy())[0]) if target_hits.any() else None

            if entry_pos is not None and target_pos is not None and entry_pos == target_pos:
                ambiguous_i = int(view.index[entry_pos])
            elif target_pos is not None and (entry_pos is None or target_pos < entry_pos):
                preentry_target_i = int(view.index[target_pos])
            elif entry_pos is not None:
                touched_i = int(view.index[entry_pos])

        if ambiguous_i is not None:
            criteria.append(_crit(
                "OTE 70.5% innerhalb 24 Bars",
                "FAIL",
                "Entry und Target lagen in derselben 15m-Bar; Intrabar-Reihenfolge ist unbekannt, daher kein künstlicher Fill."
            ))
            criteria.append(_crit(
                "Target am Impulse-Extrem",
                "FAIL",
                f"TP {target:.4f} wurde in derselben Bar wie der mögliche Entry gehandelt."
            ))
            out.update(
                stage="EXPIRED",
                side=side,
                message=f"{side} OTE verworfen · Entry/Target-Reihenfolge unklar",
                setup_key=setup_key,
                entry=float(entry),
                stop=stop,
                target=target,
                zone_low=float(zone_low),
                zone_high=float(zone_high),
                break_level=float(stp["break_level"]),
                criteria=criteria,
                validity=_validity(
                    "EXPIRED",
                    False,
                    "Entry und Target wurden innerhalb derselben 15m-Bar gehandelt; konservativ kein Fill.",
                    last_bar_utc=df.iloc[-1]["close_dt"].isoformat(),
                ),
            )
            return out

        if preentry_target_i is not None:
            target_time = df.iloc[preentry_target_i]["close_dt"].isoformat()
            criteria.append(_crit(
                "OTE 70.5% innerhalb 24 Bars",
                "FAIL",
                "Das Impulse-Target wurde erreicht, bevor der 70.5%-Entry nach Swing-Bestätigung gefüllt wurde."
            ))
            criteria.append(_crit(
                "Target am Impulse-Extrem",
                "FAIL",
                f"TP {target:.4f} bereits vor Entry konsumiert."
            ))
            out.update(
                stage="EXPIRED",
                side=side,
                message=f"{side} OTE ungültig · Target vor Entry erreicht",
                setup_key=setup_key,
                entry=float(entry),
                stop=stop,
                target=target,
                zone_low=float(zone_low),
                zone_high=float(zone_high),
                break_level=float(stp["break_level"]),
                criteria=criteria,
                validity=_validity(
                    "EXPIRED",
                    False,
                    "Das ursprüngliche Impulse-Target wurde vor dem Entry erreicht; Setup ist nicht mehr handelbar.",
                    target_consumed_at_utc=target_time,
                    last_bar_utc=df.iloc[-1]["close_dt"].isoformat(),
                ),
            )
            return out

        if touched_i is not None:
'''

    if old not in text:
        raise RuntimeError("live_signal_agent OTE patch anchor not found")

    path.write_text(text.replace(old, new, 1), encoding="utf-8")
