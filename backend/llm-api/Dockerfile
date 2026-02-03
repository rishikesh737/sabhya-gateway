# ---- Base: minimal, secure ----
FROM python:3.11-slim-bookworm

# ---- NEW: Install Build Tools (Required for ChromaDB) ----
# We need g++ to compile the vector database engine
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# ---- Security: non-root user ----
# We use a high UID to simulate OpenShift random-UID behavior
RUN useradd -m -u 10001 appuser

# ---- Data directories with proper permissions ----
# Created before dropping privileges for RAG persistence
RUN mkdir -p /app/data /app/chroma_data && chown -R appuser:appuser /app

# ---- Working directory ----
WORKDIR /app

# ---- Install deps ----
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---- Copy app code ----
COPY app ./app

# ---- Drop privileges ----
USER appuser

# ---- Runtime config ----
# PREVENTS CRASHES ON READ-ONLY FILESYSTEMS
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# ---- Expose API port ----
EXPOSE 8000

# ---- Start server ----
# Force asyncio loop to prevent uvloop segfaults on certain kernels
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--loop", "asyncio"]
