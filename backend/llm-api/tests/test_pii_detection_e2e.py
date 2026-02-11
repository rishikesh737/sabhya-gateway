"""
Sabhya AI - PII Detection E2E Tests (Hybrid Engine)

Tests for the hybrid Presidio + Regex PII detection pipeline:
- Email, credit card, SSN, phone number detection via regex
- Risk classification (HIGH/MEDIUM/LOW)
- Blocking mode behavior (BLOCK vs FLAG_ONLY)
- Partial redaction
- Empty/clean input handling
- Multiple entities in single input
"""

import pytest
import os


@pytest.fixture
def pii_svc():
    """Create PII detection service instance."""
    from app.services.pii_detection import PIIDetectionService
    return PIIDetectionService()


@pytest.fixture
def blocking_pii_svc():
    """Create PII service in BLOCK mode."""
    old_val = os.environ.get("PII_BLOCKING_MODE", "FLAG_ONLY")
    os.environ["PII_BLOCKING_MODE"] = "BLOCK_HIGH_RISK"
    from app.services.pii_detection import PIIDetectionService
    svc = PIIDetectionService()
    yield svc
    os.environ["PII_BLOCKING_MODE"] = old_val


# =========================================================================
# REGEX ENGINE TESTS — These must ALWAYS pass regardless of Presidio
# =========================================================================

class TestRegexEmailDetection:
    """Test email detection via regex fallback."""

    def test_detects_standard_email(self, pii_svc):
        result = pii_svc.detect_pii("Contact me at john.doe@example.com please")
        assert result["pii_detected"] is True
        types = [e["type"] for e in result["entities"]]
        assert "EMAIL_ADDRESS" in types

    def test_detects_email_with_subdomain(self, pii_svc):
        result = pii_svc.detect_pii("Send to admin@mail.corp.example.org")
        assert result["pii_detected"] is True
        types = [e["type"] for e in result["entities"]]
        assert "EMAIL_ADDRESS" in types


class TestRegexCreditCardDetection:
    """Test credit card number detection via regex."""

    def test_detects_visa_card(self, pii_svc):
        result = pii_svc.detect_pii("My card is 4532015112830366")
        assert result["pii_detected"] is True
        types = [e["type"] for e in result["entities"]]
        assert "CREDIT_CARD" in types

    def test_detects_card_with_spaces(self, pii_svc):
        result = pii_svc.detect_pii("Card: 4532 0151 1283 0366")
        assert result["pii_detected"] is True
        types = [e["type"] for e in result["entities"]]
        assert "CREDIT_CARD" in types

    def test_detects_card_with_dashes(self, pii_svc):
        result = pii_svc.detect_pii("Number 4532-0151-1283-0366")
        assert result["pii_detected"] is True
        types = [e["type"] for e in result["entities"]]
        assert "CREDIT_CARD" in types


class TestRegexSSNDetection:
    """Test Social Security Number detection via regex."""

    def test_detects_ssn_with_dashes(self, pii_svc):
        result = pii_svc.detect_pii("SSN: 123-45-6789")
        assert result["pii_detected"] is True
        types = [e["type"] for e in result["entities"]]
        assert "US_SSN" in types

    def test_detects_ssn_with_spaces(self, pii_svc):
        result = pii_svc.detect_pii("SSN is 123 45 6789")
        assert result["pii_detected"] is True
        types = [e["type"] for e in result["entities"]]
        assert "US_SSN" in types


class TestRegexPhoneDetection:
    """Test phone number detection via regex."""

    def test_detects_us_phone_parentheses(self, pii_svc):
        result = pii_svc.detect_pii("Call me at (555) 123-4567")
        assert result["pii_detected"] is True
        types = [e["type"] for e in result["entities"]]
        assert "PHONE_NUMBER" in types

    def test_detects_international_phone(self, pii_svc):
        result = pii_svc.detect_pii("Reach us at +1-555-123-4567")
        assert result["pii_detected"] is True
        types = [e["type"] for e in result["entities"]]
        assert "PHONE_NUMBER" in types


# =========================================================================
# RISK CLASSIFICATION TESTS
# =========================================================================

