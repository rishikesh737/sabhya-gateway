"""
Sabhya AI - Immutable Audit Log Service with Cryptographic Tamper Detection

Security Decisions:
- SHA-256 content hashing for data integrity
- HMAC-SHA256 signature for authenticity verification
- Chain hashing (blockchain-style) to detect log deletion/reordering
- PostgreSQL trigger prevents UPDATE operations
- Automatic archival with hash verification
"""

import os
import json
import hmac
import hashlib
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import uuid4

from sqlalchemy import Column, String, Float, Integer, Boolean, DateTime, Text, Index
from app.models import Base

logger = logging.getLogger(__name__)

# SECURITY: HMAC secret for signing audit logs
AUDIT_HMAC_SECRET = os.getenv(
    "AUDIT_HMAC_SECRET",
    "audit-secret-change-in-production-minimum-32-chars"
).encode()


# ============================================================================
# AUDIT LOG MODEL
# ============================================================================

class AuditLogEntry(Base):
    """
    Immutable audit log entry with cryptographic tamper detection.
    
    Once created, entries cannot be modified (enforced by DB trigger).
    Chain hashing enables detection of deleted or reordered entries.
    """
    __tablename__ = "audit_logs_v2"
    
    # Primary identification
    id = Column(String(36), primary_key=True)
    request_id = Column(String(36), unique=True, nullable=False)
    
    # Timing
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    latency_ms = Column(Float, nullable=False)
    
    # User tracking (privacy-preserving)
    user_id = Column(String(64), nullable=False)  # Can be hashed
    user_hash = Column(String(16))  # Short hash for display
    
    # Request details
    endpoint = Column(String(255), nullable=False)
    method = Column(String(10), nullable=False)
    model = Column(String(100))
    status_code = Column(Integer, nullable=False)
    
    # Token usage
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    
    # PII detection results
    pii_detected = Column(Boolean, default=False)
    pii_entity_count = Column(Integer, default=0)
    pii_risk_level = Column(String(10))  # HIGH, MEDIUM, LOW
    pii_entities_json = Column(Text)  # JSON array, anonymized
    
    # Security flags
    request_blocked = Column(Boolean, default=False)
    rate_limited = Column(Boolean, default=False)
    auth_method = Column(String(20))  # jwt, legacy_key
    
    # Cryptographic integrity
    log_hash = Column(String(64), nullable=False, unique=True)  # SHA-256
    signature = Column(String(64), nullable=False)  # HMAC-SHA256
    chain_hash = Column(String(64))  # Hash of previous log
    sequence_number = Column(Integer)  # For ordering
    
    # Metadata
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    archived = Column(Boolean, default=False)
    archive_hash = Column(String(64))  # Verification hash when archived
    
    # Indexes for common queries
    __table_args__ = (
        Index('ix_audit_logs_v2_user_id', 'user_id'),
        Index('ix_audit_logs_v2_timestamp', 'timestamp'),
        Index('ix_audit_logs_v2_pii_detected', 'pii_detected'),
        Index('ix_audit_logs_v2_status_code', 'status_code'),
    )


# ============================================================================
# AUDIT SERVICE
# ============================================================================

