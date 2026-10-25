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
| **Controlled Temperature Elasticity** | **about 8 GW per °C** (+7,780 MW/°C at 25°C base, 95% CI: [6,975, 8,585] MW/°C, White's HC1 SE: 410.7 MW/°C; controls $R^2=0.7961$, full $R^2=0.8683$, incremental $\Delta R^2=+0.0722$ across 725 days; sensitivity across 22°C–28°C spans 5.9 GW to 10.0 GW) | Controlling for day-of-week, calendar month, and multi-year economic trend, every 1°C increase above 25°C adds about 8 GW of national peak cooling demand. Temperature accounts for an incremental +0.0722 of variance beyond seasonal/trend controls. |
| **Midday Solar Suppression** | **~46,005 MW** midday solar belly depth | Midday net load is significantly depressed during summer months, requiring steep thermal ramp-downs followed by aggressive evening ramp-ups. |
| **Grid Ramping Stress** | **16,768 MW** 99th percentile 1-hour ramp; **13,093 MW** median daily peak ramp | Solar sunset coinciding with evening industrial and domestic peak creates predictable tail ramping stress; largest remaining 1-hour ramp is **26,577 MW** (not independently validated). |
| **Renewable Penetration** | **11.1%** average daily share of electricity demand (peaking at **22.4%** on 2025-05-31) | Cross-validated against official Grid-India daily reports (share of generation, peaking at 21.9% on the exact same date; Pearson $r = 0.9875$, mean difference -0.36%). Solar and wind generation are actively reshaping the diurnal load curve across all five regional grids. |
| **Peak Demand Benchmark** | **248,688 MW** in hourly dataset window (2024-05-30) | Highest demand met recorded among loaded Grid-India daily reports reached **270,820 MW** (2026-05-21). |
| **Data Quality & Telemetry Audit** | **337 glitch hours nullified** (including 177 multi-hour dips); **2 historical gaps audited** | High-frequency telemetry spans 966 days (2021: 122, 2022: 273, 2023: 30, 2024: 366, 2025: 175); 2 documented multi-month gaps in the historical archive; dropouts, multi-hour dips, and flatlined sensors were isolated and set to `NULL` (never silently interpolated). |

---

## 📊 Core Visual Findings

### 1. Daily Demand Growth and Seasonality
Continuous time-series tracking daily average demand, 7-day rolling baseline, and dataset peak demand.
![Daily Demand](docs/figures/01_daily_demand.png)
*Takeaway: Demonstrates persistent summer peak escalation (reaching 248,688 MW in the hourly dataset and 270,820 MW in loaded national daily reports) contrasted with winter base troughs (~104,310 MW).*

---

### 2. Controlled Temperature Sensitivity of Electricity Demand
Daily peak demand regressed against multi-city daily mean temperature, with categorical controls for weekday, month, and year trend.
![Temperature vs Demand](docs/figures/02_temp_vs_demand.png)
*Takeaway: Daily peak demand expands at about 8 GW per °C (+7,780 MW/°C at 25.0°C base, 95% CI: [6,975, 8,585] MW/°C, White's HC1 SE: 410.7 MW/°C, full model $R^2=0.8683$, incremental $\Delta R^2=+0.0722$, $N=725$ observations) above the 25.0°C cooling base.*

#### Candidate Threshold Sensitivity Analysis (22°C to 28°C)

Evaluated on the same full sample of 725 daily observations using an OLS regression with a hinge term $\max(T - T^*, 0)$ and categorical controls for day-of-week, calendar month, and multi-year economic trend:

| Threshold (°C) | Days $\ge T$ ($N$) | Observations ($N$) | Slope (MW/°C) | White's HC1 SE | 95% Confidence Interval | Controls $R^2$ | Full $R^2$ | Incremental $\Delta R^2$ | AIC |
|---|---|---|---|---|---|---|---|---|---|
| **22.0°C** | 631 | 725 | +5,912.6 | 433.6 | [5,062.7, 6,762.4] | 0.7961 | 0.8495 | **+0.0534** | 13,320.5 |
| **23.0°C** | 590 | 725 | +6,437.6 | 430.2 | [5,594.4, 7,280.9] | 0.7961 | 0.8555 | **+0.0595** | 13,290.6 |
| **24.0°C** | 546 | 725 | +7,054.9 | 421.5 | [6,228.7, 7,881.1] | 0.7961 | 0.8614 | **+0.0653** | 13,260.6 |
| **25.0°C** **(Selected Base)** | 517 | 725 | +7,780.1 | 410.7 | [6,975.2, 8,585.0] | 0.7961 | 0.8683 | **+0.0722** | 13,223.8 |
| **26.0°C** | 479 | 725 | +8,447.7 | 391.6 | [7,680.1, 9,215.2] | 0.7961 | 0.8730 | **+0.0770** | 13,197.1 |
| **27.0°C** | 413 | 725 | +9,259.0 | 401.1 | [8,472.9, 10,045.1] | 0.7961 | 0.8731 | **+0.0770** | 13,196.8 |
| **28.0°C** | 272 | 725 | +10,044.2 | 452.4 | [9,157.5, 10,930.8] | 0.7961 | 0.8616 | **+0.0656** | 13,259.4 |


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
*Takeaway: Intermittent renewables account for an average of 11.1% of electricity demand, reaching a recorded daily peak of 22.4% of demand (cross-validated against official Grid-India generation reports, $r = 0.9875$).*

---

### 6. Monthly Peak Demand Growth
Year-over-year peak demand comparison across calendar months.
![Monthly Peak Demand](docs/figures/06_peak_demand_by_month.png)
*Takeaway: Quantifies steady year-on-year electrification growth and rising cooling intensity across peak summer seasons.*

---

### 7. Demand Anomaly Detection
Identification of statistically anomalous grid demand days exceeding $\pm 2\sigma$ from same-season and same-weekday norms.
![Anomaly Days](docs/figures/07_anomaly_days.png)
*Takeaway: Identified 24 real demand anomaly days cleanly separated from data-quality sensor dropout and flatline days.*

---

### 8. Hourly Net Load Ramp Distribution
Histogram of hour-to-hour net load changes computed strictly between consecutive non-glitch hours exactly 1 hour apart.
![Net Load Ramps](docs/figures/08_net_load_ramps.png)
*Takeaway: 99th percentile 1-hour ramp is 16,768 MW, with a median daily maximum ramp of 13,093 MW (largest remaining 1-hour ramp: 26,577 MW, not independently validated). Telemetry flatlines, multi-hour dips, and unfreeze spikes that previously reported fake 80,000+ MW ramps have been filtered and isolated.*

#### Largest Remaining Ramps (Not Independently Validated, Flagged for Manual Review)

| Timestamp (IST) | Demand (MW) | Solar (MW) | Wind (MW) | Net Load (MW) | 1-Hour Ramp (MW) | Grid-India Daily Peak Met (MW) | Validation Status |
|---|---|---|---|---|---|---|---|
| `2024-01-27T07:00` | 195,828 | 2,243 | 10,085 | 183,500 | +26,577 | *(Report unarchived)* | Pending external report |
| `2025-01-21T17:00` | 199,637 | 8,472 | 2,608 | 188,557 | +25,329 | 226,044 | Consistent with daily peak |
| `2025-01-20T07:00` | 203,719 | 2,888 | 4,469 | 196,362 | +23,794 | *(Report unarchived)* | Pending external report |
| `2024-01-30T12:00` | 193,152 | 34,864 | 861 | 157,427 | -23,229 | *(Report unarchived)* | Pending external report |
| `2025-05-06T16:00` | 196,770 | 27,116 | 8,709 | 160,945 | +22,940 | 202,394 | Consistent with daily peak |
| `2025-01-13T07:00` | 198,424 | 1,911 | 10,859 | 185,654 | +21,772 | *(Report unarchived)* | Pending external report |
| `2025-01-24T06:00` | 187,239 | 110 | 12,183 | 174,946 | +21,393 | *(Report unarchived)* | Pending external report |
| `2025-01-28T15:00` | 212,517 | 32,190 | 2,244 | 178,083 | +21,336 | *(Report unarchived)* | Pending external report |
| `2025-01-21T06:00` | 184,326 | 139 | 5,668 | 178,519 | +21,195 | 226,044 | Consistent with daily peak |
| `2025-01-06T07:00` | 199,238 | 3,066 | 10,185 | 185,988 | +21,145 | 223,964 | Consistent with daily peak |
| `2024-12-19T06:00` | 181,023 | 299 | 5,956 | 174,769 | +21,015 | *(Report unarchived)* | Pending external report |
| `2025-01-22T06:00` | 186,839 | 184 | 6,773 | 179,881 | +20,922 | 228,085 | Consistent with daily peak |
| `2025-01-07T06:00` | 182,418 | 213 | 11,454 | 170,751 | +20,797 | *(Report unarchived)* | Pending external report |
| `2024-12-18T06:00` | 178,890 | 356 | 7,732 | 170,802 | +20,781 | *(Report unarchived)* | Pending external report |
| `2025-01-06T06:00` | 175,987 | 641 | 10,503 | 164,843 | +20,581 | 223,964 | Consistent with daily peak |
| `2025-01-15T07:00` | 190,680 | 2,055 | 11,028 | 177,598 | +20,542 | *(Report unarchived)* | Pending external report |
| `2022-05-06T15:00` | 172,503 | 23,446 | 4,792 | 144,265 | -20,492 | *(Report unarchived)* | Pending external report |
| `2025-01-18T07:00` | 199,876 | 2,516 | 8,229 | 189,131 | +20,440 | *(Report unarchived)* | Pending external report |
| `2025-01-29T06:00` | 193,557 | 270 | 6,001 | 187,286 | +20,431 | *(Report unarchived)* | Pending external report |
| `2025-01-27T06:00` | 179,649 | 275 | 3,564 | 175,809 | +20,362 | *(Report unarchived)* | Pending external report |
| `2025-01-24T07:00` | 209,896 | 2,850 | 11,812 | 195,235 | +20,290 | *(Report unarchived)* | Pending external report |
| `2025-01-13T06:00` | 175,325 | 232 | 11,212 | 163,882 | +20,284 | *(Report unarchived)* | Pending external report |
| `2022-03-09T01:00` | 136,384 | 0 | 7,620 | 128,763 | -20,251 | 192,026 | Consistent with daily peak |
| `2025-01-27T07:00` | 203,595 | 3,472 | 4,096 | 196,027 | +20,218 | *(Report unarchived)* | Pending external report |
| `2025-01-30T06:00` | 191,596 | 171 | 6,473 | 184,953 | +20,212 | *(Report unarchived)* | Pending external report |
| `2025-01-28T06:00` | 190,398 | 100 | 4,078 | 186,221 | +20,160 | *(Report unarchived)* | Pending external report |
| `2025-01-07T07:00` | 204,467 | 2,577 | 11,033 | 190,856 | +20,106 | *(Report unarchived)* | Pending external report |
| `2024-01-09T07:00` | 191,230 | 975 | 9,421 | 180,834 | +20,053 | *(Report unarchived)* | Pending external report |
| `2024-12-20T06:00` | 182,141 | 317 | 10,767 | 171,058 | +20,027 | *(Report unarchived)* | Pending external report |
| `2025-01-16T07:00` | 194,095 | 2,304 | 10,130 | 181,661 | +20,018 | 220,355 | Consistent with daily peak |


---

### 9. Pipeline Reliability and Data Completeness
Automated data quality assertion suite, records per architectural layer, and gap audit summary.
![Data Quality](docs/figures/09_data_quality.png)
*Takeaway: Automated assertion suite verifies data cleaning and independent cross-validation. The 2 documented historical multi-month gaps in the Mendeley dataset (longest: 5,881h) and 337 sensor glitches are audited and reported with complete transparency.*

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
| [Grid Controller of India (Grid-India / POSOCO)](https://grid-india.in/en/reports/daily-psp-report) | Daily PSP Reports (generation by source, peak demand met, state demand) | 2021-05-07 to 2026-10-24 (751 reports: 2021: 52, 2022: 81, 2023: 77, 2024: 82, 2025: 162, 2026: 297)* | Public Indian government data |
| [Mendeley Data Repository (DOI: 10.17632/y58jknpgs8.2)](https://doi.org/10.17632/y58jknpgs8.2) | Hourly aggregated PMU / SCADA telemetry for demand, solar, and wind generation | 2021-09-01 to 2025-06-24 (23,184 hours across 966 days: 2021: 122, 2022: 273, 2023: 30, 2024: 366, 2025: 175) | CC BY 4.0 (Attribution 4.0 International) |
| [Open-Meteo Historical Archive & Forecast API](https://open-meteo.com/) | Hourly ECMWF ERA5 reanalysis temperature, humidity, wind across 6 cities | 2021-09-01 to Present (yesterday) | Free for non-commercial open data science |

> *\*Note on Daily PSP Coverage:* Earlier years have fewer reports because the Grid-India portal published older historical reports primarily as PDF files with irregular file naming rather than direct Excel spreadsheets.
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

## 🌐 Live Interactive Dashboard

Access the interactive dashboard:
👉 **[Launch Streamlit Dashboard](https://share.streamlit.io/)** *(or run locally with `streamlit run app/streamlit_app.py`)*
