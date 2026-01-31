# backend/llm-api/app/security/pii.py
import re
from typing import Tuple, List


class PIIScanner:
    """
    Deterministic PII Scanner using Regex.
    Prioritizes low latency (sub-5ms) over NLP context awareness.
    """

    # 1. Redaction Patterns (Sanitize)
    # Simple, high-confidence patterns to avoid false positives.
    PATTERNS = {
        "EMAIL": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
        "PHONE": re.compile(
            r"\b(?:\+?(\d{1,3}))?[-. (]*(\d{3})[-. )]*(\d{3})[-. ]*(\d{4})\b"
        ),
        "IPV4": re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
        # Basic Credit Card (16 digits, naive check)
        "CREDIT_CARD": re.compile(r"\b(?:\d{4}[- ]?){3}\d{4}\b"),
    }

    # 2. Blocking Patterns (Reject Request)
    # If these are found, we abort the request entirely.
    BLOCK_PATTERNS = {
        "PRIVATE_KEY": re.compile(
            r"-----BEGIN (?:RSA|DSA|EC|OPENSSH) PRIVATE KEY-----"
        ),
        "AWS_KEY": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    }

    def scan_and_redact(self, text: str) -> Tuple[str, bool, bool]:
        """
        Scans text for PII.
        Returns:
            (clean_text, pii_found, blocked_found)
        """
        if not text:
            return text, False, False

        # 1. Check Blocklist First (Fail Fast)
        for label, pattern in self.BLOCK_PATTERNS.items():
            if pattern.search(text):
                return text, True, True  # Block immediately

        # 2. Redact PII
        cleaned_text = text
        pii_detected = False

        for label, pattern in self.PATTERNS.items():
            if pattern.search(cleaned_text):
                pii_detected = True
                cleaned_text = pattern.sub(f"<{label}>", cleaned_text)

        return cleaned_text, pii_detected, False


# Singleton instance
scanner = PIIScanner()
