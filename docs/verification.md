# Engineering verification

Verified 2026-10-26 on Windows build 26200, CPython 3.11.9, using a fresh
`.venv-verify` installed from the pinned requirements. No production-readiness or
availability guarantee is implied. Original revision: `5e86c18`.

## Results

| Check | Observed result |
|---|---|
| Original test suite | 27 passed (5.50 s) |
| Expanded suite, full local data | 54 passed (17.67 s); one upstream TestClient deprecation warning |
| Repository-files-only copy | 50 passed, 4 explicit skips (7.68 s): three optional full-DB checks and one downloaded-workbook check |
| Statement coverage (`src`, `server`) | 1,060 / 2,123 statements, 49.93%; visualization/report and live ingestion paths are not comprehensively covered |
| Ruff lint / formatting | Passed across src, server, tests, scripts |
| Mypy | Passed for config and HTTP utility modules only; no whole-project type-check claim |
| Dependency consistency | `pip check` passed |
| Vulnerability audit | `pip-audit 2.10.1`: no known vulnerabilities in the final installed environment; point-in-time database result |
| Frontend | All three JavaScript files passed syntax checks; dashboard loaded locally, responsive overflow fixed, no browser console errors observed |
| Streamlit | Headless AppTest passed against the committed marts DB |
| Notebook | All cells executed against the committed snapshot using nbconvert; outputs kept outside version control |
| Full pipeline | Offline rebuild, all nine data checks passed, seven marts plus daily PSP exported to CSV/Parquet, snapshot published |
| Repeatability | Two full rebuilds produced equal contents across all eight exported tables; integration test also rebuilds the real sample twice |
| Live refresh | Completed with Grid-India and Open-Meteo requests; 20 PSP, 780 state and 1,296 weather upserts (not counts of newly added rows); existing legacy Mendeley data reused |
| Figures / report | Nine figures and RESULTS.md regenerated from the same verified full snapshot |
| Docker / hosted deployment | Not executed: Docker daemon unavailable; no live deployment claimed |

The first dependency-upgrade test failed because PyArrow 26 requires NumPy 2 and
new Streamlit resolves test paths relative to the caller. PyArrow 23.0.1 and an
absolute AppTest path resolved these failures. Notebook execution also caught and
resolved missing values in its regression input. These failures are not hidden
behind the final passing results.

## Performance and data scope

[benchmark.json](benchmark.json) records three alternating before/after runs on
identical SQLite backups: **23,184 hourly rows**, median cleaner wall time
**4.959 s → 0.716 s (6.93×)**. Timing includes reading, transformation and staging
write; excludes downloads and database copying, uses a warm filesystem cache, and
is subject to laptop load. It is not an end-to-end speedup. The revised algorithm
also fixes dip masking and calendar-window behavior, so this is not bit-identical
optimization: demand flags change from 337 to 269 and valid demand rows from
22,847 to 22,915. Heuristic flags are not ground-truth accuracy labels.

Full offline runs took **8.56 s** and **12.29 s**; the final patched-environment run
took **7.15 s**. The live-refresh run took **20.66 s**. These are individual observed
runs, not a throughput SLA or controlled before/after pipeline comparison.
[Run reports](runs/) contain timings, row counts, platform and the raw-hourly hash.
The committed analytical snapshot contains 769 daily reports, 23,184 hourly
telemetry rows and 270,720 raw city-weather observations. Live-refresh output was
kept separate (770 daily reports), preserving comparable benchmark inputs.

## Reproduction

Follow README setup, then run:

```bash
python -m pytest -q --cov
python -m ruff check src server tests scripts
python -m ruff format --check src server tests scripts
python -m pip check
python -m scripts.load_sample
python -m src.pipeline --db data/sample.db --output data/run-sample
python -m scripts.benchmark --db data/energy.db --baseline-ref 5e86c18 --repeats 3
python -m nbconvert --to notebook --execute notebooks/01_eda.ipynb --output 01_eda.executed.ipynb --output-dir data/run-notebook
```

Benchmarking requires the optional full database. The committed real-data sample
has 168 hourly observations, 1,008 city-weather rows, two daily PSP reports and
74 state rows. Its short coverage deliberately skips the correlation check.
To repeat the security scan, install `pip-audit==2.10.1`, upgrade pip/setuptools,
then run `python -m pip_audit`. Advisory results can change over time.

## Remaining limits

- Mendeley fresh-archive download and resume behavior are not proven by the live
  run, which reused existing legacy data. Historical extract gaps remain explicit.
- API/network availability varies by source and hosting region. Refresh CI needs
  the seeded `data-latest` release and write permission.
- Export files are individually atomic; the CSV/Parquet directory is not a single
  transaction. Use a separate output directory for each concurrent execution.
- Source archive model provenance is not recorded per weather row. Temperatures
  are unweighted city means. Centered cleaning and retrospective anomaly models
  are unsuitable for leakage-safe forecasting without redesign.
- No causal effects, forecast accuracy, business savings or real-user traffic
  have been measured. Coverage and Docker validation remain areas to improve.

## Resume bullets supported by this evidence

- Hardened a Python/SQL electricity analytics pipeline processing 23,184 hourly
  records and 270,720 weather observations, with nine quality gates, seven marts,
  isolated rebuilds and atomic SQLite snapshot publication.
- Vectorized telemetry cleaning and corrected gap-aware anomaly masking, reducing
  median cleaner runtime from 4.96 s to 0.72 s across three controlled paired runs.
- Expanded regression coverage from 27 to 54 passing tests; added real-data
  repeatability checks, CI, read-only APIs and a reproducible dashboard workflow.

Suggested repository description: “Reproducible India electricity-demand ETL,
quality checks and SQL analytics with FastAPI dashboards and measured benchmarks.”

Suggested topics: `data-engineering`, `python`, `sql`, `sqlite`, `fastapi`, `etl`,
`energy-analytics`, `data-quality`, `india`, `github-actions`.
