-- Staging clean hourly demand table
-- Business question: Standardize, clean, and validate 1-hour interval India grid demand and generation data.

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
)
SELECT
    timestamp_ist,
    date(timestamp_ist) AS date_ist,
    CAST(strftime('%H', timestamp_ist) AS INTEGER) AS hour_ist,
    -- Handle outlier/negative generation values (sensor drift)
    MAX(0.0, ROUND(thermal_mw, 2)) AS thermal_mw,
    MAX(0.0, ROUND(hydro_mw, 2)) AS hydro_mw,
    MAX(0.0, ROUND(gas_mw, 2)) AS gas_mw,
    MAX(0.0, ROUND(nuclear_mw, 2)) AS nuclear_mw,
    MAX(0.0, ROUND(wind_mw, 2)) AS wind_mw,
    MAX(0.0, ROUND(solar_mw, 2)) AS solar_mw,
    -- Net load: total demand minus intermittent renewables (solar + wind)
    ROUND(
        total_demand_mw - (MAX(0.0, solar_mw) + MAX(0.0, wind_mw)),
        2
    ) AS net_load_mw,
    -- Recalculate robust total demand (sum of generation components)
    ROUND(
        MAX(0.0, thermal_mw) + MAX(0.0, hydro_mw) + MAX(0.0, gas_mw) +
        MAX(0.0, nuclear_mw) + MAX(0.0, wind_mw) + MAX(0.0, solar_mw),
        2
    ) AS demand_mw,
    source
FROM deduped
WHERE rn = 1
  -- Plausible bounds check for All-India grid: between 50,000 MW and 350,000 MW
  AND total_demand_mw BETWEEN 50000 AND 350000;

CREATE INDEX IF NOT EXISTS idx_stg_hourly_ts ON stg_hourly_demand(timestamp_ist);
CREATE INDEX IF NOT EXISTS idx_stg_hourly_date ON stg_hourly_demand(date_ist);
