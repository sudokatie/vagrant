"""Pytest configuration and fixtures."""

from pathlib import Path

import pytest


@pytest.fixture
def fixtures_dir() -> Path:
    """Return path to test fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def specs_dir(fixtures_dir: Path) -> Path:
    """Return path to spec fixtures directory."""
    return fixtures_dir / "specs"
