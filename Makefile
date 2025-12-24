PYTHON ?= python3
POETRY ?= poetry
DOCKER_COMPOSE ?= docker compose -f infra/docker-compose.yml
HELM ?= helm
KUBECTL ?= kubectl
HELM_RELEASE ?= renewal-desk
HELM_NAMESPACE ?= renewal-desk
IMAGE_REPO ?= renewal-desk
IMAGE_TAG ?= local
KIND_CLUSTER ?=

.PHONY: install run-api lint type test format docker-up docker-down eval ingest-sample migrate
.PHONY: helm-install helm-uninstall helm-ingest-sample
.PHONY: helm-urls helm-port-forward helm-renewal-brief helm-traffic helm-restart-grafana

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
	@app_id="$$($(DOCKER_COMPOSE) ps -q app)"; \
	if [ -n "$$app_id" ]; then \
		$(DOCKER_COMPOSE) exec app python scripts/load_samples.py; \
	else \
		$(DOCKER_COMPOSE) run --rm app python scripts/load_samples.py; \
	fi

run-evals:
	$(PYTHON) eval/harness.py --cases eval/golden/cases.jsonl --expected eval/golden/expected.jsonl

smoke-eval:
	$(PYTHON) eval/harness.py --smoke

eval: run-evals

docker-up:
	$(DOCKER_COMPOSE) up -d --build

docker-down:
	$(DOCKER_COMPOSE) down

helm-install:
	docker build -t $(IMAGE_REPO):$(IMAGE_TAG) .
	@if [ -n "$(KIND_CLUSTER)" ]; then \
		kind load docker-image $(IMAGE_REPO):$(IMAGE_TAG) --name $(KIND_CLUSTER); \
	fi
	$(HELM) upgrade --install $(HELM_RELEASE) charts/renewal-desk \
		--namespace $(HELM_NAMESPACE) --create-namespace \
		--set image.repository=$(IMAGE_REPO) \
		--set image.tag=$(IMAGE_TAG) \
		--set image.pullPolicy=IfNotPresent

helm-uninstall:
	$(HELM) uninstall $(HELM_RELEASE) --namespace $(HELM_NAMESPACE)

helm-ingest-sample:
	$(KUBECTL) -n $(HELM_NAMESPACE) exec deploy/$(HELM_RELEASE) -- python scripts/load_samples.py

helm-urls:
	@echo "API: $(HELM_API_BASE)"
	@echo "Grafana: $(HELM_GRAFANA_URL)"

helm-port-forward:
	@echo "Starting port-forward for API (8000)."
	@echo "API: http://localhost:8000"
	@echo "Press Ctrl+C to stop."
	$(KUBECTL) -n $(HELM_NAMESPACE) port-forward svc/$(HELM_RELEASE) 8000:8000

helm-renewal-brief:
	curl -sS -X POST "$(HELM_API_BASE)/renewal-brief?vendor_id=$(VENDOR_ID)" \
		-H "Content-Type: application/json" \
		-d '{"refresh": false}' | python3 -m json.tool

helm-traffic:
	@echo "Sending $(REQUESTS) requests to $(HELM_API_BASE)..."
	@for i in $$(seq 1 $(REQUESTS)); do \
		curl -sS -o /dev/null -X POST "$(HELM_API_BASE)/renewal-brief?vendor_id=$(VENDOR_ID)" \
			-H "Content-Type: application/json" \
			-d '{"refresh": false}'; \
		sleep $(SLEEP); \
	done

helm-restart-grafana:
	$(KUBECTL) -n $(HELM_NAMESPACE) rollout restart deploy/$(HELM_RELEASE)-grafana
HELM_API_BASE ?= http://localhost:30080
HELM_GRAFANA_URL ?= http://localhost:30030
VENDOR_ID ?= vendor_123
REQUESTS ?= 1000
SLEEP ?= 0.01
