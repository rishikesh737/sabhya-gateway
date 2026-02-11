"""
Sabhya AI - Audit Immutability Tests

Tests for cryptographic audit log guarantees:
- Content hash covers all critical fields
- HMAC signature is unique per entry
- Tampering ANY field invalidates hash + signature
- Chain hashing detects deletions/reordering
- Batch verification validates entire chains
- Immutability SQL generation for DB triggers
"""

import pytest
from copy import deepcopy


@pytest.fixture
def audit_svc():
    """Create audit service with deterministic HMAC secret."""
    from app.services.audit import AuditService
    return AuditService(hmac_secret=b"test-immutability-secret-32chars!")


@pytest.fixture
def sample_entry(audit_svc):
    """Create a standard audit entry for testing."""
    return audit_svc.create_entry(
        request_id="immut-test-001",
        user_id="test-user-42",
        endpoint="/v1/chat/completions",
        method="POST",
        status_code=200,
        latency_ms=123.45,
        model="mistral",
        prompt_tokens=100,
        completion_tokens=200,
        pii_result={"pii_detected": True, "entity_count": 1, "risk_level": "HIGH"},
        auth_method="jwt"
    )


class TestContentHashIntegrity:
    """Test SHA-256 content hashing covers all critical fields."""

    def test_hash_is_deterministic(self, audit_svc, sample_entry):
        """Recalculating hash on unchanged entry should match."""
        original_hash = sample_entry.log_hash
        recalculated = audit_svc._generate_hash(sample_entry)
        assert recalculated == original_hash

    def test_hash_changes_on_status_code_tamper(self, audit_svc, sample_entry):
        """Modifying status_code should change hash."""
        original_hash = sample_entry.log_hash
        sample_entry.status_code = 500
        new_hash = audit_svc._generate_hash(sample_entry)
        assert new_hash != original_hash

    def test_hash_changes_on_endpoint_tamper(self, audit_svc, sample_entry):
        """Modifying endpoint should change hash."""
        original_hash = sample_entry.log_hash
        sample_entry.endpoint = "/admin/secret"
        new_hash = audit_svc._generate_hash(sample_entry)
        assert new_hash != original_hash

    def test_hash_changes_on_latency_tamper(self, audit_svc, sample_entry):
        """Modifying latency should change hash."""
        original_hash = sample_entry.log_hash
        sample_entry.latency_ms = 1.0
        new_hash = audit_svc._generate_hash(sample_entry)
        assert new_hash != original_hash

    def test_hash_changes_on_user_id_tamper(self, audit_svc, sample_entry):
        """Modifying user_id should change hash."""
        original_hash = sample_entry.log_hash
        sample_entry.user_id = "attacker"
        new_hash = audit_svc._generate_hash(sample_entry)
        assert new_hash != original_hash

    def test_hash_changes_on_pii_flag_tamper(self, audit_svc, sample_entry):
        """Modifying pii_detected should change hash."""
        original_hash = sample_entry.log_hash
        sample_entry.pii_detected = False
        new_hash = audit_svc._generate_hash(sample_entry)
        assert new_hash != original_hash

    def test_hash_changes_on_request_blocked_tamper(self, audit_svc, sample_entry):
        """Modifying request_blocked should change hash."""
        original_hash = sample_entry.log_hash
        sample_entry.request_blocked = True
        new_hash = audit_svc._generate_hash(sample_entry)
        assert new_hash != original_hash


class TestHMACSignature:
    """Test HMAC-SHA256 signature authenticity."""

    def test_signature_is_present(self, sample_entry):
        """Entry must have a non-empty signature."""
        assert sample_entry.signature is not None
        assert len(sample_entry.signature) > 0

    def test_signature_unique_per_entry(self, audit_svc):
        """Different entries must produce different signatures."""
        e1 = audit_svc.create_entry(
            request_id="sig-1", user_id="u1",
            endpoint="/a", method="GET",
            status_code=200, latency_ms=10
        )
        e2 = audit_svc.create_entry(
            request_id="sig-2", user_id="u2",
            endpoint="/b", method="POST",
            status_code=201, latency_ms=20
        )
        assert e1.signature != e2.signature

    def test_signature_changes_with_different_secret(self, sample_entry):
        """Same entry signed with different secret should differ."""
        from app.services.audit import AuditService
        alt_svc = AuditService(hmac_secret=b"completely-different-secret-32ch!")
        alt_sig = alt_svc._generate_signature(sample_entry)
        assert alt_sig != sample_entry.signature

    def test_verify_detects_forged_signature(self, audit_svc, sample_entry):
        """Forged signature should fail verification."""
        sample_entry.signature = "0" * 64  # Forged
        result = audit_svc.verify_integrity(sample_entry)
        assert result['is_valid'] is False
        assert result['signature_valid'] is False


