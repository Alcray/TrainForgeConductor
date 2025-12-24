# TrainForgeConductor - Multi-Provider LLM API Conductor
FROM python:3.12-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy project files for installation
COPY pyproject.toml .
COPY app/ ./app/

# Install dependencies
RUN pip install --no-cache-dir --user .

# Production image
FROM python:3.12-slim

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /var/cache/apt/*

# Copy installed packages from builder
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Copy application code
COPY app/ ./app/

# Create config directory
RUN mkdir -p /app/config

# Environment variables
ENV CONDUCTOR_HOST=0.0.0.0 \
    CONDUCTOR_PORT=8000 \
    CONDUCTOR_LOG_LEVEL=INFO \
    CONDUCTOR_CONFIG_PATH=/app/config/config.yaml \
    PYTHONUNBUFFERED=1

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the application
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
