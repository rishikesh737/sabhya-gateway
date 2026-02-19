# Sabhya AI — Local Development Setup

> Machine-specific guide for Fedora Linux with Podman.
> Project: `/mnt/fedora-partition/llm-saas-venture`

---

## 1. Prerequisites Check

```bash
podman --version          # >= 4.x
python3.11 --version      # 3.11.x
node --version            # >= 18.x
npm --version             # >= 9.x
java -version             # JRE 8+ (only needed for BFG history scrub)
```

---

## 2. Environment Setup

### 2a. Root `.env` (used by `start-sabhya.sh`)

```bash
cp .env.example .env
```

Generate secure values:

```bash
# SECRET_KEY — JWT signing key (min 32 chars)
python3 -c "import secrets; print(secrets.token_urlsafe(48))"

# AUDIT_HMAC_SECRET — audit log HMAC signatures (separate key)
python3 -c "import secrets; print(secrets.token_urlsafe(48))"

# POSTGRES_PASSWORD — database password
python3 -c "import secrets; print(secrets.token_urlsafe(24))"
```

Edit `.env` and paste generated values into:

| Variable | Purpose |
|----------|---------|
| `POSTGRES_PASSWORD` | PostgreSQL user password for `sabhya` |
| `DATABASE_URL` | Connection string (uses `${POSTGRES_PASSWORD}` interpolation) |
| `SECRET_KEY` | Signs JWT tokens — app won't start without it |
| `AUDIT_HMAC_SECRET` | Signs audit log entries for tamper detection |
| `API_KEYS` | Comma-separated legacy API keys (optional) |
| `OLLAMA_BASE_URL` | Ollama inference server (default: `http://localhost:11434`) |
| `CORS_ORIGINS` | Allowed frontend origins (default: `http://localhost:3000`) |

### 2b. Backend `.env`

```bash
cp backend/llm-api/.env.example backend/llm-api/.env
```

Update `DATABASE_URL`, `SECRET_KEY`, and `AUDIT_HMAC_SECRET` to match the root `.env`.

### 2c. Frontend `.env.local`

```bash
cp frontend/.env.example frontend/.env.local
```

Default contents (usually fine as-is):

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_API_KEY=
```

---

## 3. Starting Infrastructure (Podman)

### 3a. First-time setup — run `rebrand_stack.sh`

Creates containers and data directories from scratch:

```bash
cd backend/llm-api
bash rebrand_stack.sh
```

This will:
1. Stop and remove any existing `sabhya-db`, `ollama`, `llm-api` containers
2. Wipe and recreate `pg_data/`, `chroma_data/`, `data/`, `ollama_data/`
3. Start PostgreSQL (`sabhya-db`) and Ollama containers
4. Build and start the `llm-api` backend container

### 3b. Pull AI models (required after first setup or data wipe)

```bash
podman exec -it ollama ollama pull nomic-embed-text
podman exec -it ollama ollama pull mistral:7b-instruct-q4_K_M
```

Expected output (models are ~4GB total):

```
pulling manifest... done
pulling layers... [████████████████] 100%
success
```

### 3c. Verify containers are running

```bash
podman ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

Expected:

```
NAMES       STATUS         PORTS
sabhya-db   Up 2 minutes
ollama      Up 2 minutes
```

### 3d. Stop everything cleanly

```bash
podman stop sabhya-db ollama llm-api 2>/dev/null
```

### 3e. Restart after reboot (containers already exist)

```bash
podman start sabhya-db ollama
```

---

## 4. Starting the Backend

### Option A: Using `start-sabhya.sh` (full stack)

```bash
# From project root
bash start-sabhya.sh
```

Starts `sabhya-db`, `ollama`, the `llm-api` container, then runs `npm run dev` for the frontend.

### Option B: Manual uvicorn (development with hot reload)

