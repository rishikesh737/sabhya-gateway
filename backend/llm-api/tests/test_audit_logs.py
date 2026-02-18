"""
Sabhya AI - Audit Log Tests

Tests for immutable audit logs with tamper detection.
"""

import pytest


@pytest.fixture
def audit_service():
    """Create audit service instance."""
    from app.services.audit import AuditService

    return AuditService(hmac_secret=b"test-secret-key-for-testing")


class TestAuditLogCreation:
    """Test audit log entry creation."""

    def test_create_basic_entry(self, audit_service):
        """Test basic entry creation."""
        entry = audit_service.create_entry(
            request_id="req-123",
            user_id="user-456",
            endpoint="/v1/chat/completions",
            method="POST",
            status_code=200,
            latency_ms=152.3,
            model="mistral",
        )

        assert entry.request_id == "req-123"
        assert entry.user_id == "user-456"
        assert entry.status_code == 200
        assert entry.log_hash is not None
        assert entry.signature is not None

    def test_entry_has_user_hash(self, audit_service):
        """Test that user ID is hashed for privacy."""
        entry = audit_service.create_entry(
            request_id="req-123",
            user_id="user-456",
            endpoint="/test",
            method="GET",
            status_code=200,
            latency_ms=10,
        )

        assert entry.user_hash is not None
        assert len(entry.user_hash) == 8  # Short hash
        assert entry.user_hash != entry.user_id

    def test_entry_with_pii_result(self, audit_service):
        """Test entry with PII detection result."""
        pii_result = {
            "pii_detected": True,
            "entity_count": 2,
            "risk_level": "HIGH",
            "entities": [
                {"type": "EMAIL_ADDRESS", "risk_level": "MEDIUM"},
                {"type": "CREDIT_CARD", "risk_level": "HIGH"},
            ],
        }

        entry = audit_service.create_entry(
            request_id="req-123",
            user_id="user-456",
            endpoint="/test",
            method="POST",
            status_code=200,
            latency_ms=100,
            pii_result=pii_result,
        )

        assert entry.pii_detected is True
        assert entry.pii_entity_count == 2
        assert entry.pii_risk_level == "HIGH"

    def test_token_tracking(self, audit_service):
        """Test token usage tracking."""
        entry = audit_service.create_entry(
            request_id="req-123",
            user_id="user-456",
            endpoint="/test",
            method="POST",
            status_code=200,
            latency_ms=100,
            prompt_tokens=50,
            completion_tokens=100,
        )

        assert entry.prompt_tokens == 50
        assert entry.completion_tokens == 100
        assert entry.total_tokens == 150


class TestTamperDetection:
    """Test cryptographic tamper detection."""

    def test_verify_untampered_entry(self, audit_service):
        """Test that untampered entry passes verification."""
        entry = audit_service.create_entry(
            request_id="req-123",
            user_id="user-456",
            endpoint="/test",
            method="GET",
            status_code=200,
            latency_ms=10,
        )

        result = audit_service.verify_integrity(entry)

        assert result["is_valid"] is True
        assert result["hash_valid"] is True
        assert result["signature_valid"] is True
        assert len(result["errors"]) == 0

    def test_detect_status_code_tampering(self, audit_service):
        """Test that status code tampering is detected."""
        entry = audit_service.create_entry(
            request_id="req-123",
            user_id="user-456",
            endpoint="/test",
            method="GET",
            status_code=200,
            latency_ms=10,
        )

        # Tamper with status code
        entry.status_code = 500

        result = audit_service.verify_integrity(entry)

        assert result["is_valid"] is False
        assert result["hash_valid"] is False

    def test_detect_user_id_tampering(self, audit_service):
        """Test that user ID tampering is detected."""
        entry = audit_service.create_entry(
            request_id="req-123",
            user_id="user-456",
            endpoint="/test",
            method="GET",
            status_code=200,
            latency_ms=10,
        )

        # Tamper with user ID
        entry.user_id = "admin-hack"

        result = audit_service.verify_integrity(entry)

        assert result["is_valid"] is False

    def test_detect_signature_modification(self, audit_service):
        """Test that signature modification is detected."""
        entry = audit_service.create_entry(
            request_id="req-123",
            user_id="user-456",
            endpoint="/test",
            method="GET",
            status_code=200,
            latency_ms=10,
        )

        # Modify signature
        entry.signature = "fake_signature_" + entry.signature[15:]

        result = audit_service.verify_integrity(entry)

        assert result["is_valid"] is False
        assert result["signature_valid"] is False


class TestChainIntegrity:
    """Test blockchain-style chain integrity."""

    def test_chain_links_entries(self, audit_service):
        """Test that entries are chain-linked."""
        entry1 = audit_service.create_entry(
            request_id="req-1",
            user_id="user-1",
            endpoint="/test",
            method="GET",
            status_code=200,
            latency_ms=10,
        )

        entry2 = audit_service.create_entry(
            request_id="req-2",
            user_id="user-2",
            endpoint="/test",
            method="GET",
            status_code=200,
            latency_ms=10,
            previous_hash=entry1.log_hash,
        )

        # Entry2 should reference entry1's hash
        assert entry2.chain_hash == entry1.log_hash

    def test_verify_valid_chain(self, audit_service):
        """Test verification of valid chain."""
        entry1 = audit_service.create_entry(
            request_id="req-1",
            user_id="user-1",
            endpoint="/test",
            method="GET",
            status_code=200,
            latency_ms=10,
        )

        entry2 = audit_service.create_entry(
            request_id="req-2",
            user_id="user-2",
            endpoint="/test",
            method="GET",
            status_code=200,
            latency_ms=10,
        )

        result = audit_service.verify_chain(entry2, entry1)

        assert result["chain_valid"] is True
        assert result["sequence_valid"] is True

    def test_detect_chain_break(self, audit_service):
        """Test detection of broken chain (deleted log)."""
        entry1 = audit_service.create_entry(
            request_id="req-1",
            user_id="user-1",
            endpoint="/test",
            method="GET",
            status_code=200,
            latency_ms=10,
        )

        # Skip entry2, go directly to entry3 with wrong chain
        entry3 = audit_service.create_entry(
            request_id="req-3",
            user_id="user-3",
            endpoint="/test",
            method="GET",
            status_code=200,
            latency_ms=10,
            previous_hash="fake_hash",  # Wrong chain
        )

        result = audit_service.verify_chain(entry3, entry1)

        assert result["chain_valid"] is False


class TestBatchVerification:
    """Test batch verification of multiple entries."""

    def test_verify_batch_all_valid(self, audit_service):
        """Test batch verification with all valid entries."""
        entries = []
        for i in range(3):
            entry = audit_service.create_entry(
                request_id=f"req-{i}",
                user_id=f"user-{i}",
                endpoint="/test",
                method="GET",
                status_code=200,
                latency_ms=10,
            )
            entries.append(entry)

        result = audit_service.verify_chain_batch(entries)

        assert result["all_valid"] is True
        assert result["entries_checked"] == 3
        assert len(result["individual_failures"]) == 0
        assert len(result["chain_failures"]) == 0
