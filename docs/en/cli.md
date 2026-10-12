# CLI (`dataflow-cli`)

Command-line client for DataFlow: talk to the [Web GUI](gui.md) API, or run a DataFlow manifest locally without Kubernetes.

**When to read this:** scripting against the web API, local pipeline smoke tests, or day-2 ops without `kubectl` YAML edits.

**See also:** [Web GUI](gui.md) · [Getting Started](getting-started.md) · [DataFlow Spec](dataflow/spec.md)

## Install

### Homebrew

```bash
brew install dataflow-operator/tap/dataflow-cli
```

The formula is published to the `dataflow-operator/tap` tap with each `v*` release (macOS and Linux, amd64 and arm64).

### Release binary

A `v*` tag publishes binaries and `SHA256SUMS` to [GitHub Releases](https://github.com/dataflow-operator/dataflow-cli/releases).

| OS | Architecture | Asset |
|----|--------------|-------|
| Linux | amd64 | `dataflow-cli-linux-amd64` |
| Linux | arm64 | `dataflow-cli-linux-arm64` |
| Linux | armv7 | `dataflow-cli-linux-arm-v7` |
| macOS | amd64 | `dataflow-cli-darwin-amd64` |
| macOS | arm64 | `dataflow-cli-darwin-arm64` |
| Windows | amd64 | `dataflow-cli-windows-amd64.exe` |
| Windows | arm64 | `dataflow-cli-windows-arm64.exe` |

```bash
curl -fsSL -o dataflow-cli \
  "https://github.com/dataflow-operator/dataflow-cli/releases/download/vX.Y.Z/dataflow-cli-linux-amd64"
chmod +x dataflow-cli
```

Replace `vX.Y.Z` and the asset name for your OS.

### Docker

Images: `ghcr.io/dataflow-operator/dataflow-cli` (`linux/amd64`, `linux/arm64`). `:latest` and the version tag come from a `v*` release. `:main` tracks the `main` branch.

```bash
docker pull ghcr.io/dataflow-operator/dataflow-cli:latest

docker run --rm ghcr.io/dataflow-operator/dataflow-cli:latest --help

# On Linux, --network host reaches a source or sink on the host.
# On Docker Desktop, use host.docker.internal in the manifest instead of localhost.
docker run --rm --network host \
  -v "$PWD:/work" -w /work \
  ghcr.io/dataflow-operator/dataflow-cli:latest \
  run manifest.yaml --once

# SecretRef is read from the mounted kubeconfig.
docker run --rm --network host \
  -v "$HOME/.kube:/root/.kube:ro" \
  -v "$PWD:/work" -w /work \
  ghcr.io/dataflow-operator/dataflow-cli:latest \
  run manifest.yaml --once
```

Build from the `dataflow-cli` directory:

```bash
docker build -t dataflow-cli .
```

### From source

Go 1.25+:

```bash
cd dataflow-cli
go build -o dataflow-cli .
```

In the monorepo, `go.work` builds the CLI against the local `dataflow` checkout. `go.mod` requires `github.com/dataflow-operator/dataflow v1.12.1-0.20261012061201-dec4eee83b3d` (branch `feat/pkg-run-oneshot`) and does not use a `replace` directive. Tag `v1.12.0` does not contain the one-shot `pkg/run` API. Pushes to `main` in the `dataflow-operator/dataflow-cli` repository run semantic-release, which tags `vX.Y.Z` and updates that requirement to `@latest` only when the module still builds the CLI. The same workflow stamps the version into the binary (`dataflow-cli --version`).

Source: [`dataflow-operator/dataflow-cli`](https://github.com/dataflow-operator/dataflow-cli). CI: [`.github/workflows/build.yml`](https://github.com/dataflow-operator/dataflow-cli/blob/main/.github/workflows/build.yml).

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

## One-shot migration

`--once` reads a polling source until it is exhausted, flushes the sink, writes a local checkpoint, and exits. Use it for a snapshot copy (for example PostgreSQL to PostgreSQL) without a cluster. `kind: DataFlowCron` is accepted; `schedule` and `triggers` are ignored.

Supported sources: `postgresql`, `clickhouse`, `trino`, `iceberg`, `nessie`. `kafka` and `postgresql-cdc` stay open, so `--once` fails before connecting.

```bash
dataflow-cli run manifest.yaml --once
dataflow-cli run manifest.yaml --once --checkpoint-file .dataflow/pg-migration.json --reset
dataflow-cli run manifest.yaml --once --timeout 2h
```

| Flag | Description |
|------|-------------|
| `--once` | Exit when the source is exhausted |
| `--checkpoint-file` | Checkpoint JSON. Default for `--once`: `.dataflow/<metadata.name>.json` |
| `--reset` | Clear that source's checkpoint before start |
| `--timeout` | Maximum run time (`2h`, `30m`). `0` means no limit |
| `--log-level` | `debug`, `info`, `warn`, `error` |

Ctrl+C or a timeout flushes the checkpoint and exits with a non-zero status. The next run resumes from the file. On success the CLI prints source, sink, processed, errors, and the checkpoint path.

`checkpointPersistence: false` skips the file. `SecretRef` is resolved from the current kubeconfig (or in-cluster config) before the pipeline starts. A missing secret or key fails the run before connect.

The manifest stays a normal DataFlow. On the source set `changeTrackingColumn`, `orderByColumn`, and `readBatchSize`. On the sink set `upsertMode` and `conflictKey`.

```yaml
apiVersion: dataflow.dataflow.io/v1
kind: DataFlow
metadata:
  name: pg-migration
spec:
  checkpointSyncOnAck: true
  source:
    type: postgresql
    config:
      connectionString: "postgres://user:pass@localhost:5432/src?sslmode=disable"
      table: public.source_table
      changeTrackingColumn: id
      orderByColumn: id
      readBatchSize: 10000
      pollInterval: 5
  sink:
    type: postgresql
    config:
      connectionString: "postgres://user:pass@localhost:5432/dst?sslmode=disable"
      table: public.target_table
      upsertMode: true
      conflictKey: id
      batchSize: 1000
```

```bash
dataflow-cli run pg-migration.yaml --once --timeout 2h
```

!!! warning "Credentials in local manifests"
    Local-dev samples may use plaintext connection strings. Prefer `SecretRef` for anything shared or production-like. See [Best Practices](best-practices.md).

## Example manifest

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
