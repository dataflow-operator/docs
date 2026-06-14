# DataFlow Operator

<div class="md-hero" markdown="block">

Kubernetes operator for streaming and scheduled data pipelines between Kafka, PostgreSQL, ClickHouse, Trino, and Nessie.

[Getting Started](getting-started.md){ .md-button .md-button--primary }
[Architecture](architecture.md){ .md-button }

</div>

## Current Versions

| Component | Version |
|-----------|---------|
| DataFlow Operator | <span data-version-repo="dataflow-operator/dataflow">—</span> |
| Helm Charts | <span data-version-repo="dataflow-operator/helm-charts">—</span> |
| DataFlow MCP | <span data-version-repo="dataflow-operator/dataflow-mcp">—</span> |
| DataFlow Web | <span data-version-repo="dataflow-operator/dataflow-web">—</span> |

## Explore the docs

<div class="grid cards" markdown="block">

-   :material-play-circle:{ .lg .middle } **Getting Started**

    ---

    Install via Helm and create your first pipeline in minutes

    [:octicons-arrow-right-24: Start](getting-started.md)

-   :material-source-branch:{ .lg .middle } **DataFlow**

    ---

    Continuous streaming pipelines backed by a Deployment

    [:octicons-arrow-right-24: Learn more](dataflow/index.md)

-   :material-clock-outline:{ .lg .middle } **DataFlowCron**

    ---

    Scheduled batch runs with optional post-run triggers

    [:octicons-arrow-right-24: Learn more](dataflow-cron/index.md)

-   :material-swap-horizontal:{ .lg .middle } **Workload Types**

    ---

    Choose between DataFlow and DataFlowCron

    [:octicons-arrow-right-24: Compare](concepts/workload-types.md)

-   :material-connection:{ .lg .middle } **Connectors**

    ---

    Kafka, PostgreSQL, ClickHouse, Trino, Nessie, Iceberg

    [:octicons-arrow-right-24: Reference](connectors.md)

-   :material-auto-fix:{ .lg .middle } **Transformations**

    ---

    Filter, mask, route, flatten, and more

    [:octicons-arrow-right-24: Reference](transformations.md)

</div>

## Overview

!!! abstract ""
    DataFlow Operator lets you declaratively define data flows between sources and sinks through Kubernetes CRDs. The operator manages processor lifecycle, applies transformations, and supports both **continuous** (`DataFlow`) and **scheduled** (`DataFlowCron`) workloads.

## Key Features

!!! note "Multiple Data Source Support"
    - **Kafka** — TLS, SASL, Avro, Schema Registry
    - **PostgreSQL** — custom SQL, batch inserts, UPSERT
    - **ClickHouse** — polling, batch inserts, auto-create MergeTree
    - **Trino** — SQL queries, Keycloak OAuth2
    - **Nessie** — Apache Iceberg via Nessie catalog
    - **Iceberg** — Apache Iceberg via REST Catalog API

!!! note "Rich Transformation Set"
    Timestamp, Flatten, Filter, Mask, Router, Select, Remove, SnakeCase, CamelCase, DebeziumUnwrap

!!! tip "Flexible Routing"
    Route messages to different sinks using JSONPath conditions.

!!! tip "Secure Configuration"
    Configure connectors from Kubernetes Secrets via `SecretRef`.

## Quick Start

```bash
helm install dataflow-operator oci://ghcr.io/dataflow-operator/helm-charts/dataflow-operator
kubectl apply -f dataflow/config/samples/kafka-to-postgres.yaml
kubectl get dataflow kafka-to-postgres
```

## Documentation map

| Topic | Link |
|-------|------|
| Installation | [Getting Started](getting-started.md) |
| DataFlow CRD | [Overview](dataflow/index.md) · [Spec](dataflow/spec.md) · [Lifecycle](dataflow/lifecycle.md) |
| DataFlowCron CRD | [Overview](dataflow-cron/index.md) · [Triggers](dataflow-cron/triggers.md) · [Examples](dataflow-cron/examples.md) |
| Operations | [Errors](errors.md) · [Fault Tolerance](fault-tolerance.md) · [Metrics](metrics.md) |
| Tools | [Web GUI](gui.md) · [MCP](mcp.md) |
| Development | [Developer Guide](development.md) |

## License

Apache License 2.0
