"""Mendeley Hourly Historical Dataset Ingest Module.

Fetches monthly Excel files from the Mendeley repository (DOI 10.17632/y58jknpgs8.2),
extracts 5-minute SCADA demand, solar, and wind values, aggregates to 1-hour interval,
and loads into raw_hourly_demand table in energy.db.
"""

from __future__ import annotations

import datetime as dt
import io
from pathlib import Path
from typing import Any
import openpyxl
import pandas as pd
import requests
from sqlalchemy import text

from src.utils.config import RAW_DIR
from src.utils.db import get_engine, init_db
from src.utils.logging import get_logger

log = get_logger(__name__)

MENDELEY_API_FILES = "https://data.mendeley.com/public-api/datasets/y58jknpgs8/files?folder_id=root&version=2&$start=0&$limit=1000"


def create_raw_hourly_table() -> None:
    """Create raw_hourly_demand table if not exists."""
    engine = get_engine()
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS raw_hourly_demand (
                timestamp_ist     TEXT PRIMARY KEY,
                thermal_mw        REAL,
                hydro_mw          REAL,
                gas_mw            REAL,
                nuclear_mw        REAL,
                wind_mw           REAL,
                solar_mw          REAL,
                total_demand_mw   REAL,
                source            TEXT NOT NULL,
                ingested_at       TEXT NOT NULL
            );
        """))
        conn.commit()


def get_mendeley_file_list() -> list[dict[str, Any]]:
    """List all available monthly files in Mendeley dataset."""
    headers = {
        "Accept": "application/vnd.mendeley-public-dataset.1+json",
        "User-Agent": "Mozilla/5.0",
    }
    try:
        r = requests.get(MENDELEY_API_FILES, headers=headers, timeout=20)
        r.raise_for_status()
        files = r.json()
        return [f for f in files if str(f.get("filename")).endswith(".xlsx")]
    except Exception as e:
        log.error("Failed to query Mendeley files API: %s", e)
        return []


def parse_mendeley_month_excel(file_bytes_or_path: bytes | Path) -> pd.DataFrame:
    """Read Sheet1 of a Mendeley monthly Excel file and return 1-hour aggregated DataFrame."""
    if isinstance(file_bytes_or_path, bytes):
        wb = openpyxl.load_workbook(io.BytesIO(file_bytes_or_path), read_only=True, data_only=True)
    else:
        wb = openpyxl.load_workbook(str(file_bytes_or_path), read_only=True, data_only=True)
    
    sheet = wb["Sheet1"]
    rows = list(sheet.iter_rows(values_only=True))
    if len(rows) < 3:
        return pd.DataFrame()
    
    data_rows = rows[2:]
    records = []
    for r in data_rows:
        ts = r[0]
        if ts is None or not isinstance(ts, (dt.datetime, str)):
            continue
        try:
            thm = float(r[1]) if r[1] is not None else 0.0
            hyd = float(r[2]) if r[2] is not None else 0.0
            gas = float(r[3]) if r[3] is not None else 0.0
            npc = float(r[4]) if r[4] is not None else 0.0
            wnd = float(r[5]) if r[5] is not None else 0.0
            sol = float(r[6]) if r[6] is not None else 0.0
            sol = max(0.0, sol)
            tot = thm + hyd + gas + npc + wnd + sol
            records.append({
                "timestamp": pd.to_datetime(ts),
                "thermal_mw": thm,
                "hydro_mw": hyd,
                "gas_mw": gas,
                "nuclear_mw": npc,
                "wind_mw": wnd,
                "solar_mw": sol,
                "total_demand_mw": tot,
            })
        except (ValueError, TypeError):
            continue

    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)
    df = df.set_index("timestamp").resample("1h").mean().reset_index()
    df["timestamp_ist"] = df["timestamp"].dt.strftime("%Y-%m-%dT%H:00")
    return df


def ingest_mendeley_historical(max_files: int = 4) -> int:
    """Download up to max_files months from Mendeley and load into raw_hourly_demand."""
    init_db()
    create_raw_hourly_table()
    engine = get_engine()
    
    files = get_mendeley_file_list()
    # Filter for representative months under 10MB each so ingestion is very fast and responsive
    small_files = [f for f in files if f.get("size", 0) < 10_000_000]
    small_files = sorted(small_files, key=lambda f: str(f.get("filename")))
    
    now_iso = dt.datetime.now(dt.timezone.utc).isoformat()
    total_rows = 0
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    for f_meta in small_files[:max_files]:
        fname = f_meta.get("filename", "")
        dl_url = f_meta.get("content_details", {}).get("download_url")
        if not dl_url:
            continue
        
        local_path = RAW_DIR / fname
        log.info("Processing Mendeley file: %s ...", fname)
        try:
            if not local_path.exists():
                r = requests.get(dl_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
                if r.status_code == 200:
                    local_path.write_bytes(r.content)
                else:
                    continue
            
            df = parse_mendeley_month_excel(local_path)
            if df.empty:
                continue

            insert_records = []
            for _, row in df.iterrows():
                insert_records.append({
                    "timestamp_ist": row["timestamp_ist"],
                    "thermal_mw": row["thermal_mw"],
                    "hydro_mw": row["hydro_mw"],
                    "gas_mw": row["gas_mw"],
                    "nuclear_mw": row["nuclear_mw"],
                    "wind_mw": row["wind_mw"],
                    "solar_mw": row["solar_mw"],
                    "total_demand_mw": row["total_demand_mw"],
                    "ingested_at": now_iso
                })

            with engine.connect() as conn:
                conn.execute(text("""
                    INSERT INTO raw_hourly_demand (
                        timestamp_ist, thermal_mw, hydro_mw, gas_mw, nuclear_mw,
                        wind_mw, solar_mw, total_demand_mw, source, ingested_at
                    ) VALUES (
                        :timestamp_ist, :thermal_mw, :hydro_mw, :gas_mw, :nuclear_mw,
                        :wind_mw, :solar_mw, :total_demand_mw, 'mendeley', :ingested_at
                    )
                    ON CONFLICT(timestamp_ist) DO UPDATE SET
                        thermal_mw=excluded.thermal_mw,
                        hydro_mw=excluded.hydro_mw,
                        gas_mw=excluded.gas_mw,
                        nuclear_mw=excluded.nuclear_mw,
                        wind_mw=excluded.wind_mw,
                        solar_mw=excluded.solar_mw,
                        total_demand_mw=excluded.total_demand_mw,
                        ingested_at=excluded.ingested_at;
                """), insert_records)
                conn.commit()
            total_rows += len(df)
            log.info("Loaded %d hourly records from %s", len(df), fname)
        except Exception as e:
            log.error("Failed to process %s: %s", fname, e)

    log.info("Mendeley historical ingest complete: %d total hourly rows", total_rows)
    return total_rows


if __name__ == "__main__":
    ingest_mendeley_historical(max_files=4)
