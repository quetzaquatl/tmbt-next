from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from zoneinfo import ZoneInfo

ROOTS = ("NQ", "ES", "YM", "GC")
OUTRIGHT_RE = re.compile(r"^(?:NQ|ES|GC)[FGHJKMNQUVXZ]\d{1,2}$")
TF_WIDTHS = {
    "5m": 5 * 60_000,
    "15m": 15 * 60_000,
    "30m": 30 * 60_000,
    "1h": 60 * 60_000,
}
CHICAGO = ZoneInfo("America/Chicago")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def write_status(path: Path, **updates) -> None:
    cur = {}
    try:
        val = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
        if isinstance(val, dict):
            cur = val
    except Exception:
        pass
    cur.update(updates)
    cur["updated_at_utc"] = now_iso()
    atomic_json(path, cur)


def discover(raw_dir: Path) -> list[Path]:
    return sorted(p for p in raw_dir.rglob("*.dbn.zst") if p.is_file())


def connect(path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(path)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=NORMAL")
    con.execute("PRAGMA temp_store=MEMORY")
    con.execute("PRAGMA cache_size=-200000")
    return con


def init_db(con: sqlite3.Connection) -> None:
    con.executescript("""
    CREATE TABLE meta (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );
    CREATE TABLE daily_volume (
        root TEXT NOT NULL,
        trade_date TEXT NOT NULL,
        symbol TEXT NOT NULL,
        volume REAL NOT NULL,
        PRIMARY KEY(root, trade_date, symbol)
    ) WITHOUT ROWID;
    CREATE TABLE active_contract (
        root TEXT NOT NULL,
        trade_date TEXT NOT NULL,
        symbol TEXT NOT NULL,
        source_trade_date TEXT NOT NULL,
        previous_session_volume REAL,
        method TEXT NOT NULL,
        PRIMARY KEY(root, trade_date)
    ) WITHOUT ROWID;
    """)
    for tf in ("1m", *TF_WIDTHS):
        con.execute(f"""
        CREATE TABLE bars_{tf} (
            root TEXT NOT NULL,
            t INTEGER NOT NULL,
            symbol TEXT NOT NULL,
            o REAL NOT NULL,
            h REAL NOT NULL,
            l REAL NOT NULL,
            c REAL NOT NULL,
            v REAL NOT NULL,
            PRIMARY KEY(root, t)
        ) WITHOUT ROWID
        """)
    con.commit()


def prepare(df):
    import pandas as pd

    if df is None or df.empty:
        return None
    x = df.reset_index()
    if "ts_event" not in x.columns:
        for candidate in ("index", "timestamp", "ts_recv"):
            if candidate in x.columns:
                x = x.rename(columns={candidate: "ts_event"})
                break
    required = {"ts_event", "open", "high", "low", "close", "volume", "symbol"}
    missing = required.difference(x.columns)
    if missing:
        raise RuntimeError(f"OHLCV DBN is missing columns: {sorted(missing)}")

    x["symbol"] = x["symbol"].astype(str).str.strip()
    x = x[x["symbol"].str.fullmatch(OUTRIGHT_RE, na=False)].copy()
    if x.empty:
        return None
    x["root"] = x["symbol"].str[:2]

    ts = pd.to_datetime(x["ts_event"], utc=True, errors="coerce")
    valid = ts.notna()
    x = x[valid].copy()
    ts = ts[valid]
    if x.empty:
        return None

    x["ts_ms"] = (ts.astype("int64") // 1_000_000).astype("int64")
    ct = ts.dt.tz_convert(CHICAGO)
    # CME futures session starts 17:00 CT; +7h maps that boundary to midnight.
    x["trade_date"] = (ct + pd.Timedelta(hours=7)).dt.strftime("%Y-%m-%d")

    for col in ("open", "high", "low", "close", "volume"):
        x[col] = pd.to_numeric(x[col], errors="coerce")
    return x.dropna(subset=["open", "high", "low", "close", "volume"])


def frames(path: Path, chunk_rows: int):
    try:
        import databento as db
    except ImportError as exc:
        raise RuntimeError("Missing Python package 'databento'. Run IMPORT_DATABENTO_HISTORY.bat.") from exc

    store = db.DBNStore.from_file(path)
    for df in store.to_df(schema="ohlcv-1m", count=chunk_rows):
        x = prepare(df)
        if x is not None and not x.empty:
            yield x


def collect_daily_volume(
    con: sqlite3.Connection,
    files: list[Path],
    status_path: Path,
    chunk_rows: int,
) -> None:
    sql = """
    INSERT INTO daily_volume(root, trade_date, symbol, volume)
    VALUES(?, ?, ?, ?)
    ON CONFLICT(root, trade_date, symbol)
    DO UPDATE SET volume=volume+excluded.volume
    """
    for i, path in enumerate(files, 1):
        write_status(
            status_path,
            state="RUNNING",
            stage="daily_volume",
            file_index=i,
            file_count=len(files),
            current_file=str(path),
        )
        for x in frames(path, chunk_rows):
            grouped = (
                x.groupby(["root", "trade_date", "symbol"], sort=False)["volume"]
                .sum()
                .reset_index()
            )
            con.executemany(
                sql,
                [
                    (str(r.root), str(r.trade_date), str(r.symbol), float(r.volume))
                    for r in grouped.itertuples(index=False)
                ],
            )
        con.commit()


def make_roll_map(con: sqlite3.Connection) -> dict[tuple[str, str], str]:
    rows = con.execute("""
        SELECT root, trade_date, symbol, volume
        FROM daily_volume
        ORDER BY root, trade_date, volume DESC, symbol
    """).fetchall()

    data: dict[str, dict[str, list[tuple[str, float]]]] = {}
    for root, day, symbol, volume in rows:
        data.setdefault(root, {}).setdefault(day, []).append((symbol, float(volume)))

    active: dict[tuple[str, str], str] = {}
    out = []
    for root in ROOTS:
        prev_day = None
        prev_leader = None
        prev_volume = None
        for day in sorted(data.get(root, {})):
            candidates = data[root][day]
            symbols = {s for s, _ in candidates}
            current_leader, current_volume = candidates[0]
            if prev_leader and prev_leader in symbols:
                chosen = prev_leader
                source_day = prev_day or day
                reference_volume = prev_volume
                method = "previous_completed_session_volume_leader"
            else:
                chosen = current_leader
                source_day = day
                reference_volume = current_volume
                method = "same_session_fallback"
            active[(root, day)] = chosen
            out.append((root, day, chosen, source_day, reference_volume, method))
            prev_day = day
            prev_leader = current_leader
            prev_volume = current_volume

    con.executemany("""
        INSERT INTO active_contract
        (root, trade_date, symbol, source_trade_date, previous_session_volume, method)
        VALUES(?, ?, ?, ?, ?, ?)
    """, out)
    con.commit()
    return active


def write_continuous_1m(
    con: sqlite3.Connection,
    files: list[Path],
    status_path: Path,
    chunk_rows: int,
    active: dict[tuple[str, str], str],
) -> None:
    sql = """
    INSERT OR REPLACE INTO bars_1m(root, t, symbol, o, h, l, c, v)
    VALUES(?, ?, ?, ?, ?, ?, ?, ?)
    """
    for i, path in enumerate(files, 1):
        write_status(
            status_path,
            state="RUNNING",
            stage="continuous_1m",
            file_index=i,
            file_count=len(files),
            current_file=str(path),
        )
        for x in frames(path, chunk_rows):
            selected = [
                active.get((str(root), str(day)))
                for root, day in zip(x["root"], x["trade_date"])
            ]
            x = x.assign(_active=selected)
            x = x[x["symbol"] == x["_active"]]
            if x.empty:
                continue
            con.executemany(
                sql,
                [
                    (
                        str(r.root),
                        int(r.ts_ms),
                        str(r.symbol),
                        float(r.open),
                        float(r.high),
                        float(r.low),
                        float(r.close),
                        float(r.volume),
                    )
                    for r in x.itertuples(index=False)
                ],
            )
        con.commit()


def aggregate(con: sqlite3.Connection, status_path: Path) -> None:
    for root in ROOTS:
        write_status(status_path, state="RUNNING", stage="aggregate", current_root=root)
        states = {
            tf: {"bucket": None, "row": None, "buffer": []}
            for tf in TF_WIDTHS
        }

        def flush(tf: str) -> None:
            st = states[tf]
            if st["row"] is not None:
                st["buffer"].append(tuple(st["row"]))
                st["row"] = None
            if len(st["buffer"]) >= 10_000:
                con.executemany(
                    f"INSERT OR REPLACE INTO bars_{tf}(root,t,symbol,o,h,l,c,v) VALUES(?,?,?,?,?,?,?,?)",
                    st["buffer"],
                )
                st["buffer"].clear()

        cursor = con.execute(
            "SELECT t,symbol,o,h,l,c,v FROM bars_1m WHERE root=? ORDER BY t",
            (root,),
        )
        for t, symbol, o, h, l, c, v in cursor:
            for tf, width in TF_WIDTHS.items():
                bucket = (int(t) // width) * width
                st = states[tf]
                if st["bucket"] != bucket:
                    flush(tf)
                    st["bucket"] = bucket
                    st["row"] = [root, bucket, str(symbol), float(o), float(h), float(l), float(c), float(v)]
                else:
                    row = st["row"]
                    row[4] = max(float(row[4]), float(h))
                    row[5] = min(float(row[5]), float(l))
                    row[6] = float(c)
                    row[7] = float(row[7]) + float(v)
                    if row[2] != str(symbol):
                        row[2] = f"{row[2]}->{symbol}"

        for tf in TF_WIDTHS:
            flush(tf)
            buf = states[tf]["buffer"]
            if buf:
                con.executemany(
                    f"INSERT OR REPLACE INTO bars_{tf}(root,t,symbol,o,h,l,c,v) VALUES(?,?,?,?,?,?,?,?)",
                    buf,
                )
                buf.clear()
        con.commit()


def summarize(con: sqlite3.Connection) -> dict:
    result = {}
    for root in ROOTS:
        count, first_ms, last_ms, contracts = con.execute(
            "SELECT COUNT(*), MIN(t), MAX(t), COUNT(DISTINCT symbol) FROM bars_1m WHERE root=?",
            (root,),
        ).fetchone()
        counts = {}
        for tf in ("1m", *TF_WIDTHS):
            counts[tf] = int(
                con.execute(f"SELECT COUNT(*) FROM bars_{tf} WHERE root=?", (root,)).fetchone()[0]
            )
        result[root] = {
            "bars_1m": int(count or 0),
            "first_ms": first_ms,
            "last_ms": last_ms,
            "contracts_used": int(contracts or 0),
            "counts": counts,
        }
    return result


def run(workspace: Path, raw_dir: Path, db_path: Path, chunk_rows: int) -> dict:
    status_path = workspace / "historical" / "databento" / "import_status.json"
    files = discover(raw_dir)
    if not files:
        raise FileNotFoundError(f"No *.dbn.zst files found below {raw_dir}")

    db_path.parent.mkdir(parents=True, exist_ok=True)
    building = db_path.with_suffix(db_path.suffix + ".building")
    for suffix in ("", "-wal", "-shm"):
        try:
            Path(str(building) + suffix).unlink()
        except FileNotFoundError:
            pass

    write_status(
        status_path,
        state="RUNNING",
        stage="start",
        started_at_utc=now_iso(),
        raw_dir=str(raw_dir),
        db=str(db_path),
        file_count=len(files),
        files=[str(p) for p in files],
        roll_method="previous_completed_CME_session_volume_leader",
    )

    con = connect(building)
    try:
        init_db(con)
        collect_daily_volume(con, files, status_path, chunk_rows)
        write_status(status_path, state="RUNNING", stage="build_roll_map")
        active = make_roll_map(con)
        write_continuous_1m(con, files, status_path, chunk_rows, active)
        aggregate(con, status_path)
        con.executemany(
            "INSERT OR REPLACE INTO meta(key,value) VALUES(?,?)",
            [
                ("source", "Databento GLBX.MDP3 OHLCV-1m"),
                ("roll_method", "previous_completed_CME_session_volume_leader"),
                ("built_at_utc", now_iso()),
            ],
        )
        con.commit()
        con.execute("ANALYZE")
        con.commit()
        result = summarize(con)
        con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        con.execute("PRAGMA journal_mode=DELETE")
        con.commit()
    finally:
        con.close()

    os.replace(building, db_path)
    write_status(
        status_path,
        state="COMPLETE",
        stage="done",
        completed_at_utc=now_iso(),
        summary=result,
        db_size_bytes=db_path.stat().st_size,
    )
    return result


def parse_args(argv: Iterable[str] | None = None):
    p = argparse.ArgumentParser(description="Import local Databento futures history into TMBT.")
    p.add_argument(
        "--workspace",
        default=os.environ.get(
            "TMBT_WORKSPACE",
            r"D:\Projekt model\Trading_Model_Backtest_Studio_WORKSPACE",
        ),
    )
    p.add_argument("--raw", default=None)
    p.add_argument("--db", default=None)
    p.add_argument("--chunk-rows", type=int, default=250_000)
    return p.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    workspace = Path(args.workspace).resolve()
    raw_dir = Path(args.raw).resolve() if args.raw else workspace / "historical" / "databento" / "raw"
    db_path = Path(args.db).resolve() if args.db else workspace / "historical" / "databento" / "tmbt_futures_history.sqlite"
    status_path = workspace / "historical" / "databento" / "import_status.json"
    try:
        result = run(workspace, raw_dir, db_path, max(10_000, int(args.chunk_rows)))
        print(json.dumps(result, indent=2))
        print(f"\nHistorical DB ready: {db_path}")
        return 0
    except Exception as exc:
        write_status(status_path, state="FAILED", stage="error", error=f"{type(exc).__name__}: {exc}")
        print(f"IMPORT FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
