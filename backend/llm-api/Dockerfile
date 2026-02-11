# ---- Base: minimal, secure ----
FROM python:3.11-slim-bookworm

# ---- NEW: Install Build Tools (Required for ChromaDB) ----
# We need g++ to compile the vector database engine
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
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

# 1. Install everything EXCEPT the large spacy model first
RUN grep -v "en_core_web_lg" requirements.txt > reqs_no_model.txt && \
    pip install --no-cache-dir --timeout 1000 --retries 10 -r reqs_no_model.txt

# 2. Manually download and install the large model (More robust)
RUN curl -L -o en_core_web_lg-3.8.0-py3-none-any.whl "https://github.com/explosion/spacy-models/releases/download/en_core_web_lg-3.8.0/en_core_web_lg-3.8.0-py3-none-any.whl" && \
    pip install en_core_web_lg-3.8.0-py3-none-any.whl && \
    rm en_core_web_lg-3.8.0-py3-none-any.whl

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
