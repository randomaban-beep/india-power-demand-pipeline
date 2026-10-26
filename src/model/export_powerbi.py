"""Export tables and atomically publish a complete dashboard snapshot."""

from __future__ import annotations
from contextlib import closing
import os
from pathlib import Path
import sqlite3
import tempfile
import pandas as pd
from src.utils.config import PROCESSED_DIR, get_db_path
from src.utils.logging import get_logger

log = get_logger(__name__)
MARTS = [
    "mart_demand_profile_by_season",
    "mart_monthly_peak_demand",
    "mart_temp_vs_demand",
    "mart_daily_weather_demand",
    "mart_net_load_profile",
    "mart_net_load_ramps",
    "mart_anomaly_days",
    "stg_daily_psp",
]


def export_powerbi_tables(output_dir: Path = PROCESSED_DIR) -> None:
    """Atomically replace each export; propagate serialization errors."""
    output_dir.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(get_db_path(writable=True))) as conn:
        for table in MARTS:
            df = pd.read_sql(f'SELECT * FROM "{table}" ORDER BY 1', conn)
            for extension in ("csv", "parquet"):
                destination = output_dir / f"{table}.{extension}"
                temporary = destination.with_suffix(destination.suffix + ".tmp")
                try:
                    if extension == "csv":
                        df.to_csv(temporary, index=False)
                    else:
                        df.to_parquet(temporary, index=False)
                    os.replace(temporary, destination)
                finally:
                    temporary.unlink(missing_ok=True)
            log.info("Exported %s: %d rows", table, len(df))


def export_slim_db(destination: Path | None = None) -> Path:
    """Publish only a complete snapshot, preserving the previous one on failure."""
    source = get_db_path(writable=True)
    destination = destination or source.parent / "energy_marts.db"
    if source.resolve() == destination.resolve():
        raise ValueError("Export source and destination must be different databases")
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(suffix=".db", dir=destination.parent)
    os.close(fd)
    temporary = Path(name)
    try:
        with closing(sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True)) as src:
            with closing(sqlite3.connect(temporary)) as dst:
                for table in MARTS + ["data_quality_checks", "pipeline_runs"]:
                    df = pd.read_sql(f'SELECT * FROM "{table}" ORDER BY 1', src)
                    if df.empty:
                        raise ValueError(f"Cannot publish empty table {table}")
                    df.to_sql(table, dst, if_exists="fail", index=False)
                dst.commit()
                if dst.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise RuntimeError("Snapshot integrity check failed")
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    log.info("Published %s (%d bytes)", destination, destination.stat().st_size)
    return destination


if __name__ == "__main__":
    export_powerbi_tables()
    export_slim_db()
