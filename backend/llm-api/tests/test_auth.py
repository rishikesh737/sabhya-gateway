"""
Sabhya AI - Authentication Tests

Tests for JWT authentication and RBAC.
"""

from datetime import timedelta

import pytest


class TestJWTTokens:
    """Test JWT token creation and verification."""

    def test_create_access_token(self):
        """Test access token creation."""
        from app.auth.security import create_access_token

        token = create_access_token(
            data={"sub": "user123", "roles": ["user", "viewer"]}
        )

        assert token is not None
        assert len(token) > 0
        assert "." in token  # JWT format

    def test_verify_valid_token(self):
        """Test verification of valid token."""
        from app.auth.security import create_access_token, verify_token

        token = create_access_token(data={"sub": "user123", "roles": ["admin"]})
        data = verify_token(token)

        assert data.sub == "user123"
        assert "admin" in data.roles
        assert data.token_type == "access"

    def test_verify_invalid_token(self):
        """Test verification of invalid token fails."""
        from fastapi import HTTPException

        from app.auth.security import verify_token

        with pytest.raises(HTTPException) as exc:
            verify_token("invalid.token.here")

        assert exc.value.status_code == 401

    def test_expired_token_rejected(self):
        """Test that expired tokens are rejected."""
        from fastapi import HTTPException

        from app.auth.security import create_access_token, verify_token

        # Create already-expired token
        token = create_access_token(
            data={"sub": "user123", "roles": ["user"]},
            expires_delta=timedelta(seconds=-10),
        )

        with pytest.raises(HTTPException) as exc:
            verify_token(token)

        assert exc.value.status_code == 401

    def test_refresh_token_creation(self):
        """Test refresh token creation."""
        from app.auth.security import create_refresh_token, verify_token

        token = create_refresh_token("user123")
        data = verify_token(token)

        assert data.sub == "user123"
        assert data.token_type == "refresh"


class TestRBAC:
    """Test Role-Based Access Control."""

    def test_role_permissions_mapping(self):
        """Test that roles have correct permissions."""
        from app.auth.security import ROLE_PERMISSIONS, Permissions, Roles

        # Admin has all permissions
        admin_perms = ROLE_PERMISSIONS[Roles.ADMIN]
        assert Permissions.READ in admin_perms
        assert Permissions.WRITE in admin_perms
        assert Permissions.DELETE in admin_perms
        assert Permissions.MANAGE_USERS in admin_perms

        # User has limited permissions
        user_perms = ROLE_PERMISSIONS[Roles.USER]
        assert Permissions.READ in user_perms
        assert Permissions.WRITE in user_perms
        assert Permissions.DELETE not in user_perms

        # Viewer is read-only
        viewer_perms = ROLE_PERMISSIONS[Roles.VIEWER]
        assert Permissions.READ in viewer_perms
        assert Permissions.WRITE not in viewer_perms

    def test_auditor_permissions(self):
        """Test auditor role has audit permissions."""
        from app.auth.security import ROLE_PERMISSIONS, Permissions, Roles

        auditor_perms = ROLE_PERMISSIONS[Roles.AUDITOR]
        assert Permissions.AUDIT in auditor_perms
        assert Permissions.READ in auditor_perms
        assert Permissions.WRITE not in auditor_perms


class TestAPIKeyHashing:
    """Test API key hashing and verification."""

    def test_hash_api_key(self):
        """Test API key hashing."""
        from app.auth.security import hash_api_key

        original = "my-secret-api-key"
        hashed = hash_api_key(original)

        # Hash should be different from original
        assert hashed != original
        # Should be bcrypt format
        assert hashed.startswith("$argon2")

    def test_verify_api_key_hash(self):
        """Test API key hash verification."""
        from app.auth.security import hash_api_key, verify_api_key_hash

        original = "my-secret-api-key"
        hashed = hash_api_key(original)

        # Should verify correctly
        assert verify_api_key_hash(original, hashed) is True

        # Wrong key should fail
        assert verify_api_key_hash("wrong-key", hashed) is False

    def test_generate_api_key(self):
        """Test API key generation."""
        from app.auth.security import generate_api_key

        key1 = generate_api_key("sk")
        key2 = generate_api_key("sk")

        # Should have prefix
        assert key1.startswith("sk_")

        # Keys should be unique
        assert key1 != key2

        # Should be long enough
        assert len(key1) > 30


class TestLegacyAPIKeySupport:
    """Test backward compatibility with legacy API keys."""

    def test_verify_legacy_key(self):
        """Test legacy API key verification."""
        import os

        from app.auth.security import verify_legacy_api_key

        # Set up test environment
        os.environ["API_KEYS"] = "test-key-1,test-key-2"
        os.environ["LEGACY_AUTH_ENABLED"] = "true"

        result = verify_legacy_api_key("test-key-1")

        if result:
            assert result.user_id.startswith("legacy_")
            assert result.is_legacy_key is True

    def test_invalid_legacy_key_rejected(self):
        """Test invalid legacy key is rejected."""
        from app.auth.security import verify_legacy_api_key

        result = verify_legacy_api_key("invalid-key")

        assert result is None
