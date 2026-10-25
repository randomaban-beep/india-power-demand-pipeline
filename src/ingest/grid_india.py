"""Grid-India Daily PSP Report Ingest Module.

Fetches latest daily PSP reports from Grid-India webapi and webcdn, parses Excel/PDF,
and loads into raw_daily_psp and raw_state_psp tables in energy.db.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any
import requests
import xlrd
from sqlalchemy import text

from src.utils.config import DB_PATH, RAW_DIR
from src.utils.db import get_engine, init_db
from src.utils.logging import get_logger

log = get_logger(__name__)

API_URL = "https://webapi.grid-india.in/api/v1/file"
CDN_BASE = "https://webcdn.grid-india.in"


def create_raw_tables() -> None:
    """Create raw tables for Grid-India daily PSP data if not exists."""
    engine = get_engine()
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS raw_daily_psp (
                report_date       TEXT PRIMARY KEY,
                evening_peak_mw   REAL,
                evening_peak_shortage_mw REAL,
                energy_met_mu     REAL,
                hydro_gen_mu      REAL,
                wind_gen_mu       REAL,
                solar_gen_mu      REAL,
                energy_shortage_mu REAL,
                max_demand_met_mw REAL,
                max_demand_time   TEXT,
                coal_gen_mu       REAL,
                lignite_gen_mu    REAL,
                nuclear_gen_mu    REAL,
                gas_gen_mu        REAL,
                res_gen_mu        REAL,
                total_gen_mu      REAL,
                ingested_at       TEXT NOT NULL
            );
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS raw_state_psp (
                report_date       TEXT,
                region            TEXT,
                state             TEXT,
                max_demand_mw     REAL,
                shortage_mw       REAL,
                energy_met_mu     REAL,
                energy_shortage_mu REAL,
                ingested_at       TEXT NOT NULL,
                PRIMARY KEY (report_date, region, state)
            );
        """))
        conn.commit()


def fetch_file_catalog(limit: int = 30) -> list[dict[str, Any]]:
    """Query Grid-India API for recent daily PSP report metadata."""
    headers = {"User-Agent": "Mozilla/5.0"}
    payload = {"_source": "GRDW", "_type": "DAILY_PSP_REPORT"}
    try:
        resp = requests.post(API_URL, json=payload, headers=headers, timeout=20)
        resp.raise_for_status()
        data = resp.json().get("retData", [])
        return data[:limit]
    except Exception as e:
        log.error("Failed to fetch Grid-India file catalog: %s", e)
        return []


