
from __future__ import annotations
import json, math, mimetypes, os, sqlite3, sys, time
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from zoneinfo import ZoneInfo

APP_VERSION = "0.9.0-beta"
PORT = int(os.environ.get("TMBT_NEXT_PORT", "8510"))
WORKSPACE = Path(os.environ.get(
    "TMBT_WORKSPACE",
    r"D:\Projekt model\Trading_Model_Backtest_Studio_WORKSPACE"
))
ROOT = Path(__file__).resolve().parent
WEB = ROOT / "web"
PID_FILE = ROOT / "next_ui.pid"

MARKET_ALIASES = {
    "NQ": ["NQ", "QQQ", "US100", "USATECHIDXUSD", "NQ=F", "NQ_F"],
    "ES": ["ES", "SPY", "US500", "USA500IDXUSD", "ES=F", "ES_F"],
    "XAU": ["XAU", "XAUUSD", "XAU/USD", "GOLD"],
}

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def read_json(path: Path, default=None):
    try:
        if path.exists():
            x = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
            return x
    except Exception:
        pass
    return default

def read_jsonl(path: Path, limit=1000):
    if not path.exists():
        return []
    out = []
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()[-max(1, int(limit)):]
        for line in lines:
            try:
                x = json.loads(line)
                if isinstance(x, dict):
                    out.append(x)
            except Exception:
                pass
    except Exception:
        pass
    return out

def repo_root():
    return WORKSPACE / "github_research_repo"

def signal_state():
    local = read_json(WORKSPACE / "live_signals" / "state.json", {})
    if isinstance(local, dict) and local:
        return local
    repo = read_json(repo_root() / "signals" / "latest.json", {})
    if isinstance(repo, dict):
        return repo.get("state") if isinstance(repo.get("state"), dict) else repo
    return {}

def signal_status():
    local = read_json(WORKSPACE / "live_signals" / "agent_status.json", {})
    if isinstance(local, dict) and local:
        return local
    repo = read_json(repo_root() / "signals" / "latest.json", {})
    if isinstance(repo, dict):
        return repo.get("status") or {}
    return {}

def normalize_models():
    st = signal_state()
    src = st.get("models") or st.get("model_states") or {}
    rows = []
    if isinstance(src, dict):
        for mid, m in src.items():
            if not isinstance(m, dict):
                continue
            v = m.get("validity") or {}
            crit = m.get("criteria") or []
            rows.append({
                "id": str(mid),
                "name": m.get("label") or m.get("name") or m.get("model") or str(mid),
                "market": m.get("market") or m.get("symbol") or "",
                "tf": m.get("timeframe") or m.get("tf") or "",
                "source": m.get("source") or "",
                "status": m.get("stage") or m.get("status") or m.get("state") or "—",
                "side": m.get("side") or "—",
                "entry": m.get("entry"),
                "sl": m.get("stop") if m.get("stop") is not None else m.get("sl"),
                "tp": m.get("target") if m.get("target") is not None else m.get("tp"),
                "rr": m.get("planned_rr") if m.get("planned_rr") is not None else m.get("rr"),
                "message": m.get("message") or m.get("info") or "",
                "validity": v,
                "criteria": crit,
                "logic": m.get("logic") or {},
                "arrays": {k: m.get(k) for k in [
                    "entry","stop","target","reference_high","reference_low","zone_low","zone_high",
                    "break_level","ifvg_low","ifvg_high","prev_high","prev_low","prev_body_high","prev_body_low",
                    "signal_high","signal_low","fib15","fib25","fib50","fib75"
                ] if m.get(k) is not None},
                "event": m.get("event") or {},
                "setup_key": m.get("setup_key"),
            })
    return rows

