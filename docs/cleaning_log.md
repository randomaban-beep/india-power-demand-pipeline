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
