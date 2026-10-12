# Development

Guide for developers who want to contribute to DataFlow Operator or set up a local development environment.

## Prerequisites

- Go 1.25 or higher
- Docker and Docker Compose
- kubectl configured to work with the cluster
- Helm 3.0+ (for testing installation)
- Task (optional, for using Taskfile)

## Environment Setup

### Cloning the Repository

```bash
git clone <repository-url>
cd dataflow
```

### Installing Dependencies

```bash
go mod download
go mod tidy
```

### Installing Development Tools

```bash
# Install controller-gen
task controller-gen

# Install envtest
task envtest
```

## Local Development

### Starting Dependencies

Start all necessary services via docker-compose:

```bash
docker-compose up -d
```

This will start:
- Kafka (port 9092) with Kafka UI (port 8080)
- PostgreSQL (port 5432) with pgAdmin (port 5050)

### Running Operator Locally

```bash
# Generate code and manifests
task generate
task manifests

# Install CRD in cluster (if using kind/minikube)
task install

# Run operator
task run
```

Or use the script:

```bash
./scripts/run-local.sh
```

### Setting up kind cluster

For full testing, use kind:

```bash
# Create kind cluster
./scripts/setup-kind.sh

# Install CRD
task install

# Run operator locally
task run
```

## Project Structure

```
dataflow/
├── api/v1/                    # CRD definitions
│   ├── dataflow_types.go      # DataFlow types; connector config is its own struct
│   ├── provider_registry.go   # Source registration: validator, checkpoint, Exhausts
│   ├── dataflow_validation.go # Spec validation, including the transformation switch
│   └── groupversion_info.go   # API version
├── pkg/
│   ├── providers/             # Source/sink type registry (checkpoint, Exhausts, validators)
│   ├── transformtypes/        # Canonical transformation type keys
│   └── run/                   # dataflow-cli run; SourceExhausts reads the providers registry
├── internal/
│   ├── connectors/            # Connectors for sources/sinks
│   │   ├── interface.go       # Connector interfaces
│   │   ├── factory.go         # createSourceConnector / registerSourceConnector
│   │   ├── provider_registrations.go  # init: factories, checked against the providers catalog
│   │   ├── kafka.go           # Kafka connector
│   │   ├── postgresql.go      # PostgreSQL connector
│   ├── transformers/          # Message transformations
│   │   ├── interface.go       # Transformation interface
│   │   ├── factory.go         # transformerRegistry + createTransformer
│   │   ├── timestamp.go       # Timestamp transformation
│   │   ├── flatten.go         # Flatten transformation
│   │   ├── filter.go          # Filter transformation
│   │   ├── mask.go            # Mask transformation
│   │   ├── router.go          # Router transformation
│   │   ├── select.go          # Select transformation
│   │   └── remove.go          # Remove transformation
│   ├── processor/             # Message processor
│   │   └── processor.go       # Processing orchestration
│   ├── controller/            # Kubernetes controller
│   │   └── dataflow_controller.go
│   └── types/                 # Internal types
│       └── message.go         # Message type
├── config/                    # Kubernetes configuration
│   ├── crd/                   # CRD manifests
│   ├── rbac/                  # RBAC manifests
│   └── samples/               # DataFlow resource examples
├── helm/                      # Helm Chart
│   └── dataflow-operator/
├── docs/                      # MkDocs documentation
├── test/                      # Tests
│   └── fixtures/              # Test data
├── scripts/                   # Helper scripts
├── main.go                    # Entry point
├── Taskfile.yml               # Build commands
└── go.mod                     # Go dependencies
```

## Code Generation

### Generate CRD and RBAC

```bash
task manifests
```

This command generates:
- CRD manifests in `dataflow/config/crd/bases/`

### Generate DeepCopy Methods

```bash
task generate
```

Generates `DeepCopy` methods for all types in `api/v1/`.

### Generate JSON Schemas

```bash
task schemas
```

Writes machine-readable schemas to monorepo `schemas/` (CRD envelope + per-connector/transform config schemas + `catalog.json`). Keep them committed; CI `provider-types-drift` regenerates and fails on diff. Drift check:

```bash
python3 scripts/check_provider_types_drift.py
```

### Updating controller-gen

If you encounter issues with code generation:

```bash
# Update controller-gen
go install sigs.k8s.io/controller-tools/cmd/controller-gen@latest

# Then
task generate
task manifests
```

