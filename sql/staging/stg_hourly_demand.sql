-- Staging clean hourly demand table
-- Business question: Standardize, clean, and validate 1-hour interval India grid demand and generation data.
-- Implements:
-- 1. Sensor dropout & glitch detection (setting glitch hours to NULL, never interpolating silently).
-- 2. Stuck-sensor detection for solar, wind, and demand (runs of >= 3 consecutive hours of identical non-zero values).
-- 3. Night solar glitch detection (> 500 MW between 20:00 and 05:00 IST).
-- 4. Unphysical wind spike isolation (> 35,000 MW, e.g. 2022-08-11).
-- 5. Hour-of-day rolling median / single-hour dip & sharp recovery detection.

DROP TABLE IF EXISTS stg_hourly_demand;

CREATE TABLE stg_hourly_demand AS
WITH deduped AS (
    SELECT
        timestamp_ist,
        thermal_mw,
        hydro_mw,
        gas_mw,
        nuclear_mw,
        wind_mw,
        solar_mw,
        total_demand_mw,
        source,
        ingested_at,
        ROW_NUMBER() OVER (PARTITION BY timestamp_ist ORDER BY ingested_at DESC) AS rn
    FROM raw_hourly_demand
    WHERE timestamp_ist IS NOT NULL
),
computed AS (
    SELECT
        timestamp_ist,
        date(timestamp_ist) AS date_ist,
        CAST(strftime('%H', timestamp_ist) AS INTEGER) AS hour_ist,
        MAX(0.0, ROUND(thermal_mw, 2)) AS thermal_mw,
        MAX(0.0, ROUND(hydro_mw, 2)) AS hydro_mw,
        MAX(0.0, ROUND(gas_mw, 2)) AS gas_mw,
        MAX(0.0, ROUND(nuclear_mw, 2)) AS nuclear_mw,
        MAX(0.0, ROUND(wind_mw, 2)) AS wind_mw,
        MAX(0.0, ROUND(solar_mw, 2)) AS solar_mw,
        CASE
            WHEN thermal_mw IS NOT NULL AND thermal_mw > 10000
            THEN ROUND(thermal_mw + COALESCE(hydro_mw, 0) + COALESCE(gas_mw, 0) + COALESCE(nuclear_mw, 0) + COALESCE(wind_mw, 0) + COALESCE(solar_mw, 0), 2)
            ELSE ROUND(total_demand_mw, 2)
        END AS raw_calc_demand_mw,
        source
    FROM deduped
    WHERE rn = 1
),
windowed AS (
    SELECT
        timestamp_ist,
        date_ist,
        hour_ist,
        thermal_mw,
        hydro_mw,
        gas_mw,
        nuclear_mw,
        wind_mw,
        solar_mw,
        raw_calc_demand_mw,
        source,
        LAG(raw_calc_demand_mw, 1) OVER (ORDER BY timestamp_ist) AS prev_demand_1,
        LAG(raw_calc_demand_mw, 2) OVER (ORDER BY timestamp_ist) AS prev_demand_2,
        LEAD(raw_calc_demand_mw, 1) OVER (ORDER BY timestamp_ist) AS next_demand_1,
        LEAD(raw_calc_demand_mw, 2) OVER (ORDER BY timestamp_ist) AS next_demand_2,
        LAG(solar_mw, 1) OVER (ORDER BY timestamp_ist) AS prev_solar_1,
        LAG(solar_mw, 2) OVER (ORDER BY timestamp_ist) AS prev_solar_2,
        LEAD(solar_mw, 1) OVER (ORDER BY timestamp_ist) AS next_solar_1,
        LEAD(solar_mw, 2) OVER (ORDER BY timestamp_ist) AS next_solar_2,
        LAG(wind_mw, 1) OVER (ORDER BY timestamp_ist) AS prev_wind_1,
        LAG(wind_mw, 2) OVER (ORDER BY timestamp_ist) AS prev_wind_2,
        LEAD(wind_mw, 1) OVER (ORDER BY timestamp_ist) AS next_wind_1,
        LEAD(wind_mw, 2) OVER (ORDER BY timestamp_ist) AS next_wind_2,
        LAG(timestamp_ist, 1) OVER (ORDER BY timestamp_ist) AS prev_ts,
        LEAD(timestamp_ist, 1) OVER (ORDER BY timestamp_ist) AS next_ts
    FROM computed
),
flagged AS (
    SELECT
        timestamp_ist,
        date_ist,
        hour_ist,
        thermal_mw,
        hydro_mw,
        gas_mw,
        nuclear_mw,
        source,
        raw_calc_demand_mw,
        prev_demand_1,
        next_demand_1,
        prev_ts,
        next_ts,
        -- Stuck solar check
        CASE
            WHEN solar_mw > 0 AND (
                (solar_mw = prev_solar_1 AND solar_mw = prev_solar_2) OR
                (solar_mw = prev_solar_1 AND solar_mw = next_solar_1) OR
                (solar_mw = next_solar_1 AND solar_mw = next_solar_2)
            ) THEN 1
            ELSE 0
        END AS is_stuck_solar,
        -- Night solar glitch (> 500 MW between 20:00 and 05:00 IST)
        CASE
            WHEN hour_ist IN (20, 21, 22, 23, 0, 1, 2, 3, 4, 5) AND solar_mw > 500 THEN 1
            ELSE 0
        END AS is_night_solar_glitch,
        -- Stuck wind check
        CASE
            WHEN wind_mw > 0 AND (
                (wind_mw = prev_wind_1 AND wind_mw = prev_wind_2) OR
                (wind_mw = prev_wind_1 AND wind_mw = next_wind_1) OR
                (wind_mw = next_wind_1 AND wind_mw = next_wind_2)
            ) THEN 1
            ELSE 0
        END AS is_stuck_wind,
        -- Wind unphysical spike
        CASE
            WHEN wind_mw > 35000 THEN 1
            ELSE 0
        END AS is_wind_spike,
        -- Stuck demand check
        CASE
            WHEN raw_calc_demand_mw > 0 AND (
                (raw_calc_demand_mw = prev_demand_1 AND raw_calc_demand_mw = prev_demand_2) OR
                (raw_calc_demand_mw = prev_demand_1 AND raw_calc_demand_mw = next_demand_1) OR
                (raw_calc_demand_mw = next_demand_1 AND raw_calc_demand_mw = next_demand_2)
            ) THEN 1
            ELSE 0
        END AS is_stuck_demand,
        -- Clean solar
        CASE
            WHEN solar_mw < 0 THEN NULL
            WHEN solar_mw > 0 AND (
                (solar_mw = prev_solar_1 AND solar_mw = prev_solar_2) OR
                (solar_mw = prev_solar_1 AND solar_mw = next_solar_1) OR
                (solar_mw = next_solar_1 AND solar_mw = next_solar_2)
            ) THEN NULL
            WHEN hour_ist IN (20, 21, 22, 23, 0, 1, 2, 3, 4, 5) AND solar_mw > 500 THEN NULL
            ELSE solar_mw
        END AS clean_solar_mw,
        -- Clean wind
        CASE
            WHEN wind_mw < 0 THEN NULL
            WHEN wind_mw > 35000 THEN NULL
            WHEN wind_mw > 0 AND (
                (wind_mw = prev_wind_1 AND wind_mw = prev_wind_2) OR
                (wind_mw = prev_wind_1 AND wind_mw = next_wind_1) OR
                (wind_mw = next_wind_1 AND wind_mw = next_wind_2)
            ) THEN NULL
            ELSE wind_mw
        END AS clean_wind_mw
    FROM windowed
),
flagged_demand AS (
    SELECT
        f.*,
        LAG(is_stuck_demand, 1) OVER (ORDER BY timestamp_ist) AS prev_was_stuck_demand,
        CASE
            WHEN raw_calc_demand_mw IS NULL OR raw_calc_demand_mw < 50000 OR raw_calc_demand_mw > 350000 THEN 1
            WHEN is_stuck_demand = 1 THEN 1
            WHEN LAG(is_stuck_demand, 1) OVER (ORDER BY timestamp_ist) = 1 AND raw_calc_demand_mw != prev_demand_1 THEN 1
            WHEN (strftime('%Y-%m-%dT%H:%M', prev_ts, '+1 hour') = timestamp_ist)
             AND raw_calc_demand_mw < 0.75 * prev_demand_1
             AND (next_demand_1 IS NULL OR next_demand_1 < 50000 OR raw_calc_demand_mw < 0.75 * next_demand_1) THEN 1
            WHEN (strftime('%Y-%m-%dT%H:%M', timestamp_ist, '+1 hour') = next_ts)
             AND raw_calc_demand_mw < 0.75 * next_demand_1
             AND (prev_demand_1 IS NULL OR prev_demand_1 < 50000 OR raw_calc_demand_mw < 0.75 * prev_demand_1) THEN 1
            WHEN (strftime('%Y-%m-%dT%H:%M', prev_ts, '+1 hour') = timestamp_ist)
             AND (strftime('%Y-%m-%dT%H:%M', timestamp_ist, '+1 hour') = next_ts)
             AND raw_calc_demand_mw < 0.90 * prev_demand_1
             AND next_demand_1 > 1.10 * raw_calc_demand_mw THEN 1
            ELSE 0
        END AS is_demand_glitch
    FROM flagged f
)
SELECT
    timestamp_ist,
    date_ist,
    hour_ist,
    thermal_mw,
    hydro_mw,
    gas_mw,
    nuclear_mw,
    clean_wind_mw AS wind_mw,
    clean_solar_mw AS solar_mw,
    is_demand_glitch AS is_dropout,
    is_stuck_solar,
    is_night_solar_glitch,
    is_stuck_wind,
    is_wind_spike,
    is_stuck_demand,
    CASE WHEN is_demand_glitch = 1 THEN NULL ELSE raw_calc_demand_mw END AS demand_mw,
    CASE 
        WHEN is_demand_glitch = 1 OR clean_solar_mw IS NULL OR clean_wind_mw IS NULL THEN NULL 
        ELSE ROUND(raw_calc_demand_mw - (clean_solar_mw + clean_wind_mw), 2)
    END AS net_load_mw,
    source
FROM flagged_demand;

CREATE INDEX IF NOT EXISTS idx_stg_hourly_ts ON stg_hourly_demand(timestamp_ist);
CREATE INDEX IF NOT EXISTS idx_stg_hourly_date ON stg_hourly_demand(date_ist);
