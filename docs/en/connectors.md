# Connectors

DataFlow Operator supports various connectors for data sources and sinks. Each connector implements a standard interface and can be used as a data source (source) or sink.

## Connector Overview

| Connector | Source | Sink | Features |
|-----------|--------|------|----------|
| Kafka | ✅ | ✅ | Consumer groups, TLS, SASL, Avro, Schema Registry |
| PostgreSQL | ✅ | ✅ | SQL queries, batch inserts, auto-create tables, UPSERT mode |
| Trino | ✅ | ✅ | SQL queries, Keycloak OAuth2 authentication, batch inserts |
| ClickHouse | ✅ | ✅ | Polling, batch inserts, auto-create MergeTree tables |
| Nessie | ✅ | ✅ | Iceberg via Nessie catalog, polling, batch appends, sink `rawMode` (`data` + `_metadata`); `spec.replicas` must be 1 |


## Using Kubernetes Secrets

DataFlow Operator supports configuring connectors from Kubernetes Secrets. This allows secure storage of sensitive data (passwords, tokens, connection strings) without explicitly specifying them in the DataFlow specification.

### Overview

Instead of specifying values directly in the configuration, you can use references to Kubernetes Secrets through `*SecretRef` fields. The operator automatically reads values from secrets and substitutes them into connector configuration.

### SecretRef Structure

Each secret reference has the following structure:

```yaml
secretRef:
  name: my-secret          # Secret name (required)
  namespace: my-namespace  # Secret namespace (optional, defaults to DataFlow namespace)
  key: my-key              # Key in secret (required)
```

### Supported Fields

All connectors support secret references for the following fields:

#### Kafka
- `brokersSecretRef` - broker list (comma-separated)
- `topicSecretRef` - topic name
- `consumerGroupSecretRef` - consumer group
- `sasl.usernameSecretRef` - SASL username
- `sasl.passwordSecretRef` - SASL password
- `tls.certSecretRef` - client certificate
- `tls.keySecretRef` - private key
- `tls.caSecretRef` - CA certificate
- `schemaRegistry.urlSecretRef` - Schema Registry URL
- `schemaRegistry.basicAuth.usernameSecretRef` - Schema Registry username
- `schemaRegistry.basicAuth.passwordSecretRef` - Schema Registry password
- `avroSchemaSecretRef` - Avro schema from secret (for static schema)

#### PostgreSQL
- `connectionStringSecretRef` - connection string
- `tableSecretRef` - table name

#### ClickHouse
- `connectionStringSecretRef` - connection string
- `tableSecretRef` - table name

#### Trino
- `serverURLSecretRef` - Trino server URL
- `catalogSecretRef` - catalog name
- `schemaSecretRef` - schema name
- `tableSecretRef` - table name
- `keycloak.serverURLSecretRef` - Keycloak server URL
- `keycloak.realmSecretRef` - Keycloak realm name
- `keycloak.clientIDSecretRef` - OAuth2 client ID
- `keycloak.clientSecretSecretRef` - OAuth2 client secret
- `keycloak.usernameSecretRef` - username for password grant
- `keycloak.passwordSecretRef` - password for password grant
- `keycloak.tokenSecretRef` - OAuth2 token (for long-lived tokens)

#### Nessie
- `baseURLSecretRef` - Nessie server base URL
- `tokenSecretRef` - Bearer token for Nessie/Iceberg REST
- `namespaceSecretRef` - namespace (schema) name
- `tableSecretRef` - table name

### Usage Examples

#### Example 1: Kafka with SASL Authentication

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: kafka-credentials
  namespace: default
type: Opaque
stringData:
  brokers: "kafka1:9092,kafka2:9092,kafka3:9092"
  topic: "input-topic"
  consumerGroup: "dataflow-group"
  username: "kafka-user"
  password: "kafka-password"
---
apiVersion: dataflow.dataflow.io/v1
kind: DataFlow
metadata:
  name: kafka-example
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
      securityProtocol: SASL_PLAINTEXT
      sasl:
        mechanism: "scram-sha-256"
        usernameSecretRef:
          name: kafka-credentials
          key: username
        passwordSecretRef:
          name: kafka-credentials
          key: password
```

#### Example 2: PostgreSQL with Connection String from Secret

```yaml
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
  name: postgres-example
spec:
  source:
    type: postgresql
    config:
      connectionStringSecretRef:
        name: postgres-credentials
        key: connectionString
      tableSecretRef:
        name: postgres-credentials
        key: table
```

### Priority of Values

If both a direct value and `SecretRef` are specified, `SecretRef` takes priority. The value from the secret will be used instead of the direct value.

### Secrets in Different Namespaces

By default, the operator looks for secrets in the same namespace where the DataFlow resource is located. You can specify a different namespace:

```yaml
connectionStringSecretRef:
  name: postgres-credentials
  namespace: shared-secrets
  key: connectionString
