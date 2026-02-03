from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
import os
import re
import time
import uuid
import hashlib
import requests
import structlog

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.services.rag import rag_service
from app.database import get_db, init_db
from app.models import AuditLog

# Setup Logging
log = structlog.get_logger()

# --- 🔐 Security ---
security = HTTPBearer()
API_KEYS = os.getenv("API_KEYS", "").split(",")

def verify_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if credentials.credentials not in API_KEYS:
        raise HTTPException(status_code=403, detail="Invalid API Key")
    return credentials.credentials

def hash_key(key: str) -> str:
    """Create a short hash for audit logging (privacy-preserving)."""
    return hashlib.sha256(key.encode()).hexdigest()[:8]


# --- 🛡️ PII Detection (Regex-based Guardrails) ---
PII_PATTERNS = {
    "email": r"\b[\w\.-]+@[\w\.-]+\.\w{2,}\b",
    "credit_card": r"\b(?:\d{4}[- ]?){3}\d{4}\b",
    "phone": r"\b(?:\+?1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b",
}

def detect_pii(text: str) -> bool:
    """Scan text for PII patterns (email, credit card, phone). Returns True if any found.
    Robust against None/empty inputs.
    """
    try:
        if not text or not isinstance(text, str):
            return False
        for pattern_name, pattern in PII_PATTERNS.items():
            if re.search(pattern, text, re.IGNORECASE):
                log.warning("pii_detected", pattern=pattern_name)
                return True
        return False
    except Exception as e:
        log.error("pii_detection_error", error=str(e))
        return False


# --- 📝 Models ---
DEFAULT_MODEL = "mistral:7b-instruct-q4_K_M"

class ChatRequest(BaseModel):
    model: Optional[str] = None
    messages: list


# --- 🚦 Rate Limiting (Proxy-aware for AWS/Load Balancers) ---
def get_client_ip(request: Request) -> str:
    """Get client IP, checking X-Forwarded-For header for proxy/load balancer scenarios."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # X-Forwarded-For can be comma-separated; first IP is the original client
        return forwarded.split(",")[0].strip()
    return get_remote_address(request)

limiter = Limiter(key_func=get_client_ip)


# --- 🚀 App Lifecycle ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database tables on startup."""
    log.info("initializing_database")
    init_db()
    log.info("database_ready")
    yield
    log.info("graceful_shutdown")


app = FastAPI(title="Sabhya AI API", version="0.3.0", lifespan=lifespan)

# Attach rate limiter to app
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# --- 🛡️ CORS SETTINGS (CRITICAL FOR FRONTEND) ---
# TODO: In production, replace with actual domain(s)
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS if CORS_ORIGINS != ["*"] else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- 🚦 Routes ---
@app.get("/health/live")
def health_check():
    return {"status": "alive"}


