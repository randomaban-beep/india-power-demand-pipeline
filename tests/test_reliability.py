"""Isolated regression tests for data contracts, failure handling and SQL semantics."""

from contextlib import closing
import sqlite3
from unittest.mock import Mock
import numpy as np
import pandas as pd
import pytest
import requests
from fastapi.testclient import TestClient
from src.clean.clean_hourly import transform_hourly
from src.ingest.open_meteo import validate_hourly
from src.utils.config import ROOT_DIR
from server import main, queries


def telemetry(values, timestamps=None):
    n = len(values)
    return pd.DataFrame(
        {
            "timestamp_ist": timestamps
            or pd.date_range("2024-01-01", periods=n, freq="h").strftime("%Y-%m-%dT%H:%M"),
            "total_demand_mw": values,
            "solar_mw": np.zeros(n),
            "wind_mw": np.arange(n) + 1000.0,
            "thermal_mw": [None] * n,
            "hydro_mw": [None] * n,
            "gas_mw": [None] * n,
            "nuclear_mw": [None] * n,
            "source": ["fixture"] * n,
        }
    )


def test_cleaning_rejects_empty_missing_and_conflicting_duplicates():
    with pytest.raises(ValueError, match="empty"):
        transform_hourly(pd.DataFrame())
    with pytest.raises(ValueError, match="Missing"):
        transform_hourly(pd.DataFrame({"x": [1]}))
    frame = telemetry([150000, 160000])
    frame.loc[1, "timestamp_ist"] = frame.loc[0, "timestamp_ist"]
    with pytest.raises(ValueError, match="duplicate"):
        transform_hourly(frame)


@pytest.mark.parametrize("stamp", ["invalid", None, "2024-01-01T01:30"])
def test_cleaning_rejects_bad_timestamps(stamp):
    with pytest.raises(ValueError, match="timestamps"):
        transform_hourly(telemetry([150000], [stamp]))


def test_stuck_detector_does_not_bridge_gaps():
    result = transform_hourly(
        telemetry([150000] * 3, ["2024-01-01T00:00", "2024-01-02T00:00", "2024-01-03T00:00"])
    )
    assert result.is_stuck_demand.sum() == 0
    assert result.demand_mw.notna().all()


def test_dip_and_recovery_are_null_not_interpolated():
    result = transform_hourly(telemetry([150000, 151000, 80000, 81000, 152000, 153000]))
    assert result.is_multi_hour_dip.tolist() == [0, 0, 1, 1, 0, 0]
    assert result.demand_mw.iloc[2:5].isna().all()
    assert result.net_load_mw.iloc[2:5].isna().all()


def test_identical_duplicates_collapse_and_missing_components_preserve_total():
    frame = telemetry([150000, 151000])
    frame["thermal_mw"] = 100000
    result = transform_hourly(pd.concat([frame, frame]))
    assert len(result) == 2
    assert result.demand_mw.tolist() == [150000, 151000]


def weather():
    return {
        "time": ["2024-01-01T00:00", "2024-01-01T01:00"],
        "temperature_2m": [25.0, None],
        "relative_humidity_2m": [40.0, 41.0],
        "wind_speed_10m": [2.0, 3.0],
    }


@pytest.mark.parametrize("mutation", ["missing", "truncated", "duplicate", "invalid", "empty", "nonnumeric"])
def test_weather_contract(mutation):
    data = weather()
    if mutation == "missing":
        del data["temperature_2m"]
    if mutation == "truncated":
        data["temperature_2m"] = [25.0]
    if mutation == "duplicate":
        data["time"][1] = data["time"][0]
    if mutation == "invalid":
        data["time"][0] = "bad"
    if mutation == "empty":
        data = {key: [] for key in data}
    if mutation == "nonnumeric":
        data["temperature_2m"][0] = "hot"
    with pytest.raises(ValueError):
        validate_hourly(data)


def test_weather_null_observation_is_preserved():
    validate_hourly(weather())


def test_retry_is_bounded(monkeypatch):
    from src.utils import http

    attempt = Mock(side_effect=requests.Timeout("timeout"))
    monkeypatch.setattr(http.requests, "get", attempt)
    monkeypatch.setattr(http.time, "sleep", lambda _: None)
    with pytest.raises(requests.Timeout):
        http.get("https://example.invalid")
    assert attempt.call_count == 3


def test_quality_failure_stops_clean_stage(monkeypatch):
    from src.clean import run_all as cleaner

    audit = Mock()
    monkeypatch.setattr(cleaner, "init_db", lambda: None)
    monkeypatch.setattr(cleaner, "run_staging_sql", lambda: None)
    monkeypatch.setattr(cleaner, "run_checks", lambda: {"failed": 1})
    monkeypatch.setattr(cleaner, "log_run", audit)
    with pytest.raises(RuntimeError, match="quality gate"):
        cleaner.run_all()
    assert audit.call_args.args[-2] == "error"