class TestRiskClassification:
    """Test that entity types map to correct risk levels."""

    def test_credit_card_is_high_risk(self, pii_svc):
        result = pii_svc.detect_pii("4532015112830366")
        cc_entities = [e for e in result["entities"] if e["type"] == "CREDIT_CARD"]
        assert len(cc_entities) > 0
        assert cc_entities[0]["risk_level"] == "HIGH"

    def test_ssn_is_high_risk(self, pii_svc):
        result = pii_svc.detect_pii("SSN: 123-45-6789")
        ssn_entities = [e for e in result["entities"] if e["type"] == "US_SSN"]
        assert len(ssn_entities) > 0
        assert ssn_entities[0]["risk_level"] == "HIGH"

    def test_email_is_medium_risk(self, pii_svc):
        result = pii_svc.detect_pii("john@example.com")
        email_entities = [e for e in result["entities"] if e["type"] == "EMAIL_ADDRESS"]
        assert len(email_entities) > 0
        assert email_entities[0]["risk_level"] == "MEDIUM"


# =========================================================================
# EDGE CASES
# =========================================================================

class TestEdgeCases:
    """Test edge cases and clean input handling."""

    def test_empty_string_returns_no_pii(self, pii_svc):
        result = pii_svc.detect_pii("")
        assert result["pii_detected"] is False

    def test_none_input_returns_no_pii(self, pii_svc):
        result = pii_svc.detect_pii(None)
        assert result["pii_detected"] is False

    def test_normal_text_no_false_positives(self, pii_svc):
        """Normal text should not trigger regex-based PII detection for critical types."""
        result = pii_svc.detect_pii("The quick brown fox jumps over the lazy dog")
        # If PII is detected, it should only be LOW risk (e.g., DATE_TIME from Presidio)
        if result["pii_detected"]:
            high_risk = [e for e in result["entities"] if e["risk_level"] == "HIGH"]
            assert len(high_risk) == 0, f"False positive HIGH risk: {high_risk}"


class TestMultiplePIITypes:
    """Test detection of multiple PII types in single input."""

    def test_detects_email_and_phone(self, pii_svc):
        text = "Email: admin@example.com, Phone: (555) 123-4567"
        result = pii_svc.detect_pii(text)
        assert result["pii_detected"] is True
        types = {e["type"] for e in result["entities"]}
        assert "EMAIL_ADDRESS" in types
        assert "PHONE_NUMBER" in types

    def test_detects_ssn_and_credit_card(self, pii_svc):
        text = "SSN: 123-45-6789, Card: 4532015112830366"
        result = pii_svc.detect_pii(text)
        assert result["pii_detected"] is True
        types = {e["type"] for e in result["entities"]}
        assert "US_SSN" in types
        assert "CREDIT_CARD" in types

    def test_risk_level_highest_wins(self, pii_svc):
        """Overall risk should be the maximum across all detected entities."""
        text = "Email john@x.com and SSN 123-45-6789"
        result = pii_svc.detect_pii(text)
        assert result["pii_detected"] is True
        assert result.get("risk_level") == "HIGH"  # SSN is HIGH


class TestBlockingMode:
    """Test PII blocking behavior."""

    def test_block_mode_blocks_high_risk(self, blocking_pii_svc):
        """BLOCK mode should flag high-risk PII for blocking."""
        result = blocking_pii_svc.detect_pii("SSN: 123-45-6789")
        assert result["pii_detected"] is True
        # In BLOCK mode, action should be 'BLOCK' for HIGH risk
        assert result.get("action") == "BLOCK" or result.get("should_block", False) is True


class TestRedaction:
    """Test partial redaction of PII entities."""

    def test_entities_are_redacted(self, pii_svc):
        """Detected entity text should be partially redacted."""
        result = pii_svc.detect_pii("john.doe@example.com")
        assert result["pii_detected"] is True
        for entity in result["entities"]:
            if entity["type"] == "EMAIL_ADDRESS":
                # Text should NOT contain the full email
                assert entity["text"] != "john.doe@example.com"
                # Should contain redaction markers (*, etc.)
                assert "*" in entity["text"] or "..." in entity["text"] or len(entity["text"]) < len("john.doe@example.com")