@app.post("/v1/documents")
async def upload_document(
    file: UploadFile = File(...),
    api_key: str = Depends(verify_api_key),
    db: Session = Depends(get_db)
):
    """Upload a PDF document for RAG ingestion."""
    request_id = str(uuid.uuid4())
    start_time = time.time()
    status_code = 200
    
    try:
        # Save file temporarily
        file_location = f"/tmp/{file.filename}"
        with open(file_location, "wb+") as file_object:
            file_object.write(await file.read())
        
        # Ingest into ChromaDB
        chunks = rag_service.ingest_pdf(file_location, file.filename)
        
        result = {
            "filename": file.filename, 
            "chunks_indexed": chunks, 
            "status": "success"
        }
        
    except Exception as e:
        status_code = 500
        log.error("upload_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
    
    finally:
        # Always log to audit table
        latency_ms = (time.time() - start_time) * 1000
        audit_entry = AuditLog(
            request_id=request_id,
            user_hash=hash_key(api_key),
            model="rag",
            endpoint="/v1/documents",
            status_code=status_code,
            latency_ms=latency_ms,
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            pii_detected=False,
        )
        db.add(audit_entry)
        db.commit()
        log.info("audit_logged_upload", request_id=request_id)
    
    return result


@app.post("/v1/chat/completions")
@limiter.limit("50/minute")
async def chat_completion(
    request: Request,
    chat_req: ChatRequest,
    api_key: str = Depends(verify_api_key),
    db: Session = Depends(get_db)
):
    """Chat completion with RAG context injection. Rate limited to 50 req/min."""
    request_id = str(uuid.uuid4())
    start_time = time.time()
    status_code = 200
    prompt_tokens = 0
    completion_tokens = 0
    pii_detected = False
    
    # Dynamic Model Routing: Fallback to default if not specified
    model = chat_req.model if chat_req.model else DEFAULT_MODEL
    log.info("model_routing", requested=chat_req.model, resolved=model)
    
    try:
        # Extract the last user message
        user_query = chat_req.messages[-1]["content"]
        
        # --- 🛡️ PII Detection (Passive Mode: Flag, don't block) ---
        pii_detected = detect_pii(user_query)
        if pii_detected:
            log.warning("pii_flagged_in_request", request_id=request_id)
        
        # 1. Retrieve Context from ChromaDB (now returns tuple: docs, context_note)
        context_docs, context_note = rag_service.query(user_query)
        context_text = "\n".join(context_docs) if context_docs else "No specific context available."
        
        # 2. Construct Prompt with RAG context + metadata note
        system_prompt = f"You are a helpful assistant. Use this context to answer: {context_text}"
        if context_note:
            system_prompt += f"\n\n{context_note}"
        
        # 3. Call Ollama LLM with dynamic model
        ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_query}
            ],
            "stream": False
        }
        
        # Estimate tokens (rough heuristic)
        prompt_tokens = len(system_prompt + user_query) // 4
        
        resp = requests.post(f"{ollama_url}/api/chat", json=payload, timeout=60)
        
        if resp.status_code == 200:
            content = resp.json()["message"]["content"]
            completion_tokens = len(content) // 4
            result = {
                "id": request_id,
                "choices": [{"message": {"role": "assistant", "content": content}}],
                "model": model,
                "pii_detected": pii_detected,
                "usage": {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": prompt_tokens + completion_tokens
                }
            }
        else:
            status_code = 502
            error_detail = f"Ollama Error ({model}): {resp.text}"
            log.error("ollama_error", model=model, status=resp.status_code)
            raise HTTPException(status_code=502, detail=error_detail)
            
    except HTTPException:
        raise
    except Exception as e:
        status_code = 500
        log.error("chat_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
    
    finally:
        # Always log to audit table with PII flag
        latency_ms = (time.time() - start_time) * 1000
        audit_entry = AuditLog(
            request_id=request_id,
            user_hash=hash_key(api_key),
            model=model,
            endpoint="/v1/chat/completions",
            status_code=status_code,
            latency_ms=latency_ms,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            pii_detected=pii_detected,
        )
        db.add(audit_entry)
        db.commit()
        log.info("audit_logged_chat", request_id=request_id, pii_detected=pii_detected)
    
    return result


@app.get("/v1/audit/logs")
async def get_audit_logs(
    limit: int = 50,
    api_key: str = Depends(verify_api_key),
    db: Session = Depends(get_db)
):
    """Retrieve audit logs for governance dashboard."""
    logs = db.query(AuditLog).order_by(AuditLog.timestamp.desc()).limit(limit).all()
    return [
        {
            "request_id": log.request_id,
            "timestamp": log.timestamp,
            "user_hash": log.user_hash,
            "model": log.model,
            "endpoint": log.endpoint,
            "status_code": log.status_code,
            "latency_ms": log.latency_ms,
            "total_tokens": log.total_tokens,
            "pii_detected": log.pii_detected,
        }
        for log in logs
    ]