## Logging

### Structured fields

Operator and processor logs use consistent fields for correlation:

| Field | Where | Purpose |
|-------|-------|---------|
| `dataflow_name` | Operator, processor, connectors | DataFlow resource name |
| `dataflow_namespace` | Operator, processor, connectors | DataFlow namespace |
| `reconcile_id` | Operator | Short id for one reconcile cycle (8 hex chars) |
| `connector_type` | Processor, connectors | Connector type (e.g. `kafka-source`, `trino-sink`) |
| `message_id` | Processor, connectors | Message id from metadata (if present) or Kafka partition/offset |

Use these fields to filter logs (e.g. by `dataflow_name` and `reconcile_id`) and correlate errors with a specific DataFlow and message.

### Log level (LOG_LEVEL)

Operator and processor read the **LOG_LEVEL** environment variable. Allowed values (case-insensitive): `debug`, `info`, `warn`, `error`.

- **Production**: set `LOG_LEVEL=info` (or leave default; Helm uses `info`) to reduce log volume.
- **Debugging**: set `LOG_LEVEL=debug` for more verbose output.

In Helm, the operator level is set via the **logLevel** value (default `"info"`), which is passed as env `LOG_LEVEL` in the operator pod.

#### PROCESSOR_LOG_LEVEL

The operator reads the **PROCESSOR_LOG_LEVEL** environment variable and passes it to every processor pod as **LOG_LEVEL**. Processor pods are the workloads created for each DataFlow; they run the actual data pipelines.

| Aspect | Description |
|--------|-------------|
| **Default** | `info` (if unset, processor pods get `LOG_LEVEL=info`) |
| **Allowed values** | Same as LOG_LEVEL: `debug`, `info`, `warn`, `error` (case-insensitive) |
| **Where to set** | In the **operator** Deployment (not in the DataFlow resource). The operator injects this value into each processor pod's `LOG_LEVEL` env. When using Helm, set the **processorLogLevel** value (see below). |

**With Helm:** use the **processorLogLevel** value (default `"info"`). Example for verbose processor logs:

```bash
helm upgrade dataflow-operator oci://ghcr.io/dataflow-operator/helm-charts/dataflow-operator \
  --set processorLogLevel=debug \
  --reuse-values
```

Or in `values.yaml`:

```yaml
processorLogLevel: "debug"   # processor pods get LOG_LEVEL=debug
```

**Without Helm:** set the env in the operator Deployment, e.g.:

```bash
kubectl set env deployment/dataflow-operator PROCESSOR_LOG_LEVEL=debug -n <operator-namespace>
```

Then restart or recreate the operator so it recreates processor pods with the new level.

## Configuring the Validating Webhook