```

### TLS Certificates from Secrets

For TLS configuration, the operator automatically determines whether the value from the secret is a file path or certificate content.

**How it works:**
- If the value starts with `-----BEGIN` (e.g., `-----BEGIN CERTIFICATE-----` or `-----BEGIN PRIVATE KEY-----`), the operator recognizes it as certificate content and creates a temporary file
- If the value doesn't start with `-----BEGIN` and exists as a file, it's used as a file path
- If the value doesn't start with `-----BEGIN` and the file doesn't exist, it's also treated as certificate content

**Supported formats:**
1. **Certificate content** (PEM format) - stored in `stringData` or decoded from `data`
2. **Base64-encoded content** - stored in secret's `data` field (Kubernetes automatically decodes it)
3. **File path** - path to an existing certificate file

**Example:**

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: kafka-tls-certs
type: Opaque
stringData:
  ca.crt: |
    -----BEGIN CERTIFICATE-----
    ...
    -----END CERTIFICATE-----
  client.crt: |
    -----BEGIN CERTIFICATE-----
    ...
    -----END CERTIFICATE-----
  client.key: |
    -----BEGIN PRIVATE KEY-----
    ...
    -----END PRIVATE KEY-----
---
apiVersion: dataflow.dataflow.io/v1
kind: DataFlow
metadata:
  name: kafka-tls-example
spec:
  source:
    type: kafka
    config:
      brokers:
        - secure-kafka:9093
      topic: secure-topic
      tls:
        caSecretRef:
          name: kafka-tls-certs
          key: ca.crt
        certSecretRef:
          name: kafka-tls-certs
          key: client.crt
        keySecretRef:
          name: kafka-tls-certs
          key: client.key
```

**Important:**
- Temporary files are automatically created for certificate content and cleaned up after use
- When using base64-encoded values in the `data` field, Kubernetes automatically decodes them when reading
- Ensure certificates are in proper PEM format with `-----BEGIN` and `-----END` headers

### Security

- **RBAC**: The operator requires permissions to read secrets (`get`, `list`, `watch`)
- **Isolation**: Secrets should be in the same namespace or in a namespace the operator has access to
- **Temporary Files**: For TLS certificates, the operator creates temporary files that are automatically deleted

### Troubleshooting

#### Secret Not Found

```bash
# Check if secret exists
kubectl get secret <secret-name> -n <namespace>

# Check operator permissions
kubectl auth can-i get secrets --as=system:serviceaccount:default:dataflow-operator
```

#### Key Not Found in Secret

```bash
# Check keys in secret
kubectl get secret <secret-name> -n <namespace> -o jsonpath='{.data}' | jq 'keys'
```

#### Secret Resolution Error

Check operator logs:

```bash
kubectl logs -l app.kubernetes.io/name=dataflow-operator | grep -i secret
```

Ensure:
1. Secret exists in the specified namespace
2. The specified key exists in the secret
3. The operator has permissions to read secrets

#### TLS Certificate Issues

If you encounter errors with TLS certificates:

1. **"file name too long" error**: Ensure the certificate is stored correctly in the secret:
   - If using `stringData`, the certificate should be in PEM format with `-----BEGIN` and `-----END` headers
   - If using `data` (base64), ensure the value is correctly encoded
   - The operator automatically detects certificate content by the `-----BEGIN` prefix

2. **"failed to read CA file" error**: Check the certificate format:
   ```bash
   # Check secret content
   kubectl get secret <secret-name> -n <namespace> -o jsonpath='{.data.ca\.crt}' | base64 -d
   ```
   Ensure the certificate starts with `-----BEGIN CERTIFICATE-----`

3. **Temporary file creation error**: Check operator permissions to create files in the temporary directory

## Kafka

The Kafka connector supports reading and writing messages from/to Apache Kafka topics. It supports consumer groups for scaling, TLS and SASL authentication, as well as Avro format through Confluent Schema Registry or static schema.

### Source

```yaml
source:
  type: kafka
  config:
    brokers:
      - kafka1:9092
    topic: input-topic
    consumerGroup: my-group

    # Kafka security protocol (optional)
    # Values: PLAINTEXT, SSL, SASL_PLAINTEXT, SASL_SSL
    # If omitted, protocol is inferred from tls/sasl sections (backward compatible)
    securityProtocol: SASL_PLAINTEXT

    # TLS configuration (optional)
    tls:
      insecureSkipVerify: false
      caFile: /path/to/ca.crt
      certFile: /path/to/client.crt
      keyFile: /path/to/client.key

    # SASL authentication (optional)
    sasl:
      # Mechanism: plain, scram-sha-256, scram-sha-512
      mechanism: scram-sha-256
      username: kafka-user
      password: kafka-password

    # Message format (optional, default: "json")
    # Supported formats: "json", "avro"
    format: json

    # Avro configuration (required if format: "avro")
    # Option 1: Use Confluent Schema Registry (recommended)
    schemaRegistry:
      url: https://schema-registry:8081
      basicAuth:
        username: schema-user
        password: schema-password
      tls:
        insecureSkipVerify: false
        caFile: /path/to/schema-registry-ca.crt

    # Option 2: Static Avro schema (alternative to Schema Registry)
    # avroSchema: |
    #   {
    #     "type": "record",
    #     "name": "MyRecord",
    #     "fields": [
    #       {"name": "id", "type": "long"},
    #       {"name": "name", "type": "string"}
    #     ]
    #   }
    # Or path to schema file:
    # avroSchemaFile: /path/to/schema.avsc
```

### Features

- **Consumer Groups**: Use different consumer groups for scaling processing
- **Initial Offset**: Reads from oldest message by default (`OffsetOldest`)
- **Data Formats**: Supports JSON (default) and Avro formats
- **Avro Support**:
  - **Confluent Schema Registry**: Automatic schema retrieval by ID from messages (format: magic byte + schema ID + data)
  - **Static Schema**: Use predefined schema from configuration or file
  - **Schema Caching**: Schemas from Schema Registry are cached for performance
- **Metadata**: Each message contains metadata:
  - `topic` - topic name
  - `partition` - partition number
  - `offset` - message offset
  - `key` - message key (if present)
- **securityProtocol**: Explicit Kafka `security.protocol`. Supported values: `PLAINTEXT`, `SSL`, `SASL_PLAINTEXT`, `SASL_SSL` (case and `-`/`_` are normalized). When omitted, the protocol is inferred: `sasl` only → `SASL_PLAINTEXT`, `tls` + `sasl` → `SASL_SSL`, `tls` only → `SSL`, neither → `PLAINTEXT`. When set explicitly, the webhook validates consistency with `tls`/`sasl` (e.g. `SASL_PLAINTEXT` requires `sasl` and forbids `tls`).

