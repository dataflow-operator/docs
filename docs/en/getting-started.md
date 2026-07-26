# Getting Started

Install the operator, create a streaming or scheduled pipeline, or set up a local development environment.

**When to read this:** first install or first pipeline. For connector field details see [Connectors](connectors.md); for DataFlow vs DataFlowCron see [Workload Types](concepts/workload-types.md).

**See also:** [FAQ](faq.md) · [Best Practices](best-practices.md) · [DataFlowCron](dataflow-cron/index.md)

## Paths

1. [Install the operator](#install-the-operator) — Helm / CRDs
2. [First streaming pipeline](#first-streaming-pipeline) — `DataFlow` with `SecretRef`
3. [First cron pipeline](#first-cron-pipeline) — `DataFlowCron`
4. [Local development](#local-development) — Go, Docker, kind

---

## Install the operator { #install-the-operator }

### Prerequisites

- Kubernetes cluster (1.24+)
- Helm 3.0+
- kubectl configured for the cluster
- Access to data sources (Kafka, PostgreSQL, etc.)

### CRD management { #crd }

The operator installs two CRDs: **`DataFlow`** (`dataflows`) and **`DataFlowCron`** (`dataflowcrons`).

#### Automatic (via Helm)

With Helm (recommended), CRDs are installed and updated automatically when `crds.install: true` (default). No separate `kubectl apply` is required.

#### Manual installation

If you manage CRDs separately (ArgoCD, FluxCD, or `crds.install: false`), apply **both** CRDs:

```bash
kubectl apply -f https://raw.githubusercontent.com/dataflow-operator/dataflow/refs/heads/main/config/crd/bases/dataflow.dataflow.io_dataflows.yaml
kubectl apply -f https://raw.githubusercontent.com/dataflow-operator/dataflow/refs/heads/main/config/crd/bases/dataflow.dataflow.io_dataflowcrons.yaml
```

Or from a local checkout:

```bash
kubectl apply -f dataflow/config/crd/bases/dataflow.dataflow.io_dataflows.yaml
kubectl apply -f dataflow/config/crd/bases/dataflow.dataflow.io_dataflowcrons.yaml
```

#### CRD Helm configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `crds.install` | `true` | Install and update CRDs on `helm install` / `helm upgrade` |
| `crds.keep` | `true` | Add `helm.sh/resource-policy: keep` so CRDs survive `helm uninstall` |

**Upgrade:** CRDs are updated on every `helm upgrade`.

**Uninstall:** With `crds.keep: true` (default), CRDs remain after `helm uninstall`. To skip Helm CRD install:

```yaml
crds:
  install: false
```

### Installation via Helm (recommended)

#### Basic install

```bash
helm install dataflow-operator oci://ghcr.io/dataflow-operator/helm-charts/dataflow-operator
```

Installs into the `default` namespace with chart defaults.

#### Specific namespace

```bash
helm install dataflow-operator oci://ghcr.io/dataflow-operator/helm-charts/dataflow-operator \
  --namespace dataflow-system \
  --create-namespace
```

For local chart development:

```bash
helm install dataflow-operator ./helm-charts/dataflow-operator
```

#### Custom settings

```bash
helm install dataflow-operator oci://ghcr.io/dataflow-operator/helm-charts/dataflow-operator \
  --set image.repository=your-registry/controller \
  --set image.tag=v1.0.0 \
  --set replicaCount=2 \
  --set resources.limits.memory=1Gi \
  --set resources.limits.cpu=500m \
  --set resources.requests.memory=256Mi \
  --set resources.requests.cpu=100m
```

#### Values file

```yaml
image:
  repository: your-registry/controller
  tag: v1.0.0

replicaCount: 2

resources:
  limits:
    cpu: 1000m
    memory: 1Gi
  requests:
    cpu: 500m
    memory: 512Mi

serviceAccount:
  create: true
  annotations:
    eks.amazonaws.com/role-arn: arn:aws:iam::123456789012:role/dataflow-operator

securityContext:
  runAsNonRoot: true
  runAsUser: 1000
  fsGroup: 1000

# Optional: Sentry
# sentry:
#   enabled: true
#   dsn: "https://xxx@o0.ingest.sentry.io/123"
#   environment: production
#   tracesSampleRate: 0.1
```

```bash
helm install dataflow-operator oci://ghcr.io/dataflow-operator/helm-charts/dataflow-operator -f my-values.yaml
```

#### Verification

```bash
kubectl get pods -l app.kubernetes.io/name=dataflow-operator

# Both CRDs
kubectl get crd dataflows.dataflow.dataflow.io dataflowcrons.dataflow.dataflow.io

kubectl logs -l app.kubernetes.io/name=dataflow-operator --tail=50
kubectl get deployment dataflow-operator
```

Expected:

```
NAME                                  READY   STATUS    RESTARTS   AGE
dataflow-operator-7d8f9c4b5d-xxxxx   1/1     Running   0          1m
```

### Updating

```bash
helm upgrade dataflow-operator oci://ghcr.io/dataflow-operator/helm-charts/dataflow-operator
```

With values:

```bash
helm upgrade dataflow-operator oci://ghcr.io/dataflow-operator/helm-charts/dataflow-operator -f my-values.yaml
```

Pin a version:

```bash
helm upgrade dataflow-operator oci://ghcr.io/dataflow-operator/helm-charts/dataflow-operator \
  --set image.tag=v1.1.0
```

### Uninstallation

```bash
helm uninstall dataflow-operator
```

With `crds.keep: true`, CRDs remain; existing resources stop being reconciled.

To remove CRDs and **all** DataFlow / DataFlowCron resources:

```bash
kubectl delete dataflow --all --all-namespaces
kubectl delete dataflowcron --all --all-namespaces

helm uninstall dataflow-operator

kubectl delete crd dataflows.dataflow.dataflow.io
kubectl delete crd dataflowcrons.dataflow.dataflow.io
```

!!! warning
    Deleting CRDs removes **all** `DataFlow` and `DataFlowCron` resources in every namespace.

---

## First streaming pipeline { #first-streaming-pipeline }

Continuous `DataFlow` (Deployment). Prefer **`SecretRef`** for credentials in cluster / production.

### Kafka → PostgreSQL with SecretRef

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: kafka-credentials
  namespace: default
type: Opaque
stringData:
  brokers: "kafka-broker:9092"
  topic: "input-topic"
  consumerGroup: "dataflow-group"
---
apiVersion: v1
kind: Secret
metadata:
  name: postgres-credentials
  namespace: default
type: Opaque
stringData:
  connectionString: "postgres://user:password@postgres-host:5432/dbname?sslmode=require"
  table: "output_table"
---
apiVersion: dataflow.dataflow.io/v1
kind: DataFlow
metadata:
  name: kafka-to-postgres
  namespace: default
spec:
  source:
    type: kafka
    config:
      brokersSecretRef:
        name: kafka-credentials
        key: brokers
      topicSecretRef:
        name: kafka-credentials
        key: topic
      consumerGroupSecretRef:
        name: kafka-credentials
        key: consumerGroup
  sink:
    type: postgresql
    config:
      connectionStringSecretRef:
        name: postgres-credentials
        key: connectionString
      tableSecretRef:
        name: postgres-credentials
        key: table
      autoCreateTable: true
```

Apply the sample from the repo (includes SASL SecretRefs):

```bash
kubectl apply -f dataflow/config/samples/kafka-to-postgres-secrets.yaml
```

Details: [Using Kubernetes Secrets](connectors.md#using-kubernetes-secrets). Pod resources and placement: [Examples](examples.md#configuring-pod-resources-and-placement).

### Check status

```bash
kubectl get dataflow kafka-to-postgres
kubectl describe dataflow kafka-to-postgres
kubectl get dataflow kafka-to-postgres -o yaml
```

Example status:

```yaml
status:
  phase: Running
  processedCount: 150
  errorCount: 0
  lastProcessedTime: "2024-01-15T10:30:00Z"
  message: "Processing messages successfully"
```

### Send a test message

```bash
kafka-console-producer --broker-list kafka-broker:9092 --topic input-topic
# Enter JSON and press Enter
{"id": 1, "name": "Test", "value": 100}
```

Or (local stack):

```bash
./scripts/send-test-message.sh
```

### Verify PostgreSQL

```bash
psql "$CONNECTION_STRING" -c "SELECT * FROM output_table;"
```

---

## First cron pipeline { #first-cron-pipeline }

`DataFlowCron` runs the same Source → Transform → Sink pipeline on a **cron schedule** (CronJob / Job), with optional post-run [triggers](dataflow-cron/triggers.md).

Best fit: **polling / batch** sources (`postgresql`, `trino`, `clickhouse`, `nessie`, `iceberg`). Kafka is streaming and usually does not finish by source exhaustion — see [DataFlowCron](dataflow-cron/index.md) and [Workload Types](concepts/workload-types.md).

### Minimal example (PostgreSQL → PostgreSQL)

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: postgres-credentials
  namespace: default
type: Opaque
stringData:
  connectionString: "postgres://user:password@postgres:5432/db?sslmode=require"
---
apiVersion: dataflow.dataflow.io/v1
kind: DataFlowCron
metadata:
  name: pg-nightly-sync
spec:
  schedule: "0 2 * * *"
  concurrencyPolicy: Forbid
  source:
    type: postgresql
    config:
      connectionStringSecretRef:
        name: postgres-credentials
        key: connectionString
      table: public.orders_staging
      pollInterval: 5
  sink:
    type: postgresql
    config:
      connectionStringSecretRef:
        name: postgres-credentials
        key: connectionString
      table: public.orders_warehouse
      autoCreateTable: true
      batchSize: 200
```

```bash
kubectl apply -f pg-nightly-sync.yaml
kubectl get dataflowcron pg-nightly-sync
kubectl get cronjob,job -l dataflow.dataflow.io/dataflow-cron=pg-nightly-sync
```

Repo sample (Kafka → Nessie + triggers): `dataflow/config/samples/dataflowcron-example.yaml`. More YAML: [DataFlowCron Examples](dataflow-cron/examples.md).

---

## Local development { #local-development }

For contributors running the operator against docker-compose / kind. Plaintext connection strings are acceptable **only** in this local path.

### Prerequisites

- Go 1.25+
- Docker and Docker Compose
- Task (optional)
- Ports: 8080, 5050, 15672, 8081, 5432, 9092, 5672

### Start dependencies

```bash
docker-compose up -d
```

Starts Kafka (9092) + Kafka UI (8080), PostgreSQL (5432) + pgAdmin (5050).

- **Kafka UI:** http://localhost:8080
- **pgAdmin:** http://localhost:5050 — `admin@admin.com` / `admin`

### Local-only DataFlow (plaintext)

!!! warning "Local development only"
    Do **not** use plaintext credentials in shared or production clusters. Prefer [SecretRef](#first-streaming-pipeline).

```yaml
apiVersion: dataflow.dataflow.io/v1
kind: DataFlow
metadata:
  name: kafka-to-postgres
  namespace: default
spec:
  source:
    type: kafka
    config:
      brokers:
        - localhost:9092
      topic: input-topic
      consumerGroup: dataflow-group
  sink:
    type: postgresql
    config:
      connectionString: "postgres://dataflow:dataflow@localhost:5432/dataflow?sslmode=disable"
      table: output_table
      autoCreateTable: true
```

```bash
kubectl apply -f dataflow/config/samples/kafka-to-postgres.yaml
```

### Run the operator locally

```bash
task install   # CRDs (kind / minikube)
task run
```

Or:

```bash
./scripts/run-local.sh
```

### Optional: kind cluster

```bash
./scripts/setup-kind.sh
task install
task run
```

### Debugging

```bash
kubectl logs -l app.kubernetes.io/name=dataflow-operator -f
kubectl get events --sort-by='.lastTimestamp' | grep dataflow
```

---

## Next steps

1. [Connectors](connectors.md) — sources and sinks
2. [Transformations](transformations.md) — message transforms
3. [Examples](examples.md) — practical manifests
4. [Agent Skills](agent-skills.md) — AI-assisted deploy and authoring
5. [Development](development.md) — contributing

---

## Troubleshooting

### Operator not starting

```bash
kubectl logs -l app.kubernetes.io/name=dataflow-operator
kubectl describe pod -l app.kubernetes.io/name=dataflow-operator
kubectl get crd dataflows.dataflow.dataflow.io dataflowcrons.dataflow.dataflow.io -o yaml
```

### DataFlow not processing messages

1. `kubectl describe dataflow <name>`
2. Check source connectivity (Kafka consumer / `psql` query)
3. Inspect operator / processor logs

### Connection issues

- Reachability from the cluster (NetworkPolicies, DNS)
- Credentials and Secret keys
- Local: `localhost` or `host.docker.internal`

### Trino: REMOTE_TASK_ERROR (Code 65542)

Worker did not answer the coordinator. The operator retries (up to 5 attempts with backoff).

If it persists: lower Trino sink `batchSize` (e.g. 3–5), check Trino workers, increase query timeouts.
