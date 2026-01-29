"""Tests for package basics."""

import vagrant


def test_version_exists():
    """Package has a version string."""
    assert hasattr(vagrant, "__version__")
    assert isinstance(vagrant.__version__, str)


def test_version_format():
    """Version follows semantic versioning."""
    parts = vagrant.__version__.split(".")
    assert len(parts) >= 2
    assert all(p.isdigit() for p in parts[:2])
