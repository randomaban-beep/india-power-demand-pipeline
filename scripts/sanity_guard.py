"""Sanity guard script run before database upload and commit in CI."""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path
from sqlalchemy import text

from src.utils.config import DATA_DIR, get_db_path
from src.utils.db import get_engine
from src.utils.logging import get_logger

log = get_logger(__name__)

MART_TABLES = [
    "mart_demand_profile_by_season",
    "mart_monthly_peak_demand",
    "mart_temp_vs_demand",
    "mart_daily_weather_demand",
    "mart_net_load_profile",
    "mart_net_load_ramps",
    "mart_anomaly_days",
]


def check_sanity() -> bool:
    engine = get_engine()
    today = dt.datetime.now(dt.timezone.utc).date()
    failures: list[str] = []

    print("=========================================================================================")
    print(f"SANITY GUARD AUDIT - {today.isoformat()} (Database: {get_db_path().name})")
    print("=========================================================================================")
    print(f"{'Check Description':<38} | {'Expected':<18} | {'Actual':<20} | {'Status'}")
    print("-" * 89)

    with engine.connect() as conn:
        pre_count_file = DATA_DIR / ".pre_ingest_psp_count"
        min_psp_count = 700
        if pre_count_file.exists():
            try:
                min_psp_count = int(pre_count_file.read_text().strip())
            except Exception:
                min_psp_count = 700

        current_psp_count = conn.execute(text("SELECT COUNT(*) FROM stg_daily_psp")).scalar() or 0
        psp_status = "PASS" if current_psp_count >= min_psp_count else "FAIL"
        if psp_status == "FAIL":
            failures.append(f"stg_daily_psp count {current_psp_count} is lower than pre-ingest count {min_psp_count}")
        print(f"{'stg_daily_psp row count':<38} | {f'>= {min_psp_count}':<18} | {str(current_psp_count):<20} | {psp_status}")

        for mart in MART_TABLES:
            try:
                cnt = conn.execute(text(f"SELECT COUNT(*) FROM {mart}")).scalar() or 0
                status = "PASS" if cnt > 0 else "FAIL"
                if status == "FAIL":
                    failures.append(f"Mart table {mart} is empty")
                print(f"{f'Mart table: {mart}':<38} | {'> 0':<18} | {str(cnt):<20} | {status}")
            except Exception as e:
                failures.append(f"Failed querying mart {mart}: {e}")
                print(f"{f'Mart table: {mart}':<38} | {'> 0':<18} | {'ERROR':<20} | FAIL")

        mwd_count = conn.execute(text("SELECT COUNT(*) FROM mart_daily_weather_demand")).scalar() or 0
        mwd_status = "PASS" if mwd_count >= 500 else "FAIL"
        if mwd_status == "FAIL":
            failures.append(f"mart_daily_weather_demand count {mwd_count} is under 500 rows")
        print(f"{'mart_daily_weather_demand rows':<38} | {'>= 500':<18} | {str(mwd_count):<20} | {mwd_status}")

        weather_res = conn.execute(text("SELECT MAX(timestamp_ist) FROM raw_weather")).scalar()
        if not weather_res:
            weather_res = conn.execute(text("SELECT MAX(timestamp_ist) FROM stg_hourly_weather")).scalar()

        if weather_res:
            newest_weather_date = dt.date.fromisoformat(weather_res[:10])
            weather_age_days = (today - newest_weather_date).days
            weather_status = "PASS" if weather_age_days <= 3 else "FAIL"
            if weather_status == "FAIL":
                failures.append(f"Newest weather ({weather_res}) is {weather_age_days} days old (> 3 days)")
            print(f"{'Newest weather timestamp age':<38} | {'<= 3 days old':<18} | {f'{weather_age_days}d ({weather_res[:10]})':<20} | {weather_status}")
        else:
            failures.append("No weather records found in raw_weather or stg_hourly_weather")
            print(f"{'Newest weather timestamp age':<38} | {'<= 3 days old':<18} | {'None':<20} | FAIL")

        psp_res = conn.execute(text("SELECT MAX(report_date) FROM stg_daily_psp")).scalar()
        if psp_res:
            newest_psp_date = dt.date.fromisoformat(psp_res[:10])
            psp_age_days = (today - newest_psp_date).days
            psp_age_status = "PASS" if psp_age_days <= 7 else "FAIL"
            if psp_age_status == "FAIL":
                failures.append(f"Newest Grid-India report ({psp_res}) is {psp_age_days} days old (> 7 days)")
            print(f"{'Newest Grid-India report age':<38} | {'<= 7 days old':<18} | {f'{psp_age_days}d ({psp_res[:10]})':<20} | {psp_age_status}")
        else:
            failures.append("No Grid-India records found in stg_daily_psp")
            print(f"{'Newest Grid-India report age':<38} | {'<= 7 days old':<18} | {'None':<20} | FAIL")

    print("=" * 89)
    if failures:
        print(f"\nSANITY GUARD REJECTED: {len(failures)} assertion(s) failed:")
        for f in failures:
            print(f"  [X] {f}")
        return False

    print("\nSANITY GUARD APPROVED: All database assertions passed successfully.")
    return True


if __name__ == "__main__":
    passed = check_sanity()
    sys.exit(0 if passed else 1)
