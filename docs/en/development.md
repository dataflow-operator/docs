# Development

Guide for developers who want to contribute to DataFlow Operator or set up a local development environment.

> **Note**: This is a simplified English version. For complete documentation, see the [Russian version](../ru/development.md).

## Prerequisites

- Go 1.21 or higher
- Docker and Docker Compose
- kubectl configured to work with the cluster
- Helm 3.0+ (for testing installation)
- Make (optional, for using Makefile)

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
make controller-gen

# Install envtest
make envtest
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
make generate
make manifests

# Install CRD in cluster (if using kind/minikube)
make install

# Run operator
make run
```

Or use the script:

```bash
./scripts/run-local.sh
```

## Project Structure

```
dataflow/
├── api/v1/                    # CRD definitions
│   ├── dataflow_types.go      # DataFlow resource types
│   └── groupversion_info.go    # API version
├── internal/
│   ├── connectors/            # Connectors for sources/sinks
│   ├── transformers/          # Message transformations
│   ├── processor/             # Message processor
│   ├── controller/            # Kubernetes controller
│   └── types/                 # Internal types
├── config/                    # Kubernetes configuration
│   ├── crd/                   # CRD manifests
│   ├── rbac/                  # RBAC manifests
│   └── samples/              # DataFlow resource examples
├── helm/                      # Helm Chart
├── docs/                      # MkDocs documentation
├── test/                      # Tests
└── scripts/                   # Helper scripts
```

## Code Generation

### Generate CRD and RBAC

```bash
make manifests
```

This command generates:
- CRD manifests in `config/crd/bases/`
- RBAC manifests in `config/rbac/`

### Generate DeepCopy Methods

```bash
make generate
```

Generates `DeepCopy` methods for all types in `api/v1/`.

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

- Required fields: `spec.source`, `spec.sink`, source/sink types from the allowed list (`kafka`, `postgresql`, `trino`), and the matching config block (e.g. `source.kafka` when `source.type: kafka`).
- For each source/sink type, required fields or SecretRef (e.g. for Kafka: brokers or brokersSecretRef, topic or topicSecretRef).
- Transformations: allowed types and config present for each type; for router, nested sinks are validated.
- Optionally: `spec.errors` (if set, validated as SinkSpec), SecretRef (name and key), non-negative resources.

On validation failure, the API returns a response with field paths and messages (aggregated from the validator’s field errors).

## Testing

### Unit Tests

```bash
# Run all unit tests
make test-unit

# Run tests with coverage
make test

# Run tests for specific package
go test ./internal/connectors/... -v
```

### Integration Tests

```bash
# Set up kind cluster
./scripts/setup-kind.sh

# Run integration tests
make test-integration
```

## Building

### Local Build

```bash
# Build binary
make build

# Binary will be in bin/manager
./bin/manager
```

### Docker Image Build

```bash
# Build image
make docker-build IMG=your-registry/dataflow-operator:v1.0.0

# Push image
make docker-push IMG=your-registry/dataflow-operator:v1.0.0
```

## Adding a New Connector

1. Define types in API (`api/v1/dataflow_types.go`)
2. Implement connector (`internal/connectors/newconnector.go`)
3. Register in factory (`internal/connectors/factory.go`)
4. Generate code (`make generate && make manifests`)
5. Write tests

## Adding a New Transformation

1. Define types in API (`api/v1/dataflow_types.go`)
2. Implement transformation (`internal/transformers/newtransformation.go`)
3. Register in factory (`internal/transformers/factory.go`)
4. Generate and test (`make generate && make test`)

## Debugging

### Logging

Use structured logging:

```go
import "github.com/go-logr/logr"

logger.Info("Processing message", "messageId", msg.ID)
logger.Error(err, "Failed to process", "messageId", msg.ID)
```

### Debugging Controller

```bash
# Run with detailed logging
go run ./main.go --zap-log-level=debug
```

## Code Formatting and Linting

### Format Code

```bash
make fmt
```

### Check Code

```bash
make vet
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
4. Ensure all tests pass: `make test`
5. Format code: `make fmt`
6. Create Pull Request

### Code Standards

- Follow Go code review comments
- Add comments for public functions
- Write tests for new functionality
- Update documentation as needed

For complete development guide, see the [Russian version](../ru/development.md).

