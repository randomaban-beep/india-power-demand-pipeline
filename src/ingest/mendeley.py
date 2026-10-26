"""Mendeley Hourly Historical Dataset Ingest Module.

Fetches monthly Excel files and multi-month aggregated reports from the Mendeley repository
(DOI 10.17632/y58jknpgs8.2), extracts demand, solar, and wind values, aggregates to 1-hour interval,
and loads into raw_hourly_demand table in energy.db.
"""

from __future__ import annotations

import datetime as dt
import io
from pathlib import Path
from typing import Any
import openpyxl
import pandas as pd
import numpy as np
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
        conn.execute(
            text("""
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
        """)
        )
        conn.commit()


def get_mendeley_file_list() -> list[dict[str, Any]]:
    """List all available files in Mendeley dataset."""
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
        raise


def parse_mendeley_month_excel(file_bytes_or_path: bytes | Path) -> pd.DataFrame:
    """Read a Mendeley Excel file (handles both Sheet1 5-min format and Report 1-hour format)."""
    if isinstance(file_bytes_or_path, bytes):
        wb = openpyxl.load_workbook(io.BytesIO(file_bytes_or_path), read_only=True, data_only=True)
    else:
        wb = openpyxl.load_workbook(str(file_bytes_or_path), read_only=True, data_only=True)

    try:
        sheet_names = wb.sheetnames

        # Check for Format B (e.g. 'January 2024- June 2025.xlsx' with 'Report' sheet)
        if "Report" in sheet_names:
            sheet = wb["Report"]
            rows = list(sheet.iter_rows(values_only=True))
            if len(rows) < 2:
                return pd.DataFrame()
            # Header is row 0: ('Timestamp', 'Demand (MW)', 'Wind (MW)', 'Solar (MW)', 'Total Generation (MW)')
            # Last rows may contain summary statistics ('Minimum', 'Maximum', 'Average', 'Sum')
            records = []
            for r in rows[1:]:
                ts_raw = r[0]
                if not ts_raw:
                    continue
                # Stop if reached summary statistics
                if str(ts_raw).strip() in ("Minimum", "Maximum", "Average", "Sum", "Timestamp"):
                    continue
                try:
                    # Format is typically '01-01-2024 00:00:00' or datetime object
                    if isinstance(ts_raw, dt.datetime):
                        ts_val = ts_raw
                    else:
                        ts_val = dt.datetime.strptime(str(ts_raw).strip(), "%d-%m-%Y %H:%M:%S")

                    d_mw = float(r[1]) if r[1] is not None else np.nan
                    w_mw = float(r[2]) if r[2] is not None else np.nan
                    s_mw = float(r[3]) if r[3] is not None else np.nan
                    s_mw = max(s_mw, 0.0)
                    w_mw = max(w_mw, 0.0)

                    records.append(
                        {
                            "timestamp": ts_val,
                            "thermal_mw": None,
                            "hydro_mw": None,
                            "gas_mw": None,
                            "nuclear_mw": None,
                            "wind_mw": w_mw,
                            "solar_mw": s_mw,
                            "total_demand_mw": d_mw,
                        }
                    )
                except Exception:
                    continue

            if not records:
                return pd.DataFrame()

            df = pd.DataFrame(records)
            df["timestamp_ist"] = df["timestamp"].dt.strftime("%Y-%m-%dT%H:00")
            df = df.drop(columns=["timestamp"]).drop_duplicates(subset=["timestamp_ist"])
            return df

        # Format A (Monthly 5-minute SCADA on Sheet1)
        if "Sheet1" in sheet_names:
            sheet = wb["Sheet1"]
            records = []
            for i, r in enumerate(sheet.iter_rows(values_only=True)):
                if i < 2:
                    continue
                ts = r[0]
                if ts is None or not isinstance(ts, (dt.datetime, str)):
                    continue
                try:
                    thm = float(r[1]) if r[1] is not None else np.nan
                    hyd = float(r[2]) if r[2] is not None else np.nan
                    gas = float(r[3]) if r[3] is not None else np.nan
                    npc = float(r[4]) if r[4] is not None else np.nan
                    wnd = float(r[5]) if r[5] is not None else np.nan
                    sol = float(r[6]) if r[6] is not None else np.nan
                    sol = max(sol, 0.0)
                    wnd = max(wnd, 0.0)
                    tot = thm + hyd + gas + npc + wnd + sol
                    records.append(
                        {
                            "timestamp": pd.to_datetime(ts),
                            "thermal_mw": thm,
                            "hydro_mw": hyd,
                            "gas_mw": gas,
                            "nuclear_mw": npc,
                            "wind_mw": wnd,
                            "solar_mw": sol,
                            "total_demand_mw": tot,
                        }
                    )
                except (ValueError, TypeError):
                    continue

            if not records:
                return pd.DataFrame()

            df = pd.DataFrame(records)
            df = df.set_index("timestamp").resample("1h").mean().reset_index()
            df["timestamp_ist"] = df["timestamp"].dt.strftime("%Y-%m-%dT%H:00")
            df = df.drop(columns=["timestamp"])
            return df

        return pd.DataFrame()
    finally:
        wb.close()


