"""Ingest orchestration: runs all source ingests and logs to pipeline_runs."""

from __future__ import annotations

import datetime as dt
import time
from sqlalchemy import text

from src.ingest.grid_india import ingest_daily_psp
from src.ingest.mendeley import ingest_mendeley_historical
from src.ingest.open_meteo import ingest_weather
from src.utils.db import get_engine, init_db
from src.utils.logging import get_logger

log = get_logger(__name__)


def log_run(stage: str, source: str, rows_fetched: int, rows_inserted: int, duration_s: float, status: str, message: str) -> None:
    """Record run details into pipeline_runs audit table."""
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


def run_all(mendeley_files: int = 12) -> None:
    """Execute all ingest stages sequentially."""
    init_db()
    log.info("Starting end-to-end ingest...")

    # 1. Grid-India daily PSP reports
    t0 = time.time()
    try:
        daily_rows, state_rows = ingest_daily_psp(limit=20)
        dur = round(time.time() - t0, 2)
        log_run("ingest", "grid_india", daily_rows, daily_rows + state_rows, dur, "ok", f"{daily_rows} daily, {state_rows} state records")
    except Exception as e:
        dur = round(time.time() - t0, 2)
        log_run("ingest", "grid_india", 0, 0, dur, "error", str(e))
        log.error("Grid-India ingest failed: %s", e)

    # 2. Mendeley historical hourly data
    t0 = time.time()
    try:
        hourly_rows = ingest_mendeley_historical(max_files=mendeley_files)
        dur = round(time.time() - t0, 2)
        log_run("ingest", "mendeley", hourly_rows, hourly_rows, dur, "ok", f"{hourly_rows} hourly records")
    except Exception as e:
        dur = round(time.time() - t0, 2)
        log_run("ingest", "mendeley", 0, 0, dur, "error", str(e))
        log.error("Mendeley ingest failed: %s", e)

    # 3. Open-Meteo weather data (covering historical period)
    t0 = time.time()
    try:
        weather_rows = ingest_weather(start_date="2022-01-01", end_date="2023-12-31")
        dur = round(time.time() - t0, 2)
        log_run("ingest", "open_meteo", weather_rows, weather_rows, dur, "ok", f"{weather_rows} weather rows across 6 cities")
    except Exception as e:
        dur = round(time.time() - t0, 2)
        log_run("ingest", "open_meteo", 0, 0, dur, "error", str(e))
        log.error("Open-Meteo ingest failed: %s", e)

    log.info("Ingest run complete!")


if __name__ == "__main__":
    run_all()
