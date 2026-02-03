"""
Sabhya AI v0.4.0 - Enterprise LLM Governance Gateway
Main FastAPI application with security hardening.
"""

# Load environment variables FIRST before any other imports
from dotenv import load_dotenv
load_dotenv()

from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Request
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
import os
import time
import uuid
import json
import structlog

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.services.rag import rag_service
from app.prompts import build_system_prompt
from app.database import get_db, init_db
from app.models import AuditLog
from app.config import settings, validate_settings_on_startup

# v0.4.0 Security Imports
from app.services.pii_detection import pii_service
from app.services.content_safety import content_safety_service
from app.auth.security import (
    get_current_user,
    require_role,
    verify_legacy_api_key,
    hash_api_key,
    Roles,
    UserInfo,
    LEGACY_AUTH_ENABLED,
)
from app.middleware.security import (
    add_security_middleware,
    security_headers_middleware,
    request_id_middleware,
)
from app.routes.health import router as health_router
from app.services.audit import audit_service, AuditLogEntry

# Setup Logging
log = structlog.get_logger()

# --- 🔐 Legacy Security (Backward Compatibility) ---
security = HTTPBearer(auto_error=False)
# Use settings object which properly loads from .env
API_KEYS = settings.get_api_keys_list()


def verify_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify API key (supports both JWT and legacy keys)."""
    if credentials is None:
        raise HTTPException(status_code=401, detail="Authorization required")
    
    token = credentials.credentials
    
    # Try legacy API key first
    if LEGACY_AUTH_ENABLED and token in API_KEYS:
        return token
    
    # Otherwise, treat as JWT (future - currently fallback to legacy check)
    if token in API_KEYS:
        return token
    
    raise HTTPException(status_code=403, detail="Invalid API Key")


def hash_key(key: str) -> str:
    """Create a short hash for audit logging (privacy-preserving)."""
    import hashlib
    return hashlib.sha256(key.encode()).hexdigest()[:8]


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
        return forwarded.split(",")[0].strip()
    return get_remote_address(request)


limiter = Limiter(key_func=get_client_ip)


# --- 🚀 App Lifecycle ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database and validate settings on startup."""
    log.info("sabhya_ai_starting", version="0.4.0")
    
    # Validate configuration
    config_result = validate_settings_on_startup()
    if not config_result['valid']:
        log.error("configuration_invalid", warnings=config_result['warnings'])
    
    # Initialize database
    log.info("initializing_database")
    init_db()
    log.info("database_ready")
    
    yield
    log.info("graceful_shutdown")


app = FastAPI(
    title="Sabhya AI API",
    version="0.4.0",
    description="Enterprise LLM Governance Gateway with Security Hardening",
    lifespan=lifespan
)

# Attach rate limiter to app
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# --- 🛡️ Security Middleware ---
add_security_middleware(app)
app.middleware("http")(request_id_middleware)
app.middleware("http")(security_headers_middleware)

# --- 🏥 Health Routes ---
app.include_router(health_router)


# --- 🚦 Routes ---

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
    pii_result = None
    request_blocked = False

    # Dynamic Model Routing
    model = chat_req.model if chat_req.model else DEFAULT_MODEL
    log.info("model_routing", requested=chat_req.model, resolved=model)

    try:
        # Extract the last user message
        user_query = chat_req.messages[-1]["content"]

        # --- 🛡️ Presidio PII Detection (v0.4.0 upgrade) ---
        pii_result = pii_service.detect_pii(user_query)
        
        if pii_result['pii_detected']:
            log.warning(
                "pii_flagged_in_request",
                request_id=request_id,
                risk_level=pii_result['risk_level'],
                entity_count=pii_result['entity_count']
            )
            
            # Block if action is BLOCK
            if pii_service.should_block_request(pii_result):
                request_blocked = True
                status_code = 400
                raise HTTPException(
                    status_code=400,
                    detail=pii_service.get_blocking_message(pii_result)
                )

        # --- 🛡️ Content Safety Check (v0.4.0) ---
        safety_result = content_safety_service.check_content(user_query)
        if not safety_result.is_safe:
            log.warning(
                "content_safety_blocked",
                request_id=request_id,
                category=safety_result.matched_category,
                reason=safety_result.blocked_reason
            )
            status_code = 400
            request_blocked = True
            raise HTTPException(
                status_code=400,
                detail=safety_result.blocked_reason or "Request blocked: Content violates usage policy"
            )

        # 1. Retrieve Context from ChromaDB
        context_docs, context_note = rag_service.query(user_query)
        context_text = "\n".join(context_docs) if context_docs else "No specific context available."

        # 2. Construct Prompt with RAG context
        system_prompt = f"You are a helpful assistant. Use this context to answer: {context_text}"
        if context_note:
            system_prompt += f"\n\n{context_note}"

        # 3. Call Ollama LLM
        import requests as http_requests
        ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_query}
            ],
            "stream": False
        }

        # Estimate tokens
        prompt_tokens = len(system_prompt + user_query) // 4

        resp = http_requests.post(f"{ollama_url}/api/chat", json=payload, timeout=60)

        if resp.status_code == 200:
            content = resp.json()["message"]["content"]
            completion_tokens = len(content) // 4
            result = {
                "id": request_id,
                "choices": [{"message": {"role": "assistant", "content": content}}],
                "model": model,
                "pii_detected": pii_result['pii_detected'] if pii_result else False,
                "pii_risk_level": pii_result.get('risk_level') if pii_result else None,
                "sources": rag_service.get_last_sources(),  # RAG source citations
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
        # Always log to audit with enhanced PII data
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
            pii_detected=pii_result['pii_detected'] if pii_result else False,
        )
        db.add(audit_entry)
        db.commit()
        log.info(
            "audit_logged_chat",
            request_id=request_id,
            pii_detected=pii_result['pii_detected'] if pii_result else False,
            risk_level=pii_result.get('risk_level') if pii_result else None
        )

    return result