class AuditService:
    """
    Service for creating and verifying immutable audit logs.
    
    All entries are cryptographically signed and chain-linked
    to enable tamper and deletion detection.
    """
    
    def __init__(self, hmac_secret: bytes = AUDIT_HMAC_SECRET):
        """
        Initialize audit service.
        
        Args:
            hmac_secret: Secret key for HMAC signing
        """
        self.hmac_secret = hmac_secret
        self._last_hash: Optional[str] = None
        self._sequence: int = 0
    
    def create_entry(
        self,
        request_id: str,
        user_id: str,
        endpoint: str,
        method: str,
        status_code: int,
        latency_ms: float,
        model: Optional[str] = None,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        pii_result: Optional[Dict[str, Any]] = None,
        request_blocked: bool = False,
        rate_limited: bool = False,
        auth_method: str = "jwt",
        previous_hash: Optional[str] = None
    ) -> AuditLogEntry:
        """
        Create a new immutable audit log entry.
        
        Args:
            request_id: Unique request identifier
            user_id: User identifier (will be hashed for display)
            endpoint: API endpoint called
            method: HTTP method
            status_code: Response status code
            latency_ms: Request duration in milliseconds
            model: LLM model used (if applicable)
            prompt_tokens: Input token count
            completion_tokens: Output token count
            pii_result: PII detection result dict
            request_blocked: Whether request was blocked
            rate_limited: Whether request was rate limited
            auth_method: Authentication method used
            previous_hash: Hash of previous log (for chaining)
            
        Returns:
            AuditLogEntry with cryptographic signatures
        """
        log_id = str(uuid4())
        now = datetime.utcnow()
        
        # Create user hash for display (privacy-preserving)
        user_hash = hashlib.sha256(user_id.encode()).hexdigest()[:8]
        
        # Parse PII result
        pii_detected = False
        pii_entity_count = 0
        pii_risk_level = None
        pii_entities_json = None
        
        if pii_result:
            pii_detected = pii_result.get('pii_detected', False)
            pii_entity_count = pii_result.get('entity_count', 0)
            pii_risk_level = pii_result.get('risk_level')
            # Store anonymized entity types only (not actual values)
            if pii_result.get('entities'):
                safe_entities = [
                    {'type': e['type'], 'risk_level': e.get('risk_level')}
                    for e in pii_result['entities']
                ]
                pii_entities_json = json.dumps(safe_entities)
        
        # Determine chain hash
        chain_hash = previous_hash or self._last_hash
        
        # Increment sequence
        self._sequence += 1
        
        # Create entry
        entry = AuditLogEntry(
            id=log_id,
            request_id=request_id,
            timestamp=now,
            latency_ms=latency_ms,
            user_id=user_id,
            user_hash=user_hash,
            endpoint=endpoint,
            method=method,
            model=model,
            status_code=status_code,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            pii_detected=pii_detected,
            pii_entity_count=pii_entity_count,
            pii_risk_level=pii_risk_level,
            pii_entities_json=pii_entities_json,
            request_blocked=request_blocked,
            rate_limited=rate_limited,
            auth_method=auth_method,
            chain_hash=chain_hash,
            sequence_number=self._sequence,
            created_at=now,
        )
        
        # Generate cryptographic signatures
        entry.log_hash = self._generate_hash(entry)
        entry.signature = self._generate_signature(entry)
        
        # Update chain state
        self._last_hash = entry.log_hash
        
        logger.debug(f"Audit entry created: {log_id[:8]}, hash: {entry.log_hash[:16]}...")
        
        return entry
    
    def _generate_hash(self, entry: AuditLogEntry) -> str:
        """
        Generate SHA-256 hash of log entry content.
        
        This hash covers all critical fields to detect any modification.
        """
        hash_data = {
            "id": entry.id,
            "request_id": entry.request_id,
            "timestamp": entry.timestamp.isoformat() if entry.timestamp else None,
            "user_id": entry.user_id,
            "endpoint": entry.endpoint,
            "method": entry.method,
            "model": entry.model,
            "status_code": entry.status_code,
            "latency_ms": entry.latency_ms,
            "prompt_tokens": entry.prompt_tokens,
            "completion_tokens": entry.completion_tokens,
            "pii_detected": entry.pii_detected,
            "pii_risk_level": entry.pii_risk_level,
            "request_blocked": entry.request_blocked,
            "chain_hash": entry.chain_hash,
            "sequence_number": entry.sequence_number,
        }
        
        # Deterministic JSON serialization
        json_str = json.dumps(hash_data, sort_keys=True, default=str)
        return hashlib.sha256(json_str.encode()).hexdigest()
    
    def _generate_signature(self, entry: AuditLogEntry) -> str:
        """
        Generate HMAC-SHA256 signature for authenticity verification.
        
        The signature includes the content hash and chain hash,
        making it impossible to forge without the secret key.
        """
        signature_data = f"{entry.log_hash}:{entry.chain_hash or 'genesis'}"
        return hmac.new(
            self.hmac_secret,
            signature_data.encode(),
            hashlib.sha256
        ).hexdigest()
    
    def verify_integrity(self, entry: AuditLogEntry) -> Dict[str, Any]:
        """
        Verify that an audit log entry has not been tampered with.
        
        Args:
            entry: Audit log entry to verify
            
        Returns:
            {
                'is_valid': bool,
                'hash_valid': bool,
                'signature_valid': bool,
                'errors': [list of issues]
            }
        """
        errors = []
        
        # Recalculate and verify hash
        expected_hash = self._generate_hash(entry)
        hash_valid = (expected_hash == entry.log_hash)
        if not hash_valid:
            errors.append(
                f"Content hash mismatch: expected {expected_hash[:16]}..., "
                f"got {entry.log_hash[:16]}..."
            )
        
        # Recalculate and verify signature
        expected_sig = self._generate_signature(entry)
        signature_valid = hmac.compare_digest(expected_sig, entry.signature)
        if not signature_valid:
            errors.append("HMAC signature verification failed - possible tampering")
        
        is_valid = hash_valid and signature_valid
        
        if not is_valid:
            logger.warning(
                f"Audit log integrity check FAILED for {entry.id}: {errors}"
            )
        
        return {
            'is_valid': is_valid,
            'hash_valid': hash_valid,
            'signature_valid': signature_valid,
            'errors': errors
        }
    
    def verify_chain(
        self,
        current: AuditLogEntry,
        previous: AuditLogEntry
    ) -> Dict[str, Any]:
        """
        Verify that two consecutive log entries form a valid chain.
        
        Detects if logs have been deleted or reordered between entries.
        
        Args:
            current: Current log entry
            previous: Previous log entry (should be immediately before current)
            
        Returns:
            {
                'is_valid': bool,
                'chain_valid': bool,
                'sequence_valid': bool,
                'errors': [list of issues]
            }
        """
        errors = []
        
        # Verify chain link
        chain_valid = (current.chain_hash == previous.log_hash)
        if not chain_valid:
            errors.append(
                f"Chain broken: current.chain_hash={current.chain_hash[:16]}... "
                f"!= previous.log_hash={previous.log_hash[:16]}..."
            )
        
        # Verify sequence order
        sequence_valid = (
            current.sequence_number is not None and
            previous.sequence_number is not None and
            current.sequence_number == previous.sequence_number + 1
        )
        if not sequence_valid:
            errors.append(
                f"Sequence gap: {previous.sequence_number} -> {current.sequence_number}"
            )
        
        is_valid = chain_valid and sequence_valid
        
        if not is_valid:
            logger.warning(
                f"Chain integrity check FAILED between "
                f"{previous.id[:8]} and {current.id[:8]}: {errors}"
            )
        
        return {
            'is_valid': is_valid,
            'chain_valid': chain_valid,
            'sequence_valid': sequence_valid,
            'errors': errors
        }
    
    def verify_chain_batch(
        self,
        entries: List[AuditLogEntry]
    ) -> Dict[str, Any]:
        """
        Verify integrity of a batch of log entries.
        
        Args:
            entries: List of entries (should be in sequence order)
            
        Returns:
            {
                'all_valid': bool,
                'entries_checked': int,
                'individual_failures': [...],
                'chain_failures': [...]
            }
        """
        individual_failures = []
        chain_failures = []
        
        for i, entry in enumerate(entries):
            # Verify individual entry
            result = self.verify_integrity(entry)
            if not result['is_valid']:
                individual_failures.append({
                    'entry_id': entry.id,
                    'sequence': entry.sequence_number,
                    'errors': result['errors']
                })
            
            # Verify chain (except first entry)
            if i > 0:
                chain_result = self.verify_chain(entry, entries[i - 1])
                if not chain_result['is_valid']:
                    chain_failures.append({
                        'current_id': entry.id,
                        'previous_id': entries[i - 1].id,
                        'errors': chain_result['errors']
                    })
        
        all_valid = len(individual_failures) == 0 and len(chain_failures) == 0
        
        return {
            'all_valid': all_valid,
            'entries_checked': len(entries),
            'individual_failures': individual_failures,
            'chain_failures': chain_failures
        }


