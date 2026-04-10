FROM python:3.14-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency resolution
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy backend code
COPY backend/pyproject.toml ./
COPY backend/dm1/ dm1/

# Install dependencies (non-editable for Docker)
RUN uv pip install --system "."

# Copy SRD data
COPY srd-data/ /app/srd-data/

# Create assets directory
RUN mkdir -p /app/assets/campaigns

EXPOSE 8000

CMD ["uvicorn", "dm1.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
