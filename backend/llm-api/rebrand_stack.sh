#!/bin/bash
# =============================================================================
# Sabhya AI Stack Migration Script (v2 - Aggressive Cleanup)
# Uses sudo to forcefully wipe all storage and start fresh
# =============================================================================

set -e

# Load environment variables from root .env
ENV_FILE="$(cd "$(dirname "$0")/../.." && pwd)/.env"
if [ -f "$ENV_FILE" ]; then
    set -a; source "$ENV_FILE"; set +a
else
    echo "⚠️  No .env file found at $ENV_FILE"
    echo "   Copy .env.example to .env and configure it first."
    exit 1
fi

: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD must be set in .env}"

echo "=============================================="
echo "🔄 SABHYA AI STACK MIGRATION (v2)"
echo "=============================================="
echo ""

echo "🛑 Stopping ALL containers..."
podman stop llm-api vectal-db ollama sabhya-db 2>/dev/null || true
podman rm -f llm-api vectal-db ollama sabhya-db 2>/dev/null || true
echo "✓ All containers stopped and removed"

echo ""
echo "💥 AGGRESSIVE WIPE: Nuking all data folders with sudo..."
sudo rm -rf pg_data chroma_data data ollama_data sabhya_pg_data
echo "✓ All data folders deleted"

echo ""
echo "📁 Recreating fresh directories..."
mkdir -p pg_data chroma_data data ollama_data
echo "✓ Directories created"

echo ""
echo "🔓 Applying 777 permissions (container write access)..."
sudo chmod -R 777 pg_data chroma_data data ollama_data
echo "✓ All directories unlocked with 777"

echo ""
echo "🚀 Starting Ollama..."
podman run -d --name ollama --network host \
  -v $(pwd)/ollama_data:/root/.ollama:Z \
  docker.io/ollama/ollama:latest
sleep 3
echo "✓ Ollama started"

echo ""
echo "🗄️  Starting Sabhya DB (PostgreSQL)..."
podman run -d --name sabhya-db --network host \
  -v $(pwd)/pg_data:/var/lib/postgresql/data:Z \
  -e POSTGRES_USER=sabhya \
  -e POSTGRES_PASSWORD="${POSTGRES_PASSWORD}" \
  -e POSTGRES_DB=sabhya_db \
  docker.io/postgres:15-alpine
sleep 5
echo "✓ sabhya-db started (user: sabhya, db: sabhya_db)"

echo ""
echo "🤖 Starting LLM-API (Sabhya AI Backend)..."
podman run -d --name llm-api --network host \
  -v $(pwd)/data:/app/data:Z \
  -v $(pwd)/chroma_data:/app/chroma_data:Z \
  -e API_KEYS="${API_KEYS:-}" \
  -e OLLAMA_BASE_URL=http://localhost:11434 \
  -e DATABASE_URL="postgresql://sabhya:${POSTGRES_PASSWORD}@localhost:5432/sabhya_db" \
  localhost/llm-api:stable
sleep 5
echo "✓ LLM-API started with Sabhya DB connection"

echo ""
echo "🩺 Health Check..."
if curl -s http://localhost:8000/health/live | grep -q "alive"; then
    echo "✓ API is healthy!"
else
    echo "⚠️  API health check failed - check logs with: podman logs llm-api"
fi

echo ""
echo "=============================================="
echo "✅ SABHYA AI STACK READY"
echo "=============================================="
echo ""
echo "🐳 Running containers:"
podman ps --format "table {{.Names}}\t{{.Status}}"
echo ""
echo "⚠️  IMPORTANT: Since ollama_data was wiped, you need to re-pull models:"
echo ""
echo "   podman exec -it ollama ollama pull nomic-embed-text"
echo "   podman exec -it ollama ollama pull mistral:7b-instruct-q4_K_M"
echo ""
echo "🌐 API Endpoint: http://localhost:8000"
echo "🎨 Frontend:     http://localhost:3000"
