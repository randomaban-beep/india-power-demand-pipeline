"""Unit tests for Phase 4 SQL analytical marts."""

import pytest
from sqlalchemy import text
from src.utils.db import get_engine


def test_mart_tables_exist_and_populated() -> None:
    engine = get_engine()
    marts = [
        "mart_demand_profile_by_season",
        "mart_monthly_peak_demand",
        "mart_temp_vs_demand",
        "mart_daily_weather_demand",
        "mart_net_load_profile",
        "mart_net_load_ramps",
        "mart_anomaly_days",
    ]
    with engine.connect() as conn:
        for m in marts:
            cnt = conn.execute(text(f"SELECT COUNT(*) FROM {m}")).scalar()
            assert cnt > 0, f"Mart table {m} is empty!"


def test_anomaly_days_detection() -> None:
    engine = get_engine()
    with engine.connect() as conn:
        real_anomalies = conn.execute(text("SELECT COUNT(*) FROM mart_anomaly_days WHERE is_real_anomaly = 1")).scalar()
        dq_anomalies = conn.execute(text("SELECT COUNT(*) FROM mart_anomaly_days WHERE is_dq_anomaly = 1")).scalar()
        assert real_anomalies > 0, "Real anomaly count must be positive"
        assert dq_anomalies > 0, "DQ anomaly count must be positive"


def test_net_load_ramps() -> None:
    engine = get_engine()
    with engine.connect() as conn:
        max_ramp = conn.execute(text("SELECT MAX(abs_ramp_1h_mw) FROM mart_net_load_ramps")).scalar()
        assert max_ramp > 0, "Max net load ramp must be strictly positive"
        # Verify fake 80,000+ MW dropout glitches are completely removed
        assert max_ramp < 60000, f"Max ramp {max_ramp} MW exceeds plausible physical boundary (expected < 60,000 MW)"
