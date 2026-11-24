FROM python:3.11-slim AS base

WORKDIR /app

# Lets Alembic (alembic/env.py imports app.core.config) and one-off scripts
# find the application package without extra flags.
ENV PYTHONPATH=/app/src \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpoppler-cpp-dev \
    pkg-config \
    python3-dev \
    libpq-dev \
    curl \
    libopenblas-dev \
    gfortran \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip && pip install "poetry==2.2.1"
RUN poetry config virtualenvs.create false

# Dependencies first, from the committed lock file, so this layer is cached
# until pyproject.toml or poetry.lock change.
COPY pyproject.toml poetry.lock ./
RUN poetry install --without dev --no-root --no-interaction

COPY . .
RUN poetry install --without dev --no-interaction

EXPOSE 8000

# The first start loads the embedding model, so the start period is long.
HEALTHCHECK --interval=30s --timeout=5s --start-period=120s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["uvicorn", "src.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
