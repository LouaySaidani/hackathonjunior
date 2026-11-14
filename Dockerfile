# syntax=docker/dockerfile:1
# ---------- 1. frontend build ----------
FROM node:22-alpine AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---------- 2. python deps (CPU only) ----------
FROM python:3.11-slim AS deps
RUN apt-get update && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*
RUN python -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH
COPY backend/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# ---------- 3. runtime ----------
FROM python:3.11-slim
LABEL org.opencontainers.image.title="Basira - AI audio description co-pilot" \
      org.opencontainers.image.description="Human-in-the-loop audio description for Tunisian and Francophone films" \
      org.opencontainers.image.licenses="Apache-2.0"
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg espeak-ng curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 1000 app \
    && mkdir -p /app/data /models && chown -R app:app /app /models
COPY --from=deps /opt/venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    DATA_DIR=/app/data \
    MODELS_DIR=/models \
    HF_HOME=/models/hf
WORKDIR /app
COPY --chown=app:app backend/ backend/
COPY --chown=app:app samples/ samples/
COPY --from=web --chown=app:app /web/dist frontend/dist
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
WORKDIR /app/backend
EXPOSE 8000
VOLUME ["/app/data", "/models"]
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1
# The entrypoint fixes ownership of bind-mounted volumes, then drops to the non-root "app" user.
ENTRYPOINT ["/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
