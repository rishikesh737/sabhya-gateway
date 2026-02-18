"""
Sabhya AI - Enterprise PII Detection Service
Using Microsoft Presidio for NLP-based PII detection.

Security Decisions:
- Uses Presidio's NLP models for context-aware detection (vs simple regex)
- Risk classification: HIGH (SSN, Credit Card), MEDIUM (Phone, Email), LOW (Names)
- Configurable blocking modes: ALLOW_ALL, FLAG_ONLY, BLOCK_HIGH_RISK, BLOCK_ALL
- Anonymization capability for logs (privacy-preserving audit trails)
"""

import logging
import os
import re
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Try to import Presidio, fallback to regex if not available
try:
    from presidio_analyzer import AnalyzerEngine, RecognizerResult
    from presidio_anonymizer import AnonymizerEngine
    from presidio_anonymizer.entities import OperatorConfig

    PRESIDIO_AVAILABLE = True
    logger.info("Presidio NLP engine loaded successfully")
except ImportError:
    PRESIDIO_AVAILABLE = False
    logger.warning("Presidio not installed, falling back to regex-based PII detection")


class PIIBlockingMode(str, Enum):
    """PII handling modes."""

    ALLOW_ALL = "ALLOW_ALL"  # No blocking, flag in logs only
    FLAG_ONLY = "FLAG_ONLY"  # Flag but don't include in response
    BLOCK_HIGH_RISK = "BLOCK_HIGH_RISK"  # Block HIGH risk only
    BLOCK_ALL = "BLOCK_ALL"  # Block all detected PII


class PIIRiskLevel(str, Enum):
    """Risk classification for PII types."""

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


# Entity type to risk level mapping
ENTITY_RISK_MAPPING = {
    # HIGH RISK - Financial & Government IDs
    "CREDIT_CARD": PIIRiskLevel.HIGH,
    "US_SSN": PIIRiskLevel.HIGH,
    "US_BANK_NUMBER": PIIRiskLevel.HIGH,
    "IBAN_CODE": PIIRiskLevel.HIGH,
    "US_PASSPORT": PIIRiskLevel.HIGH,
    "UK_NHS": PIIRiskLevel.HIGH,
    # MEDIUM RISK - Contact Information
    "PHONE_NUMBER": PIIRiskLevel.MEDIUM,
    "EMAIL_ADDRESS": PIIRiskLevel.MEDIUM,
    "IP_ADDRESS": PIIRiskLevel.MEDIUM,
    "US_DRIVER_LICENSE": PIIRiskLevel.MEDIUM,
    # LOW RISK - General PII
    "PERSON": PIIRiskLevel.LOW,
    "LOCATION": PIIRiskLevel.LOW,
    "DATE_TIME": PIIRiskLevel.LOW,
    "NRP": PIIRiskLevel.LOW,  # Nationality, Religion, Political
}

# Fallback regex patterns (when Presidio is not available)
REGEX_PATTERNS = {
    "EMAIL_ADDRESS": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
    "CREDIT_CARD": r"\b(?:\d{4}[-\s]?){3}\d{4}\b",
    "PHONE_NUMBER": r"\b(?:\+?1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b",
    "US_SSN": r"\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b",
    "IP_ADDRESS": r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
}


