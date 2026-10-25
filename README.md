# India Power Demand & Weather Pipeline

[![Daily Pipeline Refresh](https://github.com/randomaban-beep/india-power-demand-pipeline/actions/workflows/refresh.yml/badge.svg)](https://github.com/randomaban-beep/india-power-demand-pipeline/actions/workflows/refresh.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11](https://img.shields.io/badge/Python-3.11-brightgreen.svg)](https://www.python.org/)
[![Database: SQLite](https://img.shields.io/badge/Database-SQLite-lightgrey.svg)](data/energy.db)

An automated, end-to-end data engineering and analytics pipeline tracking India's electricity demand, fuel-wise generation, and weather variables. Ingests daily reports and historical SCADA telemetry, cleans and models data in SQL, refreshes daily via GitHub Actions, and renders publication-ready visualisations and an interactive Streamlit dashboard.

---

## ⚡ Executive Summary & Key Findings

| Finding | Metric / Evidence | Strategic Takeaway ("So What") |
|---|---|---|
| **Temperature Elasticity** | **+3,723 MW / °C** above 25°C base | Every 1°C heatwave across Indian urban centers adds nearly 4 GW of instantaneous peak cooling demand. |
| **Midday Solar Suppression** | **~24,000 MW** solar belly depth | Midday net load is significantly depressed, requiring steep generation ramp-downs followed by aggressive evening ramp-ups. |
| **Grid Ramping Stress** | **31,732 MW** maximum 1-hour ramp | Solar sunset coinciding with evening peak requires over 31 GW of flexible ramping capacity (hydro, gas, battery storage). |
| **Variable RE Penetration** | **11.4%** average (peaking at **27.6%**) | Growing solar and wind capacity is actively reshaping the diurnal load curve, making grid flexibility essential. |
| **Pipeline Reliability** | **100%** assertion pass rate | Automated tests validate 0 timestamp gaps, 0 duplicates, and 100% weather join overlap on every daily refresh. |

---

## 📊 Core Visual Findings

### 1. Diurnal Net Load Profile ("Duck Curve")
Solar generation creates a deep midday depression in net load that swings sharply upward at sunset.
![Net Load Profile](docs/figures/04_duck_curve.png)
*Takeaway: Solar generation suppresses net load by ~24,000 MW during midday hours, demanding rapid ramping of dispatchable resources between 16:00 and 19:30 IST.*

---

### 2. Temperature Sensitivity of Electricity Demand
Electricity demand demonstrates a pronounced hockey-stick hinge at 25°C.
![Temperature vs Demand](docs/figures/02_temp_vs_demand.png)
*Takeaway: Demand scales linearly by +3,723 MW per 1°C increase above 25°C, illustrating the massive cooling load driving summer grid strain.*

---

### 3. Diurnal Peak Load by Month
Heatmap of average hourly demand across hours of the day (IST) and calendar months.
![Demand Heatmap](docs/figures/03_demand_heatmap.png)
*Takeaway: Grid strain concentrates heavily in evening peak hours (19:00–22:00 IST) during pre-monsoon summer months (April–June).*

---

### 4. Hourly Net Load Ramp Distribution
Histogram of hour-to-hour net load changes, showing tail ramping events.
![Net Load Ramps](docs/figures/08_net_load_ramps.png)
*Takeaway: 99th percentile 1-hour ramp exceeds 18,000 MW, with maximum recorded ramps surpassing 31,000 MW/h.*

---

### 5. Daily Demand Growth and Seasonality
Continuous time-series with 7-day rolling average and all-time peak load annotation.
![Daily Demand](docs/figures/01_daily_demand.png)
*Takeaway: Strong seasonal swing between winter troughs (~130,000 MW) and summer peaks (~218,000 MW).*

---

### 6. Pipeline Reliability and Data Completeness
Data quality monitoring verifying zero duplicates, plausible ranges, and cross-layer integrity.
![Data Quality](docs/figures/09_data_quality.png)
*Takeaway: 100% automated pass rate across all staging assertions ensures audit-grade data delivery.*

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
     │  mart_net_load_ramps        mart_monthly_peak_demand    │
     │  mart_anomaly_days          mart_demand_profile_by_season
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

| Source | Description | License / Terms |
|---|---|---|
| [Grid Controller of India (Grid-India / POSOCO)](https://grid-india.in/en/reports/daily-psp-report) | Daily PSP Reports (generation by source, peak demand met, state demand) | Public government data |
| [Mendeley Data Repository (DOI: 10.17632/y58jknpgs8.2)](https://doi.org/10.17632/y58jknpgs8.2) | 5-minute SCADA telemetry for demand, solar, and wind generation | CC BY 4.0 |
| [Open-Meteo Historical Archive API](https://open-meteo.com/) | Hourly ECMWF ERA5 reanalysis temperature, humidity, wind | Free for non-commercial use |

> *Note on Weather Data:* Open-Meteo utilizes ECMWF ERA5 model reanalysis simulations, rather than physical surface weather station observations.

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

# 3. Build SQL analytical marts
python -m src.model.run_all

# 4. Generate all 9 publication figures
python -m src.viz.generate_all

# 5. Run test suite
pytest tests/ -v
```

### 3. Launch Interactive Dashboard
```bash
streamlit run app/streamlit_app.py
```

---

## ⚙️ Automated Daily Refresh

The pipeline refreshes daily at **02:00 UTC** via GitHub Actions ([`.github/workflows/refresh.yml`](.github/workflows/refresh.yml)):
1. Checks out repository.
2. Ingests latest daily PSP reports and updates weather records.
3. Cleans, checks quality assertions, and rebuilds SQL marts.
4. Regenerates all 9 figures and writes [`RESULTS.md`](RESULTS.md).
5. Commits updated database artifacts and figures back to the repository.

---

## ⚠️ Known Limitations

1. **Weather Reanalysis:** Atmospheric temperatures are derived from ECMWF ERA5 gridded reanalysis, which may show minor variations from microclimatic station readings.
2. **Historical Horizon:** High-frequency 5-minute telemetry from the Mendeley dataset concludes in mid-2025; ongoing live refreshes track Grid-India daily reports.
3. **Format Evolution:** Grid-India report structures may evolve over time; the parser handles both Excel (.xls) and fallback mechanisms.

---

## 🌐 Live Interactive Dashboard

Access the interactive dashboard deployed on Streamlit Community Cloud:
👉 **[Launch Streamlit Dashboard](https://share.streamlit.io/)** *(or run locally with `streamlit run app/streamlit_app.py`)*