### Sink

```yaml
sink:
  type: kafka
  config:
    brokers:
      - kafka1:9092
    topic: output-topic
    # Security protocol (optional, same as source)
    securityProtocol: SASL_PLAINTEXT
    # TLS and SASL configuration similar to source
    tls:
      caFile: /path/to/ca.crt
    sasl:
      mechanism: scram-sha-256
      username: kafka-user
      password: kafka-password
```

#### Example: SASL_SSL

```yaml
source:
  type: kafka
  config:
    brokers:
      - secure-kafka:9093
    topic: secure-topic
    consumerGroup: secure-group
    securityProtocol: SASL_SSL
    tls:
      caFile: /etc/kafka/ca.crt
      certFile: /etc/kafka/client.crt
      keyFile: /etc/kafka/client.key
    sasl:
      mechanism: scram-sha-512
      username: kafka-user
      password: kafka-password
```

#### Example: SASL_PLAINTEXT (no TLS)

```yaml
source:
  type: kafka
  config:
    brokers:
      - kafka1:9092
    topic: input-topic
    consumerGroup: my-group
    securityProtocol: SASL_PLAINTEXT
    sasl:
      mechanism: scram-sha-256
      usernameSecretRef:
        name: kafka-credentials
        key: username
      passwordSecretRef:
        name: kafka-credentials
        key: password
```

## PostgreSQL

The PostgreSQL connector supports reading from and writing to PostgreSQL tables. It supports custom SQL queries, periodic polling, batch inserts, auto-create tables, UPSERT mode, CDC-style change tracking (inserts and updates), soft delete, and SecretRef for credentials.

### Source

```yaml
source:
  type: postgresql
  config:
    # Connection string (required, or use connectionStringSecretRef)
    connectionString: "postgres://user:password@localhost:5432/dbname?sslmode=disable"
    # Table to read from (required if query not specified). Supports schema.table (e.g. public.products)
    table: source_table

    # Custom SQL query (optional)
    query: "SELECT * FROM source_table WHERE updated_at > NOW() - INTERVAL '1 hour'"
    # Poll interval in seconds (optional, default: 5)
    pollInterval: 60

    # CDC-style options (optional)
    readBatchSize: 1000           # Limit rows per poll to reduce DB load (0 = no limit)
    changeTrackingColumn: updated_at  # Column to track changes (default: updated_at). In query mode, set explicitly to enable incremental subquery wrapper
    orderByColumn: id             # Secondary sort key for stable pagination (default: id). Example: price_id
    autoCreateTable: true         # Create table if it doesn't exist before reading

    # SecretRef (optional) - use instead of direct values
    # connectionStringSecretRef:
    #   name: postgres-credentials
    #   key: connectionString
    # tableSecretRef:
    #   name: postgres-credentials
    #   key: table
```

### Source Features

- **Periodic Polling**: Regularly polls the table for new data
- **Custom Queries**: Support for complex SQL with JOIN, WHERE, etc.
- **Metadata**: Each message contains `table` metadata and `operation` (insert/update)
- **Read Batch Size**: Limits rows per poll to reduce database load when many new records appear
- **Change Tracking**: By default tracks changes via `updated_at` column (or `changeTrackingColumn`), captures both INSERTs and UPDATEs
- **Stable ordering**: Table mode adds `ORDER BY changeTrackingColumn, orderByColumn` (default secondary key: `id`). When `query` and `changeTrackingColumn` are both set, your SQL is wrapped in a subquery with the same composite checkpoint filter `(changeTrackingColumn, orderByColumn) > (lastTime, lastId)` and `ORDER BY`. Without explicit `changeTrackingColumn`, query mode runs your SQL as-is (legacy). Row value from `orderByColumn` is stored in message metadata key `id`.
- **Query mode requirements**: When using incremental query mode, the SELECT must include `changeTrackingColumn` and `orderByColumn` columns; otherwise checkpoint advancement will not work.
- **Auto-create Table**: When `autoCreateTable: true`, creates the table with CDC-friendly schema (`id SERIAL PRIMARY KEY`, `created_at`, `updated_at`) if it doesn't exist. Creation happens at Connect time.
- **Schema notation**: Table name supports `schema.table` format (e.g. `public.products`)
- **Checkpoint persistence**: By default, read position (`lastReadChangeTime`, `lastReadOrderByValue`) is persisted to ConfigMap; on restart, reading resumes from the last position. Set `checkpointPersistence: false` in spec to store only in memory. For pg→pg flows, enable `upsertMode: true` in sink to update duplicates instead of inserting them again.

#### One-time migration (batch exhaust)

For a **single snapshot** copy (e.g. `DataFlowCron` job that must stop after all rows are read), use table mode with explicit pagination and a stable key column:

1. **Prefer a MATERIALIZED VIEW** on the source DB when the business SQL is heavy: run `CREATE MATERIALIZED VIEW` + `REFRESH` once, then point `table` at the MVIEW.
2. Set **`changeTrackingColumn`** and **`orderByColumn`** to the same non-timestamp key (e.g. `material_id`) when no `updated_at` exists in the result.
3. Set **`readBatchSize`** (e.g. `10000`) so reads are batched.
4. On the sink: **`upsertMode: true`**, explicit **`conflictKey`**, matching column types (e.g. `BIGINT` for numeric IDs, not `TEXT`).
5. The processor stops when the next poll returns **zero rows** (`source exhausted`). Checkpoint must advance via message `Ack` after each successful sink write.

Example source fragment:

