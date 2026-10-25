-- Staging clean hourly demand table
-- Business question: Standardize, clean, and validate 1-hour interval India grid demand and generation data.
-- Implements sensor dropout detection (setting glitch hours to NULL, never interpolating silently).

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
        -- If component thermal is present (2021-2022), sum generation components; otherwise use total_demand_mw (2024-2025)
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
        LAG(raw_calc_demand_mw, 1) OVER (ORDER BY timestamp_ist) AS prev_demand_mw,
        LEAD(raw_calc_demand_mw, 1) OVER (ORDER BY timestamp_ist) AS next_demand_mw,
        LAG(timestamp_ist, 1) OVER (ORDER BY timestamp_ist) AS prev_ts,
        LEAD(timestamp_ist, 1) OVER (ORDER BY timestamp_ist) AS next_ts
    FROM computed
)
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
    -- Flag sensor dropouts:
    -- 1) Demand collapsed < 50,000 MW or above physical ceiling 350,000 MW
    -- 2) Or demand collapses > 25% below neighbouring valid hours or adjacent to dropout collapse
    CASE
        WHEN raw_calc_demand_mw IS NULL OR raw_calc_demand_mw < 50000 OR raw_calc_demand_mw > 350000 THEN 1
        WHEN (strftime('%Y-%m-%dT%H:%M', prev_ts, '+1 hour') = timestamp_ist)
         AND raw_calc_demand_mw < 0.75 * prev_demand_mw
         AND (next_demand_mw IS NULL OR next_demand_mw < 50000 OR raw_calc_demand_mw < 0.75 * next_demand_mw) THEN 1
        WHEN (strftime('%Y-%m-%dT%H:%M', timestamp_ist, '+1 hour') = next_ts)
         AND raw_calc_demand_mw < 0.75 * next_demand_mw
         AND (prev_demand_mw IS NULL OR prev_demand_mw < 50000 OR raw_calc_demand_mw < 0.75 * prev_demand_mw) THEN 1
        ELSE 0
    END AS is_dropout,
    -- Demand: set to NULL for dropout hours (never interpolate silently)
    CASE
        WHEN raw_calc_demand_mw IS NULL OR raw_calc_demand_mw < 50000 OR raw_calc_demand_mw > 350000 THEN NULL
        WHEN (strftime('%Y-%m-%dT%H:%M', prev_ts, '+1 hour') = timestamp_ist)
         AND raw_calc_demand_mw < 0.75 * prev_demand_mw
         AND (next_demand_mw IS NULL OR next_demand_mw < 50000 OR raw_calc_demand_mw < 0.75 * next_demand_mw) THEN NULL
        WHEN (strftime('%Y-%m-%dT%H:%M', timestamp_ist, '+1 hour') = next_ts)
         AND raw_calc_demand_mw < 0.75 * next_demand_mw
         AND (prev_demand_mw IS NULL OR prev_demand_mw < 50000 OR raw_calc_demand_mw < 0.75 * prev_demand_mw) THEN NULL
        ELSE raw_calc_demand_mw
    END AS demand_mw,
    -- Net load: total demand minus intermittent renewables (solar + wind); NULL if dropout
    CASE
        WHEN raw_calc_demand_mw IS NULL OR raw_calc_demand_mw < 50000 OR raw_calc_demand_mw > 350000 THEN NULL
        WHEN (strftime('%Y-%m-%dT%H:%M', prev_ts, '+1 hour') = timestamp_ist)
         AND raw_calc_demand_mw < 0.75 * prev_demand_mw
         AND (next_demand_mw IS NULL OR next_demand_mw < 50000 OR raw_calc_demand_mw < 0.75 * next_demand_mw) THEN NULL
        WHEN (strftime('%Y-%m-%dT%H:%M', timestamp_ist, '+1 hour') = next_ts)
         AND raw_calc_demand_mw < 0.75 * next_demand_mw
         AND (prev_demand_mw IS NULL OR prev_demand_mw < 50000 OR raw_calc_demand_mw < 0.75 * prev_demand_mw) THEN NULL
        ELSE ROUND(raw_calc_demand_mw - (COALESCE(solar_mw, 0) + COALESCE(wind_mw, 0)), 2)
    END AS net_load_mw,
    source
FROM windowed;

CREATE INDEX IF NOT EXISTS idx_stg_hourly_ts ON stg_hourly_demand(timestamp_ist);
CREATE INDEX IF NOT EXISTS idx_stg_hourly_date ON stg_hourly_demand(date_ist);
