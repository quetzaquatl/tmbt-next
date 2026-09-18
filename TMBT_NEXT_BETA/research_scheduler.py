from __future__ import annotations

import json
import math
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import historical_store
import research_autopilot_bridge

HERE = Path(__file__).resolve().parent
WORKSPACE = Path(os.environ.get("TMBT_WORKSPACE", r"D:\\Projekt model\\Trading_Model_Backtest_Studio_WORKSPACE")).resolve()
ROOT = WORKSPACE / "research_scheduler"
CONFIG = ROOT / "config.json"
STATUS = ROOT / "status.json"
PROFILE_STATE = ROOT / "profiles.json"
PID_FILE = ROOT / "scheduler.pid"
LOCK_FILE = ROOT / "scheduler.lock"
REPORT_ROOT = WORKSPACE / "research_reports"
LATEST_REPORT = REPORT_ROOT / "latest.json"
LATEST_MD = REPORT_ROOT / "latest.md"

DEFAULT_CONFIG: dict[str, Any] = {
    "enabled": True,
    "profiles": ["NQ_EBP_H1", "ES_EBP_H1", "XAU_OTE_BOS", "XAU_SWEEP_IFVG"],
    "cycle_hours_failed": 24,
    "cycle_hours_passed": 168,
    "poll_seconds": 60,
    "max_failed_cycles": 3,
    "test_news": True,
    "tick_audit": False,
    "run_on_start": True,
    "auto_live_promotion": False,
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        x = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
        return x if isinstance(x, dict) else {}
    except Exception:
        return {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    os.replace(tmp, path)


def _write_text(path: Path, text_value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text_value, encoding="utf-8")
    os.replace(tmp, path)


def _parse_dt(value: Any) -> datetime | None:
    try:
        d = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d.astimezone(timezone.utc)
    except Exception:
        return None


def load_config() -> dict[str, Any]:
    cfg = dict(DEFAULT_CONFIG)
    cfg.update(_read_json(CONFIG))
    cfg["profiles"] = [str(x) for x in list(cfg.get("profiles") or [])]
    cfg["poll_seconds"] = max(30, int(cfg.get("poll_seconds") or 60))
    cfg["cycle_hours_failed"] = max(1, int(cfg.get("cycle_hours_failed") or 24))
    cfg["cycle_hours_passed"] = max(24, int(cfg.get("cycle_hours_passed") or 168))
    cfg["max_failed_cycles"] = max(1, min(10, int(cfg.get("max_failed_cycles") or 3)))
    if not CONFIG.exists():
        _write_json(CONFIG, cfg)
    return cfg


def _pid_alive(pid: Any) -> bool:
    try:
        pid = int(pid)
    except Exception:
        return False
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            cp = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                timeout=5,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            return str(pid).encode("ascii") in (cp.stdout or b"")
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def status() -> dict[str, Any]:
    st = _read_json(STATUS)
    pid = int(st.get("pid") or 0)
    st["running"] = bool(st.get("running") and _pid_alive(pid))
    st["pid"] = pid or None
    st["config"] = load_config()
    st["profiles"] = _read_json(PROFILE_STATE).get("profiles", {})
    st["latest_report"] = _read_json(LATEST_REPORT)
    st["databento"] = historical_store.status(WORKSPACE)
    return st


def _status(**changes: Any) -> None:
    st = _read_json(STATUS)
    st.update(changes)
    st["updated_at_utc"] = _now_iso()
    _write_json(STATUS, st)


def _summary(report: dict[str, Any], key: str) -> dict[str, Any]:
    x = report.get(key)
    return x if isinstance(x, dict) else {}


def _num(d: dict[str, Any], key: str, default: float = 0.0) -> float:
    try:
        v = float(d.get(key, default))
        return v if math.isfinite(v) else default
    except Exception:
        return default


def _delta_text(name: str, before: float, after: float, digits: int = 3) -> str:
    diff = after - before
    sign = "+" if diff >= 0 else ""
    return f"{name}: {before:.{digits}f} -> {after:.{digits}f} ({sign}{diff:.{digits}f})"


def analyze_report(report: dict[str, Any], *, failed_cycles: int, max_failed_cycles: int) -> dict[str, Any]:
    baseline = {}
    for stage in report.get("stages") or []:
        if isinstance(stage, dict) and stage.get("name") == "development_baseline":
            baseline = stage.get("summary") or {}
            break
    dev = _summary(report, "development_summary")
    val = _summary(report, "validation_summary")
    verdict = str(((report.get("validation") or {}).get("verdict") or "UNKNOWN")).upper()

    good: list[str] = []
    bad: list[str] = []
    next_steps: list[str] = []

    b_exp, d_exp = _num(baseline, "expectancy_r"), _num(dev, "expectancy_r")
    b_pf, d_pf = _num(baseline, "profit_factor_r"), _num(dev, "profit_factor_r")
    b_dd, d_dd = _num(baseline, "max_drawdown_r"), _num(dev, "max_drawdown_r")
    v_exp, v_pf = _num(val, "expectancy_r"), _num(val, "profit_factor_r")
    v_trades = int(val.get("trades") or 0)

    if dev:
        if d_exp > b_exp:
            good.append(_delta_text("Development Expectancy", b_exp, d_exp))
        else:
            bad.append(_delta_text("Development Expectancy", b_exp, d_exp))
        if d_pf > b_pf:
            good.append(_delta_text("Development PF", b_pf, d_pf))
        else:
            bad.append(_delta_text("Development PF", b_pf, d_pf))
        if b_dd > 0 and d_dd < b_dd:
            good.append(_delta_text("Development Drawdown R", b_dd, d_dd, 1))
        elif d_dd > 0:
            bad.append(_delta_text("Development Drawdown R", b_dd, d_dd, 1))

    if v_exp > 0:
        good.append(f"Validation Expectancy positiv: {v_exp:.3f}R/Trade.")
    else:
        bad.append(f"Validation Expectancy nicht positiv: {v_exp:.3f}R/Trade.")
    if v_pf >= 1.0:
        good.append(f"Validation Profit Factor: {v_pf:.2f}.")
    else:
        bad.append(f"Validation Profit Factor unter 1: {v_pf:.2f}.")
    if v_trades < 15:
        bad.append(f"Validation Stichprobe klein: {v_trades} Trades.")

    if verdict == "PASS":
        candidate_state = "READY_FOR_LIVE_REVIEW"
        next_steps.append("Kandidat fuer manuellen Live-/Paper-Review; automatische Optimierung pausiert bis zum woechentlichen Stabilitaets-Retest.")
        next_steps.append("Kein automatisches Live-Schalten; Holdout/OOS bleibt gesperrt.")
    elif failed_cycles >= max_failed_cycles:
        candidate_state = "REVIEW_REQUIRED"
        next_steps.append("Automatische Tuning-Grenze erreicht. Modelllogik pruefen statt Validation weiter zu jagen.")
    else:
        candidate_state = "REFINE_NEXT_CYCLE"
        next_steps.append("Naechster Zyklus verfeinert die Development-Parameter um die gewaehlt en Werte.".replace("gewaehlt en", "gewaehlten"))
        next_steps.append("Trader Observations werden nicht als Parameter oder Regeln verwendet.")

    return {
        "profile": report.get("profile"),
        "label": report.get("label"),
        "finished_at_utc": report.get("finished_at_utc"),
        "verdict": verdict,
        "candidate_state": candidate_state,
        "good": good,
        "bad": bad,
        "next_steps": next_steps,
        "baseline_summary": baseline,
        "development_summary": dev,
        "validation_summary": val,
        "validation": report.get("validation") or {},
        "selected_overrides": report.get("selected_overrides") or {},
        "holdout": report.get("holdout") or {},
        "policy": {
            "auto_live_promotion": False,
            "observations_used_for_optimization": False,
            "max_failed_cycles": max_failed_cycles,
        },
    }


def _markdown(analysis: dict[str, Any]) -> str:
    lines = [
        f"# Research Report - {analysis.get('label') or analysis.get('profile')}",
        "",
        f"- Verdict: **{analysis.get('verdict')}**",
        f"- State: **{analysis.get('candidate_state')}**",
        f"- Finished: {analysis.get('finished_at_utc') or '-'}",
        "",
        "## Was gut lief",
    ]
    good = analysis.get("good") or []
    lines.extend([f"- {x}" for x in good] or ["- Nichts belastbar Positives im aktuellen Zyklus."])
    lines += ["", "## Was schlecht lief"]
    bad = analysis.get("bad") or []
    lines.extend([f"- {x}" for x in bad] or ["- Keine zentralen Warnpunkte aus den Kernmetriken."])
    lines += ["", "## Naechster Schritt"]
    lines.extend([f"- {x}" for x in (analysis.get("next_steps") or [])])
    lines += [
        "",
        "## Gewaehlte Research-Overrides",
        json.dumps(analysis.get("selected_overrides") or {}, ensure_ascii=False, indent=2),
        "",
        "Trader Thinking / Observations bleiben reine Notizen und fliessen nicht automatisch in Backtest-Regeln oder Optimierungsparameter ein.",
        "",
    ]
    return "\n".join(lines)


def archive_report(report: dict[str, Any], analysis: dict[str, Any]) -> dict[str, str]:
    profile = str(analysis.get("profile") or "unknown")
    stamp = (_parse_dt(analysis.get("finished_at_utc")) or _now()).strftime("%Y%m%dT%H%M%SZ")
    root = REPORT_ROOT / profile
    json_path = root / f"{stamp}.json"
    md_path = root / f"{stamp}.md"
    _write_json(json_path, {"analysis": analysis, "autopilot_report": report})
    _write_text(md_path, _markdown(analysis))
    _write_json(LATEST_REPORT, {"analysis": analysis, "autopilot_report": report, "json_path": str(json_path), "md_path": str(md_path)})
    _write_text(LATEST_MD, _markdown(analysis))
    _write_json(root / "latest.json", {"analysis": analysis, "autopilot_report": report})
    _write_text(root / "latest.md", _markdown(analysis))
    return {"json": str(json_path), "markdown": str(md_path)}


def _numeric_refine(values: list[Any], chosen: Any) -> list[Any]:
    nums = []
    for x in values:
        try:
            nums.append(float(x))
        except Exception:
            pass
    nums = sorted(set(nums))
    if not nums:
        return values
    try:
        chosen_num = float(chosen)
    except Exception:
        return values
    diffs = [abs(b - a) for a, b in zip(nums, nums[1:]) if abs(b - a) > 1e-12]
    step = min(diffs) if diffs else max(abs(chosen_num) * 0.1, 1.0)
    half = step / 2.0
    out = sorted(set([chosen_num - step, chosen_num - half, chosen_num, chosen_num + half, chosen_num + step]))
    all_int = all(float(x).is_integer() for x in nums)
    if all_int:
        return sorted(set(max(1, int(round(x))) for x in out))
    return [round(x, 6) for x in out]


def refined_optimizers(profile: str, previous_report: dict[str, Any]) -> list[dict[str, Any]]:
    profiles = research_autopilot_bridge.profiles()
    p = profiles.get(profile) or {}
    selected = previous_report.get("selected_overrides") or {}
    out = []
    for raw in p.get("optimizers") or []:
        spec = dict(raw)
        p1 = spec.get("param1")
        p2 = spec.get("param2")
        if p1 and p1 in selected:
            spec["values1"] = _numeric_refine(list(spec.get("values1") or []), selected[p1])
        if p2 and p2 in selected:
            spec["values2"] = _numeric_refine(list(spec.get("values2") or []), selected[p2])
        out.append(spec)
    return out


def _profile_state() -> dict[str, Any]:
    data = _read_json(PROFILE_STATE)
    if "profiles" not in data or not isinstance(data.get("profiles"), dict):
        data = {"profiles": {}}
    return data


def _save_profile_state(data: dict[str, Any]) -> None:
    data["updated_at_utc"] = _now_iso()
    _write_json(PROFILE_STATE, data)


def _due(profile: str, state: dict[str, Any], cfg: dict[str, Any]) -> bool:
    item = (state.get("profiles") or {}).get(profile) or {}
    if item.get("candidate_state") == "REVIEW_REQUIRED":
        return False
    last = _parse_dt(item.get("last_finished_at_utc"))
    if last is None:
        return True
    hours = cfg["cycle_hours_passed"] if item.get("candidate_state") == "READY_FOR_LIVE_REVIEW" else cfg["cycle_hours_failed"]
    return _now() >= last + timedelta(hours=int(hours))


def _databento_ready_for(profile: str) -> bool:
    if profile not in {"NQ_EBP_H1", "ES_EBP_H1"}:
        return True
    st = historical_store.status(WORKSPACE)
    return bool(st.get("db_exists") and str(st.get("state") or "").upper() == "COMPLETE")


def _wait_for_autopilot(profile: str, started_after: datetime, timeout_hours: int = 24) -> tuple[dict[str, Any], dict[str, Any]]:
    deadline = _now() + timedelta(hours=max(1, timeout_hours))
    stopped_since: datetime | None = None
    while True:
        st = research_autopilot_bridge.status()
        report = research_autopilot_bridge.latest_report()
        if not st.get("running"):
            report_time = _parse_dt(report.get("finished_at_utc"))
            if report.get("profile") == profile and report_time and report_time >= started_after:
                return st, report
            if str(st.get("state") or "").upper() in {"FAILED", "CANCELLED"}:
                return st, report
            if stopped_since is None:
                stopped_since = _now()
            elif (_now() - stopped_since).total_seconds() > 60:
                return st, report
        else:
            stopped_since = None
        if _now() >= deadline:
            return {**st, "state": "FAILED", "last_error": "scheduler_autopilot_timeout"}, report
        time.sleep(10)


def run_profile(profile: str, cfg: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    pstate = (state.get("profiles") or {}).get(profile) or {}
    failed_cycles = int(pstate.get("failed_cycles") or 0)
    previous_report = pstate.get("last_autopilot_report") or {}
    optimizer_overrides = refined_optimizers(profile, previous_report) if failed_cycles > 0 and previous_report else None

    started = _now()
    _status(state="RUNNING_PROFILE", active_profile=profile, active_round=failed_cycles + 1)
    result = research_autopilot_bridge.start(
        profile,
        test_news=bool(cfg.get("test_news", True)),
        tick_audit=bool(cfg.get("tick_audit", False)),
        optimizer_overrides=optimizer_overrides,
        cycle_round=failed_cycles + 1,
        requested_by="TMBT Research Scheduler",
    )
    if not result.get("started"):
        return {"ok": False, "profile": profile, "error": result.get("reason") or "autopilot_not_started"}

    worker_status, report = _wait_for_autopilot(profile, started)
    if not report or str(report.get("state") or "").upper() != "COMPLETED":
        return {
            "ok": False,
            "profile": profile,
            "error": worker_status.get("last_error") or "autopilot_failed_without_report",
            "worker_status": worker_status,
        }

    verdict = str(((report.get("validation") or {}).get("verdict") or "UNKNOWN")).upper()
    next_failed = 0 if verdict == "PASS" else failed_cycles + 1
    analysis = analyze_report(report, failed_cycles=next_failed, max_failed_cycles=int(cfg["max_failed_cycles"]))
    paths = archive_report(report, analysis)

    profiles_state = state.setdefault("profiles", {})
    profiles_state[profile] = {
        "profile": profile,
        "label": report.get("label"),
        "last_finished_at_utc": report.get("finished_at_utc") or _now_iso(),
        "last_verdict": verdict,
        "candidate_state": analysis.get("candidate_state"),
        "failed_cycles": next_failed,
        "last_report_paths": paths,
        "last_analysis": analysis,
        "last_autopilot_report": report,
    }
    _save_profile_state(state)
    return {"ok": True, "profile": profile, "verdict": verdict, "analysis": analysis, "paths": paths}


def _acquire_singleton() -> bool:
    ROOT.mkdir(parents=True, exist_ok=True)
    for _ in range(2):
        try:
            fd = os.open(str(LOCK_FILE), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(str(os.getpid()))
            return True
        except FileExistsError:
            try:
                old_pid = int(LOCK_FILE.read_text(encoding="utf-8").strip())
            except Exception:
                old_pid = 0
            if old_pid and _pid_alive(old_pid):
                return False
            try:
                LOCK_FILE.unlink(missing_ok=True)
            except Exception:
                return False
    return False


def daemon() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    if not _acquire_singleton():
        return
    PID_FILE.write_text(str(os.getpid()), encoding="utf-8")
    _status(pid=os.getpid(), running=True, state="IDLE", started_at_utc=_now_iso(), last_error="")
    try:
        while True:
            cfg = load_config()
            if not cfg.get("enabled"):
                _status(pid=os.getpid(), running=True, state="DISABLED")
                time.sleep(cfg["poll_seconds"])
                continue

            if research_autopilot_bridge.status().get("running"):
                _status(pid=os.getpid(), running=True, state="WAITING_AUTOPILOT")
                time.sleep(cfg["poll_seconds"])
                continue

            state = _profile_state()
            available = research_autopilot_bridge.profiles()
            profiles = [p for p in cfg.get("profiles") or [] if p in available]
            ran = False
            completed_profiles = []
            for profile in profiles:
                if not _due(profile, state, cfg):
                    continue
                if not _databento_ready_for(profile):
                    state.setdefault("profiles", {}).setdefault(profile, {}).update({
                        "profile": profile,
                        "candidate_state": "WAITING_FOR_DATABENTO",
                        "last_note": "Databento import must be COMPLETE before NQ/ES research.",
                    })
                    _save_profile_state(state)
                    continue
                try:
                    res = run_profile(profile, cfg, state)
                    ran = True
                    completed_profiles.append({
                        "profile": profile,
                        "ok": bool(res.get("ok")),
                        "verdict": res.get("verdict"),
                        "error": res.get("error"),
                    })
                    _status(
                        pid=os.getpid(),
                        running=True,
                        state="BETWEEN_PROFILES",
                        active_profile=None,
                        completed_profiles_this_pass=completed_profiles,
                        last_result=res,
                        last_error="" if res.get("ok") else str(res.get("error") or ""),
                    )
                except Exception as exc:
                    ran = True
                    completed_profiles.append({
                        "profile": profile,
                        "ok": False,
                        "error": f"{type(exc).__name__}: {exc}",
                    })
                    _status(
                        pid=os.getpid(),
                        running=True,
                        state="BETWEEN_PROFILES",
                        active_profile=None,
                        completed_profiles_this_pass=completed_profiles,
                        last_error=f"{type(exc).__name__}: {exc}",
                    )
                # Continue immediately with the next due profile. One model's
                # PASS/FAIL must not block ES/XAU from getting their own cycle.

            _status(
                pid=os.getpid(),
                running=True,
                state="IDLE",
                active_profile=None,
                completed_profiles_this_pass=completed_profiles,
            )
            time.sleep(cfg["poll_seconds"])
    finally:
        try:
            PID_FILE.unlink(missing_ok=True)
        except Exception:
            pass
        try:
            if LOCK_FILE.exists() and LOCK_FILE.read_text(encoding="utf-8").strip() == str(os.getpid()):
                LOCK_FILE.unlink(missing_ok=True)
        except Exception:
            pass
        _status(running=False, state="STOPPED")


def start_background() -> dict[str, Any]:
    st = status()
    if st.get("running"):
        return {"started": False, "reason": "already_running", "status": st}
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
    log_path = ROOT / "scheduler.log"
    ROOT.mkdir(parents=True, exist_ok=True)
    log = open(log_path, "a", encoding="utf-8", buffering=1)
    try:
        proc = subprocess.Popen(
            [sys.executable, str(Path(__file__).resolve()), "--daemon"],
            cwd=str(HERE),
            env={**os.environ.copy(), "TMBT_WORKSPACE": str(WORKSPACE)},
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            creationflags=flags,
        )
    except Exception:
        log.close()
        raise
    _status(pid=proc.pid, running=True, state="STARTING", started_at_utc=_now_iso())
    return {"started": True, "pid": proc.pid, "status": status()}


def stop() -> dict[str, Any]:
    st = status()
    pid = int(st.get("pid") or 0)
    if pid and _pid_alive(pid):
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=10,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        else:
            os.kill(pid, 15)
    _status(running=False, state="STOPPED", active_profile=None)
    return {"stopped": True, "status": status()}


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--daemon", action="store_true")
    parser.add_argument("--status", action="store_true")
    args = parser.parse_args()
    if args.daemon:
        daemon()
    else:
        print(json.dumps(status(), ensure_ascii=False, indent=2, default=str))
