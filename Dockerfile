# ─────────────────────────────────────────────────────
# MarketPilot — Multi-Stage Production Dockerfile
# ─────────────────────────────────────────────────────

# Stage 1: Dependencies
FROM python:3.13-slim AS deps

WORKDIR /build
COPY backend/pyproject.toml backend/README.md ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir .[all] 2>/dev/null || pip install --no-cache-dir .

# Stage 2: Application
FROM python:3.13-slim AS runtime

# Security: non-root user
RUN groupadd -r pilot && useradd -r -g pilot -d /app -s /sbin/nologin pilot

WORKDIR /app

# Copy installed packages from deps stage
COPY --from=deps /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=deps /usr/local/bin /usr/local/bin

# Copy application code
COPY backend/ ./

# Environment
ENV PYTHONPATH=/app \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Switch to non-root user
USER pilot

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import httpx; r = httpx.get('http://localhost:8000/health', timeout=3); assert r.status_code == 200"

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
