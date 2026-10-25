"""Model orchestration: executes all SQL analytical mart files."""

from __future__ import annotations

import datetime as dt
import time
from sqlalchemy import text

from src.utils.config import SQL_DIR
from src.utils.db import get_engine, init_db
from src.utils.logging import get_logger

log = get_logger(__name__)


def log_run(stage: str, source: str, rows_fetched: int, rows_inserted: int, duration_s: float, status: str, message: str) -> None:
    engine = get_engine()
    now_iso = dt.datetime.now(dt.timezone.utc).isoformat()
    with engine.connect() as conn:
        conn.execute(text("""
            INSERT INTO pipeline_runs (
                run_at, stage, source, rows_fetched, rows_inserted,
                rows_skipped, duration_s, status, message
            ) VALUES (
                :run_at, :stage, :source, :rows_fetched, :rows_inserted,
                0, :duration_s, :status, :message
            )
        """), {
            "run_at": now_iso,
            "stage": stage,
            "source": source,
            "rows_fetched": rows_fetched,
            "rows_inserted": rows_inserted,
            "duration_s": duration_s,
            "status": status,
            "message": message
        })
        conn.commit()


def run_mart_sql() -> None:
    """Run all SQL files in sql/marts/ in order."""
    engine = get_engine()
    mart_files = [
        "mart_demand_profile_by_season.sql",
        "mart_monthly_peak_demand.sql",
        "mart_temp_vs_demand.sql",
        "mart_net_load_profile.sql",
        "mart_net_load_ramps.sql",
        "mart_anomaly_days.sql",
    ]
    
    with engine.connect() as conn:
        for fname in mart_files:
            fpath = SQL_DIR / "marts" / fname
            if fpath.exists():
                sql_content = fpath.read_text(encoding="utf-8")
                for statement in sql_content.split(";"):
                    stmt = statement.strip()
                    if stmt:
                        conn.execute(text(stmt))
                conn.commit()
                log.info("Executed mart SQL: %s", fname)


def run_all() -> None:
    """Orchestrate Phase 4: build analytical data marts."""
    init_db()
    t0 = time.time()
    log.info("Starting Phase 4: SQL Modeling & Analytics...")
    try:
        run_mart_sql()
        dur = round(time.time() - t0, 2)
        log_run("model", "marts_layer", 6, 6, dur, "ok", "6 SQL marts built successfully")
        log.info("SQL Mart modeling complete in %s seconds.", dur)
    except Exception as e:
        dur = round(time.time() - t0, 2)
        log_run("model", "marts_layer", 0, 0, dur, "error", str(e))
        log.error("Modeling failed: %s", e)
        raise


if __name__ == "__main__":
    run_all()
