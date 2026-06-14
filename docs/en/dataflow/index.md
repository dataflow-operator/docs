# DataFlow

**DataFlow** is a namespaced CRD (`dataflows`, kind `DataFlow`, group `dataflow.dataflow.io`) for **continuous** data pipelines. The operator reconciles each resource into a **Deployment** running the processor until you delete the `DataFlow`.

## What it does

You declare **source**, optional **transformations**, and **sink** in the spec. The operator:

1. Resolves `SecretRef` values from Kubernetes Secrets.
2. Writes the resolved spec to a ConfigMap.
3. Creates or updates a **Deployment** with one or more processor pods.
4. Reflects Deployment health in `DataFlow.status`.

The processor runs the same pipeline as [DataFlowCron](../dataflow-cron/index.md): read → transform → write (plus optional error sink).

```mermaid
flowchart LR
  DF[DataFlow CR] --> Op[Operator]
  Op --> CM[ConfigMap spec]
  Op --> Dep[Deployment]
  Dep --> Proc[Processor Pod]
  Proc --> Ext[Kafka / PostgreSQL / Trino / ClickHouse / Nessie]
```

## When to use DataFlow

| Scenario | DataFlow | DataFlowCron |
|----------|----------|--------------|
| Kafka consumer group, always on | ✓ | |
| Real-time replication | ✓ | |
| Nightly table export | | ✓ |
| Hourly batch with Slack webhook after success | | ✓ |

See [Workload Types](../concepts/workload-types.md) for a full comparison.

!!! tip "Scheduled runs"
    For cron-based batch jobs and post-run **triggers**, use [DataFlowCron](../dataflow-cron/index.md) instead.

## API summary

| Item | Value |
|------|-------|
| API group | `dataflow.dataflow.io` |
| Resource | `dataflows` |
| Kind | `DataFlow` |
| Scope | Namespaced |

## Documentation in this section

- [Spec Reference](spec.md) — all `spec` fields, CRD diagram, secrets, checkpoint, replicas
- [Lifecycle & Status](lifecycle.md) — cluster objects (`df-*`), reconciliation, status phases, RBAC

## Minimal example

```yaml
apiVersion: dataflow.dataflow.io/v1
kind: DataFlow
metadata:
  name: kafka-to-postgres
spec:
  source:
    type: kafka
    config:
      brokers: [kafka:9092]
      topic: input-topic
      consumerGroup: dataflow-group
  sink:
    type: postgresql
    config:
      connectionString: "postgres://user:pass@postgres:5432/db?sslmode=disable"
      table: output_table
      autoCreateTable: true
```

```bash
kubectl apply -f dataflow/config/samples/kafka-to-postgres.yaml
kubectl get dataflow kafka-to-postgres
kubectl describe dataflow kafka-to-postgres
```

## See also

- [Architecture](../architecture.md) — operator and processor runtime
- [Connectors](../connectors.md) — source and sink configuration
- [Transformations](../transformations.md)
- [Getting Started](../getting-started.md)