@app.post("/v1/chat/completions/stream")
@limiter.limit("50/minute")
async def chat_completion_stream(
    request: Request,
    chat_req: ChatRequest,
    api_key: str = Depends(verify_api_key),
    db: Session = Depends(get_db)
):
    """
    Streaming chat completion with SSE (Server-Sent Events).
    Returns text chunks as they're generated by the LLM.
    """
    import requests as http_requests
    
    request_id = str(uuid.uuid4())
    start_time = time.time()
    
    # Dynamic Model Routing
    model = chat_req.model if chat_req.model else DEFAULT_MODEL
    
    # Extract the last user message
    user_query = chat_req.messages[-1]["content"]
    
    # PII Detection
    pii_result = pii_service.detect_pii(user_query)
    if pii_service.should_block_request(pii_result):
        async def error_stream():
            yield f"data: {json.dumps({'error': 'PII detected in request'})}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(error_stream(), media_type="text/event-stream")
    
    # Content Safety Check
    safety_result = content_safety_service.check_content(user_query)
    if not safety_result.is_safe:
        async def error_stream():
            yield f"data: {json.dumps({'error': safety_result.blocked_reason})}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(error_stream(), media_type="text/event-stream")
    
    # RAG Context
    context_docs, context_note = rag_service.query(user_query)
    
    # Smart Prompting: detailed system prompt with CoT for complex queries
    # Skip CoT only for very short queries (< 2 words) to reduce verbosity/latency
    use_cot = True
    if len(user_query.split()) < 2:
        use_cot = False
        
    system_prompt = build_system_prompt(
        context_docs=context_docs,
        context_note=context_note,
        use_cot=use_cot
    )
    
    # Build messages with conversation history
    messages = [{"role": "system", "content": system_prompt}]
    
    # Inject user instruction if CoT is enabled (overpowers model laziness)
    req_messages = [m.copy() for m in chat_req.messages] # Deep copy to be safe
    if use_cot and req_messages and req_messages[-1]["role"] == "user":
        req_messages[-1]["content"] += "\n\n[SYSTEM INSTRUCTION: You MUST step-by-step reason inside <thought> tags before answering.]"
        
    messages.extend(req_messages)
    
    ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    
    async def generate_stream():
        """Generator that streams LLM output as SSE events."""
        full_content = ""
        try:
            # Call Ollama with streaming
            resp = http_requests.post(
                f"{ollama_url}/api/chat",
                json={
                    "model": model,
                    "messages": messages,
                    "stream": True,
                },
                stream=True,
                timeout=120
            )
            
            if resp.status_code != 200:
                yield f"data: {json.dumps({'error': f'Ollama error: {resp.status_code}'})}\n\n"
                yield "data: [DONE]\n\n"
                return
            
            for line in resp.iter_lines():
                if line:
                    try:
                        chunk = json.loads(line)
                        if "message" in chunk and "content" in chunk["message"]:
                            token = chunk["message"]["content"]
                            full_content += token
                            yield f"data: {json.dumps({'token': token})}\n\n"
                        
                        # Check if done
                        if chunk.get("done", False):
                            break
                    except json.JSONDecodeError:
                        continue
            
            # Send final event with sources and metadata
            sources = rag_service.get_last_sources()
            final_data = {
                "done": True,
                "id": request_id,
                "model": model,
                "sources": sources,
                "full_content": full_content,
                "pii_detected": pii_result['pii_detected'] if pii_result else False,
            }
            yield f"data: {json.dumps(final_data)}\n\n"
            yield "data: [DONE]\n\n"
            
            # Log to audit
            latency_ms = (time.time() - start_time) * 1000
            log.info("stream_complete", request_id=request_id, tokens=len(full_content.split()))
            
        except Exception as e:
            log.error("stream_error", error=str(e))
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
            yield "data: [DONE]\n\n"
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Request-ID": request_id,
        }
    )


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


# --- 🔍 Audit Integrity Verification (Admin Only) ---
@app.get("/v1/audit/verify/{log_id}")
async def verify_audit_log(
    log_id: str,
    api_key: str = Depends(verify_api_key),
    db: Session = Depends(get_db)
):
    """Verify integrity of a specific audit log entry."""
    # This endpoint is prepared for v0.4.0 immutable audit logs
    # Currently returns placeholder - will be fully implemented with AuditLogEntry
    return {
        "log_id": log_id,
        "status": "verification_pending",
        "message": "Immutable audit log verification available in next release"
    }


# --- 🗑️ Delete Audit Log Entry ---
@app.delete("/v1/audit/logs/{request_id}")
async def delete_audit_log(
    request_id: str,
    api_key: str = Depends(verify_api_key),
    db: Session = Depends(get_db)
):
    """Delete a specific audit log entry by request_id."""
    entry = db.query(AuditLog).filter(AuditLog.request_id == request_id).first()
    
    if not entry:
        raise HTTPException(status_code=404, detail="Audit log entry not found")
    
    db.delete(entry)
    db.commit()
    
    log.info("audit_log_deleted", request_id=request_id, deleted_by=hash_key(api_key))
    
    return {
        "status": "deleted",
        "request_id": request_id,
        "message": "Audit log entry deleted successfully"
    }

