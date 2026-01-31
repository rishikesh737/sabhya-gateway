import time
from sqlalchemy import Column, Integer, String, Float, Boolean
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(String, index=True, nullable=False)
    timestamp = Column(Float, default=time.time, nullable=False)

    # Governance Metadata
    user_hash = Column(String, nullable=False)
    model = Column(String, nullable=False)
    endpoint = Column(String, nullable=False)

    # Performance & Reliability
    status_code = Column(Integer, nullable=False)
    latency_ms = Column(Float, nullable=False)

    # ---- Phase 2.3: Token Accounting ----
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)

    # ---- Phase 3.1: Security Events ----
    pii_detected = Column(Boolean, default=False)
    request_blocked = Column(Boolean, default=False)
