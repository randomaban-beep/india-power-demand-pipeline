"""Tests for Phase 2 ingest modules."""

from pathlib import Path
import pytest
from src.utils.config import CITIES
from src.ingest.grid_india import parse_mop_e_sheet
from src.ingest.open_meteo import fetch_city_weather_recent


def test_parse_mop_e_sheet_structure(tmp_path: Path) -> None:
    """Verify parse_mop_e_sheet extracts valid values from local sample if present."""
    sample_xls = Path("data/raw/sample_psp_20261023.xls")
    if sample_xls.exists():
        all_india, states = parse_mop_e_sheet(sample_xls)
        assert "report_date" in all_india
        assert all_india.get("energy_met_mu", 0) > 0
        assert len(states) > 10
        assert any(s["state"] == "Delhi" for s in states)


def test_cities_configuration() -> None:
    """Ensure all required major demand centres are present."""
    expected_cities = {"Delhi", "Mumbai", "Chennai", "Kolkata", "Bengaluru", "Ahmedabad"}
    assert expected_cities.issubset(set(CITIES.keys()))
