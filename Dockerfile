# VISION-BALLING Production Backend Image (Railway CPU Deployment)
# Fail-closed public API server for BETA intake & RAG demonstration.
# No CUDA / GPU dependencies installed in public container.

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_ENV=production \
    PUBLIC_UPLOAD_ENABLED=false \
    PORT=8000

WORKDIR /app

# Install system runtime dependencies for OpenCV headless and curl for healthchecks
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libglib2.0-0 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Install python requirements
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# Copy backend source and knowledge base
COPY backend /app/backend
COPY knowledge_base /app/knowledge_base

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

CMD ["sh", "-c", "python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --app-dir backend"]
