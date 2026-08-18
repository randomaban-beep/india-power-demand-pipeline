from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from server.main import app

client = TestClient(app)


def test_api_summary_endpoint():
    """Verify summary endpoint returns all required operational and audit metrics."""
    response = client.get("/api/summary")
    assert response.status_code == 200
    data = response.json()
    assert "latest_psp_peak_mw" in data
    assert "record_peak_mw" in data
    assert "latest_re_share_pct" in data
    assert "hourly_window_start" in data
    assert "total_report_count" in data
    assert "last_pipeline_run" in data
    assert data["total_report_count"] > 0
    assert data["record_peak_mw"] >= data["latest_psp_peak_mw"]


def test_api_daily_demand_endpoint():
    """Verify daily demand returns expected aggregates and honors seasonal filters."""
    response = client.get("/api/daily-demand")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    first = data[0]
    assert "date" in first
    assert "avg_mw" in first
    assert "peak_mw" in first
    assert "rolling_avg_mw" in first
    assert "season" in first

    filtered = client.get("/api/daily-demand?seasons=Summer&from=2024-03-01&to=2024-05-31")
    assert filtered.status_code == 200
    filtered_data = filtered.json()
    assert len(filtered_data) > 0
    assert all(row["season"] == "Summer" for row in filtered_data)


def test_api_daily_demand_validation_errors():
    """Verify invalid date and season parameters return unprocessable entity errors."""
    bad_date = client.get("/api/daily-demand?from=2024/01/01")
    assert bad_date.status_code == 422

    bad_season = client.get("/api/daily-demand?seasons=Autumn")
    assert bad_season.status_code == 422


def test_api_empty_filter_matching():
    """Verify non-matching date windows return an empty array without runtime errors."""
    empty_res = client.get("/api/daily-demand?from=2099-01-01&to=2099-01-05")
    assert empty_res.status_code == 200
    assert empty_res.json() == []


def test_api_monthly_peaks_endpoint():
    """Verify monthly peak demand returns series with escalation metrics."""
    response = client.get("/api/monthly-peaks")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    assert "peak_demand_mw" in data[0]
    assert "year_month" in data[0]


def test_api_temp_demand_endpoint():
    """Verify temperature-demand scatter sampling and 1C median bin calculations."""
    response = client.get("/api/temp-demand?feature=avg_temperature_c")
    assert response.status_code == 200
    data = response.json()
    assert data["feature"] == "avg_temperature_c"
    assert "points" in data
    assert "median_bins" in data
    assert len(data["points"]) > 0
    assert len(data["median_bins"]) > 0

    mumbai_res = client.get("/api/temp-demand?feature=mumbai_temp_c")
    assert mumbai_res.status_code == 200
    assert mumbai_res.json()["feature"] == "mumbai_temp_c"

    bad_feature = client.get("/api/temp-demand?feature=kolkata_temp_c")
    assert bad_feature.status_code == 422


def test_api_heatmap_endpoint():
    """Verify demand heatmap generates full 12x24 matrix entries."""
    response = client.get("/api/heatmap")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    assert "month" in data[0]
    assert "hour" in data[0]
    assert "avg_demand_mw" in data[0]


def test_api_sensitivity_endpoint():
    """Verify econometric sensitivity endpoint returns robust model parameters."""
    response = client.get("/api/sensitivity")
    assert response.status_code == 200
    data = response.json()
    assert "slope_mw_per_c" in data
    assert "se_hc1" in data
    assert "r2_ctrl" in data
    assert "r2_full" in data
    assert "thresholds" in data
    assert len(data["thresholds"]) >= 7


def test_api_duck_curve_endpoint():
    """Verify diurnal duck curve calculations and inflection ramping metrics."""
    response = client.get("/api/duck-curve?season=Summer")
    assert response.status_code == 200
    data = response.json()
    assert data["season"] == "Summer"
    assert "solar_peak_mw" in data
    assert "net_load_trough_mw" in data
    assert "evening_peak_mw" in data
    assert "trough_to_peak_ramp_mw" in data
    assert len(data["hourly_profile"]) == 24

    bad_season = client.get("/api/duck-curve?season=Spring")
    assert bad_season.status_code == 422


def test_api_re_share_endpoint():
    """Verify monthly renewable penetration calculations."""
    response = client.get("/api/re-share")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    assert "avg_re_share_pct" in data[0]
    assert "year_month" in data[0]


def test_api_anomalies_endpoint():
    """Verify demand anomaly detection outputs and categorization metrics."""
    response = client.get("/api/anomalies")
    assert response.status_code == 200
    data = response.json()
    assert "anomalies_count" in data
    assert "real_count" in data
    assert "dq_count" in data
    assert isinstance(data["data"], list)
    assert len(data["data"]) > 0


def test_api_ramps_endpoint():
    """Verify top 10 net-load ramp events and cross-checked peak values."""
    response = client.get("/api/ramps")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) <= 10
    assert "abs_ramp_1h_mw" in data[0]
    assert "grid_india_peak_mw" in data[0]


def test_api_health_endpoint():
    """Verify pipeline health endpoint returns assertions and execution runs."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert "checks" in data
    assert "runs" in data
    assert "table_counts" in data
    assert len(data["checks"]) > 0
    assert len(data["runs"]) > 0


def test_api_export_csv_endpoints():
    """Verify CSV streaming downloads for supported analytical tables."""
    for table_name in ["daily-demand", "anomalies", "ramps", "monthly-peaks"]:
        res = client.get(f"/api/export/{table_name}.csv")
        assert res.status_code == 200
        assert "text/csv" in res.headers["content-type"]
        assert f'filename="{table_name}.csv"' in res.headers["content-disposition"]
        assert len(res.text.strip().split("\n")) > 1

    bad_export = client.get("/api/export/unknown-table.csv")
    assert bad_export.status_code == 422


def test_api_caching_behavior():
    """Verify second call to cached endpoint returns consistent data."""
    res1 = client.get("/api/summary")
    res2 = client.get("/api/summary")
    assert res1.status_code == 200
    assert res2.status_code == 200
    assert res1.json() == res2.json()
