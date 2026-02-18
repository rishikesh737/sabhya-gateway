#!/bin/bash
set -euo pipefail

echo "🚀 Starting Sabhya AI Stack..."

# 1. Load environment variables from .env file
ENV_FILE="$(dirname "$0")/.env"
if [ -f "$ENV_FILE" ]; then
    echo "📋 Loading environment from $ENV_FILE"
    set -a
    source "$ENV_FILE"
    set +a
else
    echo "⚠️  No .env file found at $ENV_FILE"
    echo "   Copy .env.example to .env and configure it first:"
    echo "   cp .env.example .env"
    exit 1
fi

# 2. Define Paths
BASE_DIR="$(dirname "$0")/backend/llm-api"
FRONTEND_DIR="$(dirname "$0")/frontend"

# 3. Validate required variables
: "${DATABASE_URL:?DATABASE_URL must be set in .env}"
: "${SECRET_KEY:?SECRET_KEY must be set in .env}"

# 4. Start Containers
podman start sabhya-db ollama

echo "🚀 Launching API Container..."
podman run -d --name llm-api --network host --replace \
  -e OLLAMA_BASE_URL="${OLLAMA_BASE_URL:-http://localhost:11434}" \
  -e API_KEYS="${API_KEYS:-}" \
  -e DATABASE_URL="${DATABASE_URL}" \
  -e SECRET_KEY="${SECRET_KEY}" \
  -e AUDIT_HMAC_SECRET="${AUDIT_HMAC_SECRET:-}" \
  -e "CORS_ORIGINS=${CORS_ORIGINS:-http://localhost:3000}" \
  localhost/llm-api:stable

# 5. Check for errors
if [ $? -ne 0 ]; then
    echo "⚠️ Container launch failed. Please run 'rebrand_stack.sh' first to initialize."
    exit 1
fi

echo "✅ Backend Services Up!"
echo "   - API: http://localhost:8000"
echo "   - DB:  Postgres:5432 (sabhya_db)"
echo "   - AI:  Ollama:11434"

# 6. Start Frontend
echo "🖥️ Starting Frontend..."
cd "$FRONTEND_DIR"
npm run dev
