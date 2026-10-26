"""Unit tests for Phase 3 cleaning and data quality checks."""

from sqlalchemy import text
from src.utils.db import get_engine
from src.clean.quality_checks import run_checks


def test_staging_tables_populated(require_full_db: None) -> None:
    """Ensure staging tables exist and contain cleaned rows."""
    engine = get_engine()
    with engine.connect() as conn:
        d_count = conn.execute(text("SELECT COUNT(*) FROM stg_hourly_demand")).scalar()
        w_count = conn.execute(text("SELECT COUNT(*) FROM stg_hourly_weather")).scalar()
        p_count = conn.execute(text("SELECT COUNT(*) FROM stg_daily_psp")).scalar()

        assert d_count > 0, "stg_hourly_demand is empty"
        assert w_count > 0, "stg_hourly_weather is empty"
        assert p_count > 0, "stg_daily_psp is empty"


def test_data_quality_suite_results(require_full_db: None) -> None:
    """Verify that automated data quality assertions pass (with documented known limitations)."""
    res = run_checks()
    assert res["total_checks"] == 9
    assert res["passed"] == 9
    assert res["failed"] == 0
    assert res["gap_summary"]["total_gaps"] == 2
    assert res["gap_summary"]["longest_gap_hours"] > 4000


def test_sensor_dropouts_isolated(require_full_db: None) -> None:
    """Verify that all detected sensor dropout hours have demand_mw set to NULL."""
    engine = get_engine()
    with engine.connect() as conn:
        dropouts_count = conn.execute(
            text("SELECT COUNT(*) FROM stg_hourly_demand WHERE is_dropout = 1")
        ).scalar()
        assert dropouts_count > 0, "Expected at least 1 sensor dropout to be flagged"
        unisolated = conn.execute(
            text("SELECT COUNT(*) FROM stg_hourly_demand WHERE is_dropout = 1 AND demand_mw IS NOT NULL")
        ).scalar()
        assert unisolated == 0, f"Found {unisolated} dropouts with non-NULL demand_mw!"