def paper_payload():
    p = WORKSPACE / "paper_account"
    status = read_json(p / "agent_status.json", {}) or {}
    state = read_json(p / "state.json", {}) or {}
    config = read_json(p / "config.json", {}) or {}
    trades = read_jsonl(p / "closed_trades.jsonl", 100)
    events = read_jsonl(p / "events.jsonl", 100)
    return {
        "status": status,
        "state": state,
        "config": config,
        "trades": list(reversed(trades)),
        "events": list(reversed(events)),
    }

def research_jobs(limit=20):
    root = WORKSPACE / "research_jobs"
    rows = []
    if root.exists():
        for d in root.iterdir():
            if not d.is_dir():
                continue
            s = read_json(d / "status.json", None)
            if isinstance(s, dict):
                s = dict(s)
                if not s.get("job_id"): s["job_id"] = d.name
                try: s["_mtime"] = (d / "status.json").stat().st_mtime
                except Exception: s["_mtime"] = 0
                rows.append(s)
    if not rows:
        repo = read_json(repo_root() / "state" / "jobs.json", {}) or {}
        rows = list(repo.get("jobs") or [])
        for i, x in enumerate(rows):
            x["_mtime"] = len(rows) - i
    rows.sort(key=lambda x: (x.get("_mtime",0), str(x.get("updated_at_utc") or "")), reverse=True)
    for r in rows:
        r.pop("_mtime", None)
    return rows[:max(1,int(limit))]

def outcome_map():
    x = read_json(WORKSPACE / "live_signals" / "outcomes.json", {}) or {}
    return x.get("outcomes") if isinstance(x.get("outcomes"), dict) else {}

