# Data Source Notes

> Written during Phase 1 feasibility check. Updated as formats change.

---

## 1. Grid-India (NLDC/POSOCO) Daily PSP Report

- **URL pattern:** https://report.grid-india.in (Daily Report > PSP Report)
- **Format findings:** *(to be filled in Phase 1)*
- **Cadence:** Daily (T+1 business day)
- **Access:** Public, no authentication required
- **Parsing approach:** *(to be confirmed in Phase 1 — PDF or Excel)*
- **Fallback if unavailable:** *(to be documented if needed)*

---

## 2. Mendeley Hourly Dataset

- **DOI:** [10.17632/y58jknpgs8](https://doi.org/10.17632/y58jknpgs8)
- **Coverage:** September 2021 – June 2025 (one-time backfill only)
- **Format:** *(to be confirmed in Phase 1)*
- **License:** CC BY 4.0
- **Citation:** *(to be completed with author, title, year from the dataset page)*

---

## 3. Open-Meteo Historical API

- **Endpoint:** `https://archive-api.open-meteo.com/v1/archive`
- **Variables used:** `temperature_2m`, `relative_humidity_2m`, `wind_speed_10m`
- **Cities / coordinates:**

| City | Lat | Lon |
|---|---|---|
| Delhi | 28.6139 | 77.2090 |
| Mumbai | 19.0760 | 72.8777 |
| Chennai | 13.0827 | 80.2707 |
| Kolkata | 22.5726 | 88.3639 |
| Bengaluru | 12.9716 | 77.5946 |
| Ahmedabad | 23.0225 | 72.5714 |

- **Note:** This is ECMWF ERA5 model reanalysis, not station observations.
- **License:** Free for non-commercial use. Citation required.
- **Rate limit:** *(to be confirmed — typically 10,000 requests/day for free tier)*

---

## 4. data.gov.in / CEA Monthly Data (Optional)

- **URL:** https://data.gov.in
- **Dataset:** CEA monthly state-wise energy requirement and availability
- **Access:** Free API key required (store as `DATA_GOV_IN_API_KEY` GitHub secret)
- **Rate limits:** *(to be confirmed in Phase 1)*
- **Format findings:** *(to be filled in Phase 1)*