The Validating Webhook checks the DataFlow spec on create and update and rejects invalid objects before they are stored in the cluster. This gives immediate feedback (error on `kubectl apply` or in the GUI) and avoids creating unnecessary resources and pods with broken configuration. For the role of the webhook in the architecture, see [Admission Webhook (Validating)](architecture.md#admission-webhook-validating).

### Enabling via Helm

The webhook is **optional** and disabled by default. To enable it:

1. **Enable the webhook and set the CA for TLS** in `values.yaml` or via `--set`:
   - `webhook.enabled: true`
   - `webhook.caBundle` — base64-encoded string (PEM CA that signed the operator’s certificate on port 9443). Without it, no ValidatingWebhookConfiguration is created, because the API server requires caBundle to call the webhook over HTTPS.

2. **Configure TLS for the operator:** the API server connects to the operator over HTTPS. Set:
   - `webhook.certDir` — path inside the container where certificates are mounted (e.g. `/tmp/k8s-webhook-server/serving-certs`).
   - `webhook.secretName` — name of the Secret containing `tls.crt` and `tls.key` (and optionally `ca.crt`). This secret is mounted into the operator pod at `webhook.certDir`; the `WEBHOOK_CERT_DIR` env in the pod is set to this path.

You can create the certificate secret manually or with **cert-manager** (a Certificate for the operator service). The CA (or the CA that issued the certificate) must be placed in `webhook.caBundle` as base64.

Example snippet in `values.yaml` when using cert-manager and a known caBundle:

```yaml
webhook:
  enabled: true
  caBundle: "LS0tLS1CRUdJTi..."   # base64 PEM CA
  certDir: /tmp/k8s-webhook-server/serving-certs
  secretName: dataflow-operator-webhook-cert
```

After installing or upgrading the chart with these values, a ValidatingWebhookConfiguration is created; on the next **DataFlow** or **DataFlowCron** create/update, the API server will call the operator for validation.

### What the webhook validates

**DataFlow** (`dataflows`):

- Required fields: `spec.source`, `spec.sink`, source/sink types allowed by the provider registry (`kafka`, `postgresql`, `postgresql-cdc`, `trino`, `clickhouse`, `nessie`, `iceberg` — see `dataflow/api/v1/provider_registry.go` / `pkg/providers`), and `source.config` / `sink.config` for that `type`.
- For each source/sink type, required fields or SecretRef (e.g. for Kafka: brokers or brokersSecretRef, topic or topicSecretRef).
- Transformations: allowed types and config present for each type; for router, nested sinks are validated.
- Optionally: `spec.errors` (if set, validated as SinkSpec), SecretRef (name and key), non-negative resources.

**DataFlowCron** (`dataflowcrons`): the embedded DataFlow-shaped fields (`source`, `sink`, `transformations`, …) are validated as above; additionally `schedule` must be non-empty with 5–6 cron fields, each trigger must set `image`, and `concurrencyPolicy` (if set) must be `Allow`, `Forbid`, or `Replace`.

On validation failure, the API returns a response with field paths and messages (aggregated from the validator’s field errors).

## Testing

### Unit Tests

```bash
# Run all unit tests
task test-unit

# Run tests with coverage
task test

# Run tests for specific package
go test ./internal/connectors/... -v

# Run tests with coverage for specific package
go test ./internal/transformers/... -coverprofile=coverage.out
go tool cover -html=coverage.out
```

### Integration Tests

```bash
# Set up kind cluster
./scripts/setup-kind.sh

# Run integration tests
task test-integration
```

### Running tests manually

```bash
# Unit tests without envtest
go test ./... -v

# Tests with envtest (requires kubebuilder; run `task envtest` first to install)
KUBEBUILDER_ASSETS="$(./bin/setup-envtest use 1.28.0 -p path)" go test ./... -coverprofile cover.out
```

## Building

### Local Build

```bash
# Build binary
task build

# Binary will be in bin/manager
./bin/manager
```

### Docker Image Build

```bash
# Build image
task docker-build IMG=your-registry/dataflow-operator:v1.0.0

# Push image
task docker-push IMG=your-registry/dataflow-operator:v1.0.0
```

Or manually. If the repository is a monorepo (with `dataflow` and `dataflow-web` folders), build from the **repository root**:

```bash
docker build -f dataflow/Dockerfile -t your-registry/dataflow-operator:v1.0.0 .
docker push your-registry/dataflow-operator:v1.0.0
```

If you are in the `dataflow` directory and the build context is only that (without `dataflow-web`), use the previous variant: `docker build -t ... .`

## Adding a New Connector

A new type ships only when the operator and CLI are rebuilt. There is no out-of-process plugin loader. Manifests use `type` plus `config`; `SourceSpec` and `SinkSpec` store that config as `*runtime.RawExtension`. The API has no fields such as `source.kafka`.

> **Detailed guide:** [Connector Development with baseConnector](connector-development.md) — `baseConnector`, the two `init` functions, and schema catalog.

### 1. Config struct

Add the spec in `api/v1/dataflow_types.go`. Leave it off `SourceSpec` and `SinkSpec`: the factory and the webhook unmarshal `config` using `type`.

```go
type MyDBSourceSpec struct {
    ConnectionString string `json:"connectionString"`
    Table            string `json:"table"`
}
```

```yaml
source:
  type: mydb
  config:
    connectionString: "mydb://localhost:3306/db"
    table: my_table
```

### 2. Implementation

Create `internal/connectors/mydb.go`. Embed `baseConnector` or `baseConnectorRWMutex` and implement `SourceConnector` / `SinkConnector`. Connect/Close examples are in the [connector guide](connector-development.md).

### 3. One metadata registration, plus a factory

The validator, `SupportsCheckpoint`, and `Exhausts` are set by a single `providers.RegisterSource` call in `api/v1/provider_registry.go`. Registering the same type again panics; flags are not merged. A source without a validator is not registered.

`api/v1` does not import connector implementations, so the factory lives next to them in `internal/connectors/provider_registrations.go`. `registerSourceConnector` only stores the factory. At the end of `init`, factory keys are checked against `providers.ListSourceTypes()` and `ListSinkTypes()`: an extra factory or a catalog type without a factory stops the process. Sinks use `providers.RegisterSink` and `registerSinkConnector` the same way.

```go
providers.RegisterSource(providers.SourceDefinition{
    Type:               "mydb",
    SupportsCheckpoint: true,
    Exhausts:           true,
    ValidateConfig: func(raw []byte, path *field.Path) field.ErrorList {
        return validateSourceConfig(raw, "mydb", path, validateMyDBSource)
    },
})
```

```go
registerSourceConnector("mydb", createSourceConnectorWithOptions[v1.MyDBSourceSpec](
    "mydb source",
    func(cfg *v1.MyDBSourceSpec, opts *SourceConnectorOptions) SourceConnector {
        return NewMyDBSourceConnectorWithOptions(cfg, opts)
    },
))

registerSinkConnector("mydb", createSinkConnector[v1.MyDBSinkSpec](
    "mydb sink",
    func(cfg *v1.MyDBSinkSpec) SinkConnector { return NewMyDBSinkConnector(cfg) },
))
```

`Exhausts` means the read finishes. That is separate from checkpoint: `postgresql-cdc` checkpoints and sets `Exhausts` to false. `kafka` sets both flags off.

Use `createSourceConnector` when the source does not take `SourceConnectorOptions`. `CreateSourceConnector` / `CreateSinkConnector` in `factory.go` look up the map and unmarshal `config`. The factory has no `switch source.Type`.

`dataflow-cli run` calls `pkg/run`, which imports `internal/processor` → `internal/connectors`, so the CLI has no type list of its own. Validators load through the `api/v1` import. The processor turns checkpoint on through `providers.SourceSupportsCheckpoint`.

### 4. One-shot runs (`run --once`)

`pkg/run.SourceExhausts` reads the `Exhausts` field on that same record. There is no separate switch in `exhaust.go`. `TestSourceExhausts` walks `providers.ListSourceTypes()`, so a new source fails the test until it is classified there.

### 5. Schemas and UI lists

Add a sample struct to `sourceEntries` and, for a sink, `sinkEntries` in `dataflow/hack/genschemas/main.go`. From the `dataflow` directory:

```bash
task generate
task manifests
task schemas
```

`task schemas` checks those slices against `providers.ListSourceTypes` / `ListSinkTypes` and writes `schemas/catalog.json`. Then update the overview tables in `docs/docs/{ru,en}/connectors.md`, `docs/provider-types-inventory.md`, the lists in `dataflow-mcp/src/tools/reference.rs`, and `CONNECTOR_TYPES` in the web app (`dataflow-web/web/src/composables/useFlowManifest.js`). Check with:

```bash
python3 scripts/check_provider_types_drift.py
```

### 6. Tests

Put connector tests in `internal/connectors/mydb_test.go`: idempotent `Close`, `Connect` after `Close` returns an error, and `config` unmarshalling.

## Adding a New Transformation

Manifests use `type` and `config` (`*runtime.RawExtension` on `TransformationSpec`). There is no `transformation.flatten` field. The `when` wrapper is applied in `CreateTransformer` and is not a type key.

The key lives in three places: a constant in `pkg/transformtypes`, a `transformerRegistry` entry, and a `case` in `validateTransformations`. The first two share the constant; the switch does not. A missing `case` lets the webhook accept the type without checking config fields.

### 1. Config struct

In `api/v1/dataflow_types.go`:

```go
type MyTransform struct {
    Field string `json:"field"`
}
```

### 2. Type key

In `pkg/transformtypes/transformtypes.go` add a constant and append it to `keys`:

```go
const MyTransform = "myTransform"

var keys = []string{
    // ...
    MyTransform,
}
```

`IsRegistered` and `All()` read that slice. The webhook rejects a type that is missing from it.

### 3. Implementation and factory

Add `internal/transformers/mytransform.go` with `Transform`. Register it in `transformerRegistry` in `internal/transformers/factory.go`:

```go
transformtypes.MyTransform: {create: createTransformer[v1.MyTransform](
    transformtypes.MyTransform,
    func(cfg *v1.MyTransform) Transformer { return NewMyTransformer(cfg) },
)},
```

`createTransformer` unmarshals `config`. `CreateTransformer` looks up the map and, when `when` is set, wraps the result.

### 4. Validator

Add a `case` on the constant in `validateTransformations` (`api/v1/dataflow_validation.go`): empty `config` is `field.Required`, bad JSON is `field.Invalid`, then check spec fields.

### 5. Schemas and lists

Add a sample struct to `transformEntries` in `dataflow/hack/genschemas/main.go` (use the `transformtypes` constant, same as the existing rows). Then run `task schemas`. Update the tables in `docs/docs/{ru,en}/transformations.md`, the Transformers section of `docs/provider-types-inventory.md`, `reference.rs`, and `TRANSFORMATION_TYPES` in the web app. `task schemas` checks names against `transformtypes.All()`; `scripts/check_provider_types_drift.py` checks the catalog against docs, MCP, inventory, and web.

### 6. Tests

Add a transformation test and a webhook test for required `config` fields.


### Logging

Use structured logging:

```go
import "github.com/go-logr/logr"

logger.Info("Processing message", "messageId", msg.ID)
logger.Error(err, "Failed to process", "messageId", msg.ID)
logger.V(1).Info("Debug information", "messageId", msg.ID)
```

### Debugging Controller

```bash
# Run with detailed logging
go run ./main.go --zap-log-level=debug
```

### Debugging connectors

Add logging to connector methods:

```go
func (k *KafkaSourceConnector) Read(ctx context.Context) (<-chan *types.Message, error) {
    logger.Info("Starting to read from Kafka", "topic", k.config.Topic)
    // ...
}
```

## Code Formatting and Linting

### Format Code

```bash
task fmt
```

Or manually:

```bash
go fmt ./...
```

### Check Code

```bash
task vet
```

Or manually:

```bash
go vet ./...
```

### Linting (optional)

Install golangci-lint:

```bash
go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest
```

Run:

```bash
golangci-lint run
```

## CI/CD

### GitHub Actions

Example workflow for CI:

```yaml
name: CI

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-go@v4
        with:
          go-version: '1.25'
      - run: go mod download
      - run: task test-unit
      - run: task vet
      - run: task fmt
```

## Building the documentation

The documentation is built with [MkDocs](https://www.mkdocs.org/) and the Material theme. Diagrams use [Mermaid](https://mermaid.js.org/) via the `mkdocs-mermaid2-plugin`.

**Install dependencies** (from repo root):

```bash
pip install -r docs/requirements.txt
```

Or install manually:

```bash
pip install "mkdocs-material[imaging]" pymdown-extensions mkdocs-mermaid2-plugin
```

**Build and serve** (from repo root):

```bash
cd docs && mkdocs build
# or serve locally:
cd docs && mkdocs serve
```

Then open `http://127.0.0.1:8000` when using `mkdocs serve`.

## Contributing

### Development Process

1. Create an issue to discuss changes
2. Create a feature branch: `git checkout -b feature/new-feature`
3. Make changes and add tests
4. Ensure all tests pass: `task test`
5. Format code: `task fmt`
6. Create Pull Request

### Code Standards

- Follow Go code review comments
- Add comments for public functions
- Write tests for new functionality
- Update documentation as needed

### Commits

Use clear commit messages:

```
feat: add new connector for Redis
fix: handle connection errors in Kafka connector
docs: update getting started guide
test: add tests for filter transformation
```

## Useful commands

```bash
# View all available commands
task --list

# Clean generated files
task clean

# Update dependencies
go mod tidy

# List dependencies
go list -m all

# Check for outdated dependencies
go list -u -m all
```

## Cursor Agent Skills (maintainer)

Client-facing skills are developed in the monorepo `skills/` directory and published to **[github.com/dataflow-operator/skills](https://github.com/dataflow-operator/skills)**. Maintainer extensions: `.cursor/skills/dataflow-*`. See [Agent Skills](agent-skills.md).

## Resources

- [Agent Skills](agent-skills.md) — publish to [dataflow-operator/skills](https://github.com/dataflow-operator/skills)
- [Kubebuilder Book](https://book.kubebuilder.io/) — guide for building Kubernetes operators
- [controller-runtime](https://github.com/kubernetes-sigs/controller-runtime) — controller library
- [Go Documentation](https://golang.org/doc/) — Go documentation

## Getting help

- Create an issue in the repository
- Check existing issues and PRs
- Review examples in `dataflow/config/samples/`

