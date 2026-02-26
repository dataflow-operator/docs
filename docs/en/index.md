# DataFlow Operator

DataFlow Operator is a Kubernetes operator for streaming data between different data sources with support for message transformations.

## Overview

DataFlow Operator allows you to declaratively define data flows between different sources and sinks through Kubernetes Custom Resource Definitions (CRD). The operator automatically manages the lifecycle of data flows, processes messages, and applies necessary transformations.

## Key Features

### Multiple Data Source Support

- **Kafka** — read and write messages from/to Kafka topics (TLS, SASL, Avro, Schema Registry)
- **PostgreSQL** — read from tables and write with custom SQL, batch inserts, UPSERT mode
- **ClickHouse** — polling, batch inserts, auto-create MergeTree tables
- **Trino** — SQL queries, Keycloak OAuth2, batch inserts

### Rich Transformation Set

- **Timestamp** - add timestamp to each message
- **Flatten** - expand arrays into separate messages while preserving parent fields
- **Filter** - filter messages based on JSONPath conditions
- **Mask** - mask sensitive data with or without preserving length
- **Router** - route messages to different sinks based on conditions
- **Select** - select specific fields from messages
- **Remove** - remove specified fields from messages
- **SnakeCase** - convert field names to snake_case
- **CamelCase** - convert field names to CamelCase

### Flexible Routing

The operator supports conditional routing of messages to different sinks based on JSONPath expressions, enabling complex data processing scenarios.

### Simple Management

Declarative configuration through Kubernetes CRD allows easy management of data flows, versioning configurations, and integration with CI/CD systems.

### Secure Configuration

Support for configuring connectors from Kubernetes Secrets through `SecretRef` allows secure storage of credentials, tokens, and connection strings without explicitly specifying them in the DataFlow specification.

## Quick Start

### Installing the Operator

```bash
# Install operator via Helm from OCI registry
helm install dataflow-operator oci://ghcr.io/dataflow-operator/helm-charts/dataflow-operator

# Verify installation
kubectl get pods -l app.kubernetes.io/name=dataflow-operator

# Verify CRD
kubectl get crd dataflows.dataflow.dataflow.io
```

### Creating Your First Data Flow

Create a simple data flow from Kafka to PostgreSQL:

```bash
kubectl apply -f config/samples/kafka-to-postgres.yaml
```

Check status:

```bash
kubectl get dataflow kafka-to-postgres
kubectl describe dataflow kafka-to-postgres
```

### Local Development

For local development and testing:

```bash
# Start dependencies (Kafka, PostgreSQL)
docker-compose up -d

# Run operator locally
make run
```

## Architecture

The operator consists of the following components:

### CRD (Custom Resource Definitions)

Defines the schema for the `DataFlow` resource, which describes the data flow configuration, including source, sink, and list of transformations.

### Controller

Kubernetes controller that monitors changes to `DataFlow` resources and manages their lifecycle. The controller creates and manages processors for each active data flow.

### Connectors

Modular connector system for various data sources and sinks. Each connector implements a standard interface for reading or writing data.

### Transformers

Message transformation modules that are applied sequentially to each message in the order specified in the configuration.

### Processor

Message processing orchestrator that coordinates the work of source, transformations, and sink. Handles errors, maintains statistics, and manages the data flow lifecycle.

## Monitoring and Status

Each `DataFlow` resource has a status that includes:

- **Phase** - current phase of the data flow (Running, Error, etc.)
- **Message** - additional status information
- **LastProcessedTime** - time of the last processed message
- **ProcessedCount** - number of processed messages
- **ErrorCount** - number of errors

The operator also exports Prometheus metrics for detailed monitoring:
- Number of messages received/sent per manifest
- Errors in connectors and transformers
- Message processing time and transformer execution time
- Connector connection status

See [Metrics](metrics.md) for more details.

## Documentation

- [Getting Started](getting-started.md) — installation and first data flow
- [Connectors](connectors.md) — Kafka, PostgreSQL, ClickHouse, Trino (sources and sinks)
- [Transformations](transformations.md) — message transformations
- [Examples](examples.md) — practical examples
- [Errors](errors.md) — error handling and error sink
- [Metrics](metrics.md) — Prometheus metrics
- [Development](development.md) — developer guide

## License

Apache License 2.0

