"""One-command rebuild on an isolated SQLite copy, with JSON measurements."""

from __future__ import annotations
import argparse
from contextlib import closing
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import platform
import sqlite3
import tempfile
import time


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True, help="Full raw SQLite database")
    parser.add_argument("--output", type=Path, default=Path("data/run"))
    parser.add_argument("--ingest", action="store_true", help="Refresh network sources before rebuilding")
    args = parser.parse_args()
    source, output = args.db.resolve(), args.output.resolve()
    if not source.is_file():
        parser.error("Full database missing; restore data-latest release (see README).")
    if source.parent == output:
        parser.error("Use a separate output directory to preserve the input database.")
    output.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix="run-", suffix=".db", dir=output)
    os.close(fd)
    working = Path(name)
    report = {
        "started_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "mode": "refresh" if args.ingest else "offline",
        "stages": {},
        "status": "error",
    }
    start = time.perf_counter()
    try:
        with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as src:
            with closing(sqlite3.connect(working)) as dst:
                src.backup(dst)
        os.environ["ENERGY_DB_PATH"] = str(working)
        os.environ["ENERGY_WRITE_CLEANING_LOG"] = "0"
        from src.clean.run_all import run_all as clean
        from src.model.run_all import run_all as model
        from src.model.export_powerbi import export_powerbi_tables, export_slim_db

        stages = [("clean", clean), ("model", model)]
        if args.ingest:
            from src.ingest.run_all import run_all as ingest

            stages.insert(0, ("ingest", ingest))
        for label, function in stages:
            stage_start = time.perf_counter()
            function()
            report["stages"][label] = round(time.perf_counter() - stage_start, 6)
        export_powerbi_tables(output / "processed")
        with closing(sqlite3.connect(working)) as conn:
            report["tables"] = {}
            for (table,) in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ):
                quoted = table.replace('"', '""')
                report["tables"][table] = conn.execute(f'SELECT COUNT(*) FROM "{quoted}"').fetchone()[0]
            report["valid_demand_rows"] = conn.execute(
                "SELECT COUNT(demand_mw) FROM stg_hourly_demand"
            ).fetchone()[0]
            report["raw_hourly_sha256"] = hashlib.sha256(
                json.dumps(
                    conn.execute("SELECT * FROM raw_hourly_demand ORDER BY timestamp_ist").fetchall(),
                    separators=(",", ":"),
                ).encode()
            ).hexdigest()
        export_slim_db(output / "energy_marts.db")
        report["status"] = "ok"
    except Exception as exc:
        report["error"] = str(exc)
        raise
    finally:
        report["duration_s"] = round(time.perf_counter() - start, 6)
        if "tables" in report:
            report["hourly_records_per_second"] = round(
                report["tables"]["raw_hourly_demand"] / report["duration_s"], 2
            )
        (output / "run.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        working.unlink(missing_ok=True)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
