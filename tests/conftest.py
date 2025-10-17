"""Pytest configuration and shared fixtures for faster test execution."""
import pytest
import os

# Disable verbose output by default for speed
def pytest_configure(config):
    """Configure pytest for faster execution."""
    # Set environment variables for test mode
    os.environ.setdefault("DATA_MODE", "stubbed")
    os.environ.setdefault("RUNNING_MODE", "test")

    # Disable unnecessary plugins if they slow things down
    config.option.verbose = 0 if config.option.verbose is None else config.option.verbose


# Shared fixtures can go here if needed
@pytest.fixture(scope="session")
def test_data_dir():
    """Return the path to test data directory."""
    return os.path.join(os.path.dirname(__file__), "data")
