-- Staging clean daily demand table
-- Business question: Standardize daily power supply position and peak metrics from Grid-India reports.

DROP TABLE IF EXISTS stg_daily_psp;

CREATE TABLE stg_daily_psp AS
SELECT
    report_date,
    ROUND(evening_peak_mw, 1) AS evening_peak_mw,
    ROUND(evening_peak_shortage_mw, 1) AS evening_peak_shortage_mw,
    ROUND(energy_met_mu, 2) AS energy_met_mu,
    ROUND(hydro_gen_mu, 2) AS hydro_gen_mu,
    ROUND(wind_gen_mu, 2) AS wind_gen_mu,
    ROUND(solar_gen_mu, 2) AS solar_gen_mu,
    ROUND(energy_shortage_mu, 2) AS energy_shortage_mu,
    ROUND(max_demand_met_mw, 1) AS max_demand_met_mw,
    max_demand_time,
    ROUND(coal_gen_mu, 2) AS coal_gen_mu,
    ROUND(lignite_gen_mu, 2) AS lignite_gen_mu,
    ROUND(nuclear_gen_mu, 2) AS nuclear_gen_mu,
    ROUND(gas_gen_mu, 2) AS gas_gen_mu,
    ROUND(res_gen_mu, 2) AS res_gen_mu,
    ROUND(total_gen_mu, 2) AS total_gen_mu,
    -- Renewable generation share in gross generation (%)
    CASE 
        WHEN total_gen_mu > 0 THEN ROUND((res_gen_mu / total_gen_mu) * 100.0, 2)
        ELSE NULL 
    END AS res_share_pct
FROM raw_daily_psp
WHERE report_date IS NOT NULL
  AND energy_met_mu > 0;

CREATE INDEX IF NOT EXISTS idx_stg_psp_date ON stg_daily_psp(report_date);
