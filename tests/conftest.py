"""Pytest fixtures and shared configuration."""

from __future__ import annotations

import os
from pathlib import Path
import pytest

from src.utils.config import DATA_DIR


@pytest.fixture
def require_full_db():
    """Ensure data/energy.db is present; fail loudly in CI if REQUIRE_FULL_DB=1, else skip locally."""
    full_db = DATA_DIR / "energy.db"
    if not full_db.exists():
        if os.getenv("REQUIRE_FULL_DB") == "1":
            pytest.fail("REQUIRE_FULL_DB=1 is set but data/energy.db is absent.")
        pytest.skip("data/energy.db is absent; skipping test requiring full database.")
