"""
Sabhya AI - E2E Streaming & Route Auth Tests

Tests that:
- Legacy API keys and JWT tokens can access health endpoints
- Streaming endpoint creates audit logs even on backend failure
- Route-level auth enforcement (401/403 for missing/wrong roles)
"""

import os

import pytest

# Streaming tests require a live Ollama instance and a /stream endpoint
OLLAMA_AVAILABLE = os.getenv("OLLAMA_BASE_URL") is not None


class TestRouteAuthEnforcement:
    """Test that routes enforce authentication correctly."""

    def test_health_live_is_public(self, test_client):
        """Health liveness endpoint should be public (no auth required)."""
        response = test_client.get("/health/live")
        assert response.status_code == 200
        assert response.json()["status"] == "alive"

    def test_health_live_accepts_legacy_key(self, test_client):
        """Legacy API key should also work on /health/live."""
        response = test_client.get(
            "/health/live", headers={"Authorization": "Bearer test-key-1"}
        )
        assert response.status_code == 200

    def test_health_live_accepts_jwt(self, test_client, user_token):
        """JWT token should also work on /health/live."""
        response = test_client.get(
            "/health/live", headers={"Authorization": f"Bearer {user_token}"}
        )
        assert response.status_code == 200

    def test_chat_requires_auth(self, test_client):
        """Chat completion should require authentication."""
        response = test_client.post(
            "/v1/chat/completions",
            json={"messages": [{"role": "user", "content": "test"}]},
        )
        assert response.status_code == 401

    def test_audit_logs_requires_admin_or_auditor(self, test_client, viewer_token):
        """Viewer should not access audit logs."""
        response = test_client.get(
            "/v1/audit/logs", headers={"Authorization": f"Bearer {viewer_token}"}
        )
        assert response.status_code == 403

    def test_audit_logs_allows_admin(self, test_client, admin_token):
        """Admin should access audit logs."""
        response = test_client.get(
            "/v1/audit/logs", headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200

    def test_rag_documents_requires_auth(self, test_client):
        """RAG documents should require authentication."""
        response = test_client.get("/rag/documents")
        assert response.status_code == 401


@pytest.mark.skipif(
    not OLLAMA_AVAILABLE,
    reason="Requires live Ollama instance (OLLAMA_BASE_URL not set)",
)
class TestStreamingAuditLog:
    """Test that streaming endpoint creates audit log even on failure."""

    def test_stream_creates_audit_on_backend_failure(
        self, test_client, user_token, admin_token
    ):
        """
        When Ollama is unreachable, stream should still create an audit entry.
        This verifies the 'finally' block in generate_stream.
        """
        # Trigger streaming — Ollama will fail (not running)
        try:
            response = test_client.post(
                "/v1/chat/completions/stream",
                headers={"Authorization": f"Bearer {user_token}"},
                json={
                    "messages": [{"role": "user", "content": "Hello"}],
                    "model": "mistral",
                },
            )
            # Consume stream to trigger the generator
            for _ in response.iter_lines():
                pass
        except Exception:
            pass  # Connection errors are expected

        # Verify audit log was created
        response = test_client.get(
            "/v1/audit/logs", headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        logs = response.json()

        stream_logs = [
            entry for entry in logs if entry["endpoint"] == "/v1/chat/completions/stream"
        ]
        assert len(stream_logs) > 0, "Audit log missing for streaming endpoint"
        assert stream_logs[0]["user_hash"] is not None
        assert isinstance(stream_logs[0]["pii_detected"], bool)
