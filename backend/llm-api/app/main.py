from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import httpx
import os
import time
import asyncio
import hashlib
import structlog
from typing import List
from pydantic import BaseModel
from dotenv import load_dotenv

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
OLLAMA_GENERATE_URL = f"{OLLAMA_BASE_URL}/api/generate"
OLLAMA_CHAT_URL = f"{OLLAMA_BASE_URL}/api/chat"
MAX_PROMPT_CHARS = 4000
ALLOWED_MODELS = {"mistral:7b-instruct-q4_K_M", "tinyllama"}

# ---- App Definition (With Metadata) ----
app = FastAPI(
    title="Local LLM Gateway",
    description="A security-hardened, self-healing API gateway for local LLMs.",
    version="1.0.0",
    docs_url="/docs",  # Swagger UI
    redoc_url="/redoc",  # ReDoc UI
)

# ---- State ----
clients = {}
semaphore = asyncio.Semaphore(1)

# ---- Security Scheme (For Swagger UI) ----
security_scheme = HTTPBearer()


# ---- Helper ----
def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()[:8]


# ---- Auth (Refactored for Swagger) ----
def authenticate(creds: HTTPAuthorizationCredentials = Depends(security_scheme)):
    # HTTPBearer extracts the token from "Authorization: Bearer <token>"
    key = creds.credentials.strip()

    if key not in API_KEYS:
        log.warning("auth_failed", reason="invalid_key")
        raise HTTPException(status_code=403, detail="Invalid API key")

    # Rate Limiting Logic (Simplified for brevity, same as before)
    # Note: In a real app, we'd need the Request object here for IP tracking,
    # but for now we'll track by Key Hash to keep the signature clean for Swagger.
    now = time.time()
    key_hash = hash_key(key)
    client_id = key_hash  # Tracking by Key only for this refactor

    hits = clients.get(client_id, [])
    hits = [t for t in hits if now - t < 60]

    if len(hits) >= RATE_LIMIT:
        log.warning("rate_limit_exceeded", client_id=client_id)
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    hits.append(now)
    clients[client_id] = hits
    return {"user_hash": key_hash}


# ---- Probes ----
@app.get("/health/live", tags=["Health"])
async def health_live():
    return {"status": "alive"}


@app.get("/health/ready", tags=["Health"])
async def health_ready():
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            if (await client.get(OLLAMA_BASE_URL)).status_code == 200:
                return {"status": "ready"}
    except Exception:
        pass
    raise HTTPException(status_code=503, detail="Backend unavailable")


# ---- Models ----
class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    model: str
    messages: List[ChatMessage]


# ---- Endpoints ----
@app.post("/v1/chat/completions", tags=["Inference"])
async def chat_completions(body: ChatRequest, auth_ctx: dict = Depends(authenticate)):
    start_time = time.time()

    if body.model not in ALLOWED_MODELS:
        raise HTTPException(status_code=400, detail="Model not allowed")

    log.info("chat_request", user=auth_ctx["user_hash"], model=body.model)

    ollama_messages = [{"role": m.role, "content": m.content} for m in body.messages]

    async with semaphore:
        async with httpx.AsyncClient(timeout=60) as client:
            try:
                r = await client.post(
                    OLLAMA_CHAT_URL,
                    json={
                        "model": body.model,
                        "messages": ollama_messages,
                        "stream": False,
                    },
                )
            except Exception as e:
                log.error("upstream_error", error=str(e))
                raise HTTPException(status_code=502, detail="Ollama failed")

    if r.status_code != 200:
        raise HTTPException(status_code=500, detail="Ollama error")

    result = r.json()
    content = result.get("message", {}).get("content", "")

    log.info("chat_success", duration=round(time.time() - start_time, 3))

    return {
        "id": "chat-local",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": body.model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
    }
