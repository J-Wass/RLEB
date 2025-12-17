"""Pytest configuration and shared fixtures for faster test execution."""

import pytest
import os


def pytest_configure(config):
    # Disable unnecessary plugins if they slow things down
    config.option.verbose = (
        0 if config.option.verbose is None else config.option.verbose
    )


# Shared fixtures can go here if needed
@pytest.fixture(scope="session")
def test_data_dir():
    """Return the path to test data directory."""
    return os.path.join(os.path.dirname(__file__), "data")
