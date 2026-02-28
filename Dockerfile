FROM mcr.microsoft.com/playwright/python:v1.58.0-noble AS base

# Prevent Python from writing .pyc files and enable unbuffered output for logging
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app

# Install dependencies first (cached layer unless pyproject.toml or uv.lock change)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy source code and README (required by hatchling build) then install the project
COPY README.md ./
COPY src/ src/
RUN uv sync --frozen --no-dev

# Create data directory for SQLite DB and set ownership to built-in pwuser
RUN mkdir -p /app/data \
    && chown -R pwuser:pwuser /app
USER pwuser

ENTRYPOINT ["uv", "run", "it-job-aggregator"]
