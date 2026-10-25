"""Export modeled mart tables to CSV / Parquet for Power BI and document the data model."""

from __future__ import annotations

import sqlite3
from pathlib import Path
import pandas as pd

from src.utils.config import DB_PATH, PROCESSED_DIR
from src.utils.logging import get_logger

log = get_logger(__name__)


def export_powerbi_tables() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)

    marts = [
        "mart_demand_profile_by_season",
        "mart_monthly_peak_demand",
        "mart_temp_vs_demand",
        "mart_daily_weather_demand",
        "mart_net_load_profile",
        "mart_net_load_ramps",
        "mart_anomaly_days",
        "stg_daily_psp",
    ]

    for m in marts:
        df = pd.read_sql(f"SELECT * FROM {m}", conn)
        csv_path = PROCESSED_DIR / f"{m}.csv"
        parquet_path = PROCESSED_DIR / f"{m}.parquet"
        
        df.to_csv(csv_path, index=False)
        try:
            df.to_parquet(parquet_path, index=False)
        except Exception:
            pass
        log.info("Exported %s: %d rows to %s", m, len(df), csv_path.name)

    log.info("All Power BI mart exports complete in %s", PROCESSED_DIR)


def export_slim_db() -> Path:
    """Export clean marts and audit tables to a lightweight database (energy_marts.db)."""
    conn_src = sqlite3.connect(DB_PATH)
    slim_path = DB_PATH.parent / "energy_marts.db"
    conn_dst = sqlite3.connect(slim_path)

    tables = [
        "mart_demand_profile_by_season",
        "mart_monthly_peak_demand",
        "mart_temp_vs_demand",
        "mart_daily_weather_demand",
        "mart_net_load_profile",
        "mart_net_load_ramps",
        "mart_anomaly_days",
        "stg_daily_psp",
        "data_quality_checks",
        "pipeline_runs"
    ]
    for t in tables:
        try:
            df = pd.read_sql(f"SELECT * FROM {t}", conn_src)
            df.to_sql(t, conn_dst, if_exists="replace", index=False)
        except Exception as e:
            log.warning("Could not export table %s to slim DB: %s", t, e)

    conn_dst.execute("VACUUM")
    conn_dst.close()
    conn_src.close()
    log.info("Exported slim marts DB to %s (%d bytes)", slim_path.name, slim_path.stat().st_size)
    return slim_path


if __name__ == "__main__":
    export_powerbi_tables()
