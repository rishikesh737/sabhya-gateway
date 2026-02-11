"""
Sabhya AI - Security Headers Tests

Tests for HTTP security headers middleware:
- HSTS (Strict-Transport-Security)
- Content-Security-Policy (CSP)
- X-Frame-Options (DENY)
- X-Content-Type-Options (nosniff)
- X-XSS-Protection
- Referrer-Policy
- Permissions-Policy
- X-Process-Time
- X-Request-ID
"""

import pytest


class TestSecurityHeaders:
    """Verify that all security headers are present on responses."""

    def _get_headers(self, test_client, user_token):
        """Helper: make authenticated request and return response headers."""
        response = test_client.get(
            "/health/live",
            headers={"Authorization": f"Bearer {user_token}"}
        )
        assert response.status_code == 200
        return response.headers

    def test_hsts_header(self, test_client, user_token):
        """HSTS should enforce HTTPS for 1 year with preload."""
        headers = self._get_headers(test_client, user_token)
        hsts = headers.get("strict-transport-security", "")
        assert "max-age=31536000" in hsts
        assert "includeSubDomains" in hsts
        assert "preload" in hsts

    def test_csp_header(self, test_client, user_token):
        """CSP should restrict content sources."""
        headers = self._get_headers(test_client, user_token)
        csp = headers.get("content-security-policy", "")
        assert "default-src 'self'" in csp
        assert "frame-ancestors 'none'" in csp
        assert "base-uri 'self'" in csp
        assert "form-action 'self'" in csp

    def test_x_frame_options_deny(self, test_client, user_token):
        """X-Frame-Options should be DENY to prevent clickjacking."""
        headers = self._get_headers(test_client, user_token)
        assert headers.get("x-frame-options") == "DENY"

    def test_x_content_type_options_nosniff(self, test_client, user_token):
        """X-Content-Type-Options should prevent MIME sniffing."""
        headers = self._get_headers(test_client, user_token)
        assert headers.get("x-content-type-options") == "nosniff"

    def test_xss_protection(self, test_client, user_token):
        """X-XSS-Protection should be enabled with block mode."""
        headers = self._get_headers(test_client, user_token)
        assert headers.get("x-xss-protection") == "1; mode=block"

    def test_referrer_policy(self, test_client, user_token):
        """Referrer policy should limit cross-origin referrer data."""
        headers = self._get_headers(test_client, user_token)
        assert headers.get("referrer-policy") == "strict-origin-when-cross-origin"

    def test_permissions_policy(self, test_client, user_token):
        """Permissions-Policy should disable dangerous browser features."""
        headers = self._get_headers(test_client, user_token)
        pp = headers.get("permissions-policy", "")
        assert "geolocation=()" in pp
        assert "microphone=()" in pp
        assert "camera=()" in pp

    def test_process_time_header(self, test_client, user_token):
        """X-Process-Time should be present with numeric value."""
        headers = self._get_headers(test_client, user_token)
        process_time = headers.get("x-process-time")
        assert process_time is not None
        assert float(process_time) >= 0

    def test_request_id_header(self, test_client, user_token):
        """X-Request-ID should be generated for every response."""
        headers = self._get_headers(test_client, user_token)
        request_id = headers.get("x-request-id")
        assert request_id is not None
        assert len(request_id) > 0

    def test_request_id_unique_per_request(self, test_client, user_token):
        """Each request should get a unique request ID."""
        h1 = self._get_headers(test_client, user_token)
        h2 = self._get_headers(test_client, user_token)
        assert h1.get("x-request-id") != h2.get("x-request-id")

    def test_no_wildcard_cors(self, test_client, user_token):
        """CORS should not use wildcard origins."""
        from app.middleware.security import validate_security_config
        config = validate_security_config()
        origins = config['config']['cors_origins']
        assert "*" not in origins, "CORS wildcard (*) detected — unsafe for production"


class TestSecurityConfigValidation:
    """Test the security configuration validator."""

    def test_validate_returns_warnings_for_weak_config(self):
        """Validator should warn about weak config."""
        import os
        from app.middleware.security import validate_security_config

        old_key = os.environ.get("SECRET_KEY", "")
        os.environ["SECRET_KEY"] = "short"
        try:
            result = validate_security_config()
            assert result['is_secure'] is False
            warning_texts = " ".join(result['warnings'])
            assert "SHORT" in warning_texts.upper() or "short" in warning_texts.lower()
        finally:
            os.environ["SECRET_KEY"] = old_key

    def test_validate_passes_with_secure_config(self):
        """Validator should pass with properly configured secrets."""
        import os
        from app.middleware.security import validate_security_config

        old_key = os.environ.get("SECRET_KEY", "")
        os.environ["SECRET_KEY"] = "a-very-secure-production-key-that-is-at-least-32-characters-long"
        try:
            result = validate_security_config()
            short_warnings = [w for w in result['warnings'] if 'SHORT' in w.upper() or 'short' in w.lower()]
            assert len(short_warnings) == 0
        finally:
            os.environ["SECRET_KEY"] = old_key
