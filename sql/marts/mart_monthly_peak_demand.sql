-- Mart: Peak demand per month with Year-over-Year change
-- Business question: How is monthly peak electricity demand growing year over year, and which months record highest strain?

DROP TABLE IF EXISTS mart_monthly_peak_demand;

CREATE TABLE mart_monthly_peak_demand AS
WITH monthly_peaks AS (
    SELECT
        strftime('%Y', timestamp_ist) AS year,
        strftime('%m', timestamp_ist) AS month_num,
        strftime('%Y-%m', timestamp_ist) AS year_month,
        MAX(demand_mw) AS peak_demand_mw,
        ROUND(AVG(demand_mw), 1) AS avg_demand_mw
    FROM stg_hourly_demand
    GROUP BY strftime('%Y', timestamp_ist), strftime('%m', timestamp_ist)
),
ranked_peaks AS (
    SELECT
        year,
        month_num,
        year_month,
        peak_demand_mw,
        avg_demand_mw,
        -- Window function: Rank highest peak per year
        RANK() OVER (PARTITION BY year ORDER BY peak_demand_mw DESC) AS peak_rank_in_year,
        -- Window function: Lag 1 year (same month previous year)
        CASE WHEN CAST(year AS INTEGER) - CAST(LAG(year) OVER (PARTITION BY month_num ORDER BY year) AS INTEGER) = 1
             THEN LAG(peak_demand_mw) OVER (PARTITION BY month_num ORDER BY year) END AS prev_year_peak_mw
    FROM monthly_peaks
)
SELECT
    year,
    month_num,
    year_month,
    peak_demand_mw,
    avg_demand_mw,
    peak_rank_in_year,
    prev_year_peak_mw,
    -- Compute YoY growth in peak demand
    CASE 
        WHEN prev_year_peak_mw > 0 
        THEN ROUND(((peak_demand_mw - prev_year_peak_mw) / prev_year_peak_mw) * 100.0, 2)
        ELSE NULL 
    END AS yoy_peak_growth_pct
FROM ranked_peaks
ORDER BY year_month;