```bash
cd backend/llm-api
source venv_py311/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Verify backend is running

```bash
curl -s http://localhost:8000/health/live | python3 -m json.tool
```

Expected:

```json
{
    "status": "alive",
    "service": "sabhya-ai"
}
```

### API docs (Swagger UI)

Open in browser: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 5. Starting the Frontend

```bash
cd frontend
npm ci            # install exact lockfile deps (first time / after pull)
npm run dev       # start Next.js dev server on port 3000
```

Verify: open [http://localhost:3000](http://localhost:3000) — you should see the Sabhya AI login page.

> **Note:** Next.js rewrites proxy `/api/*` requests to the backend at `http://localhost:8000`, so no CORS issues in development.

---

## 6. Creating Your First User

### Register

```bash
curl -s -X POST http://localhost:8000/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@sabhya.local","password":"StrongPass123!","full_name":"Admin"}' \
  | python3 -m json.tool
```

Expected:

```json
{
    "id": "...",
    "email": "admin@sabhya.local",
    "full_name": "Admin"
}
```

### Get JWT token

```bash
curl -s -X POST http://localhost:8000/v1/auth/token \
  -d "username=admin@sabhya.local&password=StrongPass123!" \
  | python3 -m json.tool
```

Expected:

```json
{
    "access_token": "eyJhbGciOiJIUzI1...",
    "token_type": "bearer"
}
```

### Login via UI

Go to [http://localhost:3000/login](http://localhost:3000/login), enter the same email and password.

---

## 7. Running Tests Locally

### Backend — pytest

```bash
cd backend/llm-api
source venv_py311/bin/activate

SECRET_KEY="test-secret-key-for-testing-minimum-32-chars" \
AUDIT_HMAC_SECRET="test-audit-secret-for-testing-32-chars" \
DATABASE_URL="sqlite:///./test_sabhya.db" \
ENVIRONMENT="development" \
API_KEYS="test-key-1,test-key-2" \
LEGACY_AUTH_ENABLED="true" \
ALLOWED_HOSTS="testserver,localhost,127.0.0.1" \
python -m pytest tests/ -v --tb=short \
  --ignore=tests/test_pii_detection.py \
  --ignore=tests/test_pii_detection_e2e.py \
  --ignore=tests/test_e2e_streaming.py
```

> PII and streaming tests are ignored because they require `presidio` + the 500MB `en_core_web_lg` spaCy model.

### Backend — ruff lint

```bash
cd backend/llm-api
ruff check app/ tests/ alembic/
ruff format --check app/ tests/ alembic/
```

### Frontend — lint

```bash
cd frontend
npm run lint
```

Expected: zero errors, zero warnings.

### Frontend — build

```bash
cd frontend
npm run build
```

---

## 8. Common Problems & Fixes

### `.env` file missing

```
RuntimeError: SECRET_KEY environment variable is required but not set
RuntimeError: DATABASE_URL environment variable is required but not set
```

**Fix:** Copy `.env.example` to `.env` and fill in all `CHANGE_ME` values (see Section 2).

### Podman volume permission denied

```
FATAL: data directory "/var/lib/postgresql/data" has wrong ownership
```

**Fix:** Use the `:Z` SELinux relabel flag on volume mounts (already done in `rebrand_stack.sh`):

```bash
podman run -v $(pwd)/pg_data:/var/lib/postgresql/data:Z ...
```

If still failing, open permissions:

```bash
sudo chmod -R 777 pg_data
```

### PostgreSQL container name conflict

```
Error: creating container: container name "sabhya-db" is already in use
```

**Fix:** Remove the stale container first:

```bash
podman rm -f sabhya-db
```

### `load_dotenv()` ordering

`app/main.py` calls `load_dotenv()` before any `app.*` imports because modules like `auth/security.py` read `SECRET_KEY` at import time via `os.getenv()`. If you add new imports above `load_dotenv()`, the env vars won't be available and the app will crash with `RuntimeError`.

### Ollama connection refused

```
httpx.ConnectError: [Errno 111] Connection refused
```

**Fix:** Ensure the Ollama container is running:

```bash
podman start ollama
podman exec ollama ollama list   # verify models are loaded
```

### Frontend API 404 errors

Check that `NEXT_PUBLIC_API_URL` in `frontend/.env.local` matches the backend address (`http://localhost:8000`).

---

## Quick Reference

| Service | URL | Container |
|---------|-----|-----------|
| Frontend | http://localhost:3000 | — (local `npm run dev`) |
| Backend API | http://localhost:8000 | `llm-api` |
| Swagger UI | http://localhost:8000/docs | — |
| PostgreSQL | localhost:5432 | `sabhya-db` |
| Ollama | http://localhost:11434 | `ollama` |
| Health (live) | http://localhost:8000/health/live | — |
| Health (ready) | http://localhost:8000/health/ready | — |
