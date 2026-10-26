# Data Source Notes

> Documented during Phase 1 feasibility check and verified against live sources.

---

## 1. Grid-India (NLDC / POSOCO) Daily PSP Report

- **Website / Portal:** [Grid Controller of India Limited (Grid-India)](https://grid-india.in/en/reports/daily-psp-report) (formerly POSOCO)
- **API Endpoint:** `POST https://webapi.grid-india.in/api/v1/file`
- **Request Payload:** `{"_source": "GRDW", "_type": "DAILY_PSP_REPORT", "_fileDate": "<year>", "_month": "<month>"}`
- **CDN Base URL for Downloads:** `https://webcdn.grid-india.in/{FilePath}`
- **Format:** Both Excel (`.xls`, BIFF8 format) and `.pdf` files are published daily.
  - Verified sample: `23.10.26_NLDC_PSP_514.xls` (296 KB) and `23.10.26_NLDC_PSP_694.pdf` (1.69 MB).
  - Excel contains 5 sheets: `MOP_E`, `MOP_E1`, `IR-Line`, `CrossBorder`, `TimeSeries`.
  - Sheet `MOP_E` contains:
    - All-India Demand Met (MW) at Evening Peak
    - All-India Energy Met (MU)
    - Hydro, Wind, Solar Generation (MU)
    - Energy Shortage (MU)
    - Maximum Demand Met during the day (MW) and Time of peak
    - Fuel-wise Gross Generation breakdown (Coal, Lignite, Hydro, Nuclear, Gas, RES)
    - State-wise Demand Met and Energy Met for all 5 regions (NR, WR, SR, ER, NER)
- **Cadence:** Daily (T+1 day published around 10:30 IST).
- **Access:** Public, no API key required.
- **Parsing Approach:** Use `xlrd` (pure Python, fast, robust) for `.xls` parsing, with fallback to `pdfplumber` for `.pdf` files.

---

## 2. Mendeley Hourly Dataset (Historical Backfill)

- **Title:** *Electricity Demand, Solar and Wind Generation Data (Sept 2021 to Jun 2025) of India at 1-hour interval*
- **DOI:** [10.17632/y58jknpgs8.2](https://doi.org/10.17632/y58jknpgs8.2)
- **Authors / Contributors:** Debanjan Mukherjee, Karuna Kalita, Subhash Kumar (IIT Guwahati & Grid Controller of India)
- **License:** Creative Commons Attribution 4.0 International (CC BY 4.0) — verified on Mendeley repository page.
- **Measurement Methodology:** PMU / SCADA telemetry (Phasor Measurement Unit and Supervisory Control and Data Acquisition telemetry from regional/national load despatch centers).
- **Temporal Coverage:** 966 distinct days of hourly data (23,184 hourly observations spanning `2021-09-01T00:00` to `2025-06-24T23:00`).
  - **Per-Year Coverage Breakdown:**
    - `2021`: 122 days (Sept – Dec)
    - `2022`: 273 days (Jan – Sept)
    - `2023`: 30 days (April)
    - `2024`: 366 days (Full leap year)
    - `2025`: 175 days (Jan – June 24)
    - **Total:** 966 days
- **Repository Structure & Ingestion Details:**
  - In version 2 of the dataset, 29 separate spreadsheet files are hosted across distinct logging campaigns:
    1. **Sept 2021 – Sept 2022:** Monthly Excel files containing 5-minute SCADA telemetry (`TOTAL_THM_ONLY|P`, `TOTAL_NLDC_HYD|P`, `TOTAL_NLDC_GAS|P`, `TOTAL_NLDC_NPC|P`, `ALL_INDIA_WIND|P`, `ALL_IND_SOLAR|P`). Aggregated to 1-hour intervals (9,480 rows).
    2. **Oct 2022 – Dec 2023:** 10-second ultra-high-resolution SCADA telemetry files (~48 MB per monthly file, >260,000 rows each), from which April 2023 was bundled in standard size (720 rows).
    3. **Jan 2024 – June 2025:** Pre-aggregated 1-hour interval national SCADA dataset in `January 2024- June 2025.xlsx` under sheet `'Report'` with columns `Timestamp`, `Demand (MW)`, `Wind (MW)`, `Solar (MW)`, and `Total Generation (MW)` (12,984 rows).
  - **Temporal Continuity & Documented Repository Limitations:**
    - Gap 1: `2022-09-30 23:00` to `2023-04-01 00:00` (4,369 hours, spanning winter 2022-23 and post-monsoon).
    - Gap 2: `2023-04-30 23:00` to `2024-01-01 00:00` (5,881 hours, spanning monsoon and post-monsoon 2023).
    - Both gaps are present in this project’s selected extract; the loader excludes most files over 20 MB, so these are not evidence that the source repository lacks the corresponding data, audited by `src/clean/quality_checks.py`, and recorded transparently in `RESULTS.md` and Chart 9.
- **Cadence:** Historical backfill (ends mid-2025). Live daily refreshes are fulfilled continuously via Grid-India Daily PSP reports.

---

## 3. Open-Meteo Historical Weather API

- **Endpoint:** `https://archive-api.open-meteo.com/v1/archive`
- **Access:** Public, free for non-commercial use, no API key required.
- **Data Model:** ECMWF ERA5 reanalysis (model simulation, not station observations).
- **Variables Retrieved:**
  - `temperature_2m` (°C)
  - `relative_humidity_2m` (%)
  - `wind_speed_10m` (km/h)
- **Cities & Coordinates:**
  - Delhi: (28.6139, 77.2090)
  - Mumbai: (19.0760, 72.8777)
  - Chennai: (13.0827, 80.2707)
  - Kolkata: (22.5726, 88.3639)
  - Bengaluru: (12.9716, 77.5946)
  - Ahmedabad: (23.0225, 72.5714)
- **Timezone:** Retrieved with `timezone=Asia/Kolkata` for automatic alignment to Indian Standard Time (IST, UTC+5:30).

---

## 4. Scope and verification

The CEA/data.gov.in enrichment is not implemented. No API key is required.
The archive API uses its default model selection (not explicitly pinned to ERA5); recent records can come from the forecast API. Model provenance is not stored per row. The city aggregate is unweighted. Source-portal counts above are historical notes, not a current completeness guarantee.