class TestFieldTamperDetection:
    """Test that tampering ANY logged field is detected by verify_integrity."""

    TAMPER_FIELDS = [
        ("request_id", "hacked-id"),
        ("user_id", "admin-escalation"),
        ("endpoint", "/admin/drop-db"),
        ("method", "DELETE"),
        ("status_code", 500),  # Downgrade a 200 to 500
        ("latency_ms", 0.01),
        ("model", "gpt-4-turbo"),
        ("pii_detected", False),
        ("request_blocked", True),
    ]

    @pytest.mark.parametrize("field,fake_value", TAMPER_FIELDS)
    def test_tamper_detected(self, audit_svc, sample_entry, field, fake_value):
        """Tampering field={field} should be detected."""
        setattr(sample_entry, field, fake_value)
        result = audit_svc.verify_integrity(sample_entry)
        assert result['is_valid'] is False, f"Tamper on '{field}' was NOT detected"


class TestChainHashing:
    """Test blockchain-style chain hashing for deletion detection."""

    def test_chain_links_consecutive_entries(self, audit_svc):
        """Second entry's chain_hash should reference first entry's log_hash."""
        e1 = audit_svc.create_entry(
            request_id="chain-1", user_id="u",
            endpoint="/a", method="GET",
            status_code=200, latency_ms=10
        )
        e2 = audit_svc.create_entry(
            request_id="chain-2", user_id="u",
            endpoint="/b", method="GET",
            status_code=200, latency_ms=10,
            previous_hash=e1.log_hash
        )
        assert e2.chain_hash == e1.log_hash

    def test_chain_detects_gap(self, audit_svc):
        """Skipping an entry should break chain verification."""
        e1 = audit_svc.create_entry(
            request_id="ch-1", user_id="u",
            endpoint="/a", method="GET",
            status_code=200, latency_ms=10
        )
        # Create e2 but simulate it being deleted by skipping directly to e3
        e3 = audit_svc.create_entry(
            request_id="ch-3", user_id="u",
            endpoint="/c", method="GET",
            status_code=200, latency_ms=10,
            previous_hash="deleted_entry_hash"
        )
        result = audit_svc.verify_chain(e3, e1)
        assert result['chain_valid'] is False

    def test_batch_verification_passes_for_valid_chain(self, audit_svc):
        """Batch of correctly linked entries should pass."""
        entries = []
        prev_hash = None
        for i in range(5):
            e = audit_svc.create_entry(
                request_id=f"batch-{i}", user_id="u",
                endpoint="/test", method="GET",
                status_code=200, latency_ms=10,
                previous_hash=prev_hash
            )
            prev_hash = e.log_hash
            entries.append(e)

        result = audit_svc.verify_chain_batch(entries)
        assert result['all_valid'] is True
        assert result['entries_checked'] == 5

    def test_batch_detects_tampered_entry(self, audit_svc):
        """Batch verification should catch a tampered entry mid-chain."""
        entries = []
        prev_hash = None
        for i in range(4):
            e = audit_svc.create_entry(
                request_id=f"btamp-{i}", user_id="u",
                endpoint="/test", method="GET",
                status_code=200, latency_ms=10,
                previous_hash=prev_hash
            )
            prev_hash = e.log_hash
            entries.append(e)

        # Tamper with entry [2]
        entries[2].status_code = 999

        result = audit_svc.verify_chain_batch(entries)
        assert result['all_valid'] is False
        assert len(result['individual_failures']) > 0


class TestImmutabilitySQLGeneration:
    """Test that SQL trigger DDL is generated for PostgreSQL enforcement."""

    def test_sql_statements_generated(self):
        """Immutability SQL should produce trigger statements."""
        from app.services.audit import get_immutability_sql
        statements = get_immutability_sql()
        assert len(statements) > 0
        combined = " ".join(statements).upper()
        assert "TRIGGER" in combined or "FUNCTION" in combined
