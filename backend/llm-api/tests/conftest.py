"""
Sabhya AI - Pytest Configuration

Shared fixtures and configuration for all tests.
"""

import pytest
import os
from unittest.mock import MagicMock, patch


# ============================================================================
# ENVIRONMENT SETUP
# ============================================================================

@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Set up test environment variables."""
    os.environ["ENVIRONMENT"] = "testing"
    os.environ["DEBUG"] = "true"
    os.environ["SECRET_KEY"] = "test-secret-key-for-testing-minimum-32-chars"
    os.environ["AUDIT_HMAC_SECRET"] = "test-audit-secret-for-testing-32-chars"
    os.environ["API_KEYS"] = "test-key-1,test-key-2"
    os.environ["LEGACY_AUTH_ENABLED"] = "true"
    os.environ["DATABASE_URL"] = "postgresql://test:test@localhost:5432/test_db"
    yield
    # Cleanup if needed


# ============================================================================
# DATABASE FIXTURES
# ============================================================================

@pytest.fixture
def mock_db():
    """Mock database session."""
    mock_session = MagicMock()
    mock_session.query.return_value = mock_session
    mock_session.filter.return_value = mock_session
    mock_session.all.return_value = []
    mock_session.first.return_value = None
    return mock_session


# ============================================================================
# HTTP CLIENT FIXTURES
# ============================================================================

@pytest.fixture
def test_client():
    """Create FastAPI test client."""
    try:
        from fastapi.testclient import TestClient
        from app.main import app
        return TestClient(app)
    except ImportError:
        pytest.skip("FastAPI not available for testing")


# ============================================================================
# AUTH FIXTURES
# ============================================================================

@pytest.fixture
def admin_token():
    """Generate admin JWT token for testing."""
    from app.auth.security import create_access_token
    return create_access_token("admin-user", ["admin"])


@pytest.fixture
def user_token():
    """Generate regular user JWT token for testing."""
    from app.auth.security import create_access_token
    return create_access_token("regular-user", ["user"])


@pytest.fixture
def viewer_token():
    """Generate viewer JWT token for testing."""
    from app.auth.security import create_access_token
    return create_access_token("viewer-user", ["viewer"])


# ============================================================================
# SERVICE FIXTURES
# ============================================================================

@pytest.fixture
def pii_service():
    """Create PII detection service instance."""
    from app.services.pii_detection import PIIDetectionService
    return PIIDetectionService()


@pytest.fixture
def audit_service():
    """Create audit service instance."""
    from app.services.audit import AuditService
    return AuditService(hmac_secret=b"test-secret-key-for-testing")


# ============================================================================
# MOCK FIXTURES
# ============================================================================

@pytest.fixture
def mock_redis():
    """Mock Redis connection."""
    with patch("redis.Redis") as mock:
        mock_instance = MagicMock()
        mock_instance.ping.return_value = True
        mock_instance.get.return_value = None
        mock_instance.set.return_value = True
        mock.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_ollama():
    """Mock Ollama API responses."""
    with patch("requests.post") as mock:
        mock.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "model": "mistral:7b-instruct-q4_K_M",
                "response": "Test response from Ollama",
                "done": True
            }
        )
        yield mock


# ============================================================================
# HELPERS
# ============================================================================

def create_test_request(
    method: str = "POST",
    path: str = "/v1/chat/completions",
    headers: dict = None,
    json_body: dict = None
):
    """Helper to create test request objects."""
    return {
        "method": method,
        "path": path,
        "headers": headers or {},
        "json": json_body or {}
    }
