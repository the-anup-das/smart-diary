# Stage 1: Build virtual environment
FROM python:3.12-slim AS builder

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Install dependencies
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

# Stage 2: Production image
FROM python:3.12-slim-bookworm

WORKDIR /app

# Copy the virtual environment from the builder
COPY --from=builder /app/.venv /app/.venv

# Update PATH to use the virtual environment
ENV PATH="/app/.venv/bin:$PATH"

# Copy source code
COPY . .

# Ensure the database directory exists if using SQLite (though we use PG)
# and set permissions if needed.
# RUN mkdir -p /app/data && chown -R 1000:1000 /app/data

EXPOSE 8000

# Metadata
LABEL maintainer="Anup Das"
LABEL description="Smart Diary Backend - Production"

# Healthcheck to help NAS devices monitor container status
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/api/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
