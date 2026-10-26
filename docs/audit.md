# Initial audit — 26 October 2026

Local `main` and GitHub `main` both resolved to `5e86c18b941e7985513edeb860bb4d2eb3663b0b`.
The working tree was clean. The `custom-website` branch was older; its frontend was already
present in main, with additional recent-report support on main. Backup branches were retained.
The audit covered tracked source, SQL, both frontends, tests, notebook, deployment, generated
reports and local raw/processed data inventories. Virtualenv and Git internals are not project source.

Architecture: Grid-India PSP + Mendeley telemetry + Open-Meteo -> raw SQLite -> Python/SQL
staging -> seven SQL marts -> FastAPI/ECharts, Streamlit, CSV/Parquet, figures and report.
The existing test suite passed 27 tests (5.50 seconds); lint reported 25 findings, including
an undefined `xls_path` in the PSP parser. No forecasting service exists.

Priority findings:

1. Writes could fall back to the committed slim database; quality failures did not fail clean;
   exports swallowed failures and could leave incomplete snapshots.
2. Cleaner used an unmasked median series, ignored gaps in stuck-sensor groups, and expanded
   multi-hour dips into healthy boundary hours. Duplicate conflicts were silently grouped.
3. Weather arrays were zipped without length checks; Mendeley could silently return success
   after failed/empty downloads. API read-only connections fell back to writable connections.
4. Missing-year YoY and December season semantics were inconsistent; row-based rolling
   averages were labeled seven-day averages despite gaps.
5. HTML character replacements corrupted dates, headings, CSS classes, SVG paths and controls.
   Static claims included population-weighting absent from the SQL implementation.
6. No push/PR CI, no small offline rebuild path, tests mostly checked preexisting data,
   generated README was long and fragile, refresh commits had hardcoded dates.

Implementation order: correctness and data isolation -> isolated regression tests and offline
fixture -> measured optimization -> frontend fixes -> reproducibility/CI/docs -> final verification.
