# India Power Demand & Weather Pipeline

[![Daily Pipeline Refresh](https://github.com/randomaban-beep/india-power-demand-pipeline/actions/workflows/refresh.yml/badge.svg)](https://github.com/randomaban-beep/india-power-demand-pipeline/actions/workflows/refresh.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11](https://img.shields.io/badge/Python-3.11-brightgreen.svg)](https://www.python.org/)
[![Database: SQLite](https://img.shields.io/badge/Database-SQLite-lightgrey.svg)](data/energy_marts.db)

An automated, end-to-end data engineering and analytics pipeline tracking India's electricity demand, fuel-wise generation, and weather variables across multi-year operating horizons. Ingests daily reports from Grid Controller of India (Grid-India / POSOCO), historical PMU / SCADA telemetry (Mendeley DOI: 10.17632/y58jknpgs8.2), and hourly ECMWF ERA5 reanalysis weather data; cleans and models data in SQLite; refreshes via GitHub Actions; and renders publication-ready visualisations and an interactive Streamlit dashboard.

---

## ⚡ Executive Summary & Key Findings

> **Note on Data Synchronization:** All figures and metrics below are generated dynamically from `data/energy.db` via `src/model/write_results.py` and are identical to [`RESULTS.md`](RESULTS.md).

| Finding | Metric / Evidence | Strategic Takeaway ("So What") |
|---|---|---|
| **Controlled Temperature Elasticity** | **+8,264 MW / °C** above 25°C base (95% CI: [7,492, 9,036] MW/°C, White's HC1 SE: 394.0 MW/°C; controls $R^2=0.759$, full $R^2=0.865$, incremental $\Delta R^2=+0.106$ across 517 cooling days) | Controlling for day-of-week, month, and multi-year economic trend, every 1°C increase above 25°C adds over 8 GW of national peak cooling demand. Temperature alone accounts for an incremental +0.106 of variance beyond seasonal/trend controls. |
| **Midday Solar Suppression** | **~46,005 MW** midday solar belly depth | Midday net load is significantly depressed during summer months, requiring steep thermal ramp-downs followed by aggressive evening ramp-ups. |
| **Grid Ramping Stress** | **16,854 MW** 99th percentile 1-hour ramp; **13,229 MW** median daily peak ramp | Solar sunset coinciding with evening industrial and domestic peak creates predictable tail ramping stress; maximum clean 1-hour ramp verified at **27,899 MW** after isolating sensor glitches. |
| **Renewable Penetration** | **11.1%** average daily generation share (peaking at **22.4%** on 2025-05-31) | Cross-validated against official Grid-India daily reports (Pearson $r = 0.9865$, mean difference -0.39%). Solar and wind generation are actively reshaping the diurnal load curve across all five regional grids. |
| **Peak Demand Benchmark** | **248,688 MW** in hourly dataset window (2024-05-30) | Highest demand met recorded among loaded Grid-India daily reports reached **270,820 MW** (2026-05-21). |
| **Data Quality & Telemetry Audit** | **134 glitch hours nullified**; **2 historical gaps audited** | High-frequency telemetry spans 966 days (2021: 122, 2022: 273, 2023: 30, 2024: 366, 2025: 175); 2 documented multi-month gaps in the historical archive; dropouts and flatlined sensors were isolated and set to `NULL` (never silently interpolated). |

---

## 📊 Core Visual Findings

### 1. Daily Demand Growth and Seasonality
Continuous time-series tracking daily average demand, 7-day rolling baseline, and dataset peak demand.
![Daily Demand](docs/figures/01_daily_demand.png)
*Takeaway: Demonstrates persistent summer peak escalation (reaching 248,688 MW in the hourly dataset and 270,820 MW in loaded national daily reports) contrasted with winter base troughs (~113,070 MW).*

---

### 2. Controlled Temperature Sensitivity of Electricity Demand
Daily peak demand regressed against multi-city daily mean temperature, with categorical controls for weekday, month, and year trend.
![Temperature vs Demand](docs/figures/02_temp_vs_demand.png)
*Takeaway: Daily peak demand expands at +8,264 MW/°C (95% CI: [7,492, 9,036] MW/°C, White's HC1 SE: 394.0 MW/°C, full model $R^2=0.865$, incremental $\Delta R^2=+0.106$, $N=517$ cooling days) above the 25.0°C cooling balance point.*

#### Candidate Threshold Sensitivity Analysis (22°C to 28°C)

| Threshold (°C) | Cooling Days ($N$) | Temp Range (°C) | Slope (MW/°C) | White's HC1 SE | 95% Confidence Interval | Controls $R^2$ | Full $R^2$ | Incremental $\Delta R^2$ | AIC |
|---|---|---|---|---|---|---|---|---|---|
| **22.0°C** | 631 | 22.0 – 32.9 | +6,319.1 | 434.2 | [5,468.1, 7,170.2] | 0.7925 | 0.8564 | **+0.0640** | 11,591.3 |
| **23.0°C** | 590 | 23.0 – 32.9 | +6,768.4 | 431.2 | [5,923.3, 7,613.4] | 0.7900 | 0.8624 | **+0.0725** | 10,823.7 |
| **24.0°C** | 546 | 24.0 – 32.9 | +7,677.4 | 413.4 | [6,867.2, 8,487.7] | 0.7759 | 0.8664 | **+0.0905** | 9,984.2 |
| **25.0°C** **(Selected)** | 517 | 25.0 – 32.9 | +8,264.0 | 394.0 | [7,491.8, 9,036.3] | 0.7595 | 0.8654 | **+0.1059** | 9,427.0 |
| **26.0°C** | 479 | 26.0 – 32.9 | +8,421.6 | 389.4 | [7,658.4, 9,184.8] | 0.7520 | 0.8625 | **+0.1105** | 8,727.4 |
| **27.0°C** | 413 | 27.0 – 32.9 | +8,908.8 | 395.0 | [8,134.6, 9,683.0] | 0.7320 | 0.8581 | **+0.1261** | 7,490.5 |
| **28.0°C** | 272 | 28.0 – 32.9 | +9,059.7 | 476.5 | [8,125.8, 9,993.6] | 0.7326 | 0.8713 | **+0.1387** | 4,882.8 |


---

### 3. Diurnal Peak Load by Month
Heatmap of average hourly demand across hours of the day (IST) and calendar months.
![Demand Heatmap](docs/figures/03_demand_heatmap.png)
*Takeaway: Grid strain concentrates heavily in evening peak hours (19:00–22:00 IST) during pre-monsoon summer months (April–June).*

---

### 4. Diurnal Net Load Profile ("Duck Curve")
Net load profile by season: gross demand, solar and wind generation, and net load.
![Net Load Profile](docs/figures/04_duck_curve.png)
*Takeaway: Midday solar generation suppresses net load by ~46,005 MW during peak summer solar hours, creating steep ramp requirements at dusk.*

---

### 5. Renewable Generation Share & Generation Mix
Daily renewable energy share distribution and generation breakdown by technology.
![Renewable Share](docs/figures/05_renewable_share.png)
*Takeaway: Intermittent renewables account for an average of 11.1% of generation, reaching a recorded daily peak of 22.4%.*

---

### 6. Monthly Peak Demand Growth
Year-over-year peak demand comparison across calendar months.
![Monthly Peak Demand](docs/figures/06_peak_demand_by_month.png)
*Takeaway: Quantifies steady year-on-year electrification growth and rising cooling intensity across peak summer seasons.*

---

### 7. Demand Anomaly Detection
Identification of statistically anomalous grid demand days exceeding $\pm 2\sigma$ from same-season and same-weekday norms.
![Anomaly Days](docs/figures/07_anomaly_days.png)
*Takeaway: Identified 22 real demand anomaly days cleanly separated from data-quality sensor dropout and flatline days.*

---

### 8. Hourly Net Load Ramp Distribution
Histogram of hour-to-hour net load changes computed strictly between consecutive non-glitch hours exactly 1 hour apart.
![Net Load Ramps](docs/figures/08_net_load_ramps.png)
*Takeaway: 99th percentile 1-hour ramp is 16,854 MW, with a median daily maximum ramp of 13,229 MW (maximum clean 1-hour ramp: 27,899 MW). Telemetry flatlines and unfreeze spikes that previously reported fake 80,000+ MW ramps have been filtered and isolated.*

---

### 9. Pipeline Reliability and Data Completeness
Automated data quality assertion suite, records per architectural layer, and gap audit summary.
![Data Quality](docs/figures/09_data_quality.png)
*Takeaway: 9 of 9 automated assertion checks pass. The 2 documented historical multi-month gaps in the Mendeley dataset (longest: 5,881h) and 134 sensor glitches are audited and reported with complete transparency.*

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
| [Grid Controller of India (Grid-India / POSOCO)](https://grid-india.in/en/reports/daily-psp-report) | Daily PSP Reports (generation by source, peak demand met, state demand) | 2021-05-07 to 2026-10-24 (751 reports) | Public Indian government data |
| [Mendeley Data Repository (DOI: 10.17632/y58jknpgs8.2)](https://doi.org/10.17632/y58jknpgs8.2) | Hourly aggregated PMU / SCADA telemetry for demand, solar, and wind generation | 2021-09-01 to 2025-06-24 (23,184 hours across 966 days: 2021: 122, 2022: 273, 2023: 30, 2024: 366, 2025: 175) | CC BY 4.0 (Attribution 4.0 International) |
| [Open-Meteo Historical Archive & Forecast API](https://open-meteo.com/) | Hourly ECMWF ERA5 reanalysis temperature, humidity, wind across 6 cities | 2021-09-01 to Present (yesterday) | Free for non-commercial open data science |

> *Note on Weather Data:* Open-Meteo provides atmospheric data via ECMWF ERA5 numerical model reanalysis simulations, rather than physical surface weather station observations.
> *Note on Historical Telemetry:* The Mendeley historical archive repository contains 2 documented multi-month gaps between high-resolution logging campaigns (2022-10 to 2023-03 and 2023-05 to 2023-12). These are documented in [`docs/source_notes.md`](docs/source_notes.md) and tracked in [`RESULTS.md`](RESULTS.md).

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
