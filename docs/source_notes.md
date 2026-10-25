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

- **Title:** *Electricity Demand, Solar and Wind Generation Data of India at 1-hour interval*
- **DOI:** [10.17632/y58jknpgs8.2](https://doi.org/10.17632/y58jknpgs8.2)
- **Authors / Contributors:** Debanjan Mukherjee, Karuna Kalita, Subhash Kumar (IIT Guwahati & Grid-India)
- **License:** Creative Commons Attribution 4.0 International (CC BY 4.0)
- **API File Discovery:** `GET https://data.mendeley.com/public-api/datasets/y58jknpgs8/files?folder_id=root&version=2&$start=0&$limit=1000` with header `Accept: application/vnd.mendeley-public-dataset.1+json`
- **Direct File Downloads:** `https://data.mendeley.com/public-files/datasets/y58jknpgs8/files/{file_id}/file_downloaded`
- **Format:** Monthly Excel (`.xlsx`) files covering 2021 to 2025.
  - Sheet `Sheet1` contains timestamped 5-minute SCADA telemetry from NLDC:
    - `TOTAL_THM_ONLY|P` (Thermal generation MW)
    - `TOTAL_NLDC_HYD|P` (Hydro generation MW)
    - `TOTAL_NLDC_GAS|P` (Gas generation MW)
    - `TOTAL_NLDC_NPC|P` (Nuclear generation MW)
    - `ALL_INDIA_WIND|P` (Wind generation MW)
    - `ALL_IND_SOLAR|P` (Solar generation MW)
    - Total demand / generation (MW)
- **Cadence:** Historical static backfill (ends mid-2025). Can be aggregated from 5-minute to 1-hour intervals.

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

## 4. data.gov.in / CEA Monthly Data (Optional State-Level Context)

- **Source:** Central Electricity Authority (CEA) monthly state-wise power supply position.
- **Access:** Requires free API key (`DATA_GOV_IN_API_KEY`).
- **Pipeline Role:** Optional enrichment table; pipeline functions seamlessly even without CEA key.
