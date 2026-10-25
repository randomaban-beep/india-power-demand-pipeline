"""Unit tests for Phase 3 cleaning and data quality checks."""

from pathlib import Path
import pytest
from sqlalchemy import text
from src.utils.db import get_engine
from src.clean.quality_checks import run_checks


def test_staging_tables_populated() -> None:
    """Ensure staging tables exist and contain cleaned rows."""
    engine = get_engine()
    with engine.connect() as conn:
        d_count = conn.execute(text("SELECT COUNT(*) FROM stg_hourly_demand")).scalar()
        w_count = conn.execute(text("SELECT COUNT(*) FROM stg_hourly_weather")).scalar()
        p_count = conn.execute(text("SELECT COUNT(*) FROM stg_daily_psp")).scalar()
        
        assert d_count > 0, "stg_hourly_demand is empty"
        assert w_count > 0, "stg_hourly_weather is empty"
        assert p_count > 0, "stg_daily_psp is empty"


def test_data_quality_suite_all_pass() -> None:
    """Verify that all 5 automated data quality checks pass."""
    res = run_checks()
    assert res["total_checks"] == 5
    assert res["failed"] == 0, f"Expected 0 failures, got {res['failed']}: {res['results']}"
    assert res["passed"] == 5
