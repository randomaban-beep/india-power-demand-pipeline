"""Smoke test: imports and config resolve without errors."""

from src.utils.config import ROOT_DIR, DB_PATH, CITIES


def test_root_dir_exists() -> None:
    assert ROOT_DIR.exists(), f"ROOT_DIR not found: {ROOT_DIR}"


def test_db_path_parent_is_data() -> None:
    assert DB_PATH.parent.name == "data"
    assert DB_PATH.name in ("energy.db", "energy_marts.db")


def test_cities_not_empty() -> None:
    assert len(CITIES) >= 4
    for city, coords in CITIES.items():
        assert "lat" in coords and "lon" in coords, f"{city} missing coords"
