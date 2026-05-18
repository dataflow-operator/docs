# DataFlowCron (scheduled runs)

**DataFlowCron** is a namespaced CRD (`dataflowcrons`, kind `DataFlowCron`, group `dataflow.dataflow.io`) for running the same **Source → Transformations → Sink** pipeline as [DataFlow](architecture.md), but on a **cron schedule** using Kubernetes **CronJob** / **Job** instead of a long-lived Deployment.

Use it when the workload is naturally **batch-oriented** (e.g. poll a table, export a window, then stop) or when you want a **periodic** run with optional **post-processing steps** (`triggers`) after the processor finishes successfully.

## Spec overview

`DataFlowCronSpec` **embeds [`DataFlowSpec`](architecture.md#dataflow-crd-structure)** — so all fields that exist on `DataFlow` (`source`, `sink`, `transformations`, `errors`, `resources`, `nodeSelector`, `affinity`, `tolerations`, `checkpointPersistence`, `channelBufferSize`, `processorImage` / `processorVersion`, `imagePullSecrets`, etc.) apply the same way.

Additionally:

| Field | Description |
|-------|-------------|
| **`schedule`** (required) | Cron expression with **5 or 6** fields (standard Kubernetes cron format). |
| **`concurrencyPolicy`** | `Allow`, `Forbid`, or `Replace` — same semantics as `CronJob.spec.concurrencyPolicy`. Default Kubernetes behavior applies if omitted. |
| **`successfulJobsHistoryLimit`** / **`failedJobsHistoryLimit`** | Passed through to the managed `CronJob`. |
| **`startingDeadlineSeconds`** | Passed through to the `CronJob`. |
| **`suspend`** | When set, suspends scheduling (CronJob `suspend`). |
| **`triggers`** | See [The `triggers` section](#the-triggers-section). |

Validation reuses **DataFlow** rules for source, sink, transformations, and resources, and adds checks for `schedule`, trigger `image`, and `concurrencyPolicy`. When the [validating webhook](development.md#configuring-the-validating-webhook) is enabled (Helm: `webhook.enabled` and `webhook.caBundle`), admission validates both `DataFlowCron` and `DataFlow` before objects are stored.

## Objects created in the cluster

For a `DataFlowCron` named `<name>` in a namespace:

| Resource | Name | Role |
|----------|------|------|
| ConfigMap | `dfc-<name>-spec` | JSON spec for the processor (`spec.json`), same role as `df-<name>-spec` for `DataFlow`. |
| CronJob | `dfc-<name>` | Runs the **processor** workload on `schedule` (first step of each run). |
| Job(s) | `dfc-<name>-…` | The CronJob creates the processor Job; optional **trigger** Jobs are created by the operator after the processor succeeds. |

Processor pods use the same entrypoint as in the Deployment-based flow: `/processor --spec-path=/etc/dataflow/spec.json --namespace=… --name=…` (with `name` set to the **DataFlowCron** resource name).

## Execution flow

1. On each schedule tick, the **CronJob** starts a **Job** whose pod runs the **processor** until the source is exhausted or the process exits (behavior depends on the source type).
2. If **`triggers`** is non-empty, after that Job **succeeds**, the operator enqueues **trigger Jobs** in order; each runs the image you specified (for example `kubectl`, `curl`, or an internal CLI).
3. **Status** on `DataFlowCron` tracks phases such as runs in progress, trigger steps (`RunningTriggers`), **`Completed`** (last successful run), or **`Failed`** if a Job fails.

### Source types and “when does the run finish?”

- **Polling sources** (e.g. PostgreSQL, Trino, ClickHouse, Nessie) typically **finish** when the source is **exhausted**, so the processor Job can complete and triggers can run.
- **Kafka** is **streaming**: the processor often does **not** stop by itself, so a Cron-driven Kafka pipeline may not reach “success → triggers” unless you design for completion (for example bounded work or external cancellation). Prefer a polling or batch-friendly source for scheduled **post-triggers**.

## The `triggers` section {#the-triggers-section}

`spec.triggers` is an **ordered list of extra steps** that run after the main data pipeline. Each item describes **exactly one container**, with the same core knobs as `Pod.spec.containers[]`: `image`, `command`, `args`, `env`, `resources`, `imagePullPolicy`.

### When and how they run

1. On schedule, the **CronJob** starts the **processor Job** (same `/processor` binary as `DataFlow`).
2. Triggers **do not start** until that Job is **successful** (`JobComplete=True`).
3. The controller creates **one Kubernetes Job per trigger**, **in list order**: `triggers[0]` first, then `triggers[1]` after the previous Job succeeds, and so on.
4. All Jobs from the same cron tick share a **run ID** (`dataflow.dataflow.io/run-id`), which is useful when filtering in `kubectl` or logs.
5. Each trigger pod has **a single container** and `restartPolicy: Never` — the container must exit **0** or the chain stops with a failed step.

Steps **do not run in parallel**, and there is **no** templating of arguments from pipeline output — think **sequential hooks**, not an internal DAG.

### `triggers[]` fields

| Field | Required | Description |
|-------|----------|-------------|
| **`image`** | Yes | Container image (same as for a normal Job). |
| **`name`** | No | Container name in the Pod; if empty, the controller uses `trigger-<index>`. |
| **`command`** | No | Entrypoint (overrides the image `ENTRYPOINT` when set). |
| **`args`** | No | Arguments to `command`. |
| **`env`** | No | Environment variables, including `valueFrom.secretKeyRef` / `configMapKeyRef` (core `EnvVar`). |
| **`resources`** | No | CPU/memory `requests` and `limits`. |
| **`imagePullPolicy`** | No | E.g. `IfNotPresent` or `Always`. |

The **`DataFlowCronTrigger` API has no `volumeMounts` or extra Pod volumes**. Files appear only if they are **baked into the image**, or the container fetches them (e.g. `kubectl apply -f https://...`). The path `/manifests/...` in `dataflowcron-example.yaml` only works if your image actually provides that path, or if you extend the CRD/controller to mount a ConfigMap/Secret.

### Debugging

Labels on processor and trigger Jobs/Pods:

- `dataflow.dataflow.io/dataflow-cron=<DataFlowCron name>`
- `dataflow.dataflow.io/run-id=<run id>`
- `dataflow.dataflow.io/trigger-index=<index>` (processor Job from CronJob uses `-1`)

```bash
kubectl get jobs -l dataflow.dataflow.io/dataflow-cron=my-cron -o wide
kubectl logs job/<trigger-job-name> --all-containers=true
```

Use **`status.phase`**, **`currentTriggerIndex`**, **`activeJobName`**, **`lastFailedTime`** on the `DataFlowCron` for a high-level view.

### `triggers` examples

**Two-step chain: webhook, then another HTTP call** (if the first container exits non-zero, the second never runs):

```yaml
  triggers:
    - name: notify-slack
      image: curlimages/curl:8.8.0
      command: ["curl", "-fsS", "-X", "POST", "-H", "Content-Type: application/json"]
      args:
        - "-d"
        - '{"text":"ETL cron finished"}'
        - "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
    - name: refresh-bi-cache
      image: curlimages/curl:8.8.0
      args: ["-fsS", "-X", "POST", "http://bi-service:8080/internal/refresh"]
```

**Token from a Secret** (Airflow 2.x usually needs an `Authorization: Bearer …` header; a single shell command keeps expansion simple):

```yaml
  triggers:
    - name: start-airflow-dag
      image: curlimages/curl:8.8.0
      command: ["/bin/sh", "-c"]
      args:
        - 'curl -fsS -X POST -H "Authorization: Bearer ${AIRFLOW_TOKEN}" -H "Content-Type: application/json" --data "{}" http://airflow-webserver.dataflow.svc:8080/api/v1/dags/my_dag/dagRuns'
      env:
        - name: AIRFLOW_TOKEN
          valueFrom:
            secretKeyRef:
              name: airflow-token
              key: token
```

**`kubectl` against in-cluster resources** (the pod uses the namespace `default` ServiceAccount unless you change the Job spec elsewhere — add `Role`/`RoleBinding` as needed):

```yaml
  triggers:
    - name: annotate-last-run
      image: bitnami/kubectl:latest
      command: ["/bin/bash", "-ec"]
      args:
        - |
          kubectl annotate dataflowcron my-cron company.example.com/last-ok="$(date -Iseconds)" --overwrite
```

**Resources and pull policy** for a heavier CLI:

```yaml
  triggers:
    - name: run-spark-submit
      image: my-registry/spark-cli:v1
      imagePullPolicy: IfNotPresent
      command: ["/opt/spark/bin/spark-submit"]
      args: ["--master", "k8s://https://kubernetes.default.svc", "/app/batch.py"]
      resources:
        requests:
          cpu: "500m"
          memory: "512Mi"
        limits:
          memory: "1Gi"
```

## Status (useful fields)

- **`phase`** — high-level state (`RunningTriggers`, `Completed`, `Failed`, etc.).
- **`currentRunID`** — identifier for the current logical run (used to name trigger Jobs).
- **`currentTriggerIndex`** — which trigger step is active, when applicable.
- **`activeJobName`** — Kubernetes Job name involved in the current failure or step.
- **`lastScheduleTime`**, **`lastSuccessfulTime`**, **`lastFailedTime`** — timestamps for scheduling and outcomes.
- **`conditions`** — standard Kubernetes-style conditions when populated.

Inspect with:

```bash
kubectl get dataflowcron
kubectl describe dataflowcron <name>
kubectl get cronjob,job -l dataflow.dataflow.io/dataflow-cron=<name>
```

## Examples

Below are typical `spec` fragments. Replace connection strings, table names, and service hosts with your own. Inside Job pods use Kubernetes service DNS (e.g. `postgres.default.svc.cluster.local`), not `localhost`.

### Processor only (no `triggers`)

**PostgreSQL polling** on a schedule and writing to another table. When the source batch is exhausted, the processor Job exits successfully.

```yaml
apiVersion: dataflow.dataflow.io/v1
kind: DataFlowCron
metadata:
  name: pg-nightly-sync
spec:
  schedule: "0 2 * * *"   # daily 02:00 (timezone = kube-controller-manager zone)
  concurrencyPolicy: Forbid
  source:
    type: postgresql
    config:
      connectionString: "postgres://user:pass@postgres:5432/db?sslmode=disable"
      table: public.orders_staging
      pollInterval: 5
  sink:
    type: postgresql
    config:
      connectionString: "postgres://user:pass@postgres:5432/db?sslmode=disable"
      table: public.orders_warehouse
      autoCreateTable: true
      batchSize: 200
```

### Job history limits and start deadline

Useful when you do not want to keep a long history of **CronJob** child Jobs in etcd:

```yaml
  schedule: "15 */6 * * *"
  concurrencyPolicy: Forbid
  successfulJobsHistoryLimit: 2
  failedJobsHistoryLimit: 3
  startingDeadlineSeconds: 300   # skip launch if the schedule slot was missed by > 5 minutes
```

### ClickHouse → ClickHouse on a schedule

Periodic copy between tables (same layout as `dataflow/config/samples/clickhouse-to-clickhouse.yaml`, wrapped in `DataFlowCron`).

```yaml
apiVersion: dataflow.dataflow.io/v1
kind: DataFlowCron
metadata:
  name: ch-hourly-copy
spec:
  schedule: "0 * * * *"
  concurrencyPolicy: Forbid
  source:
    type: clickhouse
    config:
      connectionString: "clickhouse://default@clickhouse:9000/default?dial_timeout=10s"
      table: events_raw
      pollInterval: 10
  sink:
    type: clickhouse
    config:
      connectionString: "clickhouse://default@clickhouse:9000/default?dial_timeout=10s"
      table: events_hourly
      batchSize: 500
      autoCreateTable: true
```

### Nessie (Iceberg) → Kafka

Export a Nessie-backed table to a topic on a schedule. See [Nessie](connectors.md#nessie).

```yaml
apiVersion: dataflow.dataflow.io/v1
kind: DataFlowCron
metadata:
  name: nessie-to-kafka-hourly
spec:
  schedule: "0 * * * *"
  source:
    type: nessie
    config:
      baseURL: "http://nessie:19120"
      branch: main
      authenticationType: BEARER
      bearerToken: "replace-with-token"
      namespace: analytics
      table: events
      pollInterval: 30
  sink:
    type: kafka
    config:
      brokers:
        - kafka:9092
      topic: iceberg-snapshot
```

### With transformations

The embedded `DataFlowSpec` supports the same **transformations** chain as `DataFlow`:

```yaml
  schedule: "*/30 * * * *"
  source:
    type: postgresql
    config:
      connectionString: "postgres://user:pass@postgres:5432/db?sslmode=disable"
      table: public.events
      pollInterval: 5
  transformations:
    - type: timestamp
      config: {}
    - type: select
      config:
        fields: ["id", "payload", "created_at"]
  sink:
    type: kafka
    config:
      brokers: [kafka:9092]
      topic: curated-events
```

### One `trigger` after a successful run

HTTP webhook once the processor **Job** has completed successfully (replace image and URL):

```yaml
  schedule: "0 6 * * *"
  concurrencyPolicy: Forbid
  source:
    type: postgresql
    config:
      connectionString: "postgres://user:pass@postgres:5432/db?sslmode=disable"
      table: public.daily_export
      pollInterval: 5
  sink:
    type: postgresql
    config:
      connectionString: "postgres://user:pass@postgres:5432/db?sslmode=disable"
      table: public.daily_export_archive
      batchSize: 1000
  triggers:
    - name: notify-done
      image: curlimages/curl:8.8.0
      command: ["curl", "-fsS", "-X", "POST"]
      args: ["https://hooks.example.com/job-done"]
```

### Sample manifest in the repo

Kafka source, Nessie sink, and two triggers (`kubectl` and `curl` with a Secret):

```bash
kubectl apply -f dataflow/config/samples/dataflowcron-example.yaml
```

File: `dataflow/config/samples/dataflowcron-example.yaml`. A shorter walkthrough is in [Examples — DataFlowCron](examples.md#dataflowcron-example).

### Pausing the schedule

Without deleting the resource you can **suspend** new Jobs from the underlying `CronJob` (the field is passed through as `suspend`):

```yaml
spec:
  schedule: "0 * * * *"
  suspend: true
  # ...
```

To resume, remove `suspend` or set `suspend: false`.

## See also

- [Architecture](architecture.md) — how the processor and `DataFlow` work
- [Connectors](connectors.md) — source and sink configuration
- [Transformations](transformations.md)
- [Examples](examples.md)
