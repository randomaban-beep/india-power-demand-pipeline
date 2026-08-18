# India Power Demand & Weather Pipeline

[![Daily Pipeline Refresh](https://github.com/randomaban-beep/india-power-demand-pipeline/actions/workflows/refresh.yml/badge.svg)](https://github.com/randomaban-beep/india-power-demand-pipeline/actions/workflows/refresh.yml)
[![Python 3.11](https://img.shields.io/badge/Python-3.11-brightgreen.svg)](https://www.python.org/)
[![Database: SQLite](https://img.shields.io/badge/Database-SQLite-lightgrey.svg)](data/energy_marts.db)

An automated data engineering and analytics pipeline tracking India's electricity demand, fuel-wise generation, and weather variables across multi-year operating horizons. Daily operational data (Grid-India / POSOCO daily PSP reports) and multi-city ERA5 reanalysis weather (Open-Meteo) update continuously via GitHub Actions; high-frequency PMU / SCADA telemetry (Mendeley DOI: 10.17632/y58jknpgs8.2) is preserved as a static historical research archive (2021–2025). The pipeline cleans and models data in SQLite; validates data integrity via automated quality assertions and sanity guards; persists the rolling state to a GitHub release asset (`energy.db.gz`); and renders publication-ready visualisations and a custom responsive web application with FastAPI and Apache ECharts.

---

## ⚡ Executive Summary & Key Findings

> **Note on Data Synchronization:** All figures and metrics below are generated dynamically from `data/energy.db` via `src/model/write_results.py` and are identical to [`RESULTS.md`](RESULTS.md).

| Finding | Metric / Evidence | Strategic Takeaway ("So What") |
|---|---|---|
| **Controlled Temperature Elasticity** | **about 8 GW per °C** (+{{COOLING_SLOPE_MW}} MW/°C at 25°C base, 95% CI: [{{COOLING_CI_LOWER}}, {{COOLING_CI_UPPER}}] MW/°C, White's HC1 SE: {{COOLING_SE_HC1}} MW/°C; controls $R^2={{COOLING_R2_CTRL}}$, full $R^2={{COOLING_R2_FULL}}$, incremental $\Delta R^2=+{{COOLING_DELTA_R2}}$ across {{TOTAL_OBS_DAYS}} days; sensitivity across 22°C–28°C spans {{COOLING_SLOPE_RANGE}}) | Controlling for day-of-week, calendar month, and multi-year economic trend, every 1°C increase above 25°C adds about 8 GW of national peak cooling demand. Temperature accounts for an incremental +{{COOLING_DELTA_R2}} of variance beyond seasonal/trend controls. |
| **Midday Solar Suppression** | **~{{MIDDAY_SOLAR_BELLY_MW}} MW** midday solar belly depth | Midday net load is significantly depressed during summer months, requiring steep thermal ramp-downs followed by aggressive evening ramp-ups. |
| **Grid Ramping Stress** | **{{P99_1H_RAMP_MW}} MW** 99th percentile 1-hour ramp; **{{MEDIAN_DAILY_MAX_RAMP_MW}} MW** median daily peak ramp | Solar sunset coinciding with evening industrial and domestic peak creates predictable tail ramping stress; largest remaining 1-hour ramp is **{{MAX_1H_RAMP_MW}} MW** (not independently validated). |
| **Renewable Penetration** | **{{RE_AVG_SHARE}}%** average daily share of electricity demand (peaking at **{{RE_PEAK_SHARE}}%** on 2025-05-31) | Cross-validated against official Grid-India daily reports (share of generation, peaking at 21.9% on the exact same date; Pearson $r = {{RE_CROSS_CORR}}$, mean difference {{RE_CROSS_DIFF}}%). Solar and wind generation are actively reshaping the diurnal load curve across all five regional grids. |
| **Peak Demand Benchmark** | **{{PEAK_HOURLY_DEMAND_MW}} MW** in hourly dataset window ({{PEAK_HOURLY_DATE}}) | Highest demand met recorded among loaded Grid-India daily reports reached **{{ALL_TIME_GRID_PEAK_MW}} MW** ({{ALL_TIME_GRID_PEAK_DATE}}). |
| **Data Quality & Telemetry Audit** | **{{UNIQUE_NULL_HOURS}} unique hours with any NULL** in demand, solar, or wind (including {{DROPOUTS_REMOVED}} glitch hours and {{MULTI_HOUR_DIPS}} multi-hour dips); **{{TOTAL_GAPS_COUNT}} historical gaps audited** | High-frequency telemetry spans {{TOTAL_HOURLY_DAYS}} days ({{YEAR_BREAKDOWN}}); 2 documented multi-month gaps in the historical archive; dropouts, multi-hour dips, and flatlined sensors were isolated and set to `NULL` (never silently interpolated). |

---

## 📊 Core Visual Findings

### 1. Daily Demand Growth and Seasonality
Continuous time-series tracking daily average demand, 7-day rolling baseline, and dataset peak demand.
![Daily Demand](docs/figures/01_daily_demand.png)
*Takeaway: Demonstrates persistent summer peak escalation (reaching {{PEAK_HOURLY_DEMAND_MW}} MW in the hourly dataset and {{ALL_TIME_GRID_PEAK_MW}} MW in loaded national daily reports) contrasted with winter base troughs (~{{WINTER_TROUGH_MW}} MW).*

---

### 2. Controlled Temperature Sensitivity of Electricity Demand
Daily peak demand regressed against multi-city daily mean temperature, with categorical controls for weekday, month, and year trend.
![Temperature vs Demand](docs/figures/02_temp_vs_demand.png)
*Takeaway: Daily peak demand expands at about 8 GW per °C (+{{COOLING_SLOPE_MW}} MW/°C at 25.0°C base, 95% CI: [{{COOLING_CI_LOWER}}, {{COOLING_CI_UPPER}}] MW/°C, White's HC1 SE: {{COOLING_SE_HC1}} MW/°C, full model $R^2={{COOLING_R2_FULL}}$, incremental $\Delta R^2=+{{COOLING_DELTA_R2}}$, $N={{TOTAL_OBS_DAYS}}$ observations) above the 25.0°C cooling base.*

#### Candidate Threshold Sensitivity Analysis (22°C to 28°C)

Evaluated on the same full sample of {{TOTAL_OBS_DAYS}} daily observations using an OLS regression with a hinge term $\max(T - T^*, 0)$ and categorical controls for day-of-week, calendar month, and multi-year economic trend:

{{THRESHOLD_TABLE}}

---

### 3. Diurnal Peak Load by Month
Heatmap of average hourly demand across hours of the day (IST) and calendar months.
![Demand Heatmap](docs/figures/03_demand_heatmap.png)
*Takeaway: Grid strain concentrates heavily in evening peak hours (19:00–22:00 IST) during pre-monsoon summer months (April–June).*

---

### 4. Diurnal Net Load Profile ("Duck Curve")
Net load profile by season: gross demand, solar and wind generation, and net load.
![Net Load Profile](docs/figures/04_duck_curve.png)
*Takeaway: Midday solar generation suppresses net load by ~{{MIDDAY_SOLAR_BELLY_MW}} MW during peak summer solar hours, creating steep ramp requirements at dusk.*

---

### 5. Renewable Generation Share & Generation Mix
Daily renewable energy share distribution and generation breakdown by technology.
![Renewable Share](docs/figures/05_renewable_share.png)
*Takeaway: Intermittent renewables account for an average of {{RE_AVG_SHARE}}% of electricity demand, reaching a recorded daily peak of {{RE_PEAK_SHARE}}% of demand (cross-validated against official Grid-India generation reports, $r = {{RE_CROSS_CORR}}$).*

---

### 6. Monthly Peak Demand Growth
Year-over-year peak demand comparison across calendar months.
![Monthly Peak Demand](docs/figures/06_peak_demand_by_month.png)
*Takeaway: Quantifies steady year-on-year electrification growth and rising cooling intensity across peak summer seasons.*

---

### 7. Demand Anomaly Detection
Identification of statistically anomalous grid demand days exceeding $\pm 2\sigma$ from same-season and same-weekday norms.
![Anomaly Days](docs/figures/07_anomaly_days.png)
*Takeaway: Identified {{REAL_ANOMALIES_COUNT}} real demand anomaly days cleanly separated from data-quality sensor dropout and flatline days.*

---

### 8. Hourly Net Load Ramp Distribution
Histogram of hour-to-hour net load changes computed strictly between consecutive non-glitch hours exactly 1 hour apart.
![Net Load Ramps](docs/figures/08_net_load_ramps.png)
*Takeaway: 99th percentile 1-hour ramp is {{P99_1H_RAMP_MW}} MW, with a median daily maximum ramp of {{MEDIAN_DAILY_MAX_RAMP_MW}} MW (largest remaining 1-hour ramp: {{MAX_1H_RAMP_MW}} MW, not independently validated). Telemetry flatlines, multi-hour dips, and unfreeze spikes that previously reported fake 80,000+ MW ramps have been filtered and isolated.*

#### Largest Remaining Ramps (Not Independently Validated, Flagged for Manual Review)

{{TOP_TAIL_RAMPS_TABLE}}

---

### 9. Pipeline Reliability and Data Completeness
Automated data quality assertion suite, records per architectural layer, and gap audit summary.
![Data Quality](docs/figures/09_data_quality.png)
*Takeaway: Automated assertion suite verifies data cleaning and independent cross-validation. The {{TOTAL_GAPS_COUNT}} documented historical multi-month gaps in the Mendeley dataset (longest: {{LONGEST_GAP_HOURS}}h) and {{DROPOUTS_REMOVED}} sensor glitches are audited and reported with complete transparency.*

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
| [Grid Controller of India (Grid-India / POSOCO)](https://grid-india.in/en/reports/daily-psp-report) | Daily PSP Reports (generation by source, peak demand met, state demand; updated daily via CI) | {{DAILY_SPAN_START}} to {{DAILY_SPAN_END}} ({{TOTAL_DAILY_REPORTS}} reports: {{PSP_YEAR_BREAKDOWN}})* | Public Indian government data |
| [Mendeley Data Repository (DOI: 10.17632/y58jknpgs8.2)](https://doi.org/10.17632/y58jknpgs8.2) | Hourly aggregated PMU / SCADA telemetry for demand, solar, and wind generation (static historical research archive) | {{HOURLY_SPAN_START}} to {{HOURLY_SPAN_END}} ({{TOTAL_STORED_HOURS}} hours across {{TOTAL_HOURLY_DAYS}} days: {{YEAR_BREAKDOWN}}) | CC BY 4.0 (Attribution 4.0 International) |
| [Open-Meteo Historical Archive & Forecast API](https://open-meteo.com/) | Hourly ECMWF ERA5 reanalysis temperature, humidity, wind across 6 cities (incremental daily updates through yesterday) | 2021-09-01 to Present (yesterday) | Free for non-commercial open data science |

> *\*Note on Daily PSP Coverage (API Listed vs Parsed):* {{PSP_COVERAGE_EXPLANATION}}
> *Note on Weather Data:* Open-Meteo provides atmospheric data via ECMWF ERA5 numerical model reanalysis simulations, rather than physical surface weather station observations.
> *Note on Historical Telemetry:* The Mendeley historical archive repository contains 2 documented multi-month gaps between high-resolution logging campaigns (2022-10 to 2023-03 and 2023-05 to 2023-12). These are documented in [`docs/source_notes.md`](docs/source_notes.md) and tracked in [`RESULTS.md`](RESULTS.md).

---

## 🔄 Automated Daily Rebuild & Release Storage Architecture

The GitHub Actions workflow [`.github/workflows/refresh.yml`](.github/workflows/refresh.yml) runs daily (at 06:30 UTC / 12:00 IST) and on manual dispatch (`workflow_dispatch`). Rather than rebuilding the multi-year database from scratch on every run, the runner restores rolling state from a GitHub Release asset tagged `data-latest`:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        GITHUB ACTIONS RUNNER                           │
│                                                                        │
│  1. Restore Database                                                   │
│     gh release download data-latest --pattern energy.db.gz             │
│     gunzip data/energy.db.gz (fails if missing or < 1 MB)              │
│                                                                        │
│  2. Diagnostics & Ingestion                                            │
│     • Connectivity check to Grid-India catalog API                     │
│     • Incremental fetch: Grid-India daily PSP reports                  │
│     • Incremental fetch: Open-Meteo ERA5 weather (latest - 7d to yday) │
│     • Static archive: Mendeley SCADA skipped if raw rows exist         │
│                                                                        │
│  3. Processing & Analytical Marts                                      │
│     • Staging clean + dropout/flatline filters (src/clean/run_all)     │
│     • Mart generation + OLS cooling sensitivity (src/model/run_all)    │
│     • PowerBI slim database export (data/energy_marts.db)              │
│                                                                        │
│  4. Validation & Quality Gates                                         │
│     • Full test suite (REQUIRE_FULL_DB=1 pytest tests/ -v)             │
│     • Sanity guard: row count monotonic growth, non-empty marts,       │
│       freshness checks for weather (≤ 3d) & PSP (≤ 7d)                 │
│                                                                        │
│  5. Release Sync & Commit                                              │
│     • Gzip data/energy.db -> data/energy.db.gz                         │
│     • gh release upload data-latest data/energy.db.gz --clobber        │
│     • Commit slim marts, updated figures & results (git pull --rebase) │
└────────────────────────────────────────────────────────────────────────┘
```

### Seeding / Bootstrapping the Rolling Release
To seed or re-seed the rolling database asset initially:

```bash
# 1. Compress the local full database
gzip -c data/energy.db > data/energy.db.gz

# 2. Upload to GitHub Release tagged 'data-latest'
gh release create data-latest data/energy.db.gz --title "Latest Energy Database" --notes "Rolling database asset for daily GitHub Actions pipeline" || \
gh release upload data-latest data/energy.db.gz --clobber
```

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

### 3. Launch Custom Web Application & API
```bash
uvicorn server.main:app --reload --port 8000
```
Open [http://localhost:8000](http://localhost:8000) in your browser. Interactive Swagger API documentation is available at [http://localhost:8000/docs](http://localhost:8000/docs).

---

## 🌐 Live Website & Cloud Deployment

- **Live URL:** `https://india-power-demand-pipeline.onrender.com` *(Deployment URL placeholder)*
- **Interactive API Docs:** `https://india-power-demand-pipeline.onrender.com/docs`

### Cloud Deployment (Render / Docker)
The application includes a production-ready `Dockerfile` and `render.yaml` for automated deployment on Render's free tier:
1. Connect this repository to [Render](https://render.com).
2. Create a **Web Service** selecting this repository.
3. Render automatically detects `render.yaml` and deploys with:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `uvicorn server.main:app --host 0.0.0.0 --port $PORT`

Alternatively, run with Docker locally:
```bash
docker build -t india-power-pipeline .
docker run -p 8000:8000 india-power-pipeline
```

---

## 🔌 API Endpoints Reference

All analytical endpoints accept optional parameters: `?from=YYYY-MM-DD&to=YYYY-MM-DD&seasons=Summer,Winter`.

| Endpoint | Method | Description | Source Mart / Model |
|---|---|---|---|
| `/api/summary` | `GET` | Headline operational KPIs (latest/record peak, RE share, record counts, audit status) | `stg_daily_psp`, `mart_temp_vs_demand`, `pipeline_runs` |
| `/api/daily-demand` | `GET` | Daily average and peak demand met with 7-day rolling baseline | `mart_anomaly_days` |
| `/api/monthly-peaks` | `GET` | Monthly peak demand escalation and year-over-year percentage growth | `mart_monthly_peak_demand` |
| `/api/temp-demand` | `GET` | Hourly temperature vs demand response with median 1°C bins (`?feature=avg_temperature_c\|delhi_temp_c\|mumbai_temp_c`) | `mart_temp_vs_demand` |
| `/api/heatmap` | `GET` | 12×24 matrix of average demand across calendar months and diurnal hours | `mart_temp_vs_demand` |
| `/api/sensitivity` | `GET` | Full-sample hinge OLS cooling sensitivity model parameters, robust HC1 SEs, and candidate thresholds | `compute_temperature_sensitivity()` |
| `/api/duck-curve` | `GET` | Diurnal generation profile (demand, solar, wind, net load) and dusk ramping metrics (`?season=All\|Summer\|...`) | `mart_net_load_profile` |
| `/api/re-share` | `GET` | Monthly average renewable penetration share and capacity breakdown | `mart_net_load_profile` |
| `/api/anomalies` | `GET` | Daily z-score series segmented by real demand outliers (±2σ) and isolated data glitches | `mart_anomaly_days` |
| `/api/ramps` | `GET` | Top 10 one-hour net-load ramping stress events cross-checked with Grid-India daily peak met | `mart_net_load_ramps`, `stg_daily_psp` |
| `/api/health` | `GET` | Automated data quality assertions, pipeline execution audit log, and database table volume | `data_quality_checks`, `pipeline_runs` |
| `/api/export/{name}.csv` | `GET` | Parameterised CSV streaming download for analytical marts (`daily-demand`, `anomalies`, `ramps`, `monthly-peaks`) | `server/queries.py` |
