"""Robust hourly demand, renewable, and sensor glitch cleaning module.

Implements:
1. Deduplication and unit standardization.
2. Stuck-sensor detector (runs >= 3 consecutive hours of identical non-zero values for demand, solar, wind).
3. Night solar glitch detector (> 500 MW between 20:00 and 05:00 IST).
4. Unphysical wind spike detector (> 35,000 MW, e.g. 2022-08-11).
5. Multi-hour dropout and glitch isolation:
   - Physical plausible bounds [50,000, 350,000] MW.
   - Multi-hour dropout detection (dips of 1, 2, 3, or 4 hours dropping significantly below surrounding baseline and rebounding).
   - Single-hour dip (10-25%) and sharp recovery.
   - Hour-of-day rolling median outlier filter (+/- 7 day window).
   - Unfreeze transition protection: nullifying the first hour immediately following a stuck run or dropout to eliminate artificial unfreeze jump ramps.
6. Net load calculation: demand_mw - (solar_mw + wind_mw), strictly NULL if any component is invalid.
"""

from __future__ import annotations

import time
from typing import Any
import numpy as np
import pandas as pd
from sqlalchemy import text

from src.utils.db import get_engine
from src.utils.logging import get_logger

log = get_logger(__name__)


def clean_hourly_demand() -> dict[str, Any]:
    """Clean raw hourly demand data and populate stg_hourly_demand."""
    t0 = time.time()
    engine = get_engine()

    query = """
    SELECT timestamp_ist, thermal_mw, hydro_mw, gas_mw, nuclear_mw, wind_mw, solar_mw, total_demand_mw, source
    FROM raw_hourly_demand
    WHERE timestamp_ist IS NOT NULL
    GROUP BY timestamp_ist
    ORDER BY timestamp_ist;
    """
    with engine.connect() as conn:
        df = pd.read_sql(query, conn.connection)

    if df.empty:
        log.warning("raw_hourly_demand is empty, skipping cleaning.")
        return {}

    dt_series = pd.to_datetime(df["timestamp_ist"])
    df["date_ist"] = df["timestamp_ist"].str[:10]
    df["hour_ist"] = df["timestamp_ist"].str[11:13].astype(int)

    # Component rounding
    for col in ["thermal_mw", "hydro_mw", "gas_mw", "nuclear_mw"]:
        df[col] = df[col].clip(lower=0.0).round(2)

    df["solar_mw"] = df["solar_mw"].clip(lower=0.0).round(2)
    df["wind_mw"] = df["wind_mw"].clip(lower=0.0).round(2)

    # Demand calculation: sum generation if components present, otherwise total_demand_mw
    use_components = (df["thermal_mw"].notna()) & (df["thermal_mw"] > 10000)
    summed_gen = (
        df["thermal_mw"].fillna(0)
        + df["hydro_mw"].fillna(0)
        + df["gas_mw"].fillna(0)
        + df["nuclear_mw"].fillna(0)
        + df["wind_mw"].fillna(0)
        + df["solar_mw"].fillna(0)
    ).round(2)

    df["raw_calc_demand_mw"] = np.where(use_components, summed_gen, df["total_demand_mw"].round(2))

    # 1. Stuck value detection (>= 3 consecutive identical non-zero values)
    for col in ["raw_calc_demand_mw", "solar_mw", "wind_mw"]:
        s = df[col]
        grp = (s != s.shift()).cumsum()
        sizes = df.groupby(grp)[col].transform("size")
        is_stuck = (sizes >= 3) & (s > 0) & s.notna()
        df[f"is_stuck_{col}"] = is_stuck

    # 2. Night solar detection (> 500 MW between 20:00 and 05:00 IST)
    night_hours = [20, 21, 22, 23, 0, 1, 2, 3, 4, 5]
    df["is_night_solar"] = df["hour_ist"].isin(night_hours) & (df["solar_mw"] > 500)

    # 3. Wind unphysical spike (> 35,000 MW, e.g. 2022-08-11)
    df["is_wind_spike"] = df["wind_mw"] > 35000

    # Set corrupt solar and wind to NaN
    df["clean_solar_mw"] = np.where(df["is_stuck_solar_mw"] | df["is_night_solar"], np.nan, df["solar_mw"])
    df["clean_wind_mw"] = np.where(df["is_stuck_wind_mw"] | df["is_wind_spike"], np.nan, df["wind_mw"])

    # 4. Physical limits
    bound_fail = df["raw_calc_demand_mw"].isna() | (df["raw_calc_demand_mw"] < 50000) | (df["raw_calc_demand_mw"] > 350000)
    stuck_demand = df["is_stuck_raw_calc_demand_mw"]

    # 5. Multi-hour dropout detection (dips of L = 1, 2, 3, or 4 hours that drop significantly and rebound)
    d_vals = df["raw_calc_demand_mw"].values
    n = len(d_vals)
    multi_hour_dip = np.zeros(n, dtype=bool)

    for L in [1, 2, 3, 4]:
        for i in range(1, n - L):
            if (dt_series.iloc[i + L] - dt_series.iloc[i - 1]) == pd.Timedelta(hours=L + 1):
                before = d_vals[i - 1]
                after = d_vals[i + L]
                if before > 50000 and after > 50000:
                    win = d_vals[i:i + L]
                    # Condition 1: All values in window are < 0.90 of min(before, after)
                    cond1 = np.all(win < 0.90 * min(before, after))
                    # Condition 2: Deep plunge > 20 GW from before and rebounds > 15 GW to after
                    cond2 = (before - np.min(win) > 20000) and (after - np.min(win) > 15000)
                    # Condition 3: Significant drop > 12% and sharp recovery > 8%
                    cond3 = np.all(win < 0.88 * before) and (after > 1.08 * np.min(win))
                    if cond1 or cond2 or cond3:
                        multi_hour_dip[i:i + L] = True

    # 6. Hour-of-day rolling median filter (+/- 7 day window = 15 days)
    d_for_med = df["raw_calc_demand_mw"].copy()
    d_for_med[bound_fail | stuck_demand | multi_hour_dip] = np.nan
    df["same_hour_roll_med"] = df.groupby("hour_ist")[d_for_med.name].transform(
        lambda s: s.rolling(15, center=True, min_periods=5).median()
    )
    ratio = df["raw_calc_demand_mw"] / df["same_hour_roll_med"]
    hour_outlier = (ratio < 0.87) | (ratio > 1.20)

    # 7. Unfreeze transition protection:
    # Nullify the first hour immediately following a stuck run or dropout dip
    unfreeze_trans = (
        pd.Series(stuck_demand).shift(1, fill_value=False) |
        pd.Series(multi_hour_dip).shift(1, fill_value=False) |
        pd.Series(bound_fail).shift(1, fill_value=False)
    )

    is_glitch = bound_fail | stuck_demand | multi_hour_dip | hour_outlier | unfreeze_trans

    df["is_dropout"] = is_glitch.astype(int)
    df["is_multi_hour_dip"] = multi_hour_dip.astype(int)
    df["is_stuck_solar"] = df["is_stuck_solar_mw"].astype(int)
    df["is_night_solar_glitch"] = df["is_night_solar"].astype(int)
    df["is_stuck_wind"] = df["is_stuck_wind_mw"].astype(int)
    df["is_wind_spike"] = df["is_wind_spike"].astype(int)
    df["is_stuck_demand"] = df["is_stuck_raw_calc_demand_mw"].astype(int)

    df["demand_mw"] = np.where(is_glitch, np.nan, df["raw_calc_demand_mw"])
    df["solar_mw"] = df["clean_solar_mw"]
    df["wind_mw"] = df["clean_wind_mw"]

    nl_invalid = is_glitch | df["clean_solar_mw"].isna() | df["clean_wind_mw"].isna()
    df["net_load_mw"] = np.where(nl_invalid, np.nan, (df["demand_mw"] - (df["solar_mw"] + df["wind_mw"])).round(2))

    output_cols = [
        "timestamp_ist", "date_ist", "hour_ist",
        "thermal_mw", "hydro_mw", "gas_mw", "nuclear_mw",
        "wind_mw", "solar_mw", "demand_mw", "net_load_mw",
        "is_dropout", "is_multi_hour_dip", "is_stuck_solar", "is_night_solar_glitch",
        "is_stuck_wind", "is_wind_spike", "is_stuck_demand", "source"
    ]
    out_df = df[output_cols].copy()

    with engine.connect() as conn:
        conn.execute(text("DROP TABLE IF EXISTS stg_hourly_demand;"))
        conn.commit()
        out_df.to_sql("stg_hourly_demand", conn.connection, if_exists="replace", index=False)
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_stg_hourly_ts ON stg_hourly_demand(timestamp_ist);"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_stg_hourly_date ON stg_hourly_demand(date_ist);"))
        conn.commit()

    dur = round(time.time() - t0, 2)
    stats = {
        "total_rows": len(out_df),
        "valid_demand_rows": int(out_df["demand_mw"].notna().sum()),
        "valid_net_load_rows": int(out_df["net_load_mw"].notna().sum()),
        "demand_glitch_hours": int(out_df["is_dropout"].sum()),
        "multi_hour_dip_hours": int(out_df["is_multi_hour_dip"].sum()),
        "stuck_solar_hours": int(out_df["is_stuck_solar"].sum()),
        "night_solar_glitch_hours": int(out_df["is_night_solar_glitch"].sum()),
        "stuck_wind_hours": int(out_df["is_stuck_wind"].sum()),
        "wind_spike_hours": int(out_df["is_wind_spike"].sum()),
        "stuck_demand_hours": int(out_df["is_stuck_demand"].sum()),
        "duration_s": dur
    }
    log.info("stg_hourly_demand cleaned: %d rows in %ss (%d glitches, %d multi-hour dips, %d stuck solar, %d night solar, %d stuck wind, %d wind spikes)",
             len(out_df), dur, stats["demand_glitch_hours"], stats["multi_hour_dip_hours"], stats["stuck_solar_hours"], stats["night_solar_glitch_hours"], stats["stuck_wind_hours"], stats["wind_spike_hours"])
    return stats


if __name__ == "__main__":
    clean_hourly_demand()
