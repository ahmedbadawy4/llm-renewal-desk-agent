# Local Development

Two ways to run the stack on one machine: Docker Compose, and the Helm chart on a local Kubernetes cluster such as kind. Both start the same pieces: the API, PostgreSQL with pgvector, MinIO, Prometheus, Grafana and an OpenTelemetry collector.

## Model server

The brief generator calls Ollama when `LLM_PROVIDER=ollama`, which is the default.

- **Ollama on the host (Compose).** Run `ollama serve` and `ollama pull llama3.1:8b` on the host. The app container reaches it at `http://host.docker.internal:11434`.
- **No model.** Add `"llm_provider": "mock"` to a request body. The brief is then built from the facts extracted from the documents and no model is called.
- **Ollama in the cluster (Helm).** `make helm-install` enables the chart's Ollama deployment. It pulls `llama3.1:8b` into a 7Gi volume and requests 1 CPU and 4Gi of memory (limits 2 CPU and 8Gi), so the cluster needs that much room.

## 1. Docker Compose

Prerequisites: Docker with the Compose plugin, Poetry, Python 3.11.

```bash
make install        # poetry install
make docker-up      # builds the app image and starts every service
make ingest-sample  # loads the sample contract, invoices and usage for vendor_123
```

`docker-up` runs the `migrate` service first and starts the app after it has exited successfully.

Request a brief:

```bash
curl -sS -X POST "http://localhost:8000/renewal-brief?vendor_id=vendor_123" \
  -H "Content-Type: application/json" \
  -d '{"refresh": false}'
```

Stop everything with `make docker-down`.

| Service | Port | Notes |
| --- | --- | --- |
| API | 8000 | OpenAPI docs at `/docs`, metrics at `/metrics` |
| Grafana | 3000 | Dashboards are provisioned from `infra/grafana/dashboards`. The login is set in `infra/docker-compose.yml`. |
| Prometheus | 9090 | Loads the rules in `infra/prometheus/alerts.yml` |
| MinIO | 9000, 9001 | Started with the stack. The app stores uploads on local disk, not in MinIO. |
| PostgreSQL | 5432 | Database `renewaldesk` |
| OpenTelemetry collector | 4318 | OTLP over HTTP |

Notes:

- The app container has no data volume. Files from `make ingest-sample` are lost when the container is recreated, so run the target again after `docker-up`.
- To run the API on the host instead, keep the Compose services up, stop the `app` container and run `make run-api`. The database default (`localhost:5432`) matches the published port. Run `make migrate` once to create the tables. The default model address uses `host.docker.internal`, so set `LLM_BASE_URL=http://localhost:11434` when the API runs on the host.
- `make lint`, `make type` and `make test` run Ruff, mypy and pytest through the Poetry environment.

### UI

`ui/` is a static page that talks to the API. With the API on port 8000:

```bash
python -m http.server 5173 -d ui
```

Open http://localhost:5173. The API allows that origin through CORS. `ui-react/` holds Next.js sources for a second version of the UI. It is not part of Compose or the chart.

## 2. Helm chart on a local cluster

Prerequisites: Docker, Helm, kubectl and a local cluster. The examples use kind.

```bash
kind create cluster --name renewal
make helm-install KIND_CLUSTER=renewal KUBE_CONTEXT=kind-renewal
```

`helm-install` builds the image, loads it into the kind cluster, installs the chart into the `renewal-desk` namespace with Ollama enabled and restarts the deployments so they pick up the new image. Setting `KUBE_CONTEXT` makes every `helm` and `kubectl` call in the Makefile use that context instead of whichever one is current. Leave `KIND_CLUSTER` empty for a cluster that does not need the image loaded.

Load the sample data and request a brief:

```bash
make helm-ingest-sample KUBE_CONTEXT=kind-renewal
make helm-renewal-brief
```

`helm-renewal-brief` calls the API at `http://localhost:30080`. The service uses NodePorts, which kind does not publish to the host unless the cluster was created with matching port mappings. Without them, run `make helm-port-forward` (API on http://localhost:8000) and pass `HELM_API_BASE=http://localhost:8000` to `helm-renewal-brief`.

| Service | NodePort | Note |
| --- | --- | --- |
| API | 30080 | |
| Grafana | 30030 | |
| UI | 30081 | nginx serving `ui/`, with the API address from `ui.apiBaseUrl` |

`make helm-urls` prints these addresses.

Other targets:

| Target | Use |
| --- | --- |
| `make helm-lint` | `helm lint` and a render of the templates, with and without the ingress. Needs no cluster. |
| `make helm-install-ollama-external` | Installs without the in-cluster Ollama and points the app at `OLLAMA_BASE_URL` (default `http://host.docker.internal:11434`). |
| `make helm-restart-grafana` | Restarts Grafana after a dashboard change. |
| `make helm-traffic REQUESTS=200` | Sends repeated brief requests so the dashboards have data. |
| `make helm-uninstall` | Removes the release. |

The chart mounts `emptyDir` volumes for uploaded files, so they are lost when the pod is replaced. Run `make helm-ingest-sample` again after a restart. Chart values are in `charts/renewal-desk/values.yaml`. The Prometheus in the chart scrapes the app but has no alert rules.
