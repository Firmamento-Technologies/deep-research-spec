# =============================================================================
# DRS Backend — Multi-Stage Dockerfile
#
# Stage 1 (builder): Install deps + compile bytecode
# Stage 2 (runtime): Minimal image, no build tools
#
# Result: ~210 MB vs ~680 MB single-stage
# =============================================================================

# ---------------------------------------------------------------------------
# Stage 1: builder — install Python dependencies
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS builder

# Build dependencies (not needed in runtime)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Copy requirements first (cache layer)
COPY requirements.txt .

# Install into /install prefix (isolated from system Python)
RUN pip install --upgrade pip && \
    pip install \
        --no-cache-dir \
        --prefix=/install \
        --no-warn-script-location \
        -r requirements.txt

# Pre-compile Python bytecode to speed up startup
RUN python -m compileall -q /install/lib


# ---------------------------------------------------------------------------
# Stage 2: runtime — minimal production image
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

LABEL org.opencontainers.image.title="DRS Backend"
LABEL org.opencontainers.image.description="Deep Research System API"
LABEL org.opencontainers.image.version="1.0.0"

# Runtime-only system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid appuser --shell /bin/bash --create-home appuser

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application source (exclude tests, docs, __pycache__)
COPY --chown=appuser:appuser main.py ./
COPY --chown=appuser:appuser api/ ./api/
COPY --chown=appuser:appuser src/ ./src/
COPY --chown=appuser:appuser services/ ./services/
COPY --chown=appuser:appuser database/ ./database/
COPY --chown=appuser:appuser config/ ./config/
COPY --chown=appuser:appuser prompts/ ./prompts/
COPY --chown=appuser:appuser alembic.ini ./
COPY --chown=appuser:appuser alembic/ ./alembic/ 2>/dev/null || true

# Copy entrypoint script
COPY --chown=appuser:appuser docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Healthcheck
HEALTHCHECK --interval=10s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Entrypoint
ENTRYPOINT ["/entrypoint.sh"]
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
