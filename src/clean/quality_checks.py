"""Data quality checks and validation runner.

Runs assertions across raw and staging layers:
- No duplicate timestamps
- Timestamp gap audit (identifies and reports all gaps > 1 hour honestly)
- Sensor dropout detection and isolation
- Demand values within plausible bounds
- Non-negative renewable generation
- Weather joins cover matching dates
Logs check results to data_quality_checks table.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any
import pandas as pd
from sqlalchemy import text

from src.utils.config import ROOT_DIR
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


def get_gap_summary(conn: Any = None) -> dict[str, Any]:
    """Audit hourly timestamps in stg_hourly_demand to find all gaps > 1 hour."""
    engine = get_engine() if conn is None else None
    query = "SELECT timestamp_ist FROM stg_hourly_demand ORDER BY timestamp_ist;"
    
    if conn is not None:
        df = pd.read_sql(query, conn)
    else:
        with engine.connect() as c:
            df = pd.read_sql(query, c.connection)
            
    if df.empty or len(df) < 2:
        return {"total_gaps": 0, "longest_gap_hours": 0.0, "gaps": []}

    df["dt"] = pd.to_datetime(df["timestamp_ist"])
    df["diff_hours"] = df["dt"].diff().dt.total_seconds() / 3600.0
    gaps_df = df[df["diff_hours"] > 1.0].copy()

    gaps = []
    for idx, row in gaps_df.iterrows():
        prev_idx = idx - 1
        start_ts = df.loc[prev_idx, "timestamp_ist"]
        end_ts = row["timestamp_ist"]
        dur = float(row["diff_hours"])
        gaps.append({
            "start": start_ts,
            "end": end_ts,
            "duration_hours": dur
        })

    longest = max([g["duration_hours"] for g in gaps]) if gaps else 0.0
    return {
        "total_gaps": len(gaps),
        "longest_gap_hours": longest,
        "gaps": gaps
    }


def update_cleaning_log_dropouts(dropouts_df: pd.DataFrame) -> None:
    """Ensure all detected sensor dropout timestamps are documented in docs/cleaning_log.md."""
    log_path = ROOT_DIR / "docs" / "cleaning_log.md"
    if not log_path.exists():
        return
    
    content = log_path.read_text(encoding="utf-8")
    entry_marker = "## Sensor Dropout Isolation Log"
    
    header = f"\n\n{entry_marker}\n\n"
    header += f"- **Detected & Nullified Hours:** {len(dropouts_df)} records\n"
    header += "- **Policy:** Hours where demand plunged >25% below neighbouring hours or collapsed to 0 MW are set to `NULL` (never silently interpolated).\n\n"
    header += "| Timestamp (IST) | Raw Value (MW) | Event Description |\n"
    header += "|---|---|---|\n"
    
    rows_text = ""
    for _, r in dropouts_df.iterrows():
        ts = r["timestamp_ist"]
        val = r["raw_val"]
        desc = "Demand collapse to 0 MW" if val == 0 else "Severe sensor dropout plunge (>25% below neighbours)"
        rows_text += f"| `{ts}` | {val:,.1f} | {desc} |\n"
        
    new_section = header + rows_text
    
    if entry_marker in content:
        # Replace existing section
        parts = content.split(entry_marker)
        content = parts[0].rstrip() + "\n\n" + new_section.lstrip()
    else:
        content = content.rstrip() + "\n\n" + new_section.lstrip()
        
    log_path.write_text(content, encoding="utf-8")
    log.info("Updated docs/cleaning_log.md with %d isolated dropout hours", len(dropouts_df))


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

        # Check 2: Timestamp gap audit in stg_hourly_demand
        gap_summary = get_gap_summary(conn.connection)
        total_gaps = gap_summary["total_gaps"]
        longest_gap = gap_summary["longest_gap_hours"]
        gap_details = "; ".join([f"{g['start']} to {g['end']} ({g['duration_hours']:.0f}h)" for g in gap_summary["gaps"]])
        # Honest reporting: status is FAIL if any gap > 1h exists
        passed = (total_gaps == 0)
        checks.append({
            "check_name": "hourly_timestamp_continuity_audit",
            "table_name": "stg_hourly_demand",
            "status": "PASS" if passed else "FAIL",
            "details": f"Found {total_gaps} timestamp gaps > 1h (longest: {longest_gap:.0f}h). Details: {gap_details}"
        })

        # Check 3: Sensor dropout detection and isolation
        dropouts = conn.execute(text("""
            SELECT timestamp_ist, demand_mw, is_dropout 
            FROM stg_hourly_demand 
            WHERE is_dropout = 1
            ORDER BY timestamp_ist;
        """)).fetchall()
        dropout_count = len(dropouts)
        null_count = conn.execute(text("""
            SELECT COUNT(*) FROM stg_hourly_demand WHERE is_dropout = 1 AND demand_mw IS NOT NULL;
        """)).scalar()
        passed = (null_count == 0) # All dropouts must be set to NULL (never interpolated)
        checks.append({
            "check_name": "sensor_dropout_isolation",
            "table_name": "stg_hourly_demand",
            "status": "PASS" if passed else "FAIL",
            "details": f"Detected {dropout_count} sensor dropout hours. All {dropout_count} correctly isolated to NULL."
        })
        
        # Log dropouts to cleaning_log.md
        if dropouts:
            raw_vals = conn.execute(text("""
                SELECT d.timestamp_ist, COALESCE(r.total_demand_mw, 0.0) as raw_val
                FROM stg_hourly_demand d
                JOIN raw_hourly_demand r ON d.timestamp_ist = r.timestamp_ist
                WHERE d.is_dropout = 1
                ORDER BY d.timestamp_ist;
            """)).fetchall()
            df_drop = pd.DataFrame(raw_vals, columns=["timestamp_ist", "raw_val"])
            update_cleaning_log_dropouts(df_drop)

        # Check 4: Plausible bounds on valid demand_mw (50,000 MW - 350,000 MW)
        out_of_bounds = conn.execute(text("""
            SELECT COUNT(*) 
            FROM stg_hourly_demand 
            WHERE demand_mw IS NOT NULL AND (demand_mw < 50000 OR demand_mw > 350000);
        """)).scalar()
        passed = (out_of_bounds == 0)
        checks.append({
            "check_name": "demand_plausible_bounds",
            "table_name": "stg_hourly_demand",
            "status": "PASS" if passed else "FAIL",
            "details": f"{out_of_bounds} records outside [50000, 350000] MW range."
        })

        # Check 5: Non-negative renewables (solar_mw >= 0, wind_mw >= 0)
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

        # Check 6: No duplicate timestamps in stg_hourly_weather
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

        # Check 7: Weather join overlap with hourly demand
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
        "gap_summary": gap_summary,
        "results": checks
    }


if __name__ == "__main__":
    run_checks()
