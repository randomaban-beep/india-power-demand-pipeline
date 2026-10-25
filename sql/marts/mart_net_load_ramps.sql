-- Mart: Largest Hour-to-Hour Net Load Ramps
-- Business question: What are the largest 1-hour and 3-hour net load ramps on India's grid, indicating ramping stress?

DROP TABLE IF EXISTS mart_net_load_ramps;

CREATE TABLE mart_net_load_ramps AS
WITH ramp_calc AS (
    SELECT
        timestamp_ist,
        date_ist,
        hour_ist,
        net_load_mw,
        demand_mw,
        solar_mw,
        wind_mw,
        -- Window function: 1-hour previous net load
        LAG(net_load_mw, 1) OVER (ORDER BY timestamp_ist) AS prev_1h_net_load_mw,
        -- Window function: 3-hour previous net load
        LAG(net_load_mw, 3) OVER (ORDER BY timestamp_ist) AS prev_3h_net_load_mw
    FROM stg_hourly_demand
)
SELECT
    timestamp_ist,
    date_ist,
    hour_ist,
    net_load_mw,
    demand_mw,
    solar_mw,
    wind_mw,
    prev_1h_net_load_mw,
    -- 1-hour ramp (positive = ramping up, negative = ramping down)
    ROUND(net_load_mw - prev_1h_net_load_mw, 2) AS ramp_1h_mw,
    -- 3-hour ramp
    ROUND(net_load_mw - prev_3h_net_load_mw, 2) AS ramp_3h_mw,
    -- Absolute ramp magnitude
    ROUND(ABS(net_load_mw - prev_1h_net_load_mw), 2) AS abs_ramp_1h_mw
FROM ramp_calc
WHERE prev_1h_net_load_mw IS NOT NULL;
