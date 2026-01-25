FROM python:3.11-slim AS base

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    libpoppler-cpp-dev \
    pkg-config \
    python3-dev \
    libpq-dev \
    curl \
    libopenblas-dev \
    gfortran \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip && pip install poetry
RUN poetry config virtualenvs.create false

COPY pyproject.toml ./
RUN poetry lock --no-interaction
RUN poetry install --without dev --no-root --no-interaction

COPY . .
RUN poetry lock --no-interaction
RUN poetry install --without dev --no-interaction

EXPOSE 8000

CMD ["uvicorn", "src.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