def parse_mop_e_sheet(xls_path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Extract all-India daily metrics and state breakdown from MOP_E sheet."""
    wb = xlrd.open_workbook(str(xls_path))
    sheet = wb.sheet_by_name("MOP_E")
    
    # 1. Extract report date
    report_date_str = ""
    for r in range(min(5, sheet.nrows)):
        for c in range(sheet.ncols):
            val = str(sheet.cell_value(r, c)).strip()
            if "Date of Reporting:" in val or val.lower() == "date of reporting:":
                # Check next cell
                if c + 1 < sheet.ncols:
                    report_date_str = str(sheet.cell_value(r, c + 1)).strip()
                if not report_date_str and c + 2 < sheet.ncols:
                    report_date_str = str(sheet.cell_value(r, c + 2)).strip()
                break
        if report_date_str:
            break

    # Parse date into ISO YYYY-MM-DD
    # If reporting date is 24-Oct-2026, report covers previous day (23-Oct-2026)
    report_iso_date = ""
    try:
        # Expected formats: '24-Oct-2026', '24-10-2026', etc.
        dt_val = None
        for fmt in ["%d-%b-%Y", "%d-%m-%Y", "%Y-%m-%d"]:
            try:
                dt_val = dt.datetime.strptime(report_date_str, fmt).date()
                break
            except ValueError:
                pass
        if dt_val:
            # PSP report is "Report for previous day"
            report_iso_date = (dt_val - dt.timedelta(days=1)).isoformat()
    except Exception:
        pass

    if not report_iso_date:
        # Fallback to file name date if available
        # e.g. 23.10.26_NLDC_PSP
        fname = xls_path.stem
        parts = fname.split("_")[0].split(".")
        if len(parts) == 3:
            day, month, yr = int(parts[0]), int(parts[1]), int(parts[2])
            full_yr = 2000 + yr if yr < 100 else yr
            report_iso_date = f"{full_yr:04d}-{month:02d}-{day:02d}"

    def safe_float(val: Any) -> float | None:
        try:
            if str(val).strip() in ["-", "", "None"]:
                return 0.0
            return float(val)
        except (ValueError, TypeError):
            return None

    # Section A metrics (columns: Metric, '', NR, WR, SR, ER, NER, TOTAL)
    # Total is usually col 7
    all_india: dict[str, Any] = {"report_date": report_iso_date}
    states: list[dict[str, Any]] = []

    current_region = ""
    in_states_section = False

    for r in range(sheet.nrows):
        col0 = str(sheet.cell_value(r, 0)).strip()
        
        # Section A items
        if "Demand Met (MW) during Evening Peak" in col0:
            all_india["evening_peak_mw"] = safe_float(sheet.cell_value(r, 7))
        elif "Shoratge (MW) during Evening Peak" in col0 or "Shortage (MW) during Evening Peak" in col0:
            all_india["evening_peak_shortage_mw"] = safe_float(sheet.cell_value(r, 7))
        elif col0 == "Energy Met (MU)":
            all_india["energy_met_mu"] = safe_float(sheet.cell_value(r, 7))
        elif col0 == "Hydro Gen (MU)":
            all_india["hydro_gen_mu"] = safe_float(sheet.cell_value(r, 7))
        elif col0 == "Wind Gen (MU)":
            all_india["wind_gen_mu"] = safe_float(sheet.cell_value(r, 7))
        elif "Solar Gen (MU)" in col0:
            all_india["solar_gen_mu"] = safe_float(sheet.cell_value(r, 7))
        elif col0 == "Energy Shortage (MU)":
            all_india["energy_shortage_mu"] = safe_float(sheet.cell_value(r, 7))
        elif "Maximum Demand Met During the Day" in col0:
            all_india["max_demand_met_mw"] = safe_float(sheet.cell_value(r, 7))
        elif "Time of Maximum Demand Met" in col0:
            all_india["max_demand_time"] = str(sheet.cell_value(r, 7)).strip()

        # Section G items (Sourcewise generation)
        elif col0 == "Coal":
            all_india["coal_gen_mu"] = safe_float(sheet.cell_value(r, 7))
        elif col0 == "Lignite":
            all_india["lignite_gen_mu"] = safe_float(sheet.cell_value(r, 7))
        elif col0 == "Nuclear":
            all_india["nuclear_gen_mu"] = safe_float(sheet.cell_value(r, 7))
        elif "Gas" in col0 and "Naptha" in col0:
            all_india["gas_gen_mu"] = safe_float(sheet.cell_value(r, 7))
        elif "RES" in col0 and ("Wind" in col0 or "Solar" in col0):
            all_india["res_gen_mu"] = safe_float(sheet.cell_value(r, 7))
        elif col0 == "Total" and r > 70:
            all_india["total_gen_mu"] = safe_float(sheet.cell_value(r, 7))

        # Section C: States
        if "C. Power Supply Position in States" in col0:
            in_states_section = True
            continue
        if "D. Transnational Exchanges" in col0:
            in_states_section = False
            continue

        if in_states_section and r > 20:
            reg_val = str(sheet.cell_value(r, 0)).strip()
            if reg_val in ["NR", "WR", "SR", "ER", "NER"]:
                current_region = reg_val
            st_name = str(sheet.cell_value(r, 1)).strip()
            if st_name and st_name not in ["States", "TOTAL", ""]:
                max_d = safe_float(sheet.cell_value(r, 2))
                short_mw = safe_float(sheet.cell_value(r, 3))
                e_met = safe_float(sheet.cell_value(r, 4))
                e_short = safe_float(sheet.cell_value(r, 8)) if sheet.ncols > 8 else 0.0
                states.append({
                    "report_date": report_iso_date,
                    "region": current_region or "Unknown",
                    "state": st_name,
                    "max_demand_mw": max_d,
                    "shortage_mw": short_mw,
                    "energy_met_mu": e_met,
                    "energy_shortage_mu": e_short,
                })

    return all_india, states


def ingest_daily_psp(limit: int = 15) -> tuple[int, int]:
    """Download and ingest recent daily PSP reports."""
    init_db()
    create_raw_tables()
    engine = get_engine()
    
    catalog = fetch_file_catalog(limit=limit * 2)
    xls_items = [item for item in catalog if str(item.get("MimeType")).endswith("excel") or str(item.get("FilePath")).endswith(".xls")]
    
    total_daily_rows = 0
    total_state_rows = 0
    now_iso = dt.datetime.now(dt.timezone.utc).isoformat()
    
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    
    for item in xls_items[:limit]:
        rel_path = item.get("FilePath", "")
        if not rel_path:
            continue
        
        file_url = f"{CDN_BASE}/{rel_path}"
        local_path = RAW_DIR / Path(rel_path).name
        
        try:
            if not local_path.exists():
                r = requests.get(file_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
                if r.status_code == 200:
                    local_path.write_bytes(r.content)
                else:
                    continue
            
            all_india, states = parse_mop_e_sheet(local_path)
            rep_date = all_india.get("report_date")
            if not rep_date:
                continue

            with engine.connect() as conn:
                conn.execute(text("""
                    INSERT INTO raw_daily_psp (
                        report_date, evening_peak_mw, evening_peak_shortage_mw, energy_met_mu,
                        hydro_gen_mu, wind_gen_mu, solar_gen_mu, energy_shortage_mu,
                        max_demand_met_mw, max_demand_time, coal_gen_mu, lignite_gen_mu,
                        nuclear_gen_mu, gas_gen_mu, res_gen_mu, total_gen_mu, ingested_at
                    ) VALUES (
                        :report_date, :evening_peak_mw, :evening_peak_shortage_mw, :energy_met_mu,
                        :hydro_gen_mu, :wind_gen_mu, :solar_gen_mu, :energy_shortage_mu,
                        :max_demand_met_mw, :max_demand_time, :coal_gen_mu, :lignite_gen_mu,
                        :nuclear_gen_mu, :gas_gen_mu, :res_gen_mu, :total_gen_mu, :ingested_at
                    )
                    ON CONFLICT(report_date) DO UPDATE SET
                        evening_peak_mw=excluded.evening_peak_mw,
                        evening_peak_shortage_mw=excluded.evening_peak_shortage_mw,
                        energy_met_mu=excluded.energy_met_mu,
                        hydro_gen_mu=excluded.hydro_gen_mu,
                        wind_gen_mu=excluded.wind_gen_mu,
                        solar_gen_mu=excluded.solar_gen_mu,
                        energy_shortage_mu=excluded.energy_shortage_mu,
                        max_demand_met_mw=excluded.max_demand_met_mw,
                        max_demand_time=excluded.max_demand_time,
                        coal_gen_mu=excluded.coal_gen_mu,
                        lignite_gen_mu=excluded.lignite_gen_mu,
                        nuclear_gen_mu=excluded.nuclear_gen_mu,
                        gas_gen_mu=excluded.gas_gen_mu,
                        res_gen_mu=excluded.res_gen_mu,
                        total_gen_mu=excluded.total_gen_mu,
                        ingested_at=excluded.ingested_at;
                """), {**all_india, "ingested_at": now_iso})

                for s in states:
                    conn.execute(text("""
                        INSERT INTO raw_state_psp (
                            report_date, region, state, max_demand_mw, shortage_mw,
                            energy_met_mu, energy_shortage_mu, ingested_at
                        ) VALUES (
                            :report_date, :region, :state, :max_demand_mw, :shortage_mw,
                            :energy_met_mu, :energy_shortage_mu, :ingested_at
                        )
                        ON CONFLICT(report_date, region, state) DO UPDATE SET
                            max_demand_mw=excluded.max_demand_mw,
                            shortage_mw=excluded.shortage_mw,
                            energy_met_mu=excluded.energy_met_mu,
                            energy_shortage_mu=excluded.energy_shortage_mu,
                            ingested_at=excluded.ingested_at;
                    """), {**s, "ingested_at": now_iso})

                conn.commit()
                total_daily_rows += 1
                total_state_rows += len(states)
        except Exception as e:
            log.warning("Could not ingest %s: %s", local_path.name, e)

    log.info("Grid-India ingest complete: %d daily rows, %d state rows inserted/updated", total_daily_rows, total_state_rows)
    return total_daily_rows, total_state_rows


if __name__ == "__main__":
    ingest_daily_psp()