```yaml
source:
  type: postgresql
  config:
    table: price_calendar.mv_one_p_prices_migration
    changeTrackingColumn: material_id
    orderByColumn: material_id
    readBatchSize: 10000
    pollInterval: 5
```

The same pattern applies to **Trino** and **ClickHouse** incremental sources (order-by-only checkpoint). **Kafka** and **Nessie** use different offset/snapshot models.

### Sink

```yaml
sink:
  type: postgresql
  config:
    connectionString: "postgres://user:password@localhost:5432/dbname?sslmode=disable"
    # Table to write to. Supports schema.table (e.g. public.products_clone)
    table: target_table

    # Batch size (optional, default: 1). 0 = flush only by timer
    batchSize: 100
    # Flush interval in seconds (optional, default: 10). 0 = disable timer
    batchFlushIntervalSeconds: 10
    autoCreateTable: true

    # Raw mode (optional, default: false)
    # When true, expects {"value": <data>, "_metadata": {...}} or plain body with msg.Metadata
    # Table is created with data JSONB and _metadata JSONB columns
    rawMode: false

    # UPSERT mode (optional, default: false)
    upsertMode: true
    conflictKey: "id"
    upsertStrategy: ifNewer       # always (default) | ifNewer
    upsertVersionColumn: updated_at  # required when upsertStrategy is ifNewer
    # Soft delete column (optional). When set, DELETE operations UPDATE this column instead of physical delete
    softDeleteColumn: "deleted_at"

    # SecretRef (optional)
    # connectionStringSecretRef: { name: postgres-credentials, key: connectionString }
    # tableSecretRef: { name: postgres-credentials, key: table }
```

### Sink Features

- **Batch Inserts**: Groups messages for efficient writing. Flush when `batchSize` reached or on timer. Use `batchFlushIntervalSeconds: 0` for size-only flush; `batchSize: 0` for timer-only flush.
- **Auto-create Tables** (when `autoCreateTable: true`):
  - **rawMode: true** — table is created at Connect time. Schema: `id SERIAL PRIMARY KEY`, `data` JSONB, `_metadata` JSONB, `created_at`, `updated_at`, `deleted_at`, GIN index on `data`
  - **rawMode: false** — table is created at first write from the first message structure (replicates source schema). Column types are inferred automatically (TEXT, BIGINT, NUMERIC, JSONB, etc.)
- **Raw Mode**: When true, stores message body in `data` and metadata in `_metadata` (or flattened columns). When false, uses columnar format from message.
- **UPSERT Mode**: Updates existing records on conflict (PRIMARY KEY or `conflictKey`). Batch flushes run in an explicit PostgreSQL transaction.
- **Upsert strategy**: `always` (default) updates on every conflict; `ifNewer` updates only when the incoming `upsertVersionColumn` is greater than the stored value (prevents stale replays from overwriting newer rows).
- **Soft Delete**: When `softDeleteColumn` is set and message has `metadata.operation=delete`, performs `UPDATE ... SET deleted_at = NOW()` instead of physical DELETE

## ClickHouse

The ClickHouse connector supports reading from and writing to ClickHouse tables. It supports polling for incremental reads, custom SQL queries, batch inserts, and auto-creation of MergeTree tables.

### Source

```yaml
source:
  type: clickhouse
  config:
    # Connection string (required)
    # Native: clickhouse://host:9000?username=default&password=xxx&database=default
    # HTTP: http://host:8123/default?username=default&password=xxx
    connectionString: "clickhouse://default@clickhouse:9000/default?dial_timeout=10s"

    # Table to read from (required, if not using query)
    table: source_table

    # Custom SQL query (optional)
    # If specified, used instead of reading from table
    query: "SELECT * FROM source_table WHERE id > 100"

    # Poll interval in seconds (optional, default: 5)
    pollInterval: 60

    # Column for incremental pagination and stable ORDER BY (optional, default: id)
    orderByColumn: price_id

    # Column used to track changes (optional, default: created_at)
    changeTrackingColumn: created_at

    # Limit rows per poll (optional, 0 = no limit)
    readBatchSize: 1000
```

### Source Features

- **Polling**: Periodically polls the table for new data (interval set by `pollInterval`)
- **Read batching**: `readBatchSize` limits rows per query within a poll cycle (same as PostgreSQL source)
- **Incremental Reads**: Table mode uses composite checkpoint `(changeTrackingColumn, orderByColumn) > (lastTime, lastKey)` with tuple WHERE; legacy checkpoints with only `lastReadOrderByValue` fall back to `WHERE orderByColumn > N` until a timestamp is recorded
- **Custom Queries**: When `query` and `changeTrackingColumn` are both set, SQL is wrapped in a subquery with the same composite filter; without explicit `changeTrackingColumn`, query mode runs your SQL as-is (legacy)
- **Stable ordering**: Table mode adds `ORDER BY changeTrackingColumn, orderByColumn` (defaults: `created_at`, `id`)
- **Checkpoint persistence**: Read position (`lastReadChangeTime`, `lastReadOrderByValue`) is persisted to ConfigMap; legacy `lastReadID`/`lastReadTime` are migrated on load
- **Metadata**: Each message contains `table` and `id` (value from `orderByColumn` column, if present)

### Sink

```yaml
sink:
  type: clickhouse
  config:
    connectionString: "clickhouse://default@clickhouse:9000/default?dial_timeout=10s"
    table: output_table

    # Batch size for inserts (optional, default: 100). 0 = flush only by timer
    batchSize: 100
    # Flush interval in seconds (optional, default: 10). 0 = disable timer
    batchFlushIntervalSeconds: 10

    # Auto-create table (optional)
    autoCreateTable: true

    # rawMode: false (default) — creates table from first message structure (columnar, replicates source schema)
    # rawMode: true — creates MergeTree table with data String, created_at columns (JSON storage)
    rawMode: false

    # Idempotent writes (optional)
    upsertMode: true
    conflictKey: id
    replacingVersionColumn: updated_at
    tableEngine: ReplacingMergeTree  # default when upsertMode is true and unset
```

