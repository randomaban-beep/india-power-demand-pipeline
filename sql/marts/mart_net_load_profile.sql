-- Mart: Solar and Wind share of generation, Net Load, and Duck Curve
-- Business question: How are solar and wind altering daily net load (demand - solar - wind), and what hour marks daily minimum net load?

DROP TABLE IF EXISTS mart_net_load_profile;

CREATE TABLE mart_net_load_profile AS
WITH hourly_metrics AS (
    SELECT
        timestamp_ist,
        date_ist,
        hour_ist,
        demand_mw,
        solar_mw,
        wind_mw,
        (solar_mw + wind_mw) AS re_total_mw,
        net_load_mw,
        CASE 
            WHEN demand_mw > 0 THEN ROUND(((solar_mw + wind_mw) / demand_mw) * 100.0, 2)
            ELSE 0.0 
        END AS re_penetration_pct,
        CASE
            WHEN strftime('%m', timestamp_ist) IN ('12', '01', '02') THEN 'Winter'
            WHEN strftime('%m', timestamp_ist) IN ('03', '04', '05') THEN 'Summer'
            WHEN strftime('%m', timestamp_ist) IN ('06', '07', '08', '09') THEN 'Monsoon'
            ELSE 'Post-Monsoon'
        END AS season
    FROM stg_hourly_demand
),
daily_min_net AS (
    SELECT
        date_ist,
        MIN(net_load_mw) AS min_daily_net_load_mw
    FROM hourly_metrics
    GROUP BY date_ist
),
hourly_with_min_flag AS (
    SELECT
        h.*,
        m.min_daily_net_load_mw,
        CASE WHEN h.net_load_mw = m.min_daily_net_load_mw THEN 1 ELSE 0 END AS is_min_net_load_hour
    FROM hourly_metrics h
    JOIN daily_min_net m ON h.date_ist = m.date_ist
)
SELECT
    timestamp_ist,
    date_ist,
    hour_ist,
    season,
    demand_mw,
    solar_mw,
    wind_mw,
    re_total_mw,
    net_load_mw,
    re_penetration_pct,
    min_daily_net_load_mw,
    is_min_net_load_hour
FROM hourly_with_min_flag;
