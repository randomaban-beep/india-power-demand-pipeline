# India Power Demand & Weather Pipeline

[![Daily Pipeline Refresh](https://github.com/randomaban-beep/india-power-demand-pipeline/actions/workflows/refresh.yml/badge.svg)](https://github.com/randomaban-beep/india-power-demand-pipeline/actions/workflows/refresh.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11](https://img.shields.io/badge/Python-3.11-brightgreen.svg)](https://www.python.org/)
[![Database: SQLite](https://img.shields.io/badge/Database-SQLite-lightgrey.svg)](data/energy.db)

An automated, end-to-end data engineering and analytics pipeline tracking India's electricity demand, fuel-wise generation, and weather variables across multi-year operating horizons. Ingests daily reports from Grid Controller of India (Grid-India / POSOCO), historical SCADA telemetry, and hourly ECMWF ERA5 reanalysis weather data; cleans and models data in SQLite; refreshes via GitHub Actions; and renders publication-ready visualisations and an interactive Streamlit dashboard.

---

## ⚡ Executive Summary & Key Findings

> **Note on Data Synchronization:** All figures and metrics below are generated dynamically from `data/energy.db` via `src/model/write_results.py` and are identical to [`RESULTS.md`](RESULTS.md).

| Finding | Metric / Evidence | Strategic Takeaway ("So What") |
|---|---|---|
| **Controlled Temperature Elasticity** | **+8,189 MW / °C** above 25°C base (95% CI: [7,132, 9,246] MW/°C, $R^2=0.88$) | Every 1°C heatwave across Indian urban centers adds over 8 GW of instantaneous national peak cooling demand, controlling for weekday, month, and year trend. |
| **Midday Solar Suppression** | **~46,124 MW** midday solar belly depth | Midday net load is significantly depressed during summer months, requiring steep thermal ramp-downs followed by aggressive evening ramp-ups. |
| **Grid Ramping Stress** | **36,798 MW** maximum 1-hour ramp (99th percentile: **17,228 MW**) | Solar sunset coinciding with evening industrial and domestic peak requires flexible ramping capacity (hydro, pumped storage, gas, battery storage). |
| **Renewable Penetration** | **11.3%** average daily generation (peaking at **33.5%**) | Solar and wind generation are actively reshaping the diurnal load curve across all five regional grids. |
| **Peak Demand Benchmark** | **248,688 MW** in hourly window (2024-05-30) | All-time national peak demand met recorded in Grid-India daily reports reached **270,820 MW** (2026-05-21). |
| **Data Quality & Integrity** | **24 dropouts nullified**; **2 historical gaps audited** | High-frequency telemetry contains 2 multi-month gaps in the historical archive; 24 sensor dropouts were isolated and nullified (never silently interpolated). |

---

## 📊 Core Visual Findings

### 1. Daily Demand Growth and Seasonality
Continuous time-series tracking daily average demand, 7-day rolling baseline, and dataset peak demand.
![Daily Demand](docs/figures/01_daily_demand.png)
*Takeaway: Demonstrates persistent summer peak escalation (reaching 248,688 MW in the hourly dataset and 270,820 MW in national daily reports) contrasted with winter base troughs (~104,310 MW).*

---

### 2. Controlled Temperature Sensitivity of Electricity Demand
Daily peak demand regressed against multi-city daily mean temperature, with categorical controls for weekday, month, and year trend.
![Temperature vs Demand](docs/figures/02_temp_vs_demand.png)
*Takeaway: Daily peak demand expands at +8,189 MW/°C (95% CI: [7,132, 9,246] MW/°C, $R^2=0.88$, $N=272$ cooling days) above the 25.0°C cooling balance point.*

---

### 3. Diurnal Peak Load by Month
Heatmap of average hourly demand across hours of the day (IST) and calendar months.
![Demand Heatmap](docs/figures/03_demand_heatmap.png)
*Takeaway: Grid strain concentrates heavily in evening peak hours (19:00–22:00 IST) during pre-monsoon summer months (April–June).*

---

### 4. Diurnal Net Load Profile ("Duck Curve")
Net load profile by season: gross demand, solar and wind generation, and net load.
![Net Load Profile](docs/figures/04_duck_curve.png)
*Takeaway: Midday solar generation suppresses net load by ~46,124 MW during peak summer solar hours, creating steep ramp requirements at dusk.*

---

### 5. Renewable Generation Share & Generation Mix
Daily renewable energy share distribution and generation breakdown by technology.
![Renewable Share](docs/figures/05_renewable_share.png)
*Takeaway: Intermittent renewables account for an average of 11.3% of generation, reaching a recorded daily peak of 33.5%.*

---

### 6. Monthly Peak Demand Growth
Year-over-year peak demand comparison across calendar months.
![Monthly Peak Demand](docs/figures/06_peak_demand_by_month.png)
*Takeaway: Quantifies steady year-on-year electrification growth and rising cooling intensity across peak summer seasons.*

---

### 7. Demand Anomaly Detection
Identification of statistically anomalous grid demand days exceeding $\pm 2\sigma$ from same-season and same-weekday norms.
![Anomaly Days](docs/figures/07_anomaly_days.png)
*Takeaway: Identified 25 real demand anomaly days (e.g., severe heatwave days during April 2023) cleanly separated from data-quality sensor dropout days.*

---

### 8. Hourly Net Load Ramp Distribution
Histogram of hour-to-hour net load changes computed strictly between consecutive non-glitch hours exactly 1 hour apart.
![Net Load Ramps](docs/figures/08_net_load_ramps.png)
*Takeaway: Maximum clean 1-hour ramp is 36,798 MW (99th percentile: 17,228 MW). Sensor dropout glitches that previously reported fake 80,000+ MW ramps have been filtered and isolated.*

---

### 9. Pipeline Reliability and Data Completeness
Automated data quality assertion suite, records per architectural layer, and gap audit summary.
![Data Quality](docs/figures/09_data_quality.png)
*Takeaway: 6 of 7 automated assertion checks pass. The 2 historical multi-month gaps in the Mendeley dataset (longest: 5,881h) and 24 sensor dropouts are audited and reported with complete transparency.*

---

## 🏗️ Architecture

```
                    SOURCES
   ┌───────────────────┬───────────────────┬───────────────────┐
   │ Grid-India (NLDC) │ Mendeley Data     │ Open-Meteo API    │
   │ Daily PSP (.xls)  │ Hourly SCADA      │ ERA5 Reanalysis   │
   └─────────┬─────────┴─────────┬─────────┴─────────┬─────────┘
             │                   │                   │
             ▼                   ▼                   ▼
     ┌─────────────────────────────────────────────────────────┐
     │                      INGEST LAYER                       │
     │   src/ingest/grid_india.py   src/ingest/mendeley.py    │
     │              src/ingest/open_meteo.py                   │
     └───────────────────────────┬─────────────────────────────┘
                                 │
                                 ▼
     ┌─────────────────────────────────────────────────────────┐
     │                     RAW SQLITE DB                       │
     │  raw_daily_psp | raw_state_psp | raw_hourly | raw_weather│
     └───────────────────────────┬─────────────────────────────┘
                                 │
                                 ▼
     ┌─────────────────────────────────────────────────────────┐
     │                     STAGING LAYER                       │
     │  stg_hourly_demand  stg_hourly_weather  stg_daily_psp   │
     │       Automated DQ Assertions (src/clean/quality_checks) │
     └───────────────────────────┬─────────────────────────────┘
                                 │
                                 ▼
     ┌─────────────────────────────────────────────────────────┐
     │                     MODELED MARTS                       │
     │  mart_temp_vs_demand        mart_net_load_profile       │
     │  mart_daily_weather_demand  mart_monthly_peak_demand    │
     │  mart_net_load_ramps        mart_demand_profile_by_season
     │  mart_anomaly_days                                      │
     └───────────────────────────┬─────────────────────────────┘
                                 │
                    ┌────────────┴────────────┐
                    ▼                         ▼
         ┌─────────────────────┐   ┌─────────────────────┐
         │ STATIC FIGURES      │   │ STREAMLIT DASHBOARD │
         │ docs/figures/*.png  │   │ app/streamlit_app.py│
         └─────────────────────┘   └─────────────────────┘
```

---

## 💾 Data Sources & Licenses

| Source | Description | Coverage Span | License / Terms |
|---|---|---|---|
| [Grid Controller of India (Grid-India / POSOCO)](https://grid-india.in/en/reports/daily-psp-report) | Daily PSP Reports (generation by source, peak demand met, state demand) | 2021-05-07 to 2026-10-23 (408 reports) | Public Indian government data |
| [Mendeley Data Repository (DOI: 10.17632/y58jknpgs8.2)](https://doi.org/10.17632/y58jknpgs8.2) | Hourly aggregated SCADA telemetry for demand, solar, and wind generation | 2021-09-01 to 2025-06-24 (23,184 hours; 2 multi-month gaps) | CC BY 4.0 (Attribution 4.0 International) |
| [Open-Meteo Historical Archive & Forecast API](https://open-meteo.com/) | Hourly ECMWF ERA5 reanalysis temperature, humidity, wind across 6 cities | 2021-09-01 to Present (yesterday) | Free for non-commercial open data science |

> *Note on Weather Data:* Open-Meteo provides atmospheric data via ECMWF ERA5 numerical model reanalysis simulations, rather than physical surface weather station observations.
> *Note on Historical Telemetry:* The Mendeley historical archive repository contains 2 multi-month gaps between high-resolution logging campaigns (2022-10 to 2023-03 and 2023-05 to 2023-12). These are documented in [`docs/source_notes.md`](docs/source_notes.md) and tracked in [`RESULTS.md`](RESULTS.md).

---

## 🚀 How to Run Locally

### 1. Clone & Set Up Environment
```bash
git clone https://github.com/randomaban-beep/india-power-demand-pipeline.git
cd india-power-demand-pipeline

python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Run Pipeline End-to-End
```bash
# 1. Ingest raw sources
python -m src.ingest.run_all

# 2. Clean and run data quality checks
python -m src.clean.run_all

# 3. Build SQL analytical data marts
python -m src.model.run_all

# 4. Generate all 9 publication figures
python -m src.viz.generate_all

# 5. Export summary reports (RESULTS.md and README.md)
python -m src.model.write_results

# 6. Run test suite
pytest tests/ -v
```

### 3. Launch Interactive Dashboard
```bash
streamlit run app/streamlit_app.py
```

---

## ⚙️ Automated Daily Refresh

The pipeline refreshes daily at **02:00 UTC** via GitHub Actions ([`.github/workflows/refresh.yml`](.github/workflows/refresh.yml)):
1. Checks out repository with concurrency control.
2. Ingests latest daily PSP reports from Grid-India with network retry logic.
3. Updates weather records up to yesterday via Open-Meteo Forecast/Archive API.
4. Cleans data, executes assertion checks, and rebuilds SQL marts.
5. Re-fits econometric temperature sensitivity models and updates all 9 visualisations.
6. Regenerates [`RESULTS.md`](RESULTS.md) and renders [`README.md`](README.md) from [`README.template.md`](README.template.md).
7. Commits updated reports, figures, and lightweight data exports back to git.

---

## 🌐 Live Interactive Dashboard

Access the interactive dashboard:
👉 **[Launch Streamlit Dashboard](https://share.streamlit.io/)** *(or run locally with `streamlit run app/streamlit_app.py`)*
