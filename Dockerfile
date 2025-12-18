FROM python:3.11-slim as base
WORKDIR /app
COPY pyproject.toml .
RUN pip install --upgrade pip && pip install poetry
RUN poetry config virtualenvs.create false
COPY . .
RUN poetry install --no-dev

EXPOSE 8000
CMD ["uvicorn", "src.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
