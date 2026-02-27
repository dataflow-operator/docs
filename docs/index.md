# DataFlow Operator

Kubernetes operator for streaming data between different data sources with support for message transformations.

## Overview

DataFlow Operator allows you to declaratively define data flows between different sources and sinks through Kubernetes Custom Resource Definitions (CRD). The operator automatically manages the lifecycle of data flows, processes messages, and applies necessary transformations.

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

## Documentation

Documentation is available in two languages:

- **[English Documentation](en/index.md)** - Complete English documentation
- **[Русская Документация](ru/index.md)** - Полная русская документация

## Key Features

- **Connectors**: Kafka, PostgreSQL, ClickHouse, Trino, Nessie (sources and sinks)
- **Transformations**: Timestamp, Flatten, Filter, Mask, Router, Select, Remove, SnakeCase, CamelCase
- **Security**: Kubernetes Secrets via `SecretRef` for credentials

## License

Apache License 2.0
