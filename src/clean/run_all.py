"""Cleaning orchestration: executes SQL staging models and runs data quality suite."""

from __future__ import annotations

import datetime as dt
import time
from sqlalchemy import text

from src.clean.clean_hourly import clean_hourly_demand
from src.clean.quality_checks import run_checks
from src.utils.config import SQL_DIR
from src.utils.db import get_connection, get_engine, get_trigger, init_db
from src.utils.logging import get_logger

log = get_logger(__name__)


def log_run(
    stage: str,
    source: str,
    rows_fetched: int,
    rows_inserted: int,
    duration_s: float,
    status: str,
    message: str,
) -> None:
    engine = get_engine()
    now_iso = dt.datetime.now(dt.timezone.utc).isoformat()
    trigger = get_trigger()
    with engine.connect() as conn:
        conn.execute(
            text("""
            INSERT INTO pipeline_runs (
                run_at, stage, source, rows_fetched, rows_inserted,
                rows_skipped, duration_s, status, trigger, message
            ) VALUES (
                :run_at, :stage, :source, :rows_fetched, :rows_inserted,
                0, :duration_s, :status, :trigger, :message
            )
        """),
            {
                "run_at": now_iso,
                "stage": stage,
                "source": source,
                "rows_fetched": rows_fetched,
                "rows_inserted": rows_inserted,
                "duration_s": duration_s,
                "status": status,
                "trigger": trigger,
                "message": message,
            },
        )
        conn.commit()


def run_staging_sql() -> None:
    """Run Python robust cleaning for stg_hourly_demand followed by staging SQL models."""
    clean_hourly_demand()
    staging_files = [
        "stg_hourly_weather.sql",
        "stg_daily_psp.sql",
    ]
    with get_connection() as conn:
        for fname in staging_files:
            fpath = SQL_DIR / "staging" / fname
            if not fpath.exists():
                raise FileNotFoundError(f"Required SQL model missing: {fpath}")
            if fpath.exists():
                sql_content = fpath.read_text(encoding="utf-8")
                conn.executescript(sql_content)
                log.info("Executed staging SQL: %s", fname)


def run_all() -> None:
    """Orchestrate Phase 3: staging layer creation + automated quality checks."""
    init_db()
    t0 = time.time()
    log.info("Starting Phase 3: Cleaning & Data Quality...")
    try:
        run_staging_sql()
        dq_summary = run_checks()
        if dq_summary["failed"]:
            raise RuntimeError(
                f"Data quality gate failed: {dq_summary['failed']} checks; inspect data_quality_checks"
            )
        dur = round(time.time() - t0, 2)
        log_run(
            "clean",
            "staging_layer",
            dq_summary["total_checks"],
            dq_summary["passed"],
            dur,
            "ok",
            f"{dq_summary['passed']} checks passed, {dq_summary['failed']} failed",
        )
        log.info("Cleaning and quality checks complete in %s seconds.", dur)
    except Exception as e:
        dur = round(time.time() - t0, 2)
        log_run("clean", "staging_layer", 0, 0, dur, "error", str(e))
        log.error("Cleaning failed: %s", e)
        raise


if __name__ == "__main__":
    run_all()