### Sink Features

- **Batch Inserts**: Groups messages; flush when batch size or timer (10s) is reached. Size only: `batchFlushIntervalSeconds: 0`. Timer only: `batchSize: 0`
- **Upsert mode**: With `upsertMode: true`, auto-created tables use `ReplacingMergeTree`; duplicates are resolved on background merge. See [Fault Tolerance](fault-tolerance.md).
- **Retry on Transient Errors**: Batch writes automatically retry on connection refused, TOO_MANY_PARTS, memory limit, HTTP 502/503, and similar transient errors (up to 5 attempts with exponential backoff)

### Resilience and Fault Tolerance

- **Error sink**: Use `spec.errors` with ClickHouse (or Kafka) to capture failed messages for replay or analysis. See [Error Handling](errors.md).
- **Connection string**: Recommended parameters: `dial_timeout=10s`, `max_execution_time=60` (e.g. `clickhouse://host:9000/default?dial_timeout=10s&max_execution_time=60`).
- **Batch tuning**: For throughput and resilience, use `batchSize` 100–1000 and `batchFlushIntervalSeconds` 5–10. Larger batches reduce insert frequency and can help avoid TOO_MANY_PARTS.
- **TOO_MANY_PARTS**: If you see this error, increase `batchSize`, decrease flush frequency, or tune ClickHouse merge settings (`background_pool_size`, `parts_to_throw_insert`). Consider `ReplacingMergeTree` for deduplication. See [Fault Tolerance](fault-tolerance.md).
- **Auto-create Tables** (when `autoCreateTable: true`):
  - **rawMode: true** — table is created at Connect time. Schema: `data String`, `created_at DateTime DEFAULT now()`, MergeTree engine, ORDER BY created_at. Messages are stored as JSON string in `data` column
  - **rawMode: false** — table is created at first write from the first message structure. Column types are inferred automatically (String, Int32/Int64, Float64, Decimal, DateTime, etc.). Supports `{"value": {...}, "_metadata": {...}}` format — uses fields from `value`
- **Raw Mode**: When true, expects/stores JSON in `data` column. When false, uses columnar format from message (INSERT with named columns)

### Example: Kafka to ClickHouse

```yaml
apiVersion: dataflow.dataflow.io/v1
kind: DataFlow
metadata:
  name: kafka-to-clickhouse
spec:
  source:
    type: kafka
    config:
      brokers:
        - kafka:9092
      topic: input-topic
      consumerGroup: dataflow-group
  sink:
    type: clickhouse
    config:
      connectionString: "clickhouse://default@clickhouse:9000/default"
      table: output_table
      batchSize: 100
      autoCreateTable: true
```

### Example: ClickHouse to ClickHouse (schema replication)

With `autoCreateTable: true` and `rawMode: false`, the target table is created automatically from the source structure:

```yaml
apiVersion: dataflow.dataflow.io/v1
kind: DataFlow
metadata:
  name: clickhouse-to-clickhouse
spec:
  source:
    type: clickhouse
    config:
      connectionString: "clickhouse://dataflow:dataflow@localhost:9000/dataflow?dial_timeout=10s"
      table: products
      pollInterval: 5
  sink:
    type: clickhouse
    config:
      connectionString: "clickhouse://dataflow:dataflow@localhost:9000/dataflow?dial_timeout=10s"
      table: products_clone
      batchSize: 100
      autoCreateTable: true
```

## Trino

The Trino connector supports reading from and writing to Trino (formerly PrestoSQL) tables. It supports SQL queries, Keycloak OAuth2/OIDC authentication, and batch inserts.

### Source

```yaml
source:
  type: trino
  config:
    # Trino server URL (required)
    serverURL: "http://trino:8080"

    # Catalog to use (required)
    catalog: hive

    # Schema to use (required)
    schema: default

    # Table to read from (required, if not using query)
    table: source_table

    # Custom SQL query (optional)
    # If specified, used instead of reading from table
    query: "SELECT * FROM hive.default.source_table WHERE id > 100"

    # Poll interval in seconds (optional, default: 5)
    # Used for periodic reading of new data
    pollInterval: 60

    # Column for incremental pagination and stable ORDER BY (optional, default: id)
    orderByColumn: price_id

    # Limit rows per poll (optional, 0 = no limit)
    readBatchSize: 1000

    # Keycloak authentication (optional)
    keycloak:
      # Option 1: Use long-lived token directly (recommended for long-lived tokens)
      token: "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9..."

      # Option 2: Use OAuth2 flow (alternative to direct token)
      # serverURL: "https://keycloak.example.com"
      # realm: myrealm
      # clientID: trino-client
      # clientSecret: client-secret
      # username: trino-user
      # password: trino-password
```

### Features

- **SQL Queries**: Support for custom SQL queries with WHERE, JOIN, etc. When `query` and `changeTrackingColumn` are both set, SQL is wrapped with composite checkpoint filter; otherwise custom queries get `ORDER BY orderByColumn` only (legacy)
- **Read batching**: `readBatchSize` limits rows per query within a poll cycle (same as PostgreSQL source)
- **Periodic Polling**: Table mode uses composite checkpoint `(changeTrackingColumn, orderByColumn) > (lastTime, lastKey)`; legacy `lastReadID` checkpoints use `WHERE orderByColumn > N` until timestamp is recorded
- **Checkpoint persistence**: `lastReadChangeTime` and `lastReadOrderByValue` in ConfigMap; legacy `lastReadID` migrated on load
- **Metadata**: Row value from `orderByColumn` is stored in message metadata key `id`
- **Keycloak Authentication**: OAuth2/OIDC authentication via Keycloak
  - **Direct Token**: Use a long-lived token obtained from Keycloak (recommended for long-lived tokens)
  - **Password Grant**: Use username/password for authentication
  - **Client Credentials**: Use client ID/secret for service-to-service authentication
