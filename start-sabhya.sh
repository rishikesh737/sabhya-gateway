#!/bin/bash
echo "🚀 Starting Sabhya AI Stack..."

# 1. Define Paths
BASE_DIR="/mnt/fedora-partition/llm-saas-venture/backend/llm-api"
FRONTEND_DIR="/mnt/fedora-partition/llm-saas-venture/frontend"

# 2. Start Containers (The new "Sabhya" names)
# We use 'podman start' to resume the existing containers we just created
podman start sabhya-db ollama llm-api

# 3. Check for errors
if [ $? -ne 0 ]; then
    echo "⚠️ Containers not found. Please run 'rebrand_stack.sh' first to initialize."
    exit 1
fi

echo "✅ Backend Services Up!"
echo "   - API: http://localhost:8000"
echo "   - DB:  Postgres:5432 (sabhya_db)"
echo "   - AI:  Ollama:11434"

# 4. Start Frontend
echo "🖥️ Starting Frontend..."
cd $FRONTEND_DIR
npm run dev
