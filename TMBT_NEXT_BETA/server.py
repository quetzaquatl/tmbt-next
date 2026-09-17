
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
                s.setdefault("job_id", d.name)
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

def outcome_summary():
    outs = outcome_map()
    groups = {}
    for o in outs.values():
        if not isinstance(o,dict):
            continue
        name = str(o.get("model") or o.get("model_id") or "Unknown")
        g = groups.setdefault(name, {"model":name,"signals":0,"closed":0,"open":0,"ambiguous":0,"net_r":0.0,"wins":0,"losses":0,"mfe":[],"mae":[]})
        g["signals"] += 1
        st = str(o.get("status") or "").upper()
        if st in {"OPEN","ACTIVE"}: g["open"] += 1
        elif "AMBIG" in st: g["ambiguous"] += 1
        elif st: g["closed"] += 1
        r = o.get("outcome_r")
        if r is not None:
            try:
                rv=float(r); g["net_r"] += rv
                if rv > 0: g["wins"] += 1
                elif rv < 0: g["losses"] += 1
            except Exception: pass
        for key,arr in [("mfe_r","mfe"),("mae_r","mae")]:
            try:
                if o.get(key) is not None: g[arr].append(float(o.get(key)))
            except Exception: pass
    out=[]
    for g in groups.values():
        denom=g["wins"]+g["losses"]
        g["winrate"]=(g["wins"]/denom*100.0) if denom else None
        g["expectancy"]=(g["net_r"]/g["closed"]) if g["closed"] else None
        g["avg_mfe"]=sum(g["mfe"])/len(g["mfe"]) if g["mfe"] else None
        g["avg_mae"]=sum(g["mae"])/len(g["mae"]) if g["mae"] else None
        g.pop("mfe",None); g.pop("mae",None)
        out.append(g)
    out.sort(key=lambda x:x["signals"], reverse=True)
    return out

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
                score=5+(2 if mcol else 0)+(2 if tfcol else 0)+(1 if scol else 0)
                candidates.append((score,t,o,h,l,c,ts,close_ts,mcol,tfcol,scol,vol))
            candidates.sort(reverse=True, key=lambda x:x[0])
            for item in candidates:
                _,t,o,h,l,c,ts,close_ts,mcol,tfcol,scol,vol=item
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
                        bars.append({"t":r["t"],"close_t":r["close_t"],"o":float(r["o"]),"h":float(r["h"]),"l":float(r["l"]),"c":float(r["c"]),"v":r["volume"],"source":r["source"],"market":r["market"],"tf":r["tf"]})
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
            if u.path=="/api/outcomes": return self.json({"summary":outcome_summary(),"outcomes":outcome_map()})
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
