-- Mart: Anomaly Days Detection
-- Business question: Which days exhibit anomalous electricity demand exceeding 2 standard deviations from the same-season and same-weekday norm?
-- Rigorously separates Data-Quality anomalies (sensor dropouts) from Real Grid Demand anomalies.

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
        COUNT(demand_mw) AS valid_hours_count,
        SUM(is_dropout) AS dropout_hours_count,
        ROUND(AVG(demand_mw), 1) AS avg_daily_demand_mw,
        ROUND(MAX(demand_mw), 1) AS peak_daily_demand_mw,
        ROUND(SUM(demand_mw) / 1000.0, 2) AS energy_consumed_gwh
    FROM stg_hourly_demand
    GROUP BY date_ist
),
clean_baselines AS (
    -- Baselines computed strictly over days with complete/valid data (>=20 valid hours, <=2 dropouts)
    SELECT
        season,
        weekday_num,
        AVG(avg_daily_demand_mw) AS baseline_avg_mw,
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
    WHERE valid_hours_count >= 20 AND dropout_hours_count <= 2
    GROUP BY season, weekday_num
),
scored_days AS (
    SELECT
        d.date_ist,
        d.season,
        d.weekday_name,
        d.valid_hours_count,
        d.dropout_hours_count,
        d.avg_daily_demand_mw,
        d.peak_daily_demand_mw,
        d.energy_consumed_gwh,
        ROUND(b.baseline_avg_mw, 1) AS baseline_avg_mw,
        b.baseline_std_mw,
        CASE 
            WHEN b.baseline_std_mw > 0 AND d.valid_hours_count >= 20
            THEN ROUND((d.avg_daily_demand_mw - b.baseline_avg_mw) / b.baseline_std_mw, 2)
            ELSE NULL 
        END AS z_score
    FROM daily_totals d
    LEFT JOIN clean_baselines b 
      ON d.season = b.season AND d.weekday_num = b.weekday_num
)
SELECT
    date_ist,
    season,
    weekday_name,
    valid_hours_count,
    dropout_hours_count,
    avg_daily_demand_mw,
    peak_daily_demand_mw,
    energy_consumed_gwh,
    baseline_avg_mw,
    baseline_std_mw,
    z_score,
    -- Data-Quality anomaly: day had > 2 dropout hours or < 20 valid hours
    CASE WHEN dropout_hours_count > 2 OR valid_hours_count < 20 THEN 1 ELSE 0 END AS is_dq_anomaly,
    -- Real demand anomaly: clean day with z-score >= 2.0 or <= -2.0
    CASE 
        WHEN (dropout_hours_count <= 2 AND valid_hours_count >= 20) AND ABS(z_score) >= 2.0 THEN 1 
        ELSE 0 
    END AS is_real_anomaly,
    -- For backwards compatibility, is_anomaly = is_real_anomaly
    CASE 
        WHEN (dropout_hours_count <= 2 AND valid_hours_count >= 20) AND ABS(z_score) >= 2.0 THEN 1 
        ELSE 0 
    END AS is_anomaly,
    CASE 
        WHEN dropout_hours_count > 2 OR valid_hours_count < 20 THEN 'Data-Quality Dropout (Glitch)'
        WHEN z_score >= 2.0 THEN 'High Demand Spike'
        WHEN z_score <= -2.0 THEN 'Low Demand Drop'
        ELSE 'Normal'
    END AS anomaly_type
FROM scored_days
ORDER BY date_ist;