def ingest_mendeley_historical(max_files: int | None = None) -> int:
    """Download and ingest available months from Mendeley and load into raw_hourly_demand."""
    init_db()
    create_raw_hourly_table()
    engine = get_engine()

    with engine.connect() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM raw_hourly_demand")).scalar() or 0
        manifest_exists = conn.execute(
            text("SELECT COUNT(*) FROM sqlite_master WHERE name='ingestion_files'")
        ).scalar()
    if count > 0 and not manifest_exists:
        log.info(
            "raw_hourly_demand already contains %d rows; skipping Mendeley static archive re-download.", count
        )
        return 0

    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS ingestion_files (filename TEXT PRIMARY KEY, rows_loaded INTEGER NOT NULL, completed_at TEXT NOT NULL)"
            )
        )
    files = get_mendeley_file_list()
    # Prioritize 2024-2025 multi-month report and monthly 5-minute files
    # To keep CI runtime fast and manageable under GitHub timeouts, process files under 20MB
    # plus the massive 2024-2025 report which adds 12,984 hours in seconds
    files_to_process = [f for f in files if f.get("size", 0) < 20_000_000 or "2024" in f.get("filename", "")]
    files_to_process = sorted(files_to_process, key=lambda f: str(f.get("filename")))

    if max_files is not None:
        files_to_process = files_to_process[:max_files]

    now_iso = dt.datetime.now(dt.timezone.utc).isoformat()
    total_rows = 0
    failures = []
    completed = 0
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    for f_meta in files_to_process:
        fname = f_meta.get("filename", "")
        with engine.connect() as conn:
            if conn.execute(
                text("SELECT 1 FROM ingestion_files WHERE filename=:name"), {"name": fname}
            ).first():
                completed += 1
                continue
        dl_url = f_meta.get("content_details", {}).get("download_url")
        if not dl_url:
            failures.append(fname)
            continue

        local_path = RAW_DIR / Path(fname).name
        log.info("Processing Mendeley file: %s ...", fname)
        try:
            if not local_path.exists():
                r = requests.get(dl_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=120)
                if r.status_code == 200:
                    temporary = local_path.with_suffix(local_path.suffix + ".part")
                    temporary.write_bytes(r.content)
                    temporary.replace(local_path)
                else:
                    r.raise_for_status()

            df = parse_mendeley_month_excel(local_path)
            if df.empty:
                raise ValueError(f"No records extracted from {fname}")

            insert_records = []
            for _, row in df.iterrows():
                insert_records.append(
                    {
                        "timestamp_ist": row["timestamp_ist"],
                        "thermal_mw": row["thermal_mw"] if pd.notna(row["thermal_mw"]) else None,
                        "hydro_mw": row["hydro_mw"] if pd.notna(row["hydro_mw"]) else None,
                        "gas_mw": row["gas_mw"] if pd.notna(row["gas_mw"]) else None,
                        "nuclear_mw": row["nuclear_mw"] if pd.notna(row["nuclear_mw"]) else None,
                        "wind_mw": row["wind_mw"] if pd.notna(row["wind_mw"]) else None,
                        "solar_mw": row["solar_mw"] if pd.notna(row["solar_mw"]) else None,
                        "total_demand_mw": row["total_demand_mw"]
                        if pd.notna(row["total_demand_mw"])
                        else np.nan,
                        "ingested_at": now_iso,
                    }
                )

            with engine.connect() as conn:
                conn.execute(
                    text("""
                    INSERT INTO raw_hourly_demand (
                        timestamp_ist, thermal_mw, hydro_mw, gas_mw, nuclear_mw,
                        wind_mw, solar_mw, total_demand_mw, source, ingested_at
                    ) VALUES (
                        :timestamp_ist, :thermal_mw, :hydro_mw, :gas_mw, :nuclear_mw,
                        :wind_mw, :solar_mw, :total_demand_mw, 'mendeley', :ingested_at
                    )
                    ON CONFLICT(timestamp_ist) DO UPDATE SET
                        thermal_mw=COALESCE(excluded.thermal_mw, raw_hourly_demand.thermal_mw),
                        hydro_mw=COALESCE(excluded.hydro_mw, raw_hourly_demand.hydro_mw),
                        gas_mw=COALESCE(excluded.gas_mw, raw_hourly_demand.gas_mw),
                        nuclear_mw=COALESCE(excluded.nuclear_mw, raw_hourly_demand.nuclear_mw),
                        wind_mw=excluded.wind_mw,
                        solar_mw=excluded.solar_mw,
                        total_demand_mw=excluded.total_demand_mw,
                        ingested_at=excluded.ingested_at;
                """),
                    insert_records,
                )
                conn.execute(
                    text("INSERT INTO ingestion_files VALUES (:name,:rows,:at)"),
                    {"name": fname, "rows": len(df), "at": now_iso},
                )
                conn.commit()
            total_rows += len(df)
            log.info("Loaded %d hourly records from %s", len(df), fname)
        except Exception as e:
            failures.append(fname)
            log.error("Failed to process %s: %s", fname, e)

    if failures:
        raise RuntimeError(f"Mendeley files failed; retry resumes completed files: {failures}")
    if total_rows == 0 and completed == 0:
        raise RuntimeError("Mendeley ingest produced no hourly records")
    log.info("Mendeley historical ingest complete: %d total hourly rows processed", total_rows)
    return total_rows


if __name__ == "__main__":
    ingest_mendeley_historical()
