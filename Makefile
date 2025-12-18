PYTHON ?= python3
POETRY ?= poetry

.PHONY: install run-api lint type test format docker-up docker-down eval ingest-sample migrate

install:
	$(POETRY) install

run-api:
	uvicorn src.app.main:app --reload

lint:
	ruff check src tests

format:
	ruff format src tests

type:
	mypy src

test:
	pytest

migrate:
	$(PYTHON) scripts/migrate.py

ingest-sample:
	$(PYTHON) scripts/load_samples.py

run-evals:
	$(PYTHON) eval/harness.py --cases eval/golden/cases.jsonl --expected eval/golden/expected.jsonl

smoke-eval:
	$(PYTHON) eval/harness.py --smoke

eval: run-evals

docker-up:
	docker compose -f infra/docker-compose.yml up -d --build

docker-down:
	docker compose -f infra/docker-compose.yml down
