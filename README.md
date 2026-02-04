<p align="center">
  <h1 align="center">🛡️ Sabhya AI</h1>
  <p align="center"><strong>Enterprise-Grade, Self-Hosted LLM Governance Gateway</strong></p>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/version-v0.3.0-blue?style=flat-square" alt="Version">
  <img src="https://img.shields.io/badge/Privacy-First-green?style=flat-square" alt="Privacy First">
  <img src="https://img.shields.io/badge/Dockerized-Ready-purple?style=flat-square" alt="Dockerized">
</p>

---

## Executive Summary

**Sabhya AI is not a chatbot.** It is a **Governed Control Plane** designed for enterprises adopting AI responsibly.

Built for security-conscious organizations, Sabhya provides:
- **Real-time guardrails** that detect sensitive data before it reaches the model
- **Immutable audit trails** for every inference request
- **Rate limiting** to protect infrastructure from abuse
- **Dynamic model routing** for cost/performance optimization



---

## Key Features (v0.3.0)

| Feature | Description |
|---------|-------------|
| 🛡️ **Governance Engine** | Real-time PII detection (Email, Phone, Credit Card) via Regex. Rate limiting at 50 req/min per IP. |
| 🧠 **Dynamic Routing** | Switch between models at runtime: `Mistral 7B (Fast)` or `Llama 3 (Smart)`. |
| 📜 **Immutable Audit Trail** | PostgreSQL-backed logging of every request, response, token count, and PII flag. |
| ⚡ **RAG Pipeline** | Secure PDF ingestion via ChromaDB. Context injected automatically into prompts. |
| 🔐 **API Key Authentication** | Bearer token auth with SHA-256 hashed user tracking (privacy-preserving). |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        SABHYA AI STACK                          │
├─────────────────────────────────────────────────────────────────┤
│  Frontend          │  Next.js 14 (App Router) + Tailwind CSS   │
│                    │  SOC Theme, Constitutional UI              │
├────────────────────┼────────────────────────────────────────────┤
│  Backend           │  FastAPI + SlowAPI (Rate Limiting)         │
│                    │  Pydantic Models, Structlog                │
├────────────────────┼────────────────────────────────────────────┤
│  Inference         │  Ollama (Mistral 7B / Llama 3)            │
├────────────────────┼────────────────────────────────────────────┤
│  Vector Store      │  ChromaDB (RAG Context)                   │
├────────────────────┼────────────────────────────────────────────┤
│  Database          │  PostgreSQL 15 (Audit Logs)               │
├────────────────────┼────────────────────────────────────────────┤
│  Container Runtime │  Podman / Docker                          │
└─────────────────────────────────────────────────────────────────┘
```

---

## Quick Start

### Prerequisites
- **Podman** or **Docker** (with Compose)
- **Node.js 18+** (for frontend development)
- **Ollama** with `mistral:7b-instruct-q4_K_M` pulled

### Installation

```bash
# Clone the repository
git clone https://github.com/rishikesh737/llm-saas-venture-c4.git
cd llm-saas-venture-c4

# Start the full stack
./start-sabhya.sh
```

### Access Points

| Service | URL | Credentials |
|---------|-----|-------------|
| Frontend | `http://localhost:3000` | — |
| Backend API | `http://localhost:8000` | `Bearer dev-key-1` |
| API Docs | `http://localhost:8000/docs` | — |

### Test the API

```bash
# Health check
curl http://localhost:8000/health/live

# Chat completion (with PII detection)
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer dev-key-1" \
  -H "Content-Type: application/json" \
  -d '{"model": "mistral:7b-instruct-q4_K_M", "messages": [{"role": "user", "content": "Hello, world!"}]}'
```

---

## Project Structure

```
sabhya-ai/
├── backend/
│   └── llm-api/
│       ├── app/
│       │   ├── main.py           # FastAPI routes, rate limiting, PII detection
│       │   ├── models.py         # SQLAlchemy ORM (AuditLog schema)
│       │   ├── database.py       # PostgreSQL connection
│       │   └── services/
│       │       └── rag.py        # ChromaDB RAG pipeline
│       ├── requirements.txt
│       └── Dockerfile
├── frontend/
│   ├── app/
│   │   └── (protected)/
│   │       └── page.tsx          # Constitutional UI (Interaction Panel)
│   ├── components/
│   └── package.json
├── .gitignore
├── start-sabhya.sh               # One-command stack launcher
└── README.md
```

### Data Directories (Not Committed)
| Directory | Purpose |
|-----------|---------|
| `pg_data/` | PostgreSQL persistent storage |
| `chroma_data/` | ChromaDB vector embeddings |
| `ollama_data/` | Ollama model weights |

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `API_KEYS` | `dev-key-1` | Comma-separated valid API keys |
| `DATABASE_URL` | `postgresql://...` | PostgreSQL connection string |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama inference endpoint |
| `CORS_ORIGINS` | `*` | Allowed CORS origins (set for production) |

---

## Governance Features

### PII Detection (Passive Mode)
Scans all incoming prompts for:
- 📧 Email addresses
- 📱 Phone numbers
- 💳 Credit card patterns

Flagged requests are logged with `pii_detected=true` in the audit trail.

### Rate Limiting
- **Limit:** 50 requests per minute per IP
- **Proxy-aware:** Respects `X-Forwarded-For` headers for AWS/load balancers
- **Response:** HTTP 429 when exceeded

### Audit Logging
Every request is logged to PostgreSQL with:
- Request ID, Timestamp, User Hash
- Model used, Endpoint called
- Token counts (prompt + completion)
- PII detection flag, Status code, Latency

---

## License

MIT License — See [LICENSE](LICENSE) for details.

---

<p align="center">
  <sub>Built with 🛡️ by the Sabhya AI Team</sub>
</p>
