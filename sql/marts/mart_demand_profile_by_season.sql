-- Mart: Daily and hourly demand profile by season
-- Business question: What is the shape of India's electricity demand profile across different hours of the day and across seasons?

DROP TABLE IF EXISTS mart_demand_profile_by_season;

CREATE TABLE mart_demand_profile_by_season AS
WITH seasonal_hourly AS (
    SELECT
        timestamp_ist,
        hour_ist,
        demand_mw,
        CASE
            WHEN strftime('%m', timestamp_ist) IN ('12', '01', '02') THEN 'Winter'
            WHEN strftime('%m', timestamp_ist) IN ('03', '04', '05') THEN 'Summer'
            WHEN strftime('%m', timestamp_ist) IN ('06', '07', '08', '09') THEN 'Monsoon'
            ELSE 'Post-Monsoon'
        END AS season
    FROM stg_hourly_demand
)
SELECT
    season,
    hour_ist,
    COUNT(*) AS record_count,
    ROUND(AVG(demand_mw), 1) AS avg_demand_mw,
    ROUND(MIN(demand_mw), 1) AS min_demand_mw,
    ROUND(MAX(demand_mw), 1) AS max_demand_mw
FROM seasonal_hourly
GROUP BY season, hour_ist
ORDER BY 
    CASE season
        WHEN 'Summer' THEN 1
        WHEN 'Monsoon' THEN 2
        WHEN 'Post-Monsoon' THEN 3
        WHEN 'Winter' THEN 4
    END,
    hour_ist;
