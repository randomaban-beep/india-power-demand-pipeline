"""Ingest orchestration: runs all source ingests and logs to pipeline_runs."""

from __future__ import annotations

import datetime as dt
import sys
import time
from sqlalchemy import text

from src.ingest.grid_india import ingest_daily_psp
from src.ingest.mendeley import ingest_mendeley_historical
from src.ingest.open_meteo import ingest_weather
from src.utils.config import DATA_DIR
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
    engine = get_engine()

    try:
        with engine.connect() as conn:
            pre_count = conn.execute(text("SELECT COUNT(*) FROM stg_daily_psp")).scalar() or 0
        (DATA_DIR / ".pre_ingest_psp_count").write_text(str(pre_count))
    except Exception:
        pass

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
        # If we have an existing populated database from release restore, do not crash pipeline;
        # log warning and proceed so weather, models, and tests can continue.
        try:
            with engine.connect() as conn:
                existing_psp = conn.execute(text("SELECT COUNT(*) FROM stg_daily_psp")).scalar() or 0
        except Exception:
            existing_psp = 0
        if existing_psp == 0:
            raise RuntimeError(f"Grid-India ingest failed and database has 0 existing reports: {e}") from e
        log.warning("Retaining %d existing PSP reports from restored database; continuing pipeline.", existing_psp)

    # 2. Mendeley historical hourly data (skips if rows exist)
    t0 = time.time()
    try:
        hourly_rows = ingest_mendeley_historical(max_files=mendeley_files)
        dur = round(time.time() - t0, 2)
        log_run("ingest", "mendeley", hourly_rows, hourly_rows, dur, "ok", f"{hourly_rows} hourly records")
    except Exception as e:
        dur = round(time.time() - t0, 2)
        log_run("ingest", "mendeley", 0, 0, dur, "error", str(e))
        log.error("Mendeley ingest failed: %s", e)
        raise RuntimeError(f"Mendeley ingest failed: {e}") from e

    # 3. Open-Meteo weather data (incremental up to yesterday)
    t0 = time.time()
    try:
        weather_rows = ingest_weather()
        dur = round(time.time() - t0, 2)
        log_run("ingest", "open_meteo", weather_rows, weather_rows, dur, "ok", f"{weather_rows} weather rows across 6 cities")
    except Exception as e:
        dur = round(time.time() - t0, 2)
        log_run("ingest", "open_meteo", 0, 0, dur, "error", str(e))
        log.error("Open-Meteo ingest failed: %s", e)
        raise RuntimeError(f"Open-Meteo weather ingest failed: {e}") from e

    log.info("Ingest run complete!")


if __name__ == "__main__":
    try:
        run_all()
    except Exception as err:
        log.error("Ingest pipeline failed: %s", err)
        sys.exit(1)
