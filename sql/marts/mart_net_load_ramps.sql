-- Mart: Largest Hour-to-Hour Net Load Ramps
-- Business question: What are the largest 1-hour and 3-hour net load ramps on India's grid, indicating ramping stress?
-- Computed STRICTLY between consecutive timestamps exactly 1 hour apart, excluding dropouts.

DROP TABLE IF EXISTS mart_net_load_ramps;

CREATE TABLE mart_net_load_ramps AS
WITH valid_data AS (
    SELECT
        timestamp_ist,
        date_ist,
        hour_ist,
        net_load_mw,
        demand_mw,
        solar_mw,
        wind_mw,
        LAG(timestamp_ist, 1) OVER (ORDER BY timestamp_ist) AS prev_1h_ts,
        LAG(net_load_mw, 1) OVER (ORDER BY timestamp_ist) AS prev_1h_net_load_mw,
        LAG(timestamp_ist, 3) OVER (ORDER BY timestamp_ist) AS prev_3h_ts,
        LAG(net_load_mw, 3) OVER (ORDER BY timestamp_ist) AS prev_3h_net_load_mw
    FROM stg_hourly_demand
    WHERE is_dropout = 0 AND net_load_mw IS NOT NULL
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
    -- 1-hour ramp strictly computed if prev timestamp is exactly 1 hour prior
    ROUND(net_load_mw - prev_1h_net_load_mw, 2) AS ramp_1h_mw,
    -- 3-hour ramp strictly computed if prev 3h timestamp is exactly 3 hours prior
    CASE
        WHEN strftime('%Y-%m-%dT%H:%M', prev_3h_ts, '+3 hours') = timestamp_ist THEN ROUND(net_load_mw - prev_3h_net_load_mw, 2)
        ELSE NULL
    END AS ramp_3h_mw,
    -- Absolute 1-hour ramp magnitude
    ROUND(ABS(net_load_mw - prev_1h_net_load_mw), 2) AS abs_ramp_1h_mw
FROM valid_data
WHERE prev_1h_ts IS NOT NULL
  AND strftime('%Y-%m-%dT%H:%M', prev_1h_ts, '+1 hour') = timestamp_ist;
