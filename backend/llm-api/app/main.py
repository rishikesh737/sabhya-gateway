from app.routes.auth import router as auth_router
from dotenv import load_dotenv
load_dotenv()
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Request, Response
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
import os, time, uuid, json, structlog
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from app.services.rag import rag_service
from app.prompts import build_system_prompt
from app.database import get_db, init_db, get_session_factory
from app.models import AuditLog
from app.config import settings, validate_settings_on_startup
from app.services.pii_detection import pii_service
from app.services.content_safety import content_safety_service
from app.auth.security import get_current_user, require_role, hash_api_key, Roles, UserInfo
from app.middleware.security import add_security_middleware, security_headers_middleware, request_id_middleware
from app.routes.health import router as health_router
from app.services.audit import audit_service, AuditLogEntry

log = structlog.get_logger()

def hash_key(key: str) -> str:
    import hashlib
    return hashlib.sha256(key.encode()).hexdigest()[:8]

DEFAULT_MODEL = "mistral:7b-instruct-q4_K_M"

class ChatRequest(BaseModel):
    model: Optional[str] = None
    messages: list

def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded: return forwarded.split(",")[0].strip()
    return get_remote_address(request)

limiter = Limiter(key_func=get_client_ip, headers_enabled=True)

@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("sabhya_ai_starting", version="0.4.0")
    validate_settings_on_startup()
    init_db()
    os.makedirs("/app/data", exist_ok=True)
    yield

app = FastAPI(title="Sabhya AI API", version="0.4.0", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
add_security_middleware(app)
app.middleware("http")(request_id_middleware)
app.middleware("http")(security_headers_middleware)
app.include_router(health_router)
app.include_router(auth_router, prefix="/v1/auth", tags=["Authentication"])

@app.post("/v1/documents", dependencies=[Depends(require_role(Roles.USER))])
async def upload_document(file: UploadFile = File(...), current_user: UserInfo = Depends(get_current_user), db: Session = Depends(get_db)):
    request_id = str(uuid.uuid4())
    start_time = time.time()
    status_code = 200
    try:
        os.makedirs("/app/data", exist_ok=True)
        file_location = f"/app/data/{file.filename}"
        with open(file_location, "wb+") as file_object:
            file_object.write(await file.read())
        chunks = rag_service.ingest_pdf(file_location, file.filename)
        return {"filename": file.filename, "chunks_indexed": chunks, "status": "success"}
    except Exception as e:
        status_code = 500
        log.error("upload_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        latency_ms = (time.time() - start_time) * 1000
        audit_entry = AuditLog(request_id=request_id, user_hash=hash_key(current_user.user_id), model="rag", endpoint="/v1/documents", status_code=status_code, latency_ms=latency_ms, prompt_tokens=0, completion_tokens=0, total_tokens=0, pii_detected=False)
        db.add(audit_entry)
        db.commit()

@app.post("/v1/chat/completions")
@limiter.limit("50/minute")
async def chat_completion(request: Request, response: Response, chat_req: ChatRequest, current_user: UserInfo = Depends(get_current_user), db: Session = Depends(get_db)):
    request_id = str(uuid.uuid4())
    start_time = time.time()
    status_code = 200
    pii_result = None
    model = chat_req.model if chat_req.model else DEFAULT_MODEL
    try:
        all_user_messages = [m["content"] for m in chat_req.messages if m["role"] == "user"]
        full_text = " ".join(all_user_messages)
        pii_result = pii_service.detect_pii(full_text)
        if pii_result["pii_detected"] and pii_service.should_block_request(pii_result):
             raise HTTPException(status_code=400, detail=pii_service.get_blocking_message(pii_result))
        
        user_query = chat_req.messages[-1]["content"]
        context_docs, context_note = rag_service.query(user_query)
        system_prompt = build_system_prompt(context_docs, context_note, use_cot=False)
        
        import requests as http_requests
        ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        payload = {"model": model, "messages": [{"role": "system", "content": system_prompt}, *chat_req.messages], "stream": False}
        resp = http_requests.post(f"{ollama_url}/api/chat", json=payload, timeout=60)
        
        if resp.status_code == 200:
            content = resp.json()["message"]["content"]
            
            # --- CALCULATE TOKENS (NEW LOGIC) ---
            prompt_tokens = len(str(payload)) // 4
            completion_tokens = len(content) // 4
            
            return {
                "id": request_id, 
                "choices": [{"message": {"role": "assistant", "content": content}}], 
                "model": model, 
                "pii_detected": pii_result["pii_detected"], 
                "sources": rag_service.get_last_sources(),
                "usage": {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": prompt_tokens + completion_tokens
                }
            }
        else:
            raise HTTPException(status_code=502, detail=f"Ollama Error: {resp.text}")
    except Exception as e:
        status_code = 500
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.add(AuditLog(request_id=request_id, user_hash=hash_key(current_user.user_id), model=model, endpoint="/v1/chat/completions", status_code=status_code, latency_ms=(time.time()-start_time)*1000, pii_detected=pii_result["pii_detected"] if pii_result else False))
        db.commit()

@app.get("/v1/audit/logs")
async def get_audit_logs(limit: int = 50, db: Session = Depends(get_db), current_user: UserInfo = Depends(get_current_user)):
    return db.query(AuditLogEntry).order_by(AuditLogEntry.timestamp.desc()).limit(limit).all()

@app.get("/rag/documents", dependencies=[Depends(require_role(Roles.USER))])
async def list_documents(current_user: UserInfo = Depends(get_current_user)):
    try:
        data_dir = "/app/data"
        if not os.path.exists(data_dir): return {"documents": []}
        files = [f for f in os.listdir(data_dir) if f.endswith(".pdf") or f.endswith(".txt")]
        return {"documents": files}
    except Exception as e:
        return {"documents": [], "error": str(e)}

@app.delete("/rag/documents/{filename}", dependencies=[Depends(require_role(Roles.USER))])
async def delete_document(filename: str, current_user: UserInfo = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        file_path = f"/app/data/{filename}"
        if os.path.exists(file_path):
            os.remove(file_path)
            return {"status": "deleted", "filename": filename}
        else:
            raise HTTPException(status_code=404, detail="Document not found")
    except Exception as e:
         raise HTTPException(status_code=500, detail=str(e))
