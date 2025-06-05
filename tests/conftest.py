import pytest
import os
import sys
from pathlib import Path

# Add the project root to the Python path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Set environment variables for testing
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_link_profiler.db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key")
os.environ.setdefault("ADMIN_PASSWORD", "admin123")
os.environ.setdefault("API_BASE_URL", "http://localhost:8000")
os.environ.setdefault("DEBUG", "true")
os.environ.setdefault("ENVIRONMENT", "testing")

@pytest.fixture(scope="session")
def project_root():
    """Return the project root directory."""
    return PROJECT_ROOT

@pytest.fixture(autouse=True)
def setup_test_environment():
    """Automatically set up test environment for all tests."""
    # Ensure PYTHONPATH includes project root
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    
    yield
    
    # Cleanup after test if needed
    pass

@pytest.fixture
def mock_env_vars(monkeypatch):
    """Provide a fixture to easily mock environment variables."""
    def _set_env_var(key, value):
        monkeypatch.setenv(key, value)
    return _set_env_var

# Pytest configuration
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "unit: mark test as a unit test")
    config.addinivalue_line("markers", "integration: mark test as an integration test")
    config.addinivalue_line("markers", "slow: mark test as slow running")

def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers automatically."""
    for item in items:
        # Add unit marker to tests that don't have integration or slow markers
        if not any(marker.name in ["integration", "slow"] for marker in item.iter_markers()):
            item.add_marker(pytest.mark.unit)
