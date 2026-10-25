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

- **Detected & Nullified Hours:** 134 records
- **Policy:** Hours where demand plunged >25% below neighbouring hours, single-hour dips that recovered, or unfreeze spikes from stuck telemetry are set to `NULL` (never silently interpolated).

| Timestamp (IST) | Raw Value (MW) | Event Description |
|---|---|---|
| `2021-09-05T00:00` | 91,153.3 | Severe sensor glitch / dropout plunge / unfreeze spike |
| `2021-09-08T11:00` | 56,028.0 | Severe sensor glitch / dropout plunge / unfreeze spike |
| `2021-09-27T16:00` | 129,512.3 | Severe sensor glitch / dropout plunge / unfreeze spike |
| `2021-10-06T10:00` | 140,945.6 | Severe sensor glitch / dropout plunge / unfreeze spike |
| `2021-10-06T11:00` | 138,353.1 | Severe sensor glitch / dropout plunge / unfreeze spike |
| `2021-10-08T19:00` | 86,181.0 | Severe sensor glitch / dropout plunge / unfreeze spike |
| `2021-10-08T20:00` | 0.0 | Demand collapse to 0 MW |
| `2021-10-08T21:00` | 0.0 | Demand collapse to 0 MW |
| `2021-10-08T22:00` | 0.0 | Demand collapse to 0 MW |
| `2021-10-08T23:00` | 0.0 | Demand collapse to 0 MW |
| `2021-10-09T00:00` | 0.0 | Demand collapse to 0 MW |
| `2021-10-09T01:00` | 0.0 | Demand collapse to 0 MW |
| `2021-10-09T02:00` | 0.0 | Demand collapse to 0 MW |
| `2021-10-09T03:00` | 125,467.3 | Severe sensor glitch / dropout plunge / unfreeze spike |
| `2021-11-04T17:00` | 130,253.0 | Severe sensor glitch / dropout plunge / unfreeze spike |
| `2021-11-04T18:00` | 134,442.3 | Severe sensor glitch / dropout plunge / unfreeze spike |
| `2021-11-04T19:00` | 129,276.5 | Severe sensor glitch / dropout plunge / unfreeze spike |
| `2021-11-05T14:00` | 125,469.2 | Severe sensor glitch / dropout plunge / unfreeze spike |
| `2021-11-05T15:00` | 124,152.9 | Severe sensor glitch / dropout plunge / unfreeze spike |
| `2021-11-05T16:00` | 123,496.4 | Severe sensor glitch / dropout plunge / unfreeze spike |
| `2021-11-05T17:00` | 129,109.6 | Severe sensor glitch / dropout plunge / unfreeze spike |
| `2021-11-08T12:00` | 124,502.5 | Severe sensor glitch / dropout plunge / unfreeze spike |
| `2021-11-21T12:00` | 72,904.4 | Severe sensor glitch / dropout plunge / unfreeze spike |
| `2021-11-21T13:00` | 0.0 | Demand collapse to 0 MW |
| `2021-11-21T14:00` | 33,660.6 | Severe sensor glitch / dropout plunge / unfreeze spike |
| `2021-12-16T14:00` | 133,903.4 | Severe sensor glitch / dropout plunge / unfreeze spike |
| `2022-01-04T10:00` | 147,274.0 | Severe sensor glitch / dropout plunge / unfreeze spike |
| `2022-01-04T13:00` | 147,886.2 | Severe sensor glitch / dropout plunge / unfreeze spike |
| `2022-01-09T02:00` | 104,310.2 | Severe sensor glitch / dropout plunge / unfreeze spike |
| `2022-01-11T06:00` | 118,894.6 | Severe sensor glitch / dropout plunge / unfreeze spike |
| `2022-01-11T15:00` | 131,045.8 | Severe sensor glitch / dropout plunge / unfreeze spike |
| `2022-01-22T13:00` | 130,376.6 | Severe sensor glitch / dropout plunge / unfreeze spike |
| `2022-01-22T14:00` | 128,159.2 | Severe sensor glitch / dropout plunge / unfreeze spike |
| `2022-02-01T05:00` | 119,008.5 | Severe sensor glitch / dropout plunge / unfreeze spike |
| `2022-02-01T06:00` | 127,158.4 | Severe sensor glitch / dropout plunge / unfreeze spike |
| `2022-03-04T06:00` | 141,819.5 | Severe sensor glitch / dropout plunge / unfreeze spike |
| `2022-03-08T03:00` | 122,128.5 | Severe sensor glitch / dropout plunge / unfreeze spike |
| `2022-03-08T04:00` | 123,834.2 | Severe sensor glitch / dropout plunge / unfreeze spike |
| `2022-03-08T05:00` | 130,928.9 | Severe sensor glitch / dropout plunge / unfreeze spike |
| `2022-03-08T06:00` | 142,411.3 | Severe sensor glitch / dropout plunge / unfreeze spike |
| ... | ... | *(+94 additional hours isolated to NULL)* |


## Stuck Sensor & Telemetry Anomaly Log

- **Total Telemetry Anomalies Isolated:** 621 hours set to `NULL`
- **Policy:** Any run of >=3 consecutive hours with identical non-zero values, solar >500 MW at night (20:00 to 05:00 IST), or wind >35 GW is nullified.

| Category | Hours Nullified | Key Affected Dates | Description |
|---|---|---|---|
| Stuck Solar (Runs >= 3h) | 80 | 2025-03-07, 2024-12-14 | Frozen solar sensor (e.g. 64,301 MW 24h freeze on 2025-03-07) |
| Night Solar (> 500 MW) | 329 | 2021-12, 2022-01, 2024-12, 2025-03 | Telemetry bleed / inverter communication freeze between 20:00-05:00 IST |
| Stuck Wind (Runs >= 3h) | 282 | Various 2022, 2024 | Frozen wind generation telemetry runs |
| Wind Spike (> 35 GW) | 2 | 2022-08-11 21:00-22:00 | Unphysical spike to 38,701 MW (exceeds physical operating envelope) |
| Stuck Demand (Runs >= 3h) | 32 | 2025-01-10, 2025-02-03 | Telemetry freezes prior to morning pickup |
