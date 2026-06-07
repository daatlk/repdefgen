# ── Stage 1: build the React frontend ───────────────────────────────────────
FROM node:20-alpine AS ui-builder

WORKDIR /app/ui
COPY ui/package*.json ./
RUN npm ci

COPY ui/ .
RUN npm run build

# ── Stage 2: Python runtime ──────────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

# Install Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    fastapi>=0.110 uvicorn>=0.29 python-multipart>=0.0.9 || true

COPY pyproject.toml setup.py ./
COPY repdefgen/ ./repdefgen/
RUN pip install --no-cache-dir -e .

# Copy compiled React build
COPY --from=ui-builder /app/ui/dist ./ui/dist

# The index must be mounted at runtime: -v /path/to/.repdefgen:/app/.repdefgen
# The ANTHROPIC_API_KEY must be set via environment: -e ANTHROPIC_API_KEY=...
EXPOSE 8000

CMD ["uvicorn", "repdefgen.api:app", "--host", "0.0.0.0", "--port", "8000"]
