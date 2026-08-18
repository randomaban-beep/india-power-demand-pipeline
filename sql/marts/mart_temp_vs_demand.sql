-- Mart: Temperature vs Demand sensitivity
-- Business question: How strongly does temperature drive electricity demand (MW per degree C) above cooling balance point (25°C)?

DROP TABLE IF EXISTS mart_temp_vs_demand;

CREATE TABLE mart_temp_vs_demand AS
WITH joined_data AS (
    SELECT
        d.timestamp_ist,
        d.date_ist,
        d.hour_ist,
        d.demand_mw,
        w.avg_temperature_c,
        w.delhi_temp_c,
        w.mumbai_temp_c,
        w.avg_humidity_pct,
        CASE
            WHEN strftime('%m', d.timestamp_ist) IN ('12', '01', '02') THEN 'Winter'
            WHEN strftime('%m', d.timestamp_ist) IN ('03', '04', '05') THEN 'Summer'
            WHEN strftime('%m', d.timestamp_ist) IN ('06', '07', '08', '09') THEN 'Monsoon'
            ELSE 'Post-Monsoon'
        END AS season,
        -- Degrees Celsius above cooling threshold (25°C base)
        MAX(0.0, ROUND(w.avg_temperature_c - 25.0, 2)) AS cooling_degrees_c
    FROM stg_hourly_demand d
    JOIN stg_hourly_weather w ON d.timestamp_ist = w.timestamp_ist
    WHERE w.avg_temperature_c IS NOT NULL
)
SELECT
    timestamp_ist,
    date_ist,
    hour_ist,
    season,
    avg_temperature_c,
    delhi_temp_c,
    mumbai_temp_c,
    avg_humidity_pct,
    demand_mw,
    cooling_degrees_c,
    -- Round temperature to nearest integer bin for sensitivity aggregation
    CAST(ROUND(avg_temperature_c) AS INTEGER) AS temp_bin_c
FROM joined_data;
