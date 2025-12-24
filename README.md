# Renewal Desk Agent

Production-grade LLM decision-support agent for SaaS vendor renewals. It ingests contracts, invoices, and usage exports, runs retrieval + tool-gated reasoning, and returns a renewal brief with citations, risk flags, negotiation plan, and draft outreach.

## 90-second demo (Helm + Make)
Requires a local Kubernetes cluster (Docker Desktop, minikube, or kind) and Helm.
1. **Boot the stack**
   ```bash
   make helm-install
   ```
2. **Ingest the sample data**
   ```bash
   make helm-ingest-sample
   ```
3. **Generate a renewal brief**
   ```bash
   make helm-renewal-brief
   ```
4. **Open Grafana** at http://localhost:30030 to see latency/token/tool metrics.

If your cluster does not expose NodePorts on localhost, use port-forward:
```bash
make helm-port-forward
```
Generate traffic to populate dashboards:
```bash
make helm-traffic REQUESTS=10 SLEEP=1
```

![Grafana Renewal Desk dashboard](docs/assets/grafana-chart.png)

## What you get
- **Agent design**: LLM-style loop with retrieval + tool orchestration for real workflows.
- **Integration**: Clear API surface (`/ingest`, `/renewal-brief`) built for embedding into products and internal systems.
- **Guardrails**: Prompt injection detection, schema validation, and RBAC-style tool gating.
- **Reliability**: Budgets, validation outcomes, and error-rate monitoring as production signals.
- **Observability**: OTel traces + Prometheus metrics + Grafana dashboards + live debug traces.
- **Eval-ready**: Golden cases, injection suite, CI smoke evals.

## Portfolio note (AI Systems Engineer)
This repo is built as a production-style AI systems portfolio piece. It emphasizes dependable ingest flows, retrieval/tool orchestration, strict schema validation, and observable deployments. The goal is to demonstrate end-to-end system engineering: infrastructure-as-code, runtime guardrails, cost/latency controls, and metrics-driven operations.

## Debuggability proof
Minimal trace endpoint is live at `/debug/trace/{request_id}` (in-memory, last 200) and returns:
- retrieved doc IDs
- tool calls invoked
- token counters (in/out/total)
- validation outcomes

Example:
```bash
curl -sS "http://localhost:30080/debug/trace/<request_id>" | python -m json.tool
```

## How it works (high level)
- Ingests vendor contract/invoice/usage files into a local object store and updates a per-vendor manifest.
- Serves a FastAPI endpoint (`/renewal-brief`) that runs retrieval + tool-gated reasoning to generate a structured renewal brief.
- Exposes Prometheus metrics on `/metrics` for request rate, latency, agent status, and token usage.

## What happens on traffic
- Each POST increments request counters and adds latency samples.
- Agent counters (status) and token counters increase per run.
- Prometheus scrapes metrics every 15s; Grafana charts update shortly after.

## Grafana dashboard (panels)
- **Request rate (req/s)**: total API call volume over time.
- **Latency p95 (s)**: tail latency for API responses.
- **Error rate (5xx %)**: server error percentage.
- **Agent requests by status**: success vs failure count rate.
- **Token usage (per sec)**: in/out token counters.
- **Request rate by path**: which endpoints are being hit.

## Quickstart (local dev)
1. **Install dependencies**
   ```bash
   pipx install poetry  # optional
   make install
   ```
2. **Run API locally**
   ```bash
   make run-api  # or uvicorn src.app.main:app
   ```
3. **Run evals**
   ```bash
   make eval
   ```
4. **Shut everything down**
   ```bash
   make docker-down
   ```

## Helm (Kubernetes)
```bash
make helm-install  # builds a local image and installs the chart
```
For kind, pass `KIND_CLUSTER=your-cluster` so the image is loaded into the node.
Access URLs:
```bash
make helm-urls
```
If the dashboard does not auto-provision, restart Grafana:
```bash
make helm-restart-grafana
```

## Cleanup
```bash
make helm-uninstall
docker compose -f infra/docker-compose.yml down -v
rm -rf .data
```

## Architecture (short)
- `src/app` holds the FastAPI service, agent runner, tool gateway, RAG components, and storage adapters.
- `docs/architecture.md` and `docs/data-flow.md` explain ingestion, retrieval routing, validation, and observability.
- `infra/` contains docker-compose, Grafana provisioning, Prometheus, and OTel collector config.

## Docs
- `docs/local-development.md`: Docker + Minikube notes
- `docs/runbook.md`: Demo + incident procedures
- `docs/threat-model.md`: Security posture and risks
- `docs/architecture.md`: C4-ish view
- `docs/data-flow.md`: End-to-end flow

## Roadmap
- [ ] Implement document parsing (pdfminer/pymupdf) + table extraction
- [ ] Build pgvector migrations + hybrid retrieval queries
- [ ] Finish agent loop with multi-model routing
- [ ] Expand evaluator with cost/latency budgets + tolerance bands
- [ ] Add Terraform modules for AWS ECS + RDS + OpenSearch
- [ ] Ship a thin React/Next.js UI + Slack slash command
