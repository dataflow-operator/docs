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
│   ├── dataflow_types.go      # DataFlow resource types
│   └── groupversion_info.go    # API version
├── internal/
│   ├── connectors/            # Connectors for sources/sinks
│   │   ├── interface.go       # Connector interfaces
│   │   ├── factory.go         # Connector factory
│   │   ├── kafka.go           # Kafka connector
│   │   ├── postgresql.go      # PostgreSQL connector
│   ├── transformers/          # Message transformations
│   │   ├── interface.go       # Transformation interface
│   │   ├── factory.go         # Transformation factory
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

After installing or upgrading the chart with these values, a ValidatingWebhookConfiguration is created; on the next DataFlow create/update, the API server will call the operator for validation.

### What the webhook validates

- Required fields: `spec.source`, `spec.sink`, source/sink types from the allowed list (`kafka`, `postgresql`, `trino`), and the matching config block (e.g. `source.config` when `source.type: kafka`).
- For each source/sink type, required fields or SecretRef (e.g. for Kafka: brokers or brokersSecretRef, topic or topicSecretRef).
- Transformations: allowed types and config present for each type; for router, nested sinks are validated.
- Optionally: `spec.errors` (if set, validated as SinkSpec), SecretRef (name and key), non-negative resources.

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

> **Detailed guide:** see [Connector Development with baseConnector](connector-development.md) for a step-by-step guide with examples using `baseConnector` and `baseConnectorRWMutex`.

### 1. Define types in API

Add the spec to `api/v1/dataflow_types.go`:

```go
// NewConnectorSourceSpec defines new connector source configuration
type NewConnectorSourceSpec struct {
    // Configuration fields
    Endpoint string `json:"endpoint"`
    // ...
}

// Add to SourceSpec
type SourceSpec struct {
    // ...
    NewConnector *NewConnectorSourceSpec `json:"newConnector,omitempty"`
}
```

### 2. Implement connector

Create file `internal/connectors/newconnector.go`. **Recommended** to embed `baseConnector` for Connect/Close synchronization:

```go
package connectors

import (
    "context"
    "fmt"
    v1 "github.com/dataflow-operator/dataflow/api/v1"
    "github.com/dataflow-operator/dataflow/internal/types"
    "github.com/go-logr/logr"
)

type NewConnectorSourceConnector struct {
    baseConnector
    config *v1.NewConnectorSourceSpec
    conn   *Connection
    logger logr.Logger
}

func NewNewConnectorSourceConnector(config *v1.NewConnectorSourceSpec) *NewConnectorSourceConnector {
    return &NewConnectorSourceConnector{config: config, logger: logr.Discard()}
}

func (n *NewConnectorSourceConnector) Connect(ctx context.Context) error {
    if !n.guardConnect() {
        return fmt.Errorf("connector is closed")
    }
    defer n.Unlock()
    // ... connection logic
    return nil
}

func (n *NewConnectorSourceConnector) Read(ctx context.Context) (<-chan *types.Message, error) {
    // Implement read logic
    return nil, nil
}

func (n *NewConnectorSourceConnector) Close() error {
    if n.guardClose() {
        return nil
    }
    defer n.Unlock()
    // ... close logic
    return nil
}
```

### 3. Register in factory

Add to `internal/connectors/factory.go`:

```go
func CreateSourceConnector(source *v1.SourceSpec) (SourceConnector, error) {
    switch source.Type {
    // ...
    case "newconnector":
        if source.NewConnector == nil {
            return nil, fmt.Errorf("newconnector source configuration is required")
        }
        return NewNewConnectorSourceConnector(source.NewConnector), nil
    // ...
    }
}
```

### 4. Generate code

```bash
task generate
task manifests
```

### 5. Testing

Create tests in `internal/connectors/newconnector_test.go`:

```go
func TestNewConnectorSourceConnector(t *testing.T) {
    // Test implementation
}
```

## Adding a New Transformation

### 1. Define types in API

Add to `api/v1/dataflow_types.go`:

```go
// NewTransformation defines new transformation configuration
type NewTransformation struct {
    Field string `json:"field"`
    // ...
}

// Add to TransformationSpec
type TransformationSpec struct {
    // ...
    NewTransformation *NewTransformation `json:"newTransformation,omitempty"`
}
```

### 2. Implement transformation

Create file `internal/transformers/newtransformation.go`:

```go
package transformers

import (
    "context"
    v1 "github.com/dataflow-operator/dataflow/api/v1"
    "github.com/dataflow-operator/dataflow/internal/types"
)

type NewTransformer struct {
    config *v1.NewTransformation
}

func NewNewTransformer(config *v1.NewTransformation) *NewTransformer {
    return &NewTransformer{config: config}
}

func (n *NewTransformer) Transform(ctx context.Context, message *types.Message) ([]*types.Message, error) {
    // Implement transformation logic
    return []*types.Message{message}, nil
}
```

### 3. Register in factory

Add to `internal/transformers/factory.go`:

```go
func CreateTransformer(transformation *v1.TransformationSpec) (Transformer, error) {
    switch transformation.Type {
    // ...
    case "newtransformation":
        if transformation.NewTransformation == nil {
            return nil, fmt.Errorf("newtransformation configuration is required")
        }
        return NewNewTransformer(transformation.NewTransformation), nil
    // ...
    }
}
```

### 4. Generate and test

```bash
task generate
task test
```

## Debugging

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

## Resources

- [Kubebuilder Book](https://book.kubebuilder.io/) — guide for building Kubernetes operators
- [controller-runtime](https://github.com/kubernetes-sigs/controller-runtime) — controller library
- [Go Documentation](https://golang.org/doc/) — Go documentation

## Getting help

- Create an issue in the repository
- Check existing issues and PRs
- Review examples in `dataflow/config/samples/`

