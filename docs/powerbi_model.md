# Power BI Data Model Documentation

This document outlines the data model and schema relationships for building a Power BI `.pbix` report on top of the exported mart tables in `data/processed/`.

---

## Star Schema & Relationship Diagram

```
                 ┌────────────────────────────────┐
                 │       Dim_Date (Calendar)      │
                 │   date_ist (PK)                │
                 │   year, month, day, weekday    │
                 │   season                       │
                 └───────┬──────────────┬─────────┘
                         │ 1            │ 1
                         │              │
                         │ *            │ *
      ┌──────────────────┴──┐        ┌──┴──────────────────────────┐
      │ Fact_HourlyDemand   │        │ Fact_DailyPSP               │
      │ (mart_net_load_     │        │ (stg_daily_psp.csv)         │
      │  profile.csv)       │        │ report_date (FK)            │
      │ timestamp_ist (PK)  │        │ evening_peak_mw             │
      │ date_ist (FK)       │        │ energy_met_mu               │
      │ hour_ist            │        │ coal_gen_mu, res_gen_mu     │
      │ demand_mw           │        └─────────────────────────────┘
      │ solar_mw, wind_mw   │
      │ net_load_mw         │
      └──────────┬──────────┘
                 │ 1
                 │
                 │ 1
      ┌──────────┴─────────────────────┐
      │ Fact_HourlyWeather             │
      │ (mart_temp_vs_demand.csv)      │
      │ timestamp_ist (FK)             │
      │ avg_temperature_c              │
      │ delhi_temp_c, mumbai_temp_c    │
      │ avg_humidity_pct               │
      │ cooling_degrees_c              │
      └────────────────────────────────┘
```

---

## Tables in `data/processed/`

1. **`mart_net_load_profile.csv`** (Core Hourly Fact Table):
   - `timestamp_ist`: Hourly timestamp (IST, UTC+5:30)
   - `date_ist`: ISO date YYYY-MM-DD
   - `hour_ist`: Diurnal hour (0–23)
   - `season`: Summer, Monsoon, Post-Monsoon, Winter
   - `demand_mw`: All-India gross demand (MW)
   - `solar_mw`, `wind_mw`, `re_total_mw`: Variable renewable generation (MW)
   - `net_load_mw`: Net load served by dispatchable generation (MW)
   - `re_penetration_pct`: RE share of instantaneous demand (%)

2. **`mart_temp_vs_demand.csv`** (Temperature Elasticity Fact Table):
   - `timestamp_ist`, `date_ist`, `hour_ist`, `season`
   - `avg_temperature_c`: 6-city unweighted average temperature (°C)
   - `delhi_temp_c`, `mumbai_temp_c`: City temperatures (°C)
   - `cooling_degrees_c`: Temperature above 25°C base (°C)
   - `demand_mw`: Grid demand (MW)

3. **`mart_net_load_ramps.csv`** (Flexibility & Ramping Table):
   - `timestamp_ist`, `net_load_mw`
   - `ramp_1h_mw`: 1-hour ramp rate (MW/h)
   - `ramp_3h_mw`: 3-hour cumulative ramp rate (MW/3h)
   - `abs_ramp_1h_mw`: Absolute ramping magnitude

4. **`mart_anomaly_days.csv`** (Anomaly Classification Fact Table):
   - `date_ist`, `season`, `weekday_name`
   - `avg_daily_demand_mw`, `peak_daily_demand_mw`
   - `z_score`: Standard deviations from same-season/weekday baseline
   - `is_anomaly`: Flag (1 = Anomaly, 0 = Normal)
   - `anomaly_type`: High Demand Spike, Low Demand Drop, Normal

5. **`mart_monthly_peak_demand.csv`** (Monthly Aggregate Table):
   - `year`, `month_num`, `peak_demand_mw`, `avg_demand_mw`, `yoy_peak_growth_pct`

6. **`stg_daily_psp.csv`** (Grid-India Operational Daily Summary):
   - `report_date`, `evening_peak_mw`, `energy_met_mu`, `res_share_pct`

---

## Key DAX Measures

```dax
// 1. All-time Peak Demand
PeakDemandMW = MAX('mart_net_load_profile'[demand_mw])

// 2. Average Net Load
AvgNetLoadMW = AVERAGE('mart_net_load_profile'[net_load_mw])

// 3. Variable Renewable Share (%)
RE_SharePct = 
DIVIDE(
    SUM('mart_net_load_profile'[solar_mw]) + SUM('mart_net_load_profile'[wind_mw]),
    SUM('mart_net_load_profile'[demand_mw]),
    0
) * 100

// 4. Maximum 1-Hour Ramp
Max1hRampMW = MAX('mart_net_load_ramps'[abs_ramp_1h_mw])

// 5. Cooling Sensitivity Slope (MW/°C above 25°C)
CoolingSensitivity = 
DIVIDE(
    CALCULATE(AVERAGE('mart_temp_vs_demand'[demand_mw]), 'mart_temp_vs_demand'[avg_temperature_c] >= 32) -
    CALCULATE(AVERAGE('mart_temp_vs_demand'[demand_mw]), 'mart_temp_vs_demand'[avg_temperature_c] >= 25 && 'mart_temp_vs_demand'[avg_temperature_c] < 27),
    (32 - 26),
    0
)
```
