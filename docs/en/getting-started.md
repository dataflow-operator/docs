# Getting Started

This guide will help you get started with DataFlow Operator. You'll learn how to install the operator, create your first data flow, and set up a local development environment.

## Prerequisites

### For Production Installation

- Kubernetes cluster (version 1.24+)
- Helm 3.0+
- kubectl configured to work with the cluster
- Access to data sources (Kafka, PostgreSQL)

### For Local Development

- Go 1.21+
- Docker and Docker Compose
- Task (optional, for using Taskfile commands)
- Access to ports: 8080, 5050, 15672, 8081, 5432, 9092, 5672

## Installation { #installation }

### CRD Management { #crd }

The DataFlow CRD (Custom Resource Definition) defines the `DataFlow` resource type in Kubernetes.

#### Automatic Installation (via Helm)

When installing via Helm (recommended), the CRD is installed and updated automatically. No separate `kubectl apply` step is needed — the chart manages the CRD lifecycle with `crds.install: true` (default).

#### Manual Installation

If you manage CRDs separately (e.g. with ArgoCD, FluxCD, or `crds.install: false` in Helm values), install the CRD manually:

```bash
kubectl apply -f https://raw.githubusercontent.com/dataflow-operator/dataflow/refs/heads/main/config/crd/bases/dataflow.dataflow.io_dataflows.yaml
```

Or from a local file:

```bash
kubectl apply -f dataflow/config/crd/bases/dataflow.dataflow.io_dataflows.yaml
```

#### CRD Helm Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `crds.install` | `true` | Install and update CRD on `helm install` / `helm upgrade` |
| `crds.keep` | `true` | Add `helm.sh/resource-policy: keep` annotation to prevent CRD deletion on `helm uninstall` |

**Upgrade behavior**: The CRD is updated on every `helm upgrade`, so schema changes are applied automatically.

**Uninstall behavior**: With `crds.keep: true` (default), the CRD remains in the cluster after `helm uninstall`. This protects against accidental deletion of all `DataFlow` resources. To disable CRD installation via Helm:

```yaml
crds:
  install: false
```

### Installation via Helm (Recommended)

#### Basic Installation

The simplest way to install the operator from OCI registry:

```bash
helm install dataflow-operator oci://ghcr.io/dataflow-operator/helm-charts/dataflow-operator
```

This command will install the operator with default settings in the `default` namespace.

#### Installation in a Specific Namespace

```bash
helm install dataflow-operator oci://ghcr.io/dataflow-operator/helm-charts/dataflow-operator \
  --namespace dataflow-system \
  --create-namespace
```

**Note**: For local development, you can also use the local chart:
```bash
helm install dataflow-operator ./helm-charts/dataflow-operator
```

#### Installation with Custom Settings

You can override default values via flags:

```bash
helm install dataflow-operator oci://ghcr.io/dataflow-operator/helm-charts/dataflow-operator \
  --set image.repository=your-registry/controller \
  --set image.tag=v1.0.0 \
  --set replicaCount=2 \
  --set resources.limits.memory=1Gi \
  --set resources.limits.cpu=500m \
  --set resources.requests.memory=256Mi \
  --set resources.requests.cpu=100m
```

#### Installation with Values File

For more complex configurations, create a `my-values.yaml` file:

```yaml
image:
  repository: your-registry/controller
  tag: v1.0.0

replicaCount: 2

resources:
  limits:
    cpu: 1000m
    memory: 1Gi
  requests:
    cpu: 500m
    memory: 512Mi

# Settings for working with Kubernetes API
serviceAccount:
  create: true
  annotations:
    eks.amazonaws.com/role-arn: arn:aws:iam::123456789012:role/dataflow-operator

# Security settings
securityContext:
  runAsNonRoot: true
  runAsUser: 1000
  fsGroup: 1000

# Optional: Sentry for error monitoring and tracing
# sentry:
#   enabled: true
#   dsn: "https://xxx@o0.ingest.sentry.io/123"
#   environment: production
#   tracesSampleRate: 0.1
```

Then install:

```bash
helm install dataflow-operator oci://ghcr.io/dataflow-operator/helm-charts/dataflow-operator -f my-values.yaml
```

#### Verification

After installation, check the status:

```bash
# Check pod status
kubectl get pods -l app.kubernetes.io/name=dataflow-operator

# Check CRD
kubectl get crd dataflows.dataflow.dataflow.io

# Check operator logs
kubectl logs -l app.kubernetes.io/name=dataflow-operator --tail=50

# Check deployment status
kubectl get deployment dataflow-operator
```

Expected output:

```
NAME                                  READY   STATUS    RESTARTS   AGE
dataflow-operator-7d8f9c4b5d-xxxxx   1/1     Running   0          1m
```

### Updating

To update the operator to a new version:

```bash
helm upgrade dataflow-operator oci://ghcr.io/dataflow-operator/helm-charts/dataflow-operator
```

With custom values:

```bash
helm upgrade dataflow-operator oci://ghcr.io/dataflow-operator/helm-charts/dataflow-operator -f my-values.yaml
```

To update to a specific version:

```bash
helm upgrade dataflow-operator oci://ghcr.io/dataflow-operator/helm-charts/dataflow-operator \
  --set image.tag=v1.1.0
```

### Uninstallation

To uninstall the operator:

```bash
helm uninstall dataflow-operator
```

**CRD behavior on uninstall**: With `crds.keep: true` (default), the CRD remains in the cluster after `helm uninstall`. Existing `DataFlow` resources are preserved but will stop being processed.

