# DataFlowCron Examples

YAML samples for scheduled pipelines. Replace connection strings, table names, and service hosts with your own. Inside Job pods use Kubernetes service DNS (e.g. `postgres.default.svc.cluster.local`), not `localhost`.

## Status fields

- **`phase`** — high-level state (`RunningTriggers`, `Completed`, `Failed`, etc.).
- **`currentRunID`** — identifier for the current logical run (used to name trigger Jobs).
- **`currentTriggerIndex`** — which trigger step is active, when applicable.
- **`activeJobName`** — Kubernetes Job name involved in the current failure or step.
- **`lastScheduleTime`**, **`lastSuccessfulTime`**, **`lastFailedTime`** — timestamps for scheduling and outcomes.
- **`conditions`** — standard Kubernetes-style conditions when populated.

```bash
kubectl get dataflowcron
kubectl describe dataflowcron <name>
kubectl get cronjob,job -l dataflow.dataflow.io/dataflow-cron=<name>
```

## Processor only (no `triggers`)

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

## ClickHouse → ClickHouse on a schedule

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

## Nessie (Iceberg) → Kafka

Export a Nessie-backed table to a topic on a schedule. See [Nessie](../connectors.md#nessie).

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

## With transformations

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

## One `trigger` after a successful run

HTTP webhook once the processor **Job** has completed successfully:

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

More trigger patterns: [Triggers](triggers.md).

## Sample manifest in the repo

Kafka source, Nessie sink, and two triggers (`kubectl` and `curl` with a Secret):

```bash
kubectl apply -f dataflow/config/samples/dataflowcron-example.yaml
```

File: `dataflow/config/samples/dataflowcron-example.yaml`. A shorter walkthrough is in [Examples — DataFlowCron](../examples.md#dataflowcron-example).

## See also

- [DataFlowCron Overview](index.md)
- [Spec & Schedule](spec.md)
- [Triggers](triggers.md)
- [Examples](../examples.md)
