-- Mart: Daily Weather vs Demand Sensitivity
-- Business question: How strongly does temperature drive daily maximum demand met and daily energy requirement across multi-year seasons?
-- Joins Grid-India daily power supply position reports with multi-city weather aggregates.

DROP TABLE IF EXISTS mart_daily_weather_demand;

CREATE TABLE mart_daily_weather_demand AS
WITH daily_weather AS (
    SELECT
        date_ist,
        ROUND(AVG(avg_temperature_c), 2) AS daily_mean_temp_c,
        ROUND(MAX(max_temperature_c), 2) AS daily_max_temp_c,
        ROUND(MIN(min_temperature_c), 2) AS daily_min_temp_c,
        ROUND(AVG(avg_humidity_pct), 2) AS daily_mean_humidity_pct,
        ROUND(AVG(delhi_temp_c), 2) AS delhi_mean_temp_c,
        ROUND(MAX(delhi_temp_c), 2) AS delhi_max_temp_c,
        ROUND(AVG(mumbai_temp_c), 2) AS mumbai_mean_temp_c,
        ROUND(MAX(mumbai_temp_c), 2) AS mumbai_max_temp_c
    FROM stg_hourly_weather
    GROUP BY date_ist
)
SELECT
    p.report_date,
    strftime('%Y', p.report_date) AS year_str,
    strftime('%m', p.report_date) AS month_str,
    strftime('%w', p.report_date) AS weekday_str,
    CASE strftime('%w', p.report_date)
        WHEN '0' THEN 'Sunday'
        WHEN '1' THEN 'Monday'
        WHEN '2' THEN 'Tuesday'
        WHEN '3' THEN 'Wednesday'
        WHEN '4' THEN 'Thursday'
        WHEN '5' THEN 'Friday'
        ELSE 'Saturday'
    END AS weekday_name,
    CASE
        WHEN strftime('%m', p.report_date) IN ('12', '01', '02') THEN 'Winter'
        WHEN strftime('%m', p.report_date) IN ('03', '04', '05') THEN 'Summer'
        WHEN strftime('%m', p.report_date) IN ('06', '07', '08', '09') THEN 'Monsoon'
        ELSE 'Post-Monsoon'
    END AS season,
    p.max_demand_met_mw,
    p.evening_peak_mw,
    p.energy_met_mu,
    p.res_share_pct,
    w.daily_mean_temp_c,
    w.daily_max_temp_c,
    w.daily_min_temp_c,
    w.daily_mean_humidity_pct,
    w.delhi_mean_temp_c,
    w.delhi_max_temp_c,
    w.mumbai_mean_temp_c,
    w.mumbai_max_temp_c,
    -- Cooling degrees above 25°C base
    MAX(0.0, ROUND(w.daily_mean_temp_c - 25.0, 2)) AS cooling_degrees_c
FROM stg_daily_psp p
JOIN daily_weather w ON p.report_date = w.date_ist
WHERE p.max_demand_met_mw IS NOT NULL
  AND w.daily_mean_temp_c IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_mart_daily_wd_date ON mart_daily_weather_demand(report_date);