To completely remove the CRD and **all** DataFlow resources in the cluster:

```bash
# Delete all DataFlow resources first
kubectl delete dataflow --all --all-namespaces

# Then uninstall the operator
helm uninstall dataflow-operator

# Finally, remove the CRD (only if crds.keep was true)
kubectl delete crd dataflows.dataflow.dataflow.io
```

!!! warning
    Deleting the CRD removes **all** `DataFlow` resources across all namespaces in the cluster. Make sure this is intended.

## First DataFlow

### Simple Example: Kafka → PostgreSQL

Create a simple DataFlow resource to transfer data from Kafka to PostgreSQL:

```yaml
apiVersion: dataflow.dataflow.io/v1
kind: DataFlow
metadata:
  name: kafka-to-postgres
  namespace: default
spec:
  source:
    type: kafka
    config:
      brokers:
        - kafka-broker:9092
      topic: input-topic
      consumerGroup: dataflow-group
  sink:
    type: postgresql
    config:
      connectionString: "postgres://user:password@postgres-host:5432/dbname?sslmode=disable"
      table: output_table
      autoCreateTable: true
```

Apply the resource:

```bash
kubectl apply -f dataflow/config/samples/kafka-to-postgres.yaml
```

**Note**: Each DataFlow resource creates a separate pod (Deployment) for processing. You can configure resources, node selection, affinity, and tolerations. See [Examples](examples.md#configuring-pod-resources-and-placement) for details.

### Example with Kubernetes Secrets

For secure credential storage, use Kubernetes Secrets. See example:

```bash
kubectl apply -f dataflow/config/samples/kafka-to-postgres-secrets.yaml
```

This example demonstrates using `SecretRef` for connector configuration. For more details, see the [Using Kubernetes Secrets](connectors.md#using-kubernetes-secrets) section in the connectors documentation.

### Checking Status

Check the status of the created data flow:

```bash
# Get DataFlow information
kubectl get dataflow kafka-to-postgres

# Detailed information
kubectl describe dataflow kafka-to-postgres

# View status in YAML format
kubectl get dataflow kafka-to-postgres -o yaml
```

Expected status:

```yaml
status:
  phase: Running
  processedCount: 150
  errorCount: 0
  lastProcessedTime: "2024-01-15T10:30:00Z"
  message: "Processing messages successfully"
```

### Sending Test Message

To test the data flow, send a message to the Kafka topic:

```bash
# Using kafka-console-producer
kafka-console-producer --broker-list localhost:9092 --topic input-topic
# Enter JSON message and press Enter
{"id": 1, "name": "Test", "value": 100}
```

Or use the project script:

```bash
./scripts/send-test-message.sh
```

### Checking Data in PostgreSQL

Connect to PostgreSQL and check the data:

```bash
psql postgres://user:password@postgres-host:5432/dbname

# Check the table
SELECT * FROM output_table;
```

## Local Development

### Starting Dependencies

Use docker-compose to start all dependencies locally:

```bash
docker-compose up -d
```

This command will start:

- **Kafka** (port 9092) with Kafka UI (port 8080)
- **PostgreSQL** (port 5432) with pgAdmin (port 5050)

### Accessing UI Interfaces

After starting, the following UIs are available:

- **Kafka UI**: http://localhost:8080
  - View topics, messages, consumer groups
- **pgAdmin**: http://localhost:5050
  - Login: `admin@admin.com`, password: `admin`
  - PostgreSQL database management
  - Queue and exchange management

### Running Operator Locally

For development, run the operator locally:

```bash
# Install CRD in cluster (if using kind or minikube)
task install

# Run the operator
task run
```

Or use the script:

```bash
./scripts/run-local.sh
```

### Setting Up Local Cluster (Optional)

For full testing, use kind (Kubernetes in Docker):

```bash
# Create kind cluster
./scripts/setup-kind.sh

# Install CRD
task install

# Run operator locally
task run
```

### Debugging

For debugging, use operator logs:

```bash
# If operator is running locally, logs are output to console
# For operator in cluster:
kubectl logs -l app.kubernetes.io/name=dataflow-operator -f
```

Check Kubernetes events:

```bash
kubectl get events --sort-by='.lastTimestamp' | grep dataflow
```

## Next Steps

Now that you've installed the operator and created your first data flow:

1. Study [Connectors](connectors.md) to understand all available sources and sinks
2. Familiarize yourself with [Transformations](transformations.md) for working with message transformations
3. Check out [Examples](examples.md) for practical usage examples
4. Read [Development](development.md) to participate in development

## Troubleshooting

### Operator Not Starting

```bash
# Check logs
kubectl logs -l app.kubernetes.io/name=dataflow-operator

# Check events
kubectl describe pod -l app.kubernetes.io/name=dataflow-operator

# Check CRD
kubectl get crd dataflows.dataflow.dataflow.io -o yaml
```

### DataFlow Not Processing Messages

1. Check DataFlow status:
   ```bash
   kubectl describe dataflow <name>
   ```

2. Check connection to data source:
   ```bash
   # For Kafka
   kafka-console-consumer --bootstrap-server localhost:9092 --topic <topic>

   # For PostgreSQL
   psql <connection-string> -c "SELECT * FROM <table> LIMIT 10;"
   ```

3. Check operator logs for errors

### Connection Issues

- Ensure data sources are accessible from the cluster
- Check Kubernetes network policies
- Verify connection strings and credentials are correct
- For local development, use `localhost` or `host.docker.internal`
