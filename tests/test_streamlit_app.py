"""Smoke tests for Streamlit application.

Verifies that the dashboard runs headlessly with only committed repository files
(using data/energy_marts.db when data/energy.db is absent).
"""

from __future__ import annotations

import os
from pathlib import Path
import pytest
from streamlit.testing.v1 import AppTest


def test_streamlit_app_loads_with_committed_marts_only(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure the app loads and renders without exceptions using data/energy_marts.db."""
    marts_db = Path("data/energy_marts.db")
    assert marts_db.exists(), "data/energy_marts.db must be committed and present"
    
    # Force ENERGY_DB_PATH to point to energy_marts.db even if energy.db exists locally
    monkeypatch.setenv("ENERGY_DB_PATH", str(marts_db))
    
    at = AppTest.from_file("app/streamlit_app.py")
    at.run(timeout=30)
    
    assert not at.exception, f"Streamlit app raised an exception: {at.exception}"