- **Automatic Token Refresh**: Tokens are automatically refreshed before expiration (only for OAuth2 flow, not for direct tokens)
- **Metadata**: Each message contains metadata:
  - `catalog` - catalog name
  - `schema` - schema name
  - `table` - table name

#### Obtaining a Token from Keycloak

To use a long-lived token, you can obtain it from Keycloak using the following methods:

**Method 1: Using curl (Password Grant)**
```bash
curl -X POST "https://keycloak.example.com/realms/myrealm/protocol/openid-connect/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=password" \
  -d "client_id=trino-client" \
  -d "client_secret=client-secret" \
  -d "username=trino-user" \
  -d "password=trino-password"
```

**Method 2: Using curl (Client Credentials)**
```bash
curl -X POST "https://keycloak.example.com/realms/myrealm/protocol/openid-connect/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=client_credentials" \
  -d "client_id=trino-client" \
  -d "client_secret=client-secret"
```

The response will contain an `access_token` field. Use this token value in the `token` field of the Keycloak configuration.

**Note**: For long-lived tokens, configure the token lifespan in Keycloak realm settings or client settings.

### Sink

```yaml
sink:
  type: trino
  config:
    # Trino server URL (required)
    serverURL: "http://trino:8080"

    # Catalog to use (required)
    catalog: hive

    # Schema to use (required)
    schema: default

    # Table to write to (required)
    table: target_table

    # Batch size for inserts (optional, default: 1). 0 = flush only by timer
    batchSize: 100
    # Flush interval in seconds (optional, default: 10). 0 = disable timer
    batchFlushIntervalSeconds: 10

    # Auto-create table (optional, default: false)
    # If true, creates table with VARCHAR column for JSON data
    autoCreateTable: true

    # Raw mode (optional, default: false)
    # When true, creates table with data VARCHAR column; messages stored as JSON string
    # When false, uses columnar format matching message keys to table columns
    rawMode: true

    # MERGE upsert for Iceberg catalogs (catalog name must contain "iceberg")
    upsertMode: true
    conflictKey: id
    queryTimeoutSeconds: 600

    # Keycloak authentication (optional)
    keycloak:
      serverURL: "https://keycloak.example.com"
      realm: myrealm
      clientID: trino-client
      clientSecret: client-secret
      username: trino-user
      password: trino-password
```

### Features

- **Batch Inserts**: Groups messages; flush when batch size or timer (10s) is reached. Size only: `batchFlushIntervalSeconds: 0`. Timer only: `batchSize: 0`
- **Upsert mode**: `upsertMode: true` uses `MERGE INTO` for Iceberg tables (`conflictKey` required). See [Fault Tolerance](fault-tolerance.md).
- **Auto-create Tables**: Automatically creates tables if they don't exist
- **Raw Mode**: When `rawMode: true`, creates table with `data VARCHAR` column; messages stored as JSON string. When `false` (default), uses columnar format matching message keys to table columns
- **Keycloak Authentication**: OAuth2/OIDC authentication via Keycloak
- **Automatic Token Refresh**: Tokens are automatically refreshed

### Example: Kafka to Trino with Keycloak

```yaml
apiVersion: dataflow.dataflow.io/v1
kind: DataFlow
metadata:
  name: kafka-to-trino
spec:
  source:
    type: kafka
    config:
      brokers:
        - kafka:9092
      topic: input-topic
      consumerGroup: dataflow-group
  sink:
    type: trino
    config:
      serverURL: "http://trino:8080"
      catalog: hive
      schema: default
      table: output_table
      batchSize: 100
      keycloak:
        # Use long-lived token obtained from Keycloak
        token: "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9..."

        # Alternative: Use OAuth2 flow
        # serverURL: "https://keycloak.example.com"
        # realm: myrealm
        # clientID: trino-client
        # clientSecret: client-secret
        # username: trino-user
        # password: trino-password
```

## Nessie

