-- Staging clean hourly demand table
-- Standardize, clean, and validate 1-hour interval India grid demand and generation data.
-- Implements:
-- 1. Multi-hour dropout detection (dips of 1 to 4 hours that rebound).
-- 2. Stuck-sensor detection for solar, wind, and demand (runs >= 3h).
-- 3. Night solar glitch detection (> 500 MW between 20:00 and 05:00 IST).
-- 4. Unphysical wind spike isolation (> 35,000 MW, e.g. 2022-08-11).
-- 5. Hour-of-day rolling median filter and unfreeze transition protection.

DROP TABLE IF EXISTS stg_hourly_demand;

CREATE TABLE stg_hourly_demand (
    timestamp_ist         TEXT PRIMARY KEY,
    date_ist              TEXT NOT NULL,
    hour_ist              INTEGER NOT NULL,
    thermal_mw            REAL,
    hydro_mw              REAL,
    gas_mw                REAL,
    nuclear_mw            REAL,
    wind_mw               REAL,
    solar_mw              REAL,
    demand_mw             REAL,
    net_load_mw           REAL,
    is_dropout            INTEGER NOT NULL DEFAULT 0,
    is_multi_hour_dip     INTEGER NOT NULL DEFAULT 0,
    is_stuck_solar        INTEGER NOT NULL DEFAULT 0,
    is_night_solar_glitch INTEGER NOT NULL DEFAULT 0,
    is_stuck_wind         INTEGER NOT NULL DEFAULT 0,
    is_wind_spike         INTEGER NOT NULL DEFAULT 0,
    is_stuck_demand       INTEGER NOT NULL DEFAULT 0,
    source                TEXT
);

CREATE INDEX IF NOT EXISTS idx_stg_hourly_ts ON stg_hourly_demand(timestamp_ist);
CREATE INDEX IF NOT EXISTS idx_stg_hourly_date ON stg_hourly_demand(date_ist);
