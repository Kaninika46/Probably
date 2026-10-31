# ==============================================================================
# Multi-stage Dockerfile for "Probably High-Value?"
# Probabilistic Customer Intelligence with DuckDB, FastAPI & React
# ==============================================================================

# ------------------------------------------------------------------------------
# Stage 1: Build the React frontend
# ------------------------------------------------------------------------------
FROM node:20-slim AS frontend-builder
WORKDIR /app/web

# Cache package manifests for fast rebuilds
COPY web/package*.json ./
RUN npm ci

# Copy web source files and compile production SPA into /app/web/dist
COPY web/ ./
RUN npm run build

# ------------------------------------------------------------------------------
# Stage 2: Production Python runtime
# ------------------------------------------------------------------------------
FROM python:3.12-slim
WORKDIR /app

# Install curl for container healthchecks
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python analytical dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy analytical backend, DuckDB database, SQL templates, and audit tables
COPY api/ ./api/
COPY src/ ./src/
COPY sql/ ./sql/
COPY app/ ./app/
COPY reports/tables/ ./reports/tables/
COPY eval/ ./eval/
COPY docs/architecture.png ./docs/architecture.png

# Copy compiled React bundle from Stage 1 into web/dist
COPY --from=frontend-builder /app/web/dist ./web/dist

# Standard environment configuration
ENV PORT=8000
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

# Container healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT}/api/health || exit 1

# Start production uvicorn server binding to dynamic platform port
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