def dedupe_history(rows):
    seen = set()
    kept = []
    for h in reversed(rows):
        key = (
            str(h.get("model_id") or h.get("model") or ""),
            str(h.get("setup_key") or ""),
            str(h.get("stage") or ""),
            str(h.get("event_time_utc") or ""),
            str(h.get("side") or ""),
            str(h.get("entry") or ""),
            str(h.get("stop") or ""),
            str(h.get("target") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        kept.append(h)
    return list(reversed(kept))

def archive_rows(limit=500):
    hist = dedupe_history(read_jsonl(WORKSPACE / "live_signals" / "history.jsonl", max(limit*4,1000)))
    outs = outcome_map()
    by_alert = {str(v.get("alert_id")):v for v in outs.values() if isinstance(v,dict) and v.get("alert_id")}
    rows = []
    for h in reversed(hist[-limit:]):
        hid = str(h.get("history_id") or "")
        o = outs.get(hid) or by_alert.get(str(h.get("event_id") or h.get("alert_id") or "")) or {}
        v = h.get("validity") or {}
        paper = o.get("paper") or {}
        rows.append({
            "history_id": hid,
            "snapshot_id": h.get("snapshot_id"),
            "created_at_utc": h.get("created_at_utc"),
            "event_time_utc": h.get("event_time_utc"),
            "model_id": h.get("model_id"),
            "model": h.get("model"),
            "market": h.get("market"),
            "tf": h.get("timeframe"),
            "source": h.get("source"),
            "stage": h.get("stage"),
            "side": h.get("side"),
            "entry": h.get("entry"),
            "sl": h.get("stop"),
            "tp": h.get("target"),
            "rr": h.get("planned_rr"),
            "valid": v.get("still_valid"),
            "reason": v.get("reason") or h.get("message"),
            "rule_version": o.get("rule_version") or h.get("rule_version") or "legacy",
            "outcome": o.get("status"),
            "outcome_r": o.get("outcome_r") if o.get("outcome_r") is not None else o.get("current_r"),
            "mfe_r": o.get("mfe_r"),
            "mae_r": o.get("mae_r"),
            "paper_status": paper.get("status"),
            "paper_r": paper.get("r"),
            "news": (o.get("news") or {}).get("nearest_event"),
            "criteria": h.get("criteria") or [],
            "logic": h.get("logic") or {},
        })
    return rows

def outcome_trade_key(o):
    """Stable identity for one logical trade across rescans and legacy/canonical copies.

    alert_id is not sufficient: the same model trade can be re-imported/re-emitted
    under a new alert/history id. A model + signal timestamp + side is the canonical
    trade identity when available.
    """
    def _v(name):
        v = o.get(name)
        if isinstance(v, float):
            return round(v, 8)
        return "" if v is None else str(v).strip()

    model = _v("model_id") or _v("model")
    signal_time = _v("signal_time_utc") or _v("entry_time_utc")
    side = str(o.get("side") or "").strip().upper()
    if model and signal_time and side:
        return ("signal", model, signal_time, side)

    alert_id = str(o.get("alert_id") or "").strip()
    if alert_id:
        return ("alert", alert_id)

    return (
        "trade",
        model,
        signal_time,
        side,
        _v("entry"),
        _v("stop"),
        _v("target"),
    )

def dedupe_outcomes(outs):
    """Collapse duplicate outcome records for the same trade, preferring resolved/latest data."""
    chosen = {}
    for o in (outs or {}).values():
        if not isinstance(o, dict):
            continue
        key = outcome_trade_key(o)
        status = str(o.get("status") or "").upper()
        resolved = o.get("outcome_r") is not None or status not in {"", "OPEN", "ACTIVE", "PENDING"}
        rank = (1 if resolved else 0, str(o.get("updated_at_utc") or ""))
        prev = chosen.get(key)
        if prev is None or rank >= prev[0]:
            chosen[key] = (rank, o)
    return [x[1] for x in chosen.values()]

def _outcome_market(value, model_text=""):
    z = (str(value or "") + " " + str(model_text or "")).upper()
    if any(x in z for x in ("NQ", "US100", "QQQ", "NASDAQ")):
        return "NQ"
    if any(x in z for x in ("ES", "US500", "SPY", "S&P")):
        return "ES"
    if any(x in z for x in ("XAU", "GOLD", "GC")):
        return "XAU"
    return str(value or "").upper() or "OTHER"


def _outcome_tf(value, model_text=""):
    z = (str(value or "") + " " + str(model_text or "")).upper().replace(" ", "")
    aliases = [
        ("15M", "15m"), ("M15", "15m"),
        ("30M", "30m"), ("M30", "30m"),
        ("1H", "1H"), ("H1", "1H"), ("60M", "1H"),
        ("4H", "4H"), ("H4", "4H"),
        ("5M", "5m"), ("M5", "5m"),
        ("1D", "1D"), ("D1", "1D"),
    ]
    raw = str(value or "").strip()
    if raw:
        r = raw.upper().replace(" ", "")
        for token, canonical in aliases:
            if token == r:
                return canonical
    for token, canonical in aliases:
        if token in z:
            return canonical
    return raw or "—"


def _outcome_family(model_text="", model_id=""):
    z = (str(model_text or "") + " " + str(model_id or "")).lower()
    if "silver bullet" in z:
        return "Silver Bullet iFVG"
    if "ote" in z and "bos" in z:
        return "OTE BOS"
    if "sweep" in z and "ifvg" in z:
        return "Sweep iFVG"
    if "ebp" in z:
        return "EBP"
    if "ifvg" in z:
        return "iFVG"
    label = str(model_text or model_id or "Model").strip()
    for token in ("US100", "US500", "NQ", "ES", "XAU", "QQQ proxy", "SPY proxy", "LIVE", "15m", "30m", "1H", "H1", "5m"):
        label = label.replace(token, " ")
    return " ".join(label.split()) or "Model"


def _outcome_group_key(market, family):
    scope = "INDICES" if market in {"NQ", "ES"} else market
    return f"{scope}|{family}"


def _model_context_maps():
    by_id, by_name = {}, {}
    for m in normalize_models():
        item = {
            "model_id": str(m.get("id") or ""),
            "model": str(m.get("name") or ""),
            "market": _outcome_market(m.get("market"), m.get("name")),
            "tf": _outcome_tf(m.get("tf"), m.get("name")),
            "family": _outcome_family(m.get("name"), m.get("id")),
            "logic": m.get("logic") or {},
            "criteria": m.get("criteria") or [],
        }
        if item["model_id"]:
            by_id[item["model_id"]] = item
        if item["model"]:
            by_name[item["model"]] = item
    return by_id, by_name


def _outcome_context(o, by_id, by_name):
    mid = str(o.get("model_id") or "")
    name = str(o.get("model") or o.get("name") or mid or "Model")
    base = by_id.get(mid) or by_name.get(name) or {}
    market = _outcome_market(o.get("market") or base.get("market"), name)
    tf = _outcome_tf(o.get("tf") or o.get("timeframe") or base.get("tf"), name)
    family = _outcome_family(name, mid)
    return {
        "model_id": mid or str(base.get("model_id") or ""),
        "model": name,
        "market": market,
        "tf": tf,
        "family": family,
        "group_key": _outcome_group_key(market, family),
    }


def _outcome_stats(rows):
    signals = len(rows)
    closed = open_count = ambiguous = wins = losses = 0
    net_r = 0.0
    mfe, mae = [], []
    for o in rows:
        st = str(o.get("status") or "").upper()
        if st in {"OPEN", "ACTIVE", "PENDING"}:
            open_count += 1
        elif "AMBIG" in st:
            ambiguous += 1
        elif st:
            closed += 1
        r = o.get("outcome_r")
        if r is not None:
            try:
                rv = float(r)
                net_r += rv
                if rv > 0:
                    wins += 1
                elif rv < 0:
                    losses += 1
            except Exception:
                pass
        for key, target in (("mfe_r", mfe), ("mae_r", mae)):
            try:
                if o.get(key) is not None:
                    target.append(float(o.get(key)))
            except Exception:
                pass
    denom = wins + losses
    return {
        "signals": signals,
        "closed": closed,
        "open": open_count,
        "ambiguous": ambiguous,
        "net_r": net_r,
        "wins": wins,
        "losses": losses,
        "winrate": (wins / denom * 100.0) if denom else None,
        "expectancy": (net_r / closed) if closed else None,
        "avg_mfe": sum(mfe) / len(mfe) if mfe else None,
        "avg_mae": sum(mae) / len(mae) if mae else None,
    }


def _logic_summary(row):
    criteria = row.get("criteria") or []
    logic = row.get("logic") or {}
    crit_text = []
    for x in criteria[:12]:
        if isinstance(x, str):
            crit_text.append(x)
        elif isinstance(x, dict):
            label = x.get("label") or x.get("name") or ""
            detail = x.get("detail") or ""
            status = x.get("status") or ""
            text = " · ".join(str(v) for v in (status, label, detail) if v not in (None, ""))
            if text:
                crit_text.append(text)
    logic_rows = []
    if isinstance(logic, dict):
        for k, v in list(logic.items())[:16]:
            if isinstance(v, (dict, list)):
                try:
                    rendered = json.dumps(v, ensure_ascii=False, default=str)
                except Exception:
                    rendered = str(v)
            else:
                rendered = str(v)
            logic_rows.append({"key": str(k), "value": rendered})
    return {
        "reason": row.get("reason") or "",
        "criteria": crit_text,
        "logic": logic_rows,
    }


def outcome_dashboard():
    outs_map = outcome_map()
    deduped = dedupe_outcomes(outs_map)
    by_id, by_name = _model_context_maps()

    groups = {}
    instance_index = {}

    def ensure_group(market, family):
        key = _outcome_group_key(market, family)
        if key not in groups:
            groups[key] = {
                "key": key,
                "scope": "NQ + ES" if market in {"NQ", "ES"} else market,
                "family": family,
                "label": f"NQ + ES · {family}" if market in {"NQ", "ES"} else f"{market} · {family}",
                "instances": [],
                "_outcomes": [],
                "trades": [],
            }
        return groups[key]

    def ensure_instance(ctx):
        group = ensure_group(ctx["market"], ctx["family"])
        ikey = f'{ctx["market"]}|{ctx["tf"]}|{ctx["model_id"] or ctx["model"]}'
        if ikey not in instance_index:
            inst = {
                "key": ikey,
                "model_id": ctx["model_id"],
                "model": ctx["model"],
                "market": ctx["market"],
                "tf": ctx["tf"],
                "_outcomes": [],
            }
            instance_index[ikey] = inst
            group["instances"].append(inst)
        return group, instance_index[ikey]

    # Always surface every currently configured model/timeframe, even with zero trades.
    for m in normalize_models():
        ctx = {
            "model_id": str(m.get("id") or ""),
            "model": str(m.get("name") or m.get("id") or "Model"),
            "market": _outcome_market(m.get("market"), m.get("name")),
            "tf": _outcome_tf(m.get("tf"), m.get("name")),
            "family": _outcome_family(m.get("name"), m.get("id")),
        }
        ensure_instance(ctx)

    # Add historical outcome-only instances as well.
    for o in deduped:
        ctx = _outcome_context(o, by_id, by_name)
        group, inst = ensure_instance(ctx)
        inst["_outcomes"].append(o)
        group["_outcomes"].append(o)

    # Build resolved historical trade rows and attach recorded logic/criteria.
    archives = archive_rows(2500)
    seen_trades = set()
    for row in archives:
        if row.get("outcome_r") is None and not row.get("outcome"):
            continue
        ctx = {
            "model_id": str(row.get("model_id") or ""),
            "model": str(row.get("model") or row.get("model_id") or "Model"),
            "market": _outcome_market(row.get("market"), row.get("model")),
            "tf": _outcome_tf(row.get("tf"), row.get("model")),
            "family": _outcome_family(row.get("model"), row.get("model_id")),
        }
        group, _inst = ensure_instance(ctx)
        trade_key = (
            ctx["model_id"], row.get("event_time_utc"), row.get("side"),
            row.get("entry"), row.get("outcome_r"), row.get("outcome"),
        )
        if trade_key in seen_trades:
            continue
        seen_trades.add(trade_key)
        group["trades"].append({
            "history_id": row.get("history_id"),
            "snapshot_id": row.get("snapshot_id"),
            "event_time_utc": row.get("event_time_utc"),
            "model_id": ctx["model_id"],
            "model": ctx["model"],
            "market": ctx["market"],
            "tf": ctx["tf"],
            "side": row.get("side"),
            "entry": row.get("entry"),
            "sl": row.get("sl"),
            "tp": row.get("tp"),
            "planned_rr": row.get("rr"),
            "outcome": row.get("outcome"),
            "outcome_r": row.get("outcome_r"),
            "mfe_r": row.get("mfe_r"),
            "mae_r": row.get("mae_r"),
            "logic_summary": _logic_summary(row),
        })

    out = []
    for group in groups.values():
        group["stats"] = _outcome_stats(group.pop("_outcomes"))
        group["instances"].sort(key=lambda x: (x["market"], {"5m": 5, "15m": 15, "30m": 30, "1H": 60, "4H": 240, "1D": 1440}.get(x["tf"], 9999), x["model"]))
        for inst in group["instances"]:
            inst["stats"] = _outcome_stats(inst.pop("_outcomes"))
        group["trades"].sort(key=lambda x: str(x.get("event_time_utc") or ""), reverse=True)
        group["trades"] = group["trades"][:100]
        out.append(group)

    order = {"EBP": 1, "Silver Bullet iFVG": 2, "OTE BOS": 3, "Sweep iFVG": 4, "iFVG": 5}
    out.sort(key=lambda x: (0 if x["scope"] == "NQ + ES" else 1, order.get(x["family"], 99), x["label"]))
    return out


def outcome_summary():
    # Backward-compatible flat summaries for any older clients.
    rows = []
    for group in outcome_dashboard():
        s = dict(group.get("stats") or {})
        s["model"] = group.get("label")
        rows.append(s)
    return rows

def load_snapshot(snapshot_id):
    safe = "".join(ch for ch in str(snapshot_id) if ch.isalnum() or ch in "._-")
    if not safe:
        return {}
    return read_json(WORKSPACE / "live_signals" / "snapshots" / f"{safe}.json", {}) or {}

def sqlite_candidates():
    d=WORKSPACE/"live_data"
    out=[]
    for p in [d/"tradingview_live.sqlite3", d/"live.sqlite3"]:
        if p.exists(): out.append(p)
    if d.exists():
        for p in list(d.glob("*.sqlite*"))+list(d.glob("*.db")):
            if p not in out: out.append(p)
    return out

def pick_col(cols, exact, contains=()):
    low={c.lower():c for c in cols}
    for e in exact:
        if e in low: return low[e]
    for c in cols:
        z=c.lower()
        if any(t in z for t in contains): return c
    return None

def normalize_tf(tf):
    z=str(tf).strip().lower()
    mp={"60m":"1h","1hr":"1h","1hour":"1h","h1":"1h","240m":"4h","h4":"4h","d":"1d","day":"1d","5min":"5m","15min":"15m"}
    return mp.get(z,z)

def query_bars(market="NQ", tf="1H", limit=500, source=None):
    aliases=[x.upper() for x in MARKET_ALIASES.get(str(market).upper(),[market])]
    ntf=normalize_tf(tf)
    for db in sqlite_candidates():
        con=None
        try:
            con=sqlite3.connect(str(db)); con.row_factory=sqlite3.Row
            tables=[r[0] for r in con.execute("select name from sqlite_master where type='table'").fetchall()]
            candidates=[]
            for t in tables:
                safe=t.replace('"','""')
                cols=[r[1] for r in con.execute(f'pragma table_info("{safe}")').fetchall()]
                o=pick_col(cols,["open"],["open"])
                h=pick_col(cols,["high"],["high"])
                l=pick_col(cols,["low"],["low"])
                c=pick_col(cols,["close"],["close"])
                ts=pick_col(cols,["bar_open_ms","timestamp","datetime","time","ts","open_time"],["time"])
                close_ts=pick_col(cols,["bar_close_ms"],["close_ms"])
                if not all([o,h,l,c,ts]): continue
                mcol=pick_col(cols,["market","symbol","ticker","instrument"],["market","symbol","ticker"])
                tfcol=pick_col(cols,["timeframe","interval","tf"],["timeframe","interval"])
                scol=pick_col(cols,["source"],["source"])
                vol=pick_col(cols,["volume","vol"],["volume"])
                tickercol=pick_col(cols,["ticker"],["ticker"])
                tickeridcol=pick_col(cols,["tickerid"],["tickerid"])
                exchcol=pick_col(cols,["exchange"],["exchange"])
                recvcol=pick_col(cols,["received_at_utc"],["received"])
                score=5+(2 if mcol else 0)+(2 if tfcol else 0)+(1 if scol else 0)+(1 if tickeridcol else 0)
                candidates.append((score,t,o,h,l,c,ts,close_ts,mcol,tfcol,scol,vol,tickercol,tickeridcol,exchcol,recvcol))
            candidates.sort(reverse=True, key=lambda x:x[0])
            for item in candidates:
                _,t,o,h,l,c,ts,close_ts,mcol,tfcol,scol,vol,tickercol,tickeridcol,exchcol,recvcol=item
                where=[]; params=[]
                if mcol:
                    where.append("upper(cast(%s as text)) in (%s)" % ('"'+mcol+'"', ",".join("?" for _ in aliases)))
                    params += aliases
                if tfcol:
                    where.append("lower(cast(%s as text)) in (%s)" % ('"'+tfcol+'"', ",".join("?" for _ in [ntf,tf.lower()])))
                    params += [ntf, str(tf).lower()]
                if source and scol:
                    where.append('lower(cast("%s" as text))=?' % scol); params.append(str(source).lower())
                safe=t.replace('"','""')
                fields=[
                    f'"{ts}" as t', f'"{o}" as o', f'"{h}" as h', f'"{l}" as l', f'"{c}" as c',
                    f'"{close_ts}" as close_t' if close_ts else "null as close_t",
                    f'"{scol}" as source' if scol else "null as source",
                    f'"{mcol}" as market' if mcol else "null as market",
                    f'"{tfcol}" as tf' if tfcol else "null as tf",
                    f'"{vol}" as volume' if vol else "null as volume",
                    f'"{tickercol}" as ticker' if tickercol else "null as ticker",
                    f'"{tickeridcol}" as tickerid' if tickeridcol else "null as tickerid",
                    f'"{exchcol}" as exchange' if exchcol else "null as exchange",
                    f'"{recvcol}" as received_at_utc' if recvcol else "null as received_at_utc",
                ]
                q="select "+",".join(fields)+f' from "{safe}"'
                if where: q+=" where "+" and ".join(where)
                q+=f' order by "{ts}" desc limit ?'; params.append(int(limit))
                try: rows=con.execute(q,params).fetchall()
                except Exception: rows=[]
                if not rows: continue
                bars=[]
                for r in reversed(rows):
                    try:
                        bars.append({
                            "t":r["t"],"close_t":r["close_t"],
                            "o":float(r["o"]),"h":float(r["h"]),"l":float(r["l"]),"c":float(r["c"]),
                            "v":r["volume"],"source":r["source"],"market":r["market"],"tf":r["tf"],
                            "ticker":r["ticker"],"tickerid":r["tickerid"],"exchange":r["exchange"],
                            "received_at_utc":r["received_at_utc"],
                        })
                    except Exception: pass
                if bars:
                    return {"bars":bars,"db":str(db),"table":t,"source":bars[-1].get("source")}
        except Exception:
            pass
        finally:
            if con:
                try: con.close()
                except Exception: pass
    return {"bars":[],"db":None,"table":None,"source":None,"note":"Keine passende lokale OHLC-Serie gefunden."}

def to_dt(v):
    try:
        if v is None: return None
        if isinstance(v,(int,float)) or (isinstance(v,str) and v.strip().isdigit()):
            n=float(v)
            if n>1e12: n/=1000
            return datetime.fromtimestamp(n,tz=timezone.utc)
        z=str(v).replace("Z","+00:00")
        dt=datetime.fromisoformat(z)
        if dt.tzinfo is None: dt=dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None

def previous_period_level(bars, market):
    tz=ZoneInfo("America/New_York" if str(market).upper() in {"NQ","ES"} else "Europe/Berlin")
    rows=[]
    for b in bars:
        dt=to_dt(b.get("close_t") or b.get("t"))
        if dt: rows.append((dt.astimezone(tz),b))
    if not rows: return {}
    latest=max(x[0] for x in rows)
    out={}
    specs=[
        ("day", lambda dt:(dt.year,dt.month,dt.day), "PDH","PDL"),
        ("week", lambda dt:dt.isocalendar()[:2], "PWH","PWL"),
        ("month", lambda dt:(dt.year,dt.month), "PMH","PML"),
    ]
    for name,keyf,kh,kl in specs:
        cur=keyf(latest)
        groups={}
        for dt,b in rows:
            groups.setdefault(keyf(dt),[]).append(b)
        keys=list(groups.keys())
        candidates=[k for k in keys if k!=cur]
        if not candidates: continue
        # preserve chronological order based on first occurrence
        order=[]
        for dt,b in rows:
            k=keyf(dt)
            if k not in order: order.append(k)
        prev=next((k for k in reversed(order) if k!=cur),None)
        if prev is None: continue
        vals=groups[prev]
        hi=max(float(x["h"]) for x in vals); lo=min(float(x["l"]) for x in vals)
        out[kh]=hi; out[kl]=lo; out[name+"_eq"]=(hi+lo)/2
    return out

def bootstrap():
    models=normalize_models()
    paper=paper_payload()
    jobs=research_jobs(12)
    archive=archive_rows(200)
    return {
        "version":APP_VERSION,
        "generated_at_utc":now_iso(),
        "workspace":str(WORKSPACE),
        "signal_status":signal_status(),
        "models":models,
        "paper":{"status":paper["status"],"state":paper["state"],"config":paper["config"]},
        "research":jobs,
        "archive":archive[:80],
        "outcome_summary":outcome_summary(),
        "outcome_groups":outcome_dashboard(),
    }

class Handler(BaseHTTPRequestHandler):
    def json(self,obj,code=200):
        raw=json.dumps(obj,ensure_ascii=False,default=str).encode("utf-8")
        self.send_response(code); self.send_header("Content-Type","application/json; charset=utf-8")
        self.send_header("Cache-Control","no-store"); self.send_header("Content-Length",str(len(raw)))
        self.end_headers(); self.wfile.write(raw)

    def do_GET(self):
        u=urlparse(self.path); q=parse_qs(u.query)
        try:
            if u.path=="/api/bootstrap": return self.json(bootstrap())
            if u.path=="/api/models": return self.json({"models":normalize_models(),"status":signal_status()})
            if u.path=="/api/archive": return self.json({"rows":archive_rows(int(q.get("limit",["500"])[0]))})
            if u.path=="/api/outcomes": return self.json({"summary":outcome_summary(),"groups":outcome_dashboard(),"outcomes":outcome_map()})
            if u.path=="/api/paper": return self.json(paper_payload())
            if u.path=="/api/research": return self.json({"jobs":research_jobs(int(q.get("limit",["20"])[0]))})
            if u.path=="/api/snapshot":
                sid=q.get("id",[""])[0]; snap=load_snapshot(sid)
                return self.json(snap if snap else {"error":"snapshot_not_found"}, 200 if snap else 404)
            if u.path=="/api/bars":
                market=q.get("market",["NQ"])[0]; tf=q.get("tf",["1H"])[0]
                source=q.get("source",[None])[0]; limit=int(q.get("limit",["800"])[0])
                x=query_bars(market,tf,min(max(limit,50),5000),source)
                return self.json(x)
            if u.path=="/api/pd":
                market=q.get("market",["NQ"])[0]; source=q.get("source",[None])[0]
                x=query_bars(market,"1H",3000,source)
                return self.json({"levels":previous_period_level(x.get("bars") or [],market),"source":x.get("source"),"bars":len(x.get("bars") or [])})
            if u.path=="/api/health":
                return self.json({"ok":True,"version":APP_VERSION,"workspace":str(WORKSPACE),"workspace_exists":WORKSPACE.exists(),"time":now_iso()})
        except Exception as e:
            return self.json({"error":str(e)},500)

        rel="index.html" if u.path in ("","/") else u.path.lstrip("/")
        p=(WEB/rel).resolve()
        if not str(p).startswith(str(WEB.resolve())) or not p.exists() or not p.is_file():
            self.send_error(404); return
        data=p.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type",mimetypes.guess_type(str(p))[0] or "application/octet-stream")
        self.send_header("Cache-Control","no-store")
        self.send_header("Content-Length",str(len(data))); self.end_headers(); self.wfile.write(data)

    def log_message(self,*args): pass

if __name__=="__main__":
    PID_FILE.write_text(str(os.getpid()),encoding="utf-8")
    print("TMBT Next",APP_VERSION)
    print("Workspace:",WORKSPACE)
    print("Open: http://127.0.0.1:%s" % PORT)
    try:
        ThreadingHTTPServer(("127.0.0.1",PORT),Handler).serve_forever()
    finally:
        try: PID_FILE.unlink(missing_ok=True)
        except Exception: pass
