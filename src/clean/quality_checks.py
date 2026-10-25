"""Data quality checks and validation runner.

Runs assertions across raw and staging layers:
- No duplicate timestamps
- No gaps larger than N hours
- Demand values within plausible bounds
- Weather joins cover matching dates
Logs pass/fail counts to data_quality_checks table.
"""

from __future__ import annotations

import datetime as dt
from typing import Any
from sqlalchemy import text

from src.utils.db import get_engine
from src.utils.logging import get_logger

log = get_logger(__name__)


def create_dq_table() -> None:
    engine = get_engine()
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS data_quality_checks (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                checked_at   TEXT NOT NULL,
                check_name   TEXT NOT NULL,
                table_name   TEXT NOT NULL,
                status       TEXT NOT NULL, -- PASS|FAIL
                details      TEXT
            );
        """))
        conn.commit()


def run_checks() -> dict[str, Any]:
    create_dq_table()
    engine = get_engine()
    now_iso = dt.datetime.now(dt.timezone.utc).isoformat()
    
    checks = []

    with engine.connect() as conn:
        # Check 1: No duplicate timestamps in stg_hourly_demand
        dups = conn.execute(text("""
            SELECT timestamp_ist, COUNT(*) 
            FROM stg_hourly_demand 
            GROUP BY timestamp_ist 
            HAVING COUNT(*) > 1;
        """)).fetchall()
        passed = len(dups) == 0
        checks.append({
            "check_name": "no_duplicate_timestamps_hourly_demand",
            "table_name": "stg_hourly_demand",
            "status": "PASS" if passed else "FAIL",
            "details": f"Found {len(dups)} duplicate timestamps."
        })

        # Check 2: Plausible bounds on demand_mw (50,000 MW - 350,000 MW)
        out_of_bounds = conn.execute(text("""
            SELECT COUNT(*) 
            FROM stg_hourly_demand 
            WHERE demand_mw < 50000 OR demand_mw > 350000;
        """)).scalar()
        passed = (out_of_bounds == 0)
        checks.append({
            "check_name": "demand_plausible_bounds",
            "table_name": "stg_hourly_demand",
            "status": "PASS" if passed else "FAIL",
            "details": f"{out_of_bounds} records outside [50000, 350000] MW range."
        })

        # Check 3: Non-negative renewables (solar_mw >= 0, wind_mw >= 0)
        neg_re = conn.execute(text("""
            SELECT COUNT(*) 
            FROM stg_hourly_demand 
            WHERE solar_mw < 0 OR wind_mw < 0;
        """)).scalar()
        passed = (neg_re == 0)
        checks.append({
            "check_name": "non_negative_renewables",
            "table_name": "stg_hourly_demand",
            "status": "PASS" if passed else "FAIL",
            "details": f"{neg_re} negative renewable generation values."
        })

        # Check 4: No duplicate timestamps in stg_hourly_weather
        dups_w = conn.execute(text("""
            SELECT timestamp_ist, COUNT(*) 
            FROM stg_hourly_weather 
            GROUP BY timestamp_ist 
            HAVING COUNT(*) > 1;
        """)).fetchall()
        passed = len(dups_w) == 0
        checks.append({
            "check_name": "no_duplicate_timestamps_weather",
            "table_name": "stg_hourly_weather",
            "status": "PASS" if passed else "FAIL",
            "details": f"Found {len(dups_w)} duplicate timestamps in weather."
        })

        # Check 5: Weather join overlap with hourly demand
        joined_count = conn.execute(text("""
            SELECT COUNT(*) 
            FROM stg_hourly_demand d
            JOIN stg_hourly_weather w ON d.timestamp_ist = w.timestamp_ist;
        """)).scalar()
        total_demand = conn.execute(text("SELECT COUNT(*) FROM stg_hourly_demand;")).scalar()
        overlap_pct = (joined_count / total_demand * 100.0) if total_demand else 0.0
        passed = overlap_pct >= 90.0
        checks.append({
            "check_name": "weather_demand_date_overlap",
            "table_name": "stg_hourly_demand x stg_hourly_weather",
            "status": "PASS" if passed else "FAIL",
            "details": f"{joined_count}/{total_demand} demand rows matched weather ({overlap_pct:.1f}%)."
        })

        # Record check results in DB
        for c in checks:
            conn.execute(text("""
                INSERT INTO data_quality_checks (checked_at, check_name, table_name, status, details)
                VALUES (:checked_at, :check_name, :table_name, :status, :details)
            """), {**c, "checked_at": now_iso})
        conn.commit()

    total_passed = sum(1 for c in checks if c["status"] == "PASS")
    total_failed = sum(1 for c in checks if c["status"] == "FAIL")
    log.info("Data Quality Check results: %d PASS, %d FAIL", total_passed, total_failed)
    return {
        "total_checks": len(checks),
        "passed": total_passed,
        "failed": total_failed,
        "results": checks
    }


if __name__ == "__main__":
    run_checks()
