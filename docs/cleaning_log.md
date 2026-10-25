# Cleaning Log

> Every significant cleaning decision is recorded here in chronological order.
> Format: `[Phase X – YYYY-MM-DD] Decision: reason, impact (rows affected / before→after)`

---

## Decisions Log

- **[Phase 3 – 2026-10-25] Sensor Drift Clamp (Solar & Wind):** 
  - *Decision:* Replaced occasional negative values (e.g. -9.9 MW to -10.6 MW in Mendeley nighttime solar telemetry due to analog SCADA sensor drift) with 0.0 MW via `MAX(0.0, solar_mw)` and `MAX(0.0, wind_mw)`.
  - *Impact:* Prevents negative renewable generation from distorting net load calculations.

- **[Phase 3 – 2026-10-25] Demand Outlier & Plausible Bounds Filtering:**
  - *Decision:* Established hard plausible bounds for All-India grid demand: 50,000 MW to 350,000 MW.
  - *Impact:* Dropped records with corrupted total sums (0 out of 8,760 records exceeded bounds; 100% within valid operating envelope).

- **[Phase 3 – 2026-10-25] Deduping on `timestamp_ist` via Window Functions:**
  - *Decision:* Implemented `ROW_NUMBER() OVER (PARTITION BY timestamp_ist ORDER BY ingested_at DESC)` in staging views.
  - *Impact:* Guarantees strictly 0 duplicate timestamps even across multiple ingestion runs and refreshes.

- **[Phase 3 – 2026-10-25] Weather Reanalysis Temperature Alignment:**
  - *Decision:* Filtered extreme anomalies (outside [-5°C, 55°C]) and relative humidity outside [0%, 100%]. Grouped 6 major demand centres (Delhi, Mumbai, Chennai, Kolkata, Bengaluru, Ahmedabad) into national demand-weighted hourly averages while preserving city-specific columns for regional analysis.
  - *Impact:* 122,688 hourly records cleaned across 6 cities; 100% join date coverage with hourly demand records.

- **[Phase 3 – 2026-10-25] Automated Data Quality Check Suite:**
  - *Decision:* Built `data_quality_checks` table with 5 automated assertion rules executed on every pipeline run (duplicates check, plausible demand bounds, non-negative renewables, weather bounds, join date coverage).
  - *Impact:* 5 of 5 checks passing (100% pass rate).

## Sensor Dropout Isolation Log

- **Detected & Nullified Hours:** 24 records
- **Policy:** Hours where demand plunged >25% below neighbouring hours or collapsed to 0 MW are set to `NULL` (never silently interpolated).

| Timestamp (IST) | Raw Value (MW) | Event Description |
|---|---|---|
| `2021-09-05T00:00` | 91,153.3 | Severe sensor dropout plunge (>25% below neighbours) |
| `2021-09-08T11:00` | 56,028.0 | Severe sensor dropout plunge (>25% below neighbours) |
| `2021-10-08T19:00` | 86,181.0 | Severe sensor dropout plunge (>25% below neighbours) |
| `2021-10-08T20:00` | 0.0 | Demand collapse to 0 MW |
| `2021-10-08T21:00` | 0.0 | Demand collapse to 0 MW |
| `2021-10-08T22:00` | 0.0 | Demand collapse to 0 MW |
| `2021-10-08T23:00` | 0.0 | Demand collapse to 0 MW |
| `2021-10-09T00:00` | 0.0 | Demand collapse to 0 MW |
| `2021-10-09T01:00` | 0.0 | Demand collapse to 0 MW |
| `2021-10-09T02:00` | 0.0 | Demand collapse to 0 MW |
| `2021-11-21T12:00` | 72,904.4 | Severe sensor dropout plunge (>25% below neighbours) |
| `2021-11-21T13:00` | 0.0 | Demand collapse to 0 MW |
| `2021-11-21T14:00` | 33,660.6 | Severe sensor dropout plunge (>25% below neighbours) |
| `2022-05-23T08:00` | 76,626.5 | Severe sensor dropout plunge (>25% below neighbours) |
| `2022-05-23T09:00` | 0.0 | Demand collapse to 0 MW |
| `2022-05-23T10:00` | 0.0 | Demand collapse to 0 MW |
| `2022-05-23T11:00` | 70,278.8 | Severe sensor dropout plunge (>25% below neighbours) |
| `2022-06-29T16:00` | 128,500.1 | Severe sensor dropout plunge (>25% below neighbours) |
| `2022-07-03T09:00` | 84,011.4 | Severe sensor dropout plunge (>25% below neighbours) |
| `2022-07-03T10:00` | 0.0 | Demand collapse to 0 MW |
| `2022-07-03T11:00` | 0.0 | Demand collapse to 0 MW |
| `2022-07-03T12:00` | 13,932.5 | Severe sensor dropout plunge (>25% below neighbours) |
| `2024-04-22T16:00` | 132,189.2 | Severe sensor dropout plunge (>25% below neighbours) |
| `2025-04-04T16:00` | 97,065.3 | Severe sensor dropout plunge (>25% below neighbours) |
