from fastapi import FastAPI, Request, HTTPException, Depends, BackgroundTasks, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import httpx
import os
import time
import asyncio
import hashlib
import uuid
import structlog
import tiktoken
from typing import List
from pydantic import BaseModel
from dotenv import load_dotenv
from sqlalchemy.orm import Session
from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    generate_latest,
    CONTENT_TYPE_LATEST,
    REGISTRY,
    PROCESS_COLLECTOR,
    PLATFORM_COLLECTOR,
    GC_COLLECTOR,
)

# ---- CRITICAL STABILITY FIX ----
# Unregister default collectors to prevent crashes in hardened/read-only containers
try:
    REGISTRY.unregister(PROCESS_COLLECTOR)
    REGISTRY.unregister(PLATFORM_COLLECTOR)
    REGISTRY.unregister(GC_COLLECTOR)
except ValueError:
    pass  # Already unregistered

from app.database import init_db, get_db
from app.models import AuditLog
from app.security.pii import scanner
from app.security.guardrails import guardrails

load_dotenv()

# ---- Logging Setup ----
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
)
log = structlog.get_logger()

# ---- Config ----
API_KEYS = set(filter(None, os.getenv("API_KEYS", "").split(",")))
RATE_LIMIT = int(os.getenv("RATE_LIMIT_PER_MIN", "30"))
OLLAMA_BASE_URL = "http://ollama:11434"
OLLAMA_CHAT_URL = f"{OLLAMA_BASE_URL}/api/chat"
ALLOWED_MODELS = {"mistral:7b-instruct-q4_K_M", "tinyllama"}

# ---- PROMETHEUS METRICS DEFINITION ----
REQUESTS_TOTAL = Counter(
    "llm_gateway_http_requests_total",
    "Total HTTP requests processed",
    ["method", "endpoint", "status_code"],
)
REQUEST_LATENCY = Histogram(
    "llm_gateway_http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"],
    buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0],
)
TOKENS_TOTAL = Counter(
    "llm_gateway_tokens_total",
    "Total tokens processed (prompt + completion)",
    ["type", "model"],
)
SECURITY_VIOLATIONS = Counter(
    "llm_gateway_security_violations_total",
    "Total security policy violations blocked",
    ["violation_type"],
)
PII_DETECTED = Counter(
    "llm_gateway_pii_detected_total",
    "Total requests where PII was detected and redacted",
    ["model"],
)
OLLAMA_UP = Gauge(
    "llm_gateway_ollama_up", "Status of the Ollama inference engine (1=Up, 0=Down)"
)

# ---- ROBUST TOKENIZER SETUP ----
encoding = None
try:
    encoding = tiktoken.get_encoding("cl100k_base")
except Exception:
    try:
        log.warning(
            "tokenizer_download_failed", detail="cl100k_base failed, trying gpt2"
        )
        encoding = tiktoken.get_encoding("gpt2")
    except Exception:
        log.warning(
            "tokenizer_offline",
            detail="Network unreachable. Using heuristic token counting.",
        )
        encoding = None


def count_tokens(text: str) -> int:
    if encoding:
        try:
            return len(encoding.encode(text))
        except Exception:
            pass
    return len(text) // 4 if text else 0


def upgrade_db_schema(engine):
    with engine.connect() as conn:
        try:
            conn.execute(
                "ALTER TABLE audit_logs ADD COLUMN pii_detected BOOLEAN DEFAULT 0"
            )
            conn.execute(
                "ALTER TABLE audit_logs ADD COLUMN request_blocked BOOLEAN DEFAULT 0"
            )
        except Exception:
            pass


# ---- App Lifecycle ----
async def lifespan(app: FastAPI):
    from app.database import engine

    init_db()
    upgrade_db_schema(engine)
    yield


app = FastAPI(
    title="Local LLM Gateway",
    description="Enterprise-grade AI Gateway with strict governance.",
    version="4.1.0",
    lifespan=lifespan,
)

clients = {}
semaphore = asyncio.Semaphore(1)
security_scheme = HTTPBearer()


def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()[:8]


