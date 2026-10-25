# India Power Demand & Weather Pipeline

> **Work in progress** — pipeline under active development. This README will be updated with live numbers and charts once the data pipeline is running.

---

## Problem Statement

India's electricity grid is navigating a dual transition: surging demand driven by rising temperatures and economic growth, while an expanding fleet of solar and wind plants is reshaping the daily generation mix. Understanding *how strongly temperature drives demand*, *how solar and wind are changing the net-load shape*, and *which days or hours are anomalous* is critical for grid planning, storage investment, and policy.

This project builds an **automated, end-to-end analytics pipeline** that:

1. Ingests daily Grid-India demand reports, hourly Mendeley historical data, and Open-Meteo reanalysis weather for six major demand centres.
2. Cleans and models everything in SQL (SQLite, schema-portable to Postgres).
3. Refreshes itself daily via **GitHub Actions** and commits updated figures and results back to the repo.
4. Presents findings through **static charts** embedded here and an **interactive Streamlit dashboard**.

---

## Planned Architecture

```
sources ──► ingest (Python) ──► raw layer (raw_*)
                                     │
                              clean (Python + SQL)
                                     │
                            staging layer (stg_*)
                                     │
                           modeled layer (mart_*)
                            ╱                 ╲
                    docs/figures/        Streamlit app
                    README charts        (interactive)
                                     │
                        GitHub Actions (daily cron)
              ingest → clean → model → tests → figures → RESULTS.md → commit
```

**Database:** SQLite at `data/energy.db` (committed after each CI run; raw downloads are `.gitignore`d).

---

## Key Findings

> *(Auto-generated — will be populated after pipeline first runs successfully.)*

---

## Data Sources & Licenses

| Source | Type | License / Terms |
|---|---|---|
| [Grid-India (NLDC/POSOCO) Daily PSP Report](https://report.grid-india.in) | Daily demand, peak, generation by source | Public government data; cite source |
| [Mendeley: Hourly Demand, Solar & Wind (Sep 2021–Jun 2025)](https://doi.org/10.17632/y58jknpgs8) | Hourly historical backfill | CC BY 4.0 |
| [Open-Meteo Historical API](https://open-meteo.com) | Hourly weather (model reanalysis, not station data) | Free for non-commercial use; cited accordingly |
| [data.gov.in / CEA](https://data.gov.in) | Monthly state-wise energy requirement (optional) | Government Open Data License v1.0 |

> ⚠️ Open-Meteo data is **model reanalysis**, not station observations. It may diverge from actual station readings, especially during extreme events.

---

## How to Run Locally

```bash
# 1. Clone
git clone https://github.com/randomaban-beep/india-power-demand-pipeline.git
cd india-power-demand-pipeline

# 2. Create virtual environment
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Mac/Linux:
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure secrets
cp .env.example .env
# Edit .env and add your DATA_GOV_IN_API_KEY if using CEA data

# 5. Run the full pipeline
python -m src.ingest.run_all
python -m src.clean.run_all
python -m src.model.run_all
python -m src.viz.generate_all

# 6. Run tests
pytest tests/ -v

# 7. Launch dashboard
streamlit run app/streamlit_app.py
```

---

## How the Scheduled Refresh Works

A GitHub Actions workflow (`.github/workflows/refresh.yml`) runs every day at 02:00 UTC:

1. Checks out the repo
2. Installs Python 3.11 and dependencies
3. Runs `ingest → clean → model → tests → generate figures → write RESULTS.md`
4. Commits the updated `data/energy.db`, `docs/figures/`, and `RESULTS.md` back to `main`

The raw downloads are never committed (kept in `data/raw/` which is `.gitignore`d). The SQLite DB stays well under GitHub's 50 MB warning threshold; if it grows, a Parquet export of the mart layer will replace it.

---

## Limitations

- **Reanalysis weather:** Open-Meteo uses ECMWF ERA5 model output, not station observations. Accuracy varies by region and season.
- **Backfill horizon:** The Mendeley hourly dataset ends June 2025 and cannot supply live refreshes.
- **Grid-India format changes:** The daily PSP report has changed format historically; the parser may break if the format changes again.
- **Non-commercial only:** Open-Meteo is free for non-commercial use only.

---

## Live Dashboard

> *(Link will be added after Streamlit Community Cloud deployment in Phase 6.)*

---

## Repository Topics

`data-analysis` · `sql` · `python` · `streamlit` · `energy` · `india` · `etl` · `github-actions`
