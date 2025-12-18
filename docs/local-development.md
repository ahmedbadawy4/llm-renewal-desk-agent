# Local Development Guide

This guide covers two common workflows:

1. Running everything via docker-compose (default).
2. Building the API container locally and deploying it on Minikube to exercise a Kubernetes-style workflow.

## 1. docker-compose (baseline)

```bash
make install          # poetry install
make docker-up        # builds app image + starts Postgres, MinIO, Grafana, Prometheus, OTEL collector
make ingest-sample    # seed `.data/vendor_123`
make run-api          # or rely on the compose service
curl localhost:8000/renewal-brief?vendor_id=vendor_123 -d '{"refresh": false}' -H 'Content-Type: application/json'
```

Shutdown with `make docker-down`.

## 2. Deploying on Minikube

This workflow mimics a managed cluster while keeping everything on your laptop.

### Prerequisites
- Docker / Podman
- Minikube
- Kubectl
- (Optional) Helm for installing dependencies

### Steps

1. **Start Minikube**
   ```bash
   minikube start --cpus=4 --memory=6g
   ```

2. **Point Docker builds at the Minikube Docker daemon**
   ```bash
   eval "$(minikube docker-env)"
   ```
   Now all `docker build` commands register images inside the Minikube cluster without pushing to an external registry.

3. **Build the API image**
   ```bash
   docker build -t renewal-desk:dev .
   ```
   Confirm it exists:
   ```bash
   docker images | grep renewal-desk
   ```

4. **Create supporting services**

   For a lightweight setup, reuse the compose services by running them outside of Minikube (Postgres, MinIO). For a fully in-cluster experience:
   - Deploy Postgres:
     ```bash
     kubectl create namespace renewal
     kubectl apply -n renewal -f infra/k8s/postgres.yaml   # create this manifest mirroring docker-compose settings
     ```
   - Deploy MinIO or reuse S3-compatible storage.
   - Deploy Prometheus/Grafana via Helm or manifests (optional for v0).

5. **Deploy the API + Service**
   Example manifest (`infra/k8s/api.yaml` you can craft from this outline):
   ```yaml
   apiVersion: apps/v1
   kind: Deployment
   metadata:
     name: renewal-desk-api
     namespace: renewal
   spec:
     replicas: 1
     selector:
       matchLabels:
         app: renewal-desk-api
     template:
       metadata:
         labels:
           app: renewal-desk-api
       spec:
         containers:
           - name: api
             image: renewal-desk:dev
             imagePullPolicy: Never
             env:
               - name: APP_ENV
                 value: minikube
               - name: DATABASE_URL
                 value: postgresql://postgres:postgres@postgres.renewal.svc.cluster.local:5432/renewaldesk
               - name: OBJECT_STORE_BUCKET
                 value: renewal-desk
               - name: OTEL_EXPORTER_OTLP_ENDPOINT
                 value: http://otel-collector.renewal.svc.cluster.local:4318
             ports:
               - containerPort: 8000
   ---
   apiVersion: v1
   kind: Service
   metadata:
     name: renewal-desk-api
     namespace: renewal
   spec:
     selector:
       app: renewal-desk-api
     ports:
       - name: http
         port: 80
         targetPort: 8000
     type: ClusterIP
   ```
   Apply:
   ```bash
   kubectl apply -f infra/k8s/api.yaml
   ```

6. **Expose the service locally**
   ```bash
   minikube service renewal-desk-api -n renewal --url
   ```
   Use the returned URL to call `/health`, `/metrics`, and `/renewal-brief`.

7. **Load sample data**
   - Easiest path: run `make ingest-sample` locally, then `kubectl cp` the `.data/vendor_123` directory into the pod, or mount a PersistentVolumeClaim and populate it via a Kubernetes job. A simple approach:
     ```bash
     kubectl exec -it deployment/renewal-desk-api -n renewal -- mkdir -p /app/.data
     kubectl cp .data/vendor_123 renewal/renewal-desk-api-<pod-id>:/app/.data/vendor_123
     ```
   - Alternatively, hit the `/ingest` endpoint with `kubectl port-forward` or via the service URL.

8. **Cleanup**
   ```bash
   kubectl delete namespace renewal
   minikube stop
   ```

### Tips
- Keep manifests in `infra/k8s/` and reuse environment variables from docker-compose.
- Use `minikube tunnel` if you expose services via LoadBalancer type.
- For iterative dev, rebuild the image (step 3) after code changes; Minikube picks up the new image automatically because `imagePullPolicy: Never` forces local usage.

This workflow mirrors what you'd do on a managed cluster (EKS/GKE) but keeps the entire experience on your laptop, making it interview-demo friendly.
