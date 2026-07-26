# CLI (`dataflow-cli`)

Command-line client for DataFlow: talk to the [Web GUI](gui.md) API, or run a DataFlow manifest locally without Kubernetes.

**When to read this:** scripting against the web API, local pipeline smoke tests, or day-2 ops without `kubectl` YAML edits.

**See also:** [Web GUI](gui.md) · [Getting Started](getting-started.md) · [DataFlow Spec](dataflow/spec.md)

## Install

Build from source (Go 1.25+):

```bash
cd dataflow-cli
go build -o dataflow-cli .
```

In the monorepo, `go.mod` already has `replace github.com/dataflow-operator/dataflow => ../dataflow` for local development.

Release binaries (when published): [GitHub Releases](https://github.com/dataflow-operator/dataflow-operator/releases).

Source: [`dataflow-cli/`](https://github.com/dataflow-operator/dataflow-operator/tree/main/dataflow-cli).

## Global flags

| Flag / env | Description | Default |
|------------|-------------|---------|
| `--api-url` / `DATAFLOW_API_URL` | Base URL of the dataflow-web API | `http://localhost:8080/api` |
| `--namespace` | Kubernetes namespace for DataFlow resources | `default` |

Point `--api-url` at a port-forwarded or Ingress GUI, for example:

```bash
kubectl port-forward svc/dataflow-operator-gui 8080:8080 -n dataflow-system
export DATAFLOW_API_URL=http://localhost:8080/api
```

## Web API commands

Same actions as the browser UI:

```bash
# Namespaces
dataflow-cli namespaces

# DataFlows
dataflow-cli dataflows list
dataflow-cli dataflows list --namespace=my-ns
dataflow-cli dataflows get my-dataflow
dataflow-cli dataflows create --file=manifest.yaml
dataflow-cli dataflows update my-dataflow --file=manifest.yaml
dataflow-cli dataflows delete my-dataflow

# Logs (--follow / -f for live stream)
dataflow-cli logs my-dataflow --tail=200
dataflow-cli logs my-dataflow -f

# Status and metrics
dataflow-cli status my-dataflow
dataflow-cli metrics my-dataflow
```

All of these accept `--namespace` (default `default`).

## Local run (no Kubernetes)

Runs the pipeline in-process inside the CLI. The cluster and operator are not required; source and sink must be reachable (Kafka, PostgreSQL, etc.).

```bash
dataflow-cli run manifest.yaml
dataflow-cli run manifest.yaml --log-level=debug
```

Stop with Ctrl+C.

!!! warning "Credentials in local manifests"
    Local-dev samples may use plaintext connection strings. Prefer `SecretRef` for anything shared or production-like. See [Best Practices](best-practices.md).

### Example manifest

Standard DataFlow CR YAML:

```yaml
apiVersion: dataflow.dataflow.io/v1
kind: DataFlow
metadata:
  name: kafka-to-postgres
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
      connectionString: "postgres://user:pass@localhost:5432/db?sslmode=disable"
      table: output_table
```

Golden samples: [config/samples](https://github.com/dataflow-operator/dataflow/tree/main/config/samples) (prefer `*-secrets.yaml` patterns for cluster apply).

## When to use CLI vs GUI vs kubectl

| Goal | Prefer |
|------|--------|
| Browse / edit in the browser | [Web GUI](gui.md) |
| Scripts, CI, quick API calls | `dataflow-cli` |
| Full cluster control, CRD status, events | `kubectl` |
| AI-assisted YAML draft/validate | [MCP](mcp.md) + [Agent Skills](agent-skills.md) |
