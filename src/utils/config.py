"""Shared utilities for DB connection and path resolution."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

# Project root is three levels up from this file: src/utils/config.py
ROOT_DIR: Path = Path(__file__).resolve().parents[2]
DATA_DIR: Path = ROOT_DIR / "data"
RAW_DIR: Path = DATA_DIR / "raw"
PROCESSED_DIR: Path = DATA_DIR / "processed"
DOCS_DIR: Path = ROOT_DIR / "docs"
FIGURES_DIR: Path = DOCS_DIR / "figures"
SQL_DIR: Path = ROOT_DIR / "sql"

def get_db_path() -> Path:
    """Return DB path, falling back to committed slim energy_marts.db when energy.db is absent."""
    env_path = os.getenv("ENERGY_DB_PATH")
    if env_path:
        return Path(env_path)
    primary = DATA_DIR / "energy.db"
    if primary.exists():
        return primary
    slim = DATA_DIR / "energy_marts.db"
    if slim.exists():
        return slim
    return primary


DB_PATH: Path = get_db_path()

# ---------------------------------------------------------------------------
# Open-Meteo cities
# ---------------------------------------------------------------------------

CITIES: dict[str, dict[str, float]] = {
    "Delhi":     {"lat": 28.6139, "lon": 77.2090},
    "Mumbai":    {"lat": 19.0760, "lon": 72.8777},
    "Chennai":   {"lat": 13.0827, "lon": 80.2707},
    "Kolkata":   {"lat": 22.5726, "lon": 88.3639},
    "Bengaluru": {"lat": 12.9716, "lon": 77.5946},
    "Ahmedabad": {"lat": 23.0225, "lon": 72.5714},
}

# ---------------------------------------------------------------------------
# Misc
# ---------------------------------------------------------------------------

LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
DATA_GOV_IN_API_KEY: str | None = os.getenv("DATA_GOV_IN_API_KEY")
