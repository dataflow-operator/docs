# Examples

Practical examples of using DataFlow Operator for various data processing scenarios.

The data flow in each pipeline follows the pattern **Source → Transformations → Sink**. See [Architecture — Data Flow Pipeline](architecture.md#data-flow-pipeline-conceptual) for a conceptual diagram.

## Simple Kafka → PostgreSQL Flow

Basic example of transferring data from a Kafka topic to a PostgreSQL table.

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
      connectionString: "postgres://dataflow:dataflow@postgres:5432/dataflow?sslmode=disable"
      table: output_table
      autoCreateTable: true
```

**Apply:**
```bash
kubectl apply -f dataflow/config/samples/kafka-to-postgres.yaml
```

## Kafka → Nessie

Example of exporting Kafka events into an Iceberg table via the Nessie sink.

**Apply:**
```bash
kubectl apply -f dataflow/config/samples/kafka-to-nessie.yaml
```

See also the connector setup details in [Connectors — Nessie](connectors.md#nessie).

## Nessie → Kafka

Example of reading from a Nessie-backed Iceberg table and publishing rows to a Kafka topic.

**Apply:**
```bash
kubectl apply -f dataflow/config/samples/nessie-to-kafka.yaml
```

See also the connector setup details in [Connectors — Nessie](connectors.md#nessie).

## Kafka with Raw Mode (rawMode)

Example of preserving full Kafka message context: value + metadata (offset, partition, timestamp, key, topic). Use `rawMode: true` in the sink to store messages as JSON with `value` and `_metadata` columns.

```yaml
apiVersion: dataflow.dataflow.io/v1
kind: DataFlow
metadata:
  name: kafka-raw-to-clickhouse
spec:
  source:
    type: kafka
    config:
      brokers:
        - localhost:9092
      topic: input-topic
      consumerGroup: dataflow-group
  sink:
    type: clickhouse
    config:
      connectionString: "clickhouse://default@clickhouse:9000/default"
      table: raw_events
      autoCreateTable: true
      rawMode: true  # Stores each message as {"value": ..., "_metadata": {...}}
```

**Output message format with rawMode (sink wraps using msg.Metadata):**
```json
{
  "value": {"id": 1, "event": "user_login"},
  "_metadata": {
    "offset": 100,
    "partition": 0,
    "timestamp": "2024-02-27T10:13:20.000Z",
    "key": "user-123",
    "topic": "input-topic"
  }
}
```

For sinks expecting only data without the wrapper, add a select transformation with the `value` field:
```yaml
transformations:
    - type: select
    config:
      fields: ["value"]
```

## Error Handling with Error Sink

Example of configuring a separate sink for messages that failed to be written to the main sink.

```yaml
apiVersion: dataflow.dataflow.io/v1
kind: DataFlow
metadata:
  name: kafka-to-postgres-with-errors
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
      connectionString: "postgres://dataflow:dataflow@postgres:5432/dataflow?sslmode=disable"
      table: output_table
      autoCreateTable: true
  errors:
    type: kafka
    config:
      brokers:
        - localhost:9092
      topic: error-topic
```

**Apply:**
```bash
kubectl apply -f dataflow/config/samples/kafka-to-postgres-with-errors.yaml
```

For error message structure and configuration details, see [Error Handling](errors.md).

## PostgreSQL → PostgreSQL (replication / ETL)

Example of reading data from one PostgreSQL database and writing transformed data into another PostgreSQL database.

```yaml
apiVersion: dataflow.dataflow.io/v1
kind: DataFlow
metadata:
  name: postgres-to-postgres
spec:
  source:
    type: postgresql
    config:
      connectionString: "postgres://dataflow:dataflow@source-postgres:5432/source_db?sslmode=disable"
      table: source_orders
      query: "SELECT * FROM source_orders WHERE updated_at > NOW() - INTERVAL '5 minutes'"
      pollInterval: 60
  sink:
    type: postgresql
    config:
      connectionString: "postgres://dataflow:dataflow@target-postgres:5432/target_db?sslmode=disable"
      table: target_orders
      autoCreateTable: true
      batchSize: 100
      upsertMode: true  # Enables updating existing records instead of skipping them
  transformations:
    # Keep only required fields
    - type: select
      config:
        fields:
          - id
          - customer_id
          - total
          - status
          - updated_at
    # Add sync time
    - type: timestamp
      config:
        fieldName: synced_at
```

**Typical use cases:**

- **Online replication**: periodically copying updated rows from OLTP database to analytics database
- **ETL pipeline**: cleaning and reshaping data when moving between PostgreSQL schemas/clusters

**Important:** With `upsertMode: true`, existing records in the target table will be updated on conflict with PRIMARY KEY (or specified `conflictKey`). Without `upsertMode`, updated records from the source will be skipped if they already exist in the target table.

## Using Secrets for Credentials

DataFlow Operator supports configuring connectors from Kubernetes Secrets through `*SecretRef` fields.

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: kafka-credentials
  namespace: default
type: Opaque
stringData:
  brokers: "kafka1:9092,kafka2:9092"
  topic: "input-topic"
  consumerGroup: "dataflow-group"
  username: "kafka-user"
  password: "kafka-password"
---
apiVersion: v1
kind: Secret
metadata:
  name: postgres-credentials
  namespace: default
type: Opaque
stringData:
  connectionString: "postgres://user:password@postgres:5432/dbname?sslmode=disable"
  table: "output_table"
---
apiVersion: dataflow.dataflow.io/v1
kind: DataFlow
metadata:
  name: secure-dataflow
spec:
  source:
    type: kafka
    config:
      brokersSecretRef:
        name: kafka-credentials
        key: brokers
      topicSecretRef:
        name: kafka-credentials
        key: topic
      consumerGroupSecretRef:
        name: kafka-credentials
        key: consumerGroup
      sasl:
        mechanism: scram-sha-256
        usernameSecretRef:
          name: kafka-credentials
          key: username
        passwordSecretRef:
          name: kafka-credentials
          key: password
  sink:
    type: postgresql
    config:
      connectionStringSecretRef:
        name: postgres-credentials
        key: connectionString
      tableSecretRef:
        name: postgres-credentials
        key: table
      autoCreateTable: true
```

**Apply:**
```bash
kubectl apply -f dataflow/config/samples/kafka-to-postgres-secrets.yaml
```

For supported fields, TLS certificates, and troubleshooting, see [Using Kubernetes Secrets](connectors.md#using-kubernetes-secrets).

## High-Throughput Kafka Pipeline

For high Kafka message rates (tens of thousands msg/s), increase `channelBufferSize` and sink `batchSize`:

```yaml
spec:
  channelBufferSize: 500   # default 100; reduces blocking when sink is slower than source
  source:
    type: kafka
    config:
      brokers: [localhost:9092]
      topic: high-volume-topic
      consumerGroup: dataflow-group
  sink:
    type: postgresql
    config:
      connectionString: "..."
      table: events
      batchSize: 500
      batchFlushIntervalSeconds: 2
```

## Configuring Pod Resources and Placement

Each DataFlow resource creates a separate pod (Deployment) for processing. You can configure resources, node selection, affinity, and tolerations for these pods.

### Example: Custom Resources and Node Selection

```yaml
apiVersion: dataflow.dataflow.io/v1
kind: DataFlow
metadata:
  name: kafka-to-postgres-with-resources
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
      connectionString: "postgres://dataflow:dataflow@postgres:5432/dataflow?sslmode=disable"
      table: output_table
  # Configure resources for the processor pod
  resources:
    requests:
      cpu: "200m"
      memory: "256Mi"
    limits:
      cpu: "1000m"
      memory: "1Gi"
  # Select nodes for pod placement
  nodeSelector:
    node-type: compute
    zone: us-east-1
  # Affinity rules for more precise placement control
  affinity:
    nodeAffinity:
      requiredDuringSchedulingIgnoredDuringExecution:
        nodeSelectorTerms:
        - matchExpressions:
          - key: kubernetes.io/arch
            operator: In
            values:
            - amd64
      preferredDuringSchedulingIgnoredDuringExecution:
      - weight: 100
        preference:
          matchExpressions:
          - key: node-type
            operator: In
            values:
            - compute
    podAffinity:
      preferredDuringSchedulingIgnoredDuringExecution:
      - weight: 50
        podAffinityTerm:
          labelSelector:
            matchExpressions:
            - key: app
              operator: In
              values:
              - dataflow-processor
          topologyKey: kubernetes.io/hostname
  # Tolerations for working with tainted nodes
  tolerations:
  - key: dedicated
    operator: Equal
    value: dataflow
    effect: NoSchedule
  - key: workload-type
    operator: Equal
    value: batch
    effect: NoSchedule
```

**Apply:**
```bash
kubectl apply -f dataflow/config/samples/kafka-to-postgres-with-resources.yaml
```

### Resource Configuration

- **resources**: Defines CPU and memory requests and limits for the processor pod
  - If not specified, defaults are used: `100m` CPU / `128Mi` memory (requests), `500m` CPU / `512Mi` memory (limits)
  - Use this to ensure pods have sufficient resources for high-throughput processing

### Node Selection

- **nodeSelector**: Simple key-value pairs to select specific nodes
  - Example: `node-type: compute` ensures pods run only on nodes labeled with `node-type=compute`

### Affinity Rules

- **affinity**: Advanced placement rules using Kubernetes affinity
  - **nodeAffinity**: Control which nodes pods can run on
  - **podAffinity**: Prefer to run pods near other pods (e.g., other dataflow processors)
  - **podAntiAffinity**: Avoid running pods near other pods (e.g., spread across nodes)

### Tolerations

- **tolerations**: Allow pods to run on tainted nodes
  - Useful for dedicated compute nodes or specialized hardware
  - Example: Run dataflow processors on nodes dedicated to batch workloads

### Default Behavior

If resources, nodeSelector, affinity, or tolerations are not specified:
- Default resources are applied (100m CPU / 128Mi memory requests, 500m CPU / 512Mi memory limits)
- Pods can run on any node (no nodeSelector)
- No affinity rules are applied
- Pods cannot run on tainted nodes (no tolerations)

### Checking Pod Status

After creating a DataFlow with custom resources, check the pod:

```bash
# List pods created by DataFlow
kubectl get pods -l app=dataflow-processor

# Describe a specific pod
kubectl describe pod df-<name>-<hash>

# Check resource usage
kubectl top pod df-<name>-<hash>
```

Additional examples are available in `dataflow/config/samples/` directory:

- `kafka-to-postgres.yaml` - basic Kafka -> PostgreSQL
- `kafka-debezium-to-postgres.yaml` - Kafka (Debezium envelope) -> PostgreSQL via `debeziumUnwrap`
- `kafka-to-postgres-with-resources.yaml` - example with custom resources and scheduling
- `flatten-example.yaml` - example with Flatten transformation
- `router-example.yaml` - example with Router transformation

