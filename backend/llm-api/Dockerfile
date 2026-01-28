# ---- Base: minimal, secure ----
FROM python:3.12-slim

# ---- Security: non-root user ----
# We use a high UID to simulate OpenShift random-UID behavior
RUN useradd -m -u 10001 appuser

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
# Note: We rely on the runtime injecting a tmpfs at /tmp for temporary storage
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