def test_year_over_year_requires_previous_calendar_year():
    with closing(sqlite3.connect(":memory:")) as conn:
        conn.executescript(
            "CREATE TABLE stg_hourly_demand(timestamp_ist TEXT, demand_mw REAL); INSERT INTO stg_hourly_demand VALUES ('2022-01-01T00:00',100000), ('2024-01-01T00:00',150000), ('2025-01-01T00:00',165000);"
        )
        conn.executescript((ROOT_DIR / "sql/marts/mart_monthly_peak_demand.sql").read_text())
        rows = conn.execute(
            "SELECT prev_year_peak_mw,yoy_peak_growth_pct FROM mart_monthly_peak_demand ORDER BY year"
        ).fetchall()
        assert rows == [(None, None), (None, None), (150000.0, 10.0)]


def test_read_only_missing_database_does_not_create_file(tmp_path, monkeypatch):
    path = tmp_path / "missing.db"
    monkeypatch.setenv("ENERGY_DB_PATH", str(path))
    with pytest.raises(sqlite3.OperationalError):
        queries.get_connection()
    assert not path.exists()


def test_export_failure_preserves_previous_snapshot(tmp_path, monkeypatch):
    from src.model.export_powerbi import export_slim_db

    source, target = tmp_path / "raw.db", tmp_path / "snapshot.db"
    with closing(sqlite3.connect(source)) as conn:
        conn.execute("CREATE TABLE irrelevant(x)")
    target.write_bytes(b"previous snapshot")
    monkeypatch.setenv("ENERGY_DB_PATH", str(source))
    with pytest.raises(Exception):
        export_slim_db(target)
    assert target.read_bytes() == b"previous snapshot"


def test_api_invalid_range_and_missing_db(tmp_path, monkeypatch):
    main._IN_MEMORY_CACHE.clear()
    with TestClient(main.app) as client:
        assert client.get("/api/daily-demand?from=2025-01-01&to=2024-01-01").status_code == 422
        monkeypatch.setenv("ENERGY_DB_PATH", str(tmp_path / "missing.db"))
        assert client.get("/api/ready").status_code == 503
    main._IN_MEMORY_CACHE.clear()


def test_cache_bound():
    main._IN_MEMORY_CACHE.clear()
    for i in range(250):
        main.set_cached_response(str(i), i)
    assert len(main._IN_MEMORY_CACHE) == 200
    main._IN_MEMORY_CACHE.clear()


def test_empty_snapshot_is_not_ready(tmp_path, monkeypatch):
    path = tmp_path / "empty.db"
    with closing(sqlite3.connect(path)) as conn:
        conn.execute("CREATE TABLE mart_temp_vs_demand(x)")
    monkeypatch.setenv("ENERGY_DB_PATH", str(path))
    with TestClient(main.app) as client:
        assert client.get("/api/ready").status_code == 503


def test_december_is_winter_and_seasonal_re_filter():
    rows = queries.get_monthly_re_share(seasons=["Winter"])
    assert rows and all(int(r["year_month"][5:7]) in [12, 1, 2] for r in rows)
    december = queries.get_daily_demand("2025-12-01", "2025-12-31", ["Winter"])
    assert december and all(r["season"] == "Winter" for r in december)


def test_html_controls_have_valid_markup():
    html = (ROOT_DIR / "web/index.html").read_text(encoding="utf-8")
    assert "<h2 " in html and 'data-span="2y"' in html
    assert 'viewBox="0 0 24 24"' in html
    assert "ΔΔR²" not in html
    assert "card-grid-±2σ" not in html


def test_mendeley_parser_preserves_missing_values(tmp_path):
    import datetime as dt
    from openpyxl import Workbook
    from src.ingest.mendeley import parse_mendeley_month_excel

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Report"
    sheet.append(["Timestamp", "Demand (MW)", "Wind (MW)", "Solar (MW)"])
    sheet.append([dt.datetime(2024, 1, 1), 150000, None, None])
    path = tmp_path / "sample.xlsx"
    workbook.save(path)
    workbook.close()
    frame = parse_mendeley_month_excel(path)
    assert len(frame) == 1
    assert pd.isna(frame.iloc[0].wind_mw) and pd.isna(frame.iloc[0].solar_mw)
    assert frame.iloc[0].total_demand_mw == 150000


def test_database_connections_release_file(tmp_path):
    from src.utils.db import get_engine
    from sqlalchemy import text

    path = tmp_path / "releasable.db"
    engine = get_engine(path)
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE t(x)"))
    # On Windows a pooled connection would keep this file open.
    path.unlink()
    assert not path.exists()