# Singleton instance
audit_service = AuditService()


# ============================================================================
# DATABASE MIGRATION HELPERS
# ============================================================================

def get_immutability_sql() -> List[str]:
    """
    Generate SQL statements to enforce immutability on audit_logs_v2 table.
    
    Returns:
        List of SQL statements to execute
    """
    return [
        # Create function to prevent updates
        """
        CREATE OR REPLACE FUNCTION prevent_audit_log_update()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION 'Audit logs are immutable and cannot be updated. '
                'Attempted to modify entry: %', OLD.id;
        END;
        $$ LANGUAGE plpgsql;
        """,
        
        # Create trigger to call function on UPDATE
        """
        DROP TRIGGER IF EXISTS audit_log_v2_immutability ON audit_logs_v2;
        CREATE TRIGGER audit_log_v2_immutability
        BEFORE UPDATE ON audit_logs_v2
        FOR EACH ROW
        EXECUTE FUNCTION prevent_audit_log_update();
        """,
        
        # Optionally prevent DELETE (uncomment for full immutability)
        # """
        # CREATE OR REPLACE FUNCTION prevent_audit_log_delete()
        # RETURNS TRIGGER AS $$
        # BEGIN
        #     RAISE EXCEPTION 'Audit logs cannot be deleted. Entry: %', OLD.id;
        # END;
        # $$ LANGUAGE plpgsql;
        # 
        # CREATE TRIGGER audit_log_v2_no_delete
        # BEFORE DELETE ON audit_logs_v2
        # FOR EACH ROW
        # EXECUTE FUNCTION prevent_audit_log_delete();
        # """,
    ]
