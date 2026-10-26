# Real-data smoke-test fixture

These CSVs are unmodified rows selected from the local raw database on 26 October 2026,
covering 1–7 April 2024 (IST). They support an offline, reproducible pipeline smoke test;
they are not representative enough for national conclusions or forecasting evaluation.

- Hourly demand: Mendeley dataset **10.17632/y58jknpgs8.2**, Debanjan Mukherjee,
  Karuna Kalita and Subhash Kumar, CC BY 4.0. https://doi.org/10.17632/y58jknpgs8.2
- City weather: Open-Meteo historical API, https://open-meteo.com/.
- Daily and state reports: Grid Controller of India, https://grid-india.in/en/reports/daily-psp-report.

Selection: `substr(timestamp_ist,1,10)` or `report_date` between `2024-04-01`
and `2024-04-07`, ordered by the timestamp/date. Ingestion timestamps retain original provenance.
Daily reports may be sparse. The cross-source correlation check explicitly reports SKIP
when fewer than ten overlapping days exist. The full historical archive is not bundled.
