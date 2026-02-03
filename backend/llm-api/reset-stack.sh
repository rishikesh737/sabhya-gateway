#!/bin/bash
# =============================================================================
# Vectal Stack Hard Reset Script
# Fixes ChromaDB permission issues by nuking and recreating storage with 777
# =============================================================================

set -e

echo "🛑 Stopping containers..."
podman stop llm-api vectal-db ollama 2>/dev/null || true
podman rm -f llm-api vectal-db ollama 2>/dev/null || true

echo ""
echo "💥 Nuking corrupted chroma_data..."
rm -rf chroma_data
mkdir -p chroma_data
chmod -R 777 chroma_data
echo "✓ chroma_data recreated with 777 permissions"

echo ""
echo "🔓 Fixing data directory permissions..."
mkdir -p data
chmod -R 777 data
echo "✓ data directory fixed"

echo ""
echo "🚀 Starting Ollama..."
podman run -d --name ollama --network host \
  -v $(pwd)/ollama_data:/root/.ollama:Z \
  docker.io/ollama/ollama:latest
sleep 3
echo "✓ Ollama started"

echo ""
echo "🗄️  Starting PostgreSQL..."
podman run -d --name vectal-db --network host \
  -v $(pwd)/pg_data:/var/lib/postgresql/data:Z \
  -e POSTGRES_USER=vectal \
  -e POSTGRES_PASSWORD=***REMOVED*** \
  -e POSTGRES_DB=vectal_db \
  docker.io/postgres:15-alpine
sleep 3
echo "✓ PostgreSQL started"

echo ""
echo "🤖 Starting LLM-API..."
podman run -d --name llm-api --network host \
  -v $(pwd)/data:/app/data:Z \
  -v $(pwd)/chroma_data:/app/chroma_data:Z \
  -e API_KEYS=dev-key-1,dev-key-2 \
  -e OLLAMA_BASE_URL=http://localhost:11434 \
  -e DATABASE_URL=postgresql://vectal:***REMOVED***@localhost:5432/vectal_db \
  localhost/llm-api:stable
sleep 5
echo "✓ LLM-API started"

echo ""
echo "🩺 Health Check..."
curl -s http://localhost:8000/health/live && echo ""

echo ""
echo "=============================================="
echo "✅ STACK RESET COMPLETE"
echo "=============================================="
echo ""
echo "📂 Directory permissions:"
ls -la chroma_data/ data/ 2>/dev/null | head -5
echo ""
echo "🐳 Running containers:"
podman ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
