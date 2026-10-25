-- Mart: Anomaly Days Detection
-- Business question: Which days exhibit anomalous electricity demand exceeding 2 standard deviations from the same-season and same-weekday norm?

DROP TABLE IF EXISTS mart_anomaly_days;

CREATE TABLE mart_anomaly_days AS
WITH daily_totals AS (
    SELECT
        date_ist,
        strftime('%w', date_ist) AS weekday_num,
        CASE strftime('%w', date_ist)
            WHEN '0' THEN 'Sunday'
            WHEN '1' THEN 'Monday'
            WHEN '2' THEN 'Tuesday'
            WHEN '3' THEN 'Wednesday'
            WHEN '4' THEN 'Thursday'
            WHEN '5' THEN 'Friday'
            ELSE 'Saturday'
        END AS weekday_name,
        CASE
            WHEN strftime('%m', date_ist) IN ('12', '01', '02') THEN 'Winter'
            WHEN strftime('%m', date_ist) IN ('03', '04', '05') THEN 'Summer'
            WHEN strftime('%m', date_ist) IN ('06', '07', '08', '09') THEN 'Monsoon'
            ELSE 'Post-Monsoon'
        END AS season,
        ROUND(AVG(demand_mw), 1) AS avg_daily_demand_mw,
        ROUND(MAX(demand_mw), 1) AS peak_daily_demand_mw,
        ROUND(SUM(demand_mw) / 1000.0, 2) AS energy_consumed_gwh
    FROM stg_hourly_demand
    GROUP BY date_ist
),
season_weekday_stats AS (
    SELECT
        season,
        weekday_num,
        AVG(avg_daily_demand_mw) AS baseline_avg_mw,
        -- Approximate sample standard deviation
        -- (SQL window / aggregation formula: sqrt(avg(x^2) - avg(x)^2))
        ROUND(
            SQRT(
                MAX(
                    0.0,
                    AVG(avg_daily_demand_mw * avg_daily_demand_mw) - (AVG(avg_daily_demand_mw) * AVG(avg_daily_demand_mw))
                )
            ),
            2
        ) AS baseline_std_mw
    FROM daily_totals
    GROUP BY season, weekday_num
),
scored_days AS (
    SELECT
        d.date_ist,
        d.season,
        d.weekday_name,
        d.avg_daily_demand_mw,
        d.peak_daily_demand_mw,
        d.energy_consumed_gwh,
        ROUND(s.baseline_avg_mw, 1) AS baseline_avg_mw,
        s.baseline_std_mw,
        CASE 
            WHEN s.baseline_std_mw > 0 
            THEN ROUND((d.avg_daily_demand_mw - s.baseline_avg_mw) / s.baseline_std_mw, 2)
            ELSE 0.0 
        END AS z_score
    FROM daily_totals d
    JOIN season_weekday_stats s 
      ON d.season = s.season AND d.weekday_num = s.weekday_num
)
SELECT
    date_ist,
    season,
    weekday_name,
    avg_daily_demand_mw,
    peak_daily_demand_mw,
    energy_consumed_gwh,
    baseline_avg_mw,
    baseline_std_mw,
    z_score,
    CASE WHEN ABS(z_score) >= 2.0 THEN 1 ELSE 0 END AS is_anomaly,
    CASE 
        WHEN z_score >= 2.0 THEN 'High Demand Spike'
        WHEN z_score <= -2.0 THEN 'Low Demand Drop'
        ELSE 'Normal'
    END AS anomaly_type
FROM scored_days
ORDER BY date_ist;