# ---- Middleware (METRICS LAYER 1) ----
@app.middleware("http")
async def add_request_id_and_audit(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    request.state.request_id = request_id
    structlog.contextvars.bind_contextvars(request_id=request_id)

    start_time = time.time()
    status_code = 500

    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    except Exception as e:
        status_code = 500
        raise e
    finally:
        duration = time.time() - start_time
        try:
            REQUESTS_TOTAL.labels(
                method=request.method,
                endpoint=request.url.path,
                status_code=str(status_code),
            ).inc()
            REQUEST_LATENCY.labels(
                method=request.method, endpoint=request.url.path
            ).observe(duration)
        except Exception as metric_err:
            log.error("metrics_collection_failed", error=str(metric_err))


# ---- Auth ----
def authenticate(creds: HTTPAuthorizationCredentials = Depends(security_scheme)):
    key = creds.credentials.strip()
    if key not in API_KEYS:
        log.warning("auth_failed", reason="invalid_key")
        raise HTTPException(status_code=403, detail="Invalid API key")

    now = time.time()
    key_hash = hash_key(key)
    hits = clients.get(key_hash, [])
    hits = [t for t in hits if now - t < 60]
    if len(hits) >= RATE_LIMIT:
        log.warning("rate_limit_exceeded", client_id=key_hash)
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    hits.append(now)
    clients[key_hash] = hits
    return {"user_hash": key_hash}


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    model: str
    messages: List[ChatMessage]


class LogEntry(BaseModel):
    request_id: str
    timestamp: float
    user_hash: str
    model: str
    status_code: int
    latency_ms: float
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    pii_detected: bool = False
    request_blocked: bool = False

    class Config:
        from_attributes = True


# ---- Endpoints ----


@app.get("/metrics", tags=["Observability"])
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/health/live", tags=["Health"])
async def health_live():
    return {"status": "alive"}


@app.get("/health/ready", tags=["Health"])
async def health_ready():
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(OLLAMA_BASE_URL)
            if resp.status_code == 200:
                OLLAMA_UP.set(1)
                return {"status": "ready", "component": "ollama"}
    except Exception:
        pass
    OLLAMA_UP.set(0)
    raise HTTPException(status_code=503, detail="Inference engine not ready")


@app.get("/v1/audit/logs", response_model=List[LogEntry], tags=["Governance"])
async def get_audit_logs(
    limit: int = 50,
    auth_ctx: dict = Depends(authenticate),
    db: Session = Depends(get_db),
):
    logs = db.query(AuditLog).order_by(AuditLog.timestamp.desc()).limit(limit).all()
    return logs


@app.post("/v1/chat/completions", tags=["Inference"])
async def chat_completions(
    request: Request,
    body: ChatRequest,
    background_tasks: BackgroundTasks,
    auth_ctx: dict = Depends(authenticate),
    db: Session = Depends(get_db),
):
    request_id = request.state.request_id
    start_time = time.time()

    if body.model not in ALLOWED_MODELS:
        raise HTTPException(status_code=400, detail="Model not allowed")

    clean_messages = []
    pii_flag = False
    blocked_flag = False
    block_reason = None

    for m in body.messages:
        if m.role == "user":
            cleaned, found, blocked = scanner.scan_and_redact(m.content)
            if blocked:
                blocked_flag = True
                block_reason = "secret_key_detected"
                SECURITY_VIOLATIONS.labels(violation_type="secret_key").inc()
                break
            if found:
                pii_flag = True
                PII_DETECTED.labels(model=body.model).inc()

            if guardrails.scan_for_jailbreaks(cleaned):
                blocked_flag = True
                block_reason = "jailbreak_attempt"
                SECURITY_VIOLATIONS.labels(violation_type="jailbreak").inc()
                break
            clean_messages.append({"role": m.role, "content": cleaned})
        else:
            clean_messages.append({"role": m.role, "content": m.content})

    status_code = 200
    c_tokens = 0
    content = ""
    p_tokens = 0

    try:
        if blocked_flag:
            status_code = 400
            content = f"Request rejected: Security violation ({block_reason})."
            log.warning(
                "security_block", user=auth_ctx["user_hash"], reason=block_reason
            )
        else:
            final_messages = guardrails.enforce_system_prompt(clean_messages)
            prompt_text = "".join([m["content"] for m in final_messages])
            p_tokens = count_tokens(prompt_text)
            TOKENS_TOTAL.labels(type="prompt", model=body.model).inc(p_tokens)

            log.info(
                "chat_request",
                user=auth_ctx["user_hash"],
                model=body.model,
                prompt_tokens=p_tokens,
                pii_detected=pii_flag,
            )

            async with semaphore:
                async with httpx.AsyncClient(timeout=60) as client:
                    r = await client.post(
                        OLLAMA_CHAT_URL,
                        json={
                            "model": body.model,
                            "messages": final_messages,
                            "stream": False,
                        },
                    )

            if r.status_code != 200:
                status_code = 502
                raise HTTPException(status_code=502, detail="Ollama failed")

            result = r.json()
            content = result.get("message", {}).get("content", "")
            c_tokens = count_tokens(content)
            TOKENS_TOTAL.labels(type="completion", model=body.model).inc(c_tokens)

    except HTTPException as he:
        raise he
    except Exception as e:
        status_code = 500
        log.error("inference_failed", error=str(e))
        raise e
    finally:
        latency = (time.time() - start_time) * 1000
        audit_entry = AuditLog(
            request_id=request_id,
            user_hash=auth_ctx["user_hash"],
            model=body.model,
            endpoint="/v1/chat/completions",
            status_code=status_code,
            latency_ms=latency,
            prompt_tokens=p_tokens,
            completion_tokens=c_tokens,
            total_tokens=p_tokens + c_tokens,
            pii_detected=pii_flag,
            request_blocked=blocked_flag,
        )
        db.add(audit_entry)
        db.commit()
        log.info(
            "audit_log_persisted",
            request_id=request_id,
            latency_ms=latency,
            blocked=blocked_flag,
        )

    if blocked_flag:
        raise HTTPException(status_code=400, detail=content)

    return {
        "id": request_id,
        "object": "chat.completion",
        "created": int(time.time()),
        "model": body.model,
        "usage": {
            "prompt_tokens": p_tokens,
            "completion_tokens": c_tokens,
            "total_tokens": p_tokens + c_tokens,
        },
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
    }