class PIIDetectionService:
    """
    Enterprise-grade PII detection service.

    Uses Microsoft Presidio when available, falls back to regex otherwise.
    Provides risk classification and anonymization capabilities.
    """

    def __init__(self):
        """Initialize PII detection engines."""
        self.blocking_mode = PIIBlockingMode(
            os.getenv("PII_BLOCKING_MODE", "FLAG_ONLY")
        )
        self.confidence_threshold = float(os.getenv("PII_CONFIDENCE_THRESHOLD", "0.5"))
        self.anonymize_logs = os.getenv("PII_ANONYMIZE_LOGS", "true").lower() == "true"

        # Always initialize regex patterns as baseline
        self._init_regex()

        if PRESIDIO_AVAILABLE:
            self._init_presidio()
        else:
            self.use_presidio = False

    def _init_presidio(self):
        """Initialize Presidio analyzer and anonymizer."""
        try:
            self.analyzer = AnalyzerEngine()
            self.anonymizer = AnonymizerEngine()
            self.use_presidio = True
            logger.info("Presidio PII detection initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Presidio: {e}")
            self.use_presidio = False

    def _init_regex(self):
        """Initialize regex-based patterns."""
        self.patterns = {
            name: re.compile(pattern, re.IGNORECASE)
            for name, pattern in REGEX_PATTERNS.items()
        }

    def detect_pii(
        self, text: str, language: str = "en", threshold: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Detect PII entities in text with confidence scores.
        """
        if not text or not isinstance(text, str):
            return self._empty_result()

        threshold = threshold or self.confidence_threshold

        try:
            entities = []

            # 1. Run Presidio if available
            if self.use_presidio:
                presidio_result = self._detect_with_presidio(text, language, threshold)
                if presidio_result["pii_detected"]:
                    entities.extend(presidio_result["entities"])

            # 2. Run Regex (always run for critical patterns check)
            regex_result = self._detect_with_regex(text)
            if regex_result["pii_detected"]:
                # Deduplicate: Only add if not overlapping with existing Presidio entities
                for regex_entity in regex_result["entities"]:
                    if not self._is_overlapping(regex_entity, entities):
                        entities.append(regex_entity)

            if not entities:
                return self._empty_result()

            # Recalculate risk and counts
            max_risk = PIIRiskLevel.LOW
            high_risk_count = 0

            for entity in entities:
                risk_val = entity.get("risk_level", "LOW")
                if risk_val == "HIGH":
                    max_risk = PIIRiskLevel.HIGH
                    high_risk_count += 1
                elif risk_val == "MEDIUM" and max_risk != PIIRiskLevel.HIGH:
                    max_risk = PIIRiskLevel.MEDIUM

            action = self._determine_action(max_risk)

            return {
                "pii_detected": True,
                "entities": entities,
                "risk_level": max_risk.value,
                "action": action,
                "entity_count": len(entities),
                "high_risk_count": high_risk_count,
            }

        except Exception as e:
            logger.error(f"PII detection error: {e}")
            return {
                "pii_detected": True,
                "entities": [],
                "risk_level": PIIRiskLevel.MEDIUM.value,
                "action": "FLAG",
                "entity_count": 0,
                "high_risk_count": 0,
                "error": str(e),
            }

    def _is_overlapping(self, entity, existing_entities):
        """Check if entity overlaps with any existing entity."""
        for existing in existing_entities:
            # Check for overlap in ranges
            if max(entity["start"], existing["start"]) < min(
                entity["end"], existing["end"]
            ):
                return True
        return False

    def _detect_with_presidio(
        self, text: str, language: str, threshold: float
    ) -> Dict[str, Any]:
        """Detect PII using Presidio NLP engine."""
        try:
            results: List[RecognizerResult] = self.analyzer.analyze(
                text=text, language=language, score_threshold=threshold
            )
        except Exception:
            return self._empty_result()

        if not results:
            return self._empty_result()

        entities = []

        for result in results:
            # Get risk level for entity type
            risk = ENTITY_RISK_MAPPING.get(result.entity_type, PIIRiskLevel.LOW)

            # Partially redact the detected text for logging
            original_text = text[result.start : result.end]
            redacted_text = self._partial_redact(original_text, result.entity_type)

            entities.append(
                {
                    "type": result.entity_type,
                    "text": redacted_text,
                    "start": result.start,
                    "end": result.end,
                    "confidence": round(result.score, 2),
                    "risk_level": risk.value,
                }
            )

        return {"pii_detected": True, "entities": entities}

    def _detect_with_regex(self, text: str) -> Dict[str, Any]:
        """Fallback regex-based detection."""
        entities = []

        for entity_type, pattern in self.patterns.items():
            for match in pattern.finditer(text):
                risk = ENTITY_RISK_MAPPING.get(entity_type, PIIRiskLevel.LOW)

                original_text = match.group()
                redacted_text = self._partial_redact(original_text, entity_type)

                entities.append(
                    {
                        "type": entity_type,
                        "text": redacted_text,
                        "start": match.start(),
                        "end": match.end(),
                        "confidence": 0.85,  # Fixed confidence for regex
                        "risk_level": risk.value,
                    }
                )

        if not entities:
            return self._empty_result()

        return {"pii_detected": True, "entities": entities}

    def anonymize_text(self, text: str, replacement: str = "[REDACTED]") -> str:
        """
        Anonymize all detected PII in text.

        Args:
            text: Input text
            replacement: Replacement string for PII

        Returns:
            Anonymized text
        """
        if not text:
            return text

        try:
            if self.use_presidio:
                results = self.analyzer.analyze(text=text, language="en")
                if not results:
                    return text

                operators = {
                    "DEFAULT": OperatorConfig("replace", {"new_value": replacement})
                }
                anonymized = self.anonymizer.anonymize(
                    text=text, analyzer_results=results, operators=operators
                )
                return anonymized.text
            else:
                # Regex-based anonymization
                anonymized = text
                for pattern in self.patterns.values():
                    anonymized = pattern.sub(replacement, anonymized)
                return anonymized
        except Exception as e:
            logger.error(f"Anonymization error: {e}")
            return text

    def _partial_redact(self, text: str, entity_type: str) -> str:
        """
        Partially redact text for logging (show first/last chars).
        Example: "john@example.com" -> "j***@e***.com"
        """
        if len(text) <= 4:
            return "*" * len(text)

        if entity_type == "EMAIL_ADDRESS" and "@" in text:
            local, domain = text.split("@", 1)
            return f"{local[0]}***@{domain[0]}***.{domain.split('.')[-1]}"
        elif entity_type in ("CREDIT_CARD", "US_SSN"):
            return f"****-****-****-{text[-4:]}"
        elif entity_type == "PHONE_NUMBER":
            return f"***-***-{text[-4:]}"
        else:
            return f"{text[0]}{'*' * (len(text) - 2)}{text[-1]}"

    def _determine_action(self, risk_level: PIIRiskLevel) -> str:
        """Determine action based on risk level and blocking mode."""
        if self.blocking_mode == PIIBlockingMode.ALLOW_ALL:
            return "ALLOW"
        elif self.blocking_mode == PIIBlockingMode.FLAG_ONLY:
            return "FLAG"
        elif self.blocking_mode == PIIBlockingMode.BLOCK_HIGH_RISK:
            return "BLOCK" if risk_level == PIIRiskLevel.HIGH else "FLAG"
        elif self.blocking_mode == PIIBlockingMode.BLOCK_ALL:
            return "BLOCK"
        return "FLAG"

    def _empty_result(self) -> Dict[str, Any]:
        """Return empty result for no PII detected."""
        return {
            "pii_detected": False,
            "entities": [],
            "risk_level": PIIRiskLevel.LOW.value,
            "action": "ALLOW",
            "entity_count": 0,
            "high_risk_count": 0,
        }

    def should_block_request(self, pii_result: Dict[str, Any]) -> bool:
        """Check if request should be blocked based on PII detection."""
        return pii_result.get("action") == "BLOCK"

    def get_blocking_message(self, pii_result: Dict[str, Any]) -> str:
        """Generate user-friendly blocking message."""
        high_risk = pii_result.get("high_risk_count", 0)
        total = pii_result.get("entity_count", 0)

        if high_risk > 0:
            return (
                f"Request blocked: {high_risk} high-risk PII pattern(s) detected "
                f"(e.g., SSN, credit card). Please remove sensitive data and retry."
            )
        return f"Request blocked: {total} PII pattern(s) detected. Please remove sensitive data."


# Singleton instance
pii_service = PIIDetectionService()