The Nessie connector reads from and writes to Apache Iceberg tables via the [Nessie](https://projectnessie.org/) catalog (Iceberg REST API). All operations are performed in the context of a Nessie branch; metadata and data are managed by the catalog.

### Nessie Core API vs Iceberg REST

- **Nessie Core API** (`/api/v1`, `/api/v2`) manages repository metadata: references, commits, and content entries.
- **Iceberg REST catalog API** (`{baseURL}/iceberg[/{branch}][|{warehouse}]`) is used by DataFlow for table reads and writes.
- **Physical table files** are stored in the configured warehouse/object storage (for example S3-compatible storage), while Nessie tracks catalog metadata and versioned pointers.

If you need Core API details for administrative operations, use the OpenAPI document at repository root: `nessie-openapi-0.107.5.yaml`.

### Source

```yaml
source:
  type: nessie
  config:
    # Nessie server base URL (required), e.g. https://nessie:19120
    baseURL: "http://nessie:19120"

    # Nessie branch to read from (optional, default: main)
    branch: main

    # Warehouse name for storage location (optional), e.g. for /iceberg/|warehouse
    warehouse: ""

    # Namespace (schema) of the Iceberg table (required)
    namespace: my_schema

    # Table name (required)
    table: my_table

    # Poll interval in seconds (optional, default: 10)
    pollInterval: 10

    # Incremental read by Iceberg snapshot (optional, default: false)
    # incrementalBySnapshot: true
    # startSnapshotID: "1234567890123456789"  # first run without checkpoint
    # snapshotCheckpoints: true              # default

    # Authentication (optional)
    # authenticationType: AUTO (default) | BEARER | BASIC | NONE
    authenticationType: BEARER
    bearerToken: "your-token"
    # Or Basic auth:
    # basicAuth:
    #   username: user
    #   password: pass
```

### Features

- **Branch context**: Reads from the specified Nessie branch; table metadata is resolved from the catalog.
- **Polling**: Periodically scans the Iceberg table for new data.
- **Full scan (default)**: Each poll scans the table’s current snapshot in full.
- **Incremental mode** (`incrementalBySnapshot: true`): Reads only snapshots newer than the last `Ack`; position is stored in the checkpoint ConfigMap (see [fault tolerance](fault-tolerance.md)). The `query` field is not supported in this mode.
- **Authentication**: Bearer token (OAuth2) or Basic auth for Nessie/Iceberg REST.
- **No `rawMode` on source**: Each Iceberg row is emitted as a JSON object keyed by column names (for example `data` and `_metadata` if the table was written with sink `rawMode: true`). Incremental mode reduces duplicates on restart but does **not** enable multiple processor pods — see [Horizontal scaling](#horizontal-scaling-specreplicas) below.

### Sink

```yaml
sink:
  type: nessie
  config:
    baseURL: "http://nessie:19120"
    branch: main
    warehouse: ""
    namespace: my_schema
    table: my_table

    # Batch size for appends (optional, default: 100). 0 = flush only by timer
    batchSize: 100
    # Flush interval in seconds (optional, default: 10). 0 = disable timer
    batchFlushIntervalSeconds: 10

    # Create table if it does not exist (optional)
    autoCreateTable: true

    # Raw mode (optional, default: false)
    # When true, creates table with data and _metadata string columns; plain messages use msg.Metadata for _metadata
    rawMode: false

    authenticationType: BEARER
    bearerToken: "your-token"
    # Or basicAuth: { username, password }

    # Optional: Iceberg warehouse object storage (S3-compatible). Separate from Nessie REST auth above.
    # Set accessKeySecretRef and secretAccessKeySecretRef together.
    # If namespace is omitted, defaults to the DataFlow namespace and values use secretKeyRef (recommended).
    # If namespace points elsewhere, the operator reads those Secrets at reconcile time and sets literal env on the Deployment (values appear in the Deployment object in the API).
    # Credential refs stay as refs inside mounted spec JSON for Nessie sink (plaintext keys do not go through resolve into ConfigMap for these fields).
    # s3Endpoint: "https://storage.yandexcloud.net"
    # s3Region: "ru-central1"
    # accessKeySecretRef:
    #   name: iceberg-s3-creds
    #   key: AWS_ACCESS_KEY_ID
    # secretAccessKeySecretRef:
    #   name: iceberg-s3-creds
    #   key: AWS_SECRET_ACCESS_KEY
```

### Features

- **Branch context**: Writes are committed to the specified Nessie branch via the catalog.
- **Batch appends**: Groups messages; flush when batch size or timer (10s) is reached. Size only: `batchFlushIntervalSeconds: 0`. Timer only: `batchSize: 0`
- **Auto-create table**: When `autoCreateTable: true`, creates an Iceberg table if missing. Default: one `data` (string) column. With `rawMode: true`: `data` and `_metadata` (string) columns — see [rawMode and `_metadata`](#rawmode-and-_metadata-column-sink-only).
- **Authentication**: Same as source (Bearer or Basic).
- **Warehouse object storage**: Optional static credentials for the Parquet warehouse (`accessKeySecretRef` + `secretAccessKeySecretRef`) set iceberg-go / AWS SDK env (`AWS_S3_ENDPOINT`, `AWS_REGION` when `s3Endpoint` / `s3Region` are set). Same-namespace refs use `secretKeyRef`; other namespaces are resolved by the operator into Deployment env literals. Changing a referenced Secret triggers reconcile via normal Secret watches.

### Horizontal scaling (`spec.replicas`)

Nessie is a **polling** source. The processor Deployment follows `spec.replicas` (default `1`).

| `spec.source.type` | `spec.replicas` | Behavior |
|--------------------|-----------------|----------|
| `kafka` | `> 1` allowed | Consumer group assigns topic partitions across pods. Nessie sink can run on multiple pods only in this case (each pod writes batches independently). |
| `nessie` (or any other polling source) | must be `1` or unset | Admission webhook rejects `replicas > 1`. Multiple pods would share one checkpoint ConfigMap and **duplicate** reads/writes. |
| any ( **DataFlowCron** ) | must be `1` or unset | One processor Job per schedule tick; `replicas > 1` is always rejected. |

`incrementalBySnapshot` on the Nessie source improves restart behavior (checkpoint by Iceberg snapshot) but **does not** replace Kafka-style horizontal scaling.

For higher throughput with Nessie sink, tune `batchSize`, `batchFlushIntervalSeconds`, and `channelBufferSize` instead of increasing `replicas`. Details: [fault tolerance — horizontal scaling](fault-tolerance.md#horizontal-scaling-specreplicas), [architecture — CRD](architecture.md#custom-resource-definition-crd).

### rawMode and `_metadata` column (sink only)

`rawMode` is configured on the **sink** (`sink.config.rawMode`). It is **not** available on the Nessie source.

Iceberg schema when `autoCreateTable: true` and `rawMode: true`:

| Column | Iceberg type | Content |
|--------|--------------|---------|
| `data` | string | Payload JSON (message body) |
| `_metadata` | string | JSON object with lineage fields (Kafka offset, partition, topic, etc.) |

Unlike PostgreSQL sink raw mode (`data` / `_metadata` as **JSONB**), Nessie stores both fields as **string** columns containing JSON text.

**How messages are mapped on write**

1. **Plain message** — `msg.Data` is the payload; `msg.Metadata` (for example from Kafka source) is serialized into `_metadata`:

   ```json
   {"id": 1, "event": "login"}
   ```

   → `data` = body JSON, `_metadata` = `{"offset":100,"partition":0,"topic":"events",...}`

2. **Pre-wrapped message** — body already has `value` and `_metadata` keys (common when chaining from another rawMode sink):

   ```json
   {"value": {"id": 1}, "_metadata": {"offset": 10, "topic": "t1"}}
   ```

   → inner `value` → `data` column, inner `_metadata` → `_metadata` column (same convention as Trino/PostgreSQL rawMode).

**Existing tables**

- With `rawMode: true`, `Connect` validates that the table has both `data` and `_metadata` string-compatible columns (case-insensitive). Otherwise the processor fails fast.
- A table created without `_metadata` cannot be used with `rawMode: true` until you recreate it or add the column manually.

**Reading back (Nessie source)**

The source does not unwrap `rawMode`; it emits one JSON object per row with Iceberg column names. A row from a rawMode table looks like:

```json
{"data": "{\"id\":1}", "_metadata": "{\"offset\":100,\"topic\":\"events\"}"}
```

Parse `data` / `_metadata` in the downstream sink if you need structured fields.

#### flattenMetadataColumns — flat metadata columns (sink)

Supported on **PostgreSQL**, **Trino**, **ClickHouse**, and **Nessie** sinks when `rawMode: true`.

When `flattenMetadataColumns: true`, each key from `msg.Metadata` is written to a **separate** column instead of a JSON `_metadata` column. Optional `flattenMetadataColumnsPrefix` is prepended to column names (for example `kafka_` + `offset` → `kafka_offset`).

| Parameter | Description |
|-----------|-------------|
| `flattenMetadataColumns` | `true` — expand metadata into columns |
| `flattenMetadataColumnsPrefix` | Column name prefix (for example `kafka_`) |

With `autoCreateTable: true`, the schema is `data` (string) plus columns for metadata keys from the **first** batch (types inferred: int/long/string/bool/timestamp). The metadata key `timestamp` (for example `kafka_timestamp` with prefix `kafka_`) is stored as **timestamptz** (Kafka source provides `time.Time` in UTC). Legacy string timestamps in metadata are parsed when possible. The `_metadata` column is **not** created. New metadata keys in later batches are skipped (warning logged).

Tables with an `_metadata` column are **incompatible** with `flattenMetadataColumns: true` — recreate the table or use a new table name.

**Reading (Nessie source):** rows with `data` and prefixed columns (without `_metadata`) are emitted as `{"value": ..., "_metadata": ...}`; metadata fields are also copied to `msg.Metadata`.

### Example: Kafka to Nessie (Iceberg)

```yaml
apiVersion: dataflow.dataflow.io/v1
kind: DataFlow
metadata:
  name: kafka-to-nessie
spec:
  source:
    type: kafka
    config:
      brokers:
        - kafka:9092
      topic: input-topic
      consumerGroup: dataflow-group
  sink:
    type: nessie
    config:
      baseURL: "http://nessie:19120"
      branch: main
      namespace: analytics
      table: events
      batchSize: 100
      autoCreateTable: true
      rawMode: true
      flattenMetadataColumns: true
      flattenMetadataColumnsPrefix: kafka_
```

## Error Sink

DataFlow Operator supports configuring a separate sink for messages that failed to be written to the main sink. The `errors` section uses the same connector types (Kafka, PostgreSQL, Trino, ClickHouse, Nessie) as the main sink.

For configuration, error message structure, and error types, see [Error Handling](errors.md).

## Performance Recommendations

### Spec-level settings

#### channelBufferSize

Buffer size for message channels between source, processor, and sink (default 100). For high Kafka throughput (tens of thousands msg/s), increase to 500–1000 to reduce blocking when the sink is slower than the source.

#### ackGranularity

When source offsets / checkpoints are committed relative to sink writes: `batch` (default) or `message`. With `message`, batch sinks flush one row at a time and Kafka source commits offsets immediately after each ack. See [Fault Tolerance — Ack granularity](fault-tolerance.md#ack-granularity-specackgranularity).

#### checkpointSyncOnAck and checkpointSaveInterval

`checkpointSyncOnAck: true` flushes polling checkpoints to the ConfigMap after each sink ack (coalesced by `checkpointSaveInterval`, default `30s`). Recommended for migration and cron workloads. Details: [Fault Tolerance](fault-tolerance.md#sync-checkpoint-on-ack-speccheckpointsynconack).

### Kafka

- Use multiple brokers for fault tolerance
- Configure an appropriate consumer group size for parallel processing
- Use batch writes for higher throughput

### PostgreSQL

- Increase `batchSize` for the sink (recommended 50–100)
- Add indexes on frequently queried columns
- Tune `pollInterval` based on data update frequency

## Troubleshooting

### Connection issues

1. Verify data source accessibility from the cluster
2. Ensure credentials are correct
3. Check Kubernetes network policies
4. For TLS, verify certificates

### Performance issues

1. Increase `channelBufferSize` (500–1000) for high Kafka load
2. Increase batch sizes for sinks
3. Tune `pollInterval` for sources
4. For Kafka sources, increase `spec.replicas` (up to topic partition count). For Nessie and other polling sources, keep `replicas: 1` and tune `batchSize` / `channelBufferSize` instead
5. Monitor message processing metrics

