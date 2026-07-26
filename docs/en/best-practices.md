# Best Practices

Guidelines for designing, deploying, and operating DataFlow Operator to achieve optimal performance, reliability, and security.

## Pipeline Design

### Choosing Between DataFlow and DataFlowCron

**Use DataFlow when:**
- Continuous streaming is needed
- Source is Kafka (streaming)
- Low latency is required
- There is no explicit "end" to the data stream

**Use DataFlowCron when:**
- Task needs to run on a schedule
- Source is a polling database (PostgreSQL, ClickHouse, Trino, Nessie)
- Post-processing steps (triggers) are needed
- Process has a beginning and end (batch processing)

### Pipeline Architecture

**1. Single Responsibility**
Each DataFlow should solve one task:
```yaml
# Good: clear purpose
name: user-events-enrichment
source: kafka://user-events
sink: postgresql://analytics.users

# Bad: mixing purposes
name: everything-pipeline
source: kafka://all-topics  # Too broad
```

**2. Intermediate Topics**
For complex routes, use Kafka as an intermediate buffer:
```
DataFlow A: Source → Kafka Topic A
DataFlow B: Kafka Topic A → Transform → Kafka Topic B
DataFlow C: Kafka Topic B → Sink
```

**3. Error Handling Strategy**
```yaml
# Always configure error sink for production
spec:
  errors:
    type: kafka
    config:
      brokers: [kafka:9092]
      topic: error-messages-${ENV}
    ackPolicy: afterWrite
```

## Security

### Secrets Management

**Never store credentials in manifests:**
```yaml
# Bad: plaintext credentials
sink:
  config:
    connectionString: "postgres://user:password@host/db"  # ❌

# Good: SecretRef
sink:
  config:
    connectionStringSecretRef:
      name: db-credentials
      key: connection-string
```

**Creating Secrets:**
```bash
# Create secret from literal
kubectl create secret generic db-credentials \
  --from-literal=connection-string="postgres://user:pass@host/db" \
  --from-literal=password="secure-password"

# Or from file
echo -n "secure-password" > password.txt
kubectl create secret generic db-credentials \
  --from-file=password=password.txt
rm password.txt
```

### TLS/SSL Configuration

**Always use TLS for production Kafka:**
```yaml
source:
  type: kafka
  config:
    securityProtocol: SASL_SSL
    tls:
      caFile: /etc/certs/ca.crt
      certFile: /etc/certs/client.crt
      keyFile: /etc/certs/client.key
    sasl:
      mechanism: scram-sha-512
      usernameSecretRef:
        name: kafka-credentials
        key: username
      passwordSecretRef:
        name: kafka-credentials
        key: password
```

**Mounting Certificates:**
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: kafka-certs
type: Opaque
data:
  ca.crt: <base64-encoded>
  client.crt: <base64-encoded>
  client.key: <base64-encoded>
```

### Network Policies

**Restrict network access:**
```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: dataflow-processor
spec:
  podSelector:
    matchLabels:
      app: dataflow-processor
  policyTypes:
    - Ingress
    - Egress
  egress:
    - to:
        - podSelector:
            matchLabels:
              app: kafka
      ports:
        - protocol: TCP
          port: 9092
    - to:
        - podSelector:
            matchLabels:
              app: postgresql
      ports:
        - protocol: TCP
          port: 5432
```

## Performance

### Batch Size Optimization (SQL sinks)

Physical write-batch size (`sink.config.batchSize`) and source ack timing (`spec.ackGranularity`) are **separate knobs**. With default `collapseBatchOnMessageAck: true`, `ackGranularity: message` still forces `MaxBatchSize = 1` — set `collapseBatchOnMessageAck: false` if you need bulk SQL writes **and** per-message source commit. Details: [Fault Tolerance — decoupling ack and sink batch](fault-tolerance.md#decoupling-ack-and-sink-batch-speccollapsebatchonmessageack).

| Sink | Runtime default (если `batchSize` не задан) | Recommended | Admission warning if set below |
|------|----------------------|-------------|-------------------------------|
| PostgreSQL | **100** (`sinkbatch.DefaultPostgreSQLBatchSize`) | 100–500 (up to ~1000) | &lt; 100 |
| ClickHouse | **500** (`sinkbatch.DefaultClickHouseBatchSize`) | 500–1000 | &lt; 500 |
| Trino | **10** (`sinkbatch.DefaultTrinoBatchSize`) | ≥ 10 (keep modest for large JSON / Iceberg) | &lt; 10 |

`sink.config` is unstructured (`RawExtension`), so these floors are applied by the **processor** when the field is omitted — not by CRD OpenAPI defaulting. Single source of truth: `dataflow/pkg/sinkbatch`. `batchSize: 0` means flush **only by timer** (`batchFlushIntervalSeconds`, default **10** via `sinkbatch.DefaultBatchFlushIntervalSeconds`). Explicit values below the recommended floor produce an admission **warning** (not a reject).

#### How each SQL sink writes

**PostgreSQL**

- Accumulates up to `batchSize` (or flush interval), then runs **one transaction**.
- Flush path (automatic): `COPY FROM` for homogeneous plain `INSERT` (no `ON CONFLICT`); else one multi-row `INSERT … VALUES` (including `ON CONFLICT` / upsert); mixed `UPDATE`/heterogeneous shapes use `pgx.Batch`.
- Source ack runs **only after** a successful Commit (`AckAfterSuccessfulWrite`).
- One DB connection per sink pod (`pgx.Connect`, not a pool). Prefer larger batches over parallel connections.
- Soft-delete is queued into the same batch TX (forces `pgx.Batch` for that flush).

```yaml
sink:
  type: postgresql
  config:
    batchSize: 500
    batchFlushIntervalSeconds: 10
    upsertMode: true
    conflictKey: id
```

**ClickHouse**

- Default batch **500**. Flush uses native `PrepareBatch` when available; otherwise one multi-row `INSERT … VALUES` via Exec.
- Source ack runs **once** after a successful flush (not mid-batch). That preserves at-least-once if the flush fails partway.
- Raw mode writes `message.Data` as-is (no JSON Unmarshal→Marshal on the insert path).
- Large batches reduce insert frequency and help avoid `TOO_MANY_PARTS`. Prefer `batchFlushIntervalSeconds: 5–10` with `batchSize` 500–1000.

```yaml
sink:
  type: clickhouse
  config:
    batchSize: 1000
    batchFlushIntervalSeconds: 5
    upsertMode: true
    conflictKey: id
```

**Trino**

- Default batch **10**. Each flush is one HTTP statement (multi-row `INSERT ... VALUES`) plus `nextUri` polling until `FINISHED`.
- Upsert uses **`MERGE`** (Iceberg catalogs) — slower than plain INSERT; admission warns when `upsertMode: true`. Keep batches modest and set `queryTimeoutSeconds` to cover the full poll window.
- Prefer multi-row INSERT for throughput; use MERGE only when you need idempotent updates.

```yaml
sink:
  type: trino
  config:
    batchSize: 10
    batchFlushIntervalSeconds: 10
    queryTimeoutSeconds: 600
    # upsertMode: true   # MERGE slow-path — only when needed
    # conflictKey: id
```

#### Tuning checklist

1. Start from the defaults above; raise PG/CH batch sizes under sustained load until latency or memory bounds appear.
2. Pair Kafka high volume with `ackGranularity: batch` **or** `message` + `collapseBatchOnMessageAck: false`.
3. For ClickHouse `TOO_MANY_PARTS`, increase `batchSize` / flush interval before lowering concurrency.
4. For Trino Iceberg/Nessie, keep `batchSize` small enough that one statement finishes within `queryTimeoutSeconds`.
5. For Nessie/Iceberg sources, enable `incrementalBySnapshot` and optionally `maxRowsPerPoll` / `maxBytesPerPoll` on large tables.

### Configurable vs automatic (throughput)

| Knob | Where | Notes |
|------|--------|--------|
| `channelBufferSize`, `transformWorkers`, `ackGranularity`, `collapseBatchOnMessageAck` | DataFlow `spec` | Pipeline backpressure and ack vs write batch |
| `checkpointSyncOnAck`, `checkpointSaveInterval` | DataFlow `spec` | Checkpoint flush policy; sync-on-ack flush is **async/coalesced** (does not block the ack path on ConfigMap Patch) |
| Sink `batchSize`, `batchFlushIntervalSeconds` | sink `config` | Physical write batch |
| Kafka `async`, `compression`, `flush*` | Kafka sink `config` | Defaults: `async=true`, `compression=snappy`, flush 100 msgs / 100ms |
| `incrementalBySnapshot`, `maxRowsPerPoll`, `maxBytesPerPoll` | Nessie/Iceberg source `config` | Snapshot incremental + poll caps |
| PG `COPY` vs multi-VALUES vs `pgx.Batch` | Automatic | Chosen per flush shape |
| CH `PrepareBatch` vs Exec | Automatic | Native driver when available |
| Lakehouse file-delta / parquet fast path | Automatic | When incremental mode finds added files without deletes |

### Buffer Sizing

Channels between source, transform, and sink are **buffered and blocking** (default size 100). A larger buffer absorbs short sink stalls. Watch `dataflow_channel_fill_ratio{channel="source|routing|…"}` for sustained saturation (CDC and lakehouse sources sample the source channel). Sink flush already overlaps the next batch (double-buffer). For CPU-heavy transforms, raise `transformWorkers` (ordered emit). Details: [Architecture — Pipeline concurrency](architecture.md#pipeline-concurrency-implementation).

**Channel Buffer:**
```yaml
spec:
  # For normal load
  channelBufferSize: 100  # default
  
  # For high-volume streams
  channelBufferSize: 1000
  
  # For limited memory
  channelBufferSize: 50
```

**Transform workers (in-pod parallelism):**
```yaml
spec:
  transformWorkers: 4  # default 1; range 1–64
```

Use `replicas > 1` only with a **Kafka** source. For polling/CDC sources keep `replicas: 1` and raise `readBatchSize` / sink `batchSize` / `resources` / `transformWorkers` instead.

### Resource Allocation

**Baseline Resources:**
```yaml
spec:
  resources:
    requests:
      cpu: "200m"
      memory: "256Mi"
    limits:
      cpu: "1000m"
      memory: "512Mi"
```

**High-Volume Processing:**
```yaml
spec:
  resources:
    requests:
      cpu: "1000m"
      memory: "1Gi"
    limits:
      cpu: "2000m"
      memory: "2Gi"
```

**Resource Guidelines:**
| Scenario | CPU Request | Memory Request | CPU Limit | Memory Limit |
|----------|-------------|----------------|-----------|--------------|
| Light load | 100m | 128Mi | 500m | 256Mi |
| Normal load | 200m | 256Mi | 1000m | 512Mi |
| Heavy load | 500m | 512Mi | 2000m | 1Gi |
| High volume | 1000m | 1Gi | 2000m | 2Gi |

### Polling Source Optimization

**PostgreSQL Source:**
```yaml
source:
  type: postgresql
  config:
    # Frequent poll for real-time
    pollInterval: 5  # seconds
    
    # Rare poll for batch
    pollInterval: 300  # 5 minutes
    
    # Batch read size
    readBatchSize: 1000
    
    # Column for change tracking
    changeTrackingColumn: updated_at
    orderByColumn: id
```

## Fault Tolerance

### Idempotency Configuration

**Always configure idempotency:**
```yaml
spec:
  sink:
    type: postgresql
    config:
      upsertMode: true
      conflictKey: id
```

**Different Upsert Strategies:**

PostgreSQL:
```yaml
sink:
  type: postgresql
  config:
    upsertMode: true
    conflictKey: id
    upsertStrategy: ifNewer  # or replace
    upsertVersionColumn: updated_at
```

ClickHouse:
```yaml
sink:
  type: clickhouse
  config:
    upsertMode: true
    conflictKey: id
    replacingVersionColumn: updated_at
    tableEngine: ReplacingMergeTree
```

### Checkpoint Configuration

**Polling Sources (PostgreSQL, ClickHouse, Trino):**
```yaml
spec:
  checkpointPersistence: true  # default
  checkpointSyncOnAck: true   # for critical data
  checkpointSaveInterval: 30s
```

**Kafka Source:**
```yaml
spec:
  # checkpointPersistence not needed for Kafka
  # uses consumer group offset
  ackGranularity: message              # faster offset commit
  collapseBatchOnMessageAck: false     # keep sink.config.batchSize for throughput
```

Details: [Fault Tolerance — decoupling ack and sink batch](fault-tolerance.md#decoupling-ack-and-sink-batch-speccollapsebatchonmessageack).

### Graceful Shutdown

**Termination Grace Period:**
```yaml
spec:
  # Enough time to flush batch
  terminationGracePeriodSeconds: 600
```

**PreStop Hook:**
```yaml
lifecycle:
  preStop:
    exec:
      command: ["/bin/sh", "-c", "sleep 30"]
```

### Dead Letter Queue Pattern

```yaml
spec:
  errors:
    type: kafka
    config:
      brokers: [kafka:9092]
      topic: dlq-${ENV}
    ackPolicy: afterWrite
  transformations:
    - type: filter
      config:
        condition: "$.required_field"  # Check required fields
```

## Monitoring

### Key Metrics to Watch

**Throughput:**
```
dataflow_processed_messages_total
rate(dataflow_processed_messages_total[5m])
```

**Error Rate:**
```
dataflow_errors_total
rate(dataflow_errors_total[5m])
```

**Lag (for Kafka):**
```
kafka_consumer_group_lag
```

**Latency:**
```
dataflow_processing_duration_seconds
```

### Health Checks

**Liveness Probe:**
```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8080
  initialDelaySeconds: 30
  periodSeconds: 30
```

**Readiness Probe:**
```yaml
readinessProbe:
  httpGet:
    path: /ready
    port: 8080
  initialDelaySeconds: 10
  periodSeconds: 10
```

### Alerting Rules

**Prometheus Alerts:**
```yaml
groups:
  - name: dataflow
    rules:
      - alert: DataFlowHighErrorRate
        expr: rate(dataflow_errors_total[5m]) > 0.1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High error rate in DataFlow"
          
      - alert: DataFlowNoMessages
        expr: rate(dataflow_processed_messages_total[10m]) == 0
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "DataFlow stopped processing messages"
          
      - alert: DataFlowKafkaLagHigh
        expr: kafka_consumer_group_lag > 10000
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Kafka consumer lag is high"
```

## Operations

### Deployment Strategy

**Canary Deployment:**
```bash
# 1. Create new DataFlow with different name
kubectl apply -f dataflow-canary.yaml

# 2. Check metrics
kubectl top pods -l app=dataflow-processor

# 3. Delete old and rename canary
kubectl delete dataflow old-pipeline
kubectl patch dataflow canary-pipeline -p '{"metadata":{"name":"new-pipeline"}}'
```

**Blue-Green Deployment:**
```yaml
# blue.yaml
metadata:
  name: pipeline-blue
  labels:
    version: blue

# green.yaml
metadata:
  name: pipeline-green
  labels:
    version: green
```

### Backup and Recovery

**Backup Checkpoint ConfigMap:**
```bash
# Export checkpoint
kubectl get configmap df-<name>-checkpoint -o yaml > checkpoint-backup.yaml

# Restore
kubectl apply -f checkpoint-backup.yaml
```

**Reset Checkpoint:**
```yaml
# One-shot reset
spec:
  checkpointReset: true
```

### Maintenance Windows

**Scheduled Maintenance:**
```yaml
spec:
  maintenance:
    - startTime: "2024-01-15T02:00:00Z"
      duration: 2h
      repeat: weekly
      timezone: UTC
```

**Manual Suspension:**
```yaml
spec:
  suspended: true
```

## Testing

### Unit Testing Transformations

**Test JSONPath Expressions:**
```bash
# Use gjson cli or online playground
echo '{"user":{"active":true}}' | gjson "user.active"
# Output: true
```

### Integration Testing

**Test DataFlow:**
```bash
# 1. Create DataFlow for test
kubectl apply -f test-dataflow.yaml

# 2. Send test message
echo '{"test": true}' | kafka-console-producer --topic test-topic

# 3. Check result
kubectl logs -l app=dataflow-processor --tail=10

# 4. Clean up
kubectl delete dataflow test-dataflow
```

### Load Testing

**Generate Load:**
```bash
# Use kcat or kafka-producer-perf-test
kafka-producer-perf-test \
  --topic test-topic \
  --num-records 1000000 \
  --record-size 1000 \
  --throughput 10000 \
  --producer-props bootstrap.servers=localhost:9092
```

**Monitor Resources:**
```bash
watch kubectl top pods -l app=dataflow-processor
```

## Production Checklist

### Pre-Deployment
- [ ] Correct Kind version (DataFlow vs DataFlowCron)
- [ ] Secrets via `*SecretRef` (not plaintext)
- [ ] Idempotent sink: `upsertMode: true` + `conflictKey`
- [ ] For polling/cron: `checkpointSyncOnAck: true` + upsert
- [ ] `replicas: 1` for non-Kafka sources
- [ ] For CPU-heavy transforms: `transformWorkers` tuned (keep `1` if transforms are cheap)
- [ ] Error sink configured
- [ ] Resources (requests/limits) set
- [ ] `batchSize` / `ackGranularity` / `collapseBatchOnMessageAck` balanced (message ack does not have to mean `batchSize: 1`)
- [ ] For Trino: `queryTimeoutSeconds` with margin

### Post-Deployment
- [ ] Pod in Running status
- [ ] Metrics for processing/published messages
- [ ] No errors in logs
- [ ] Monitoring and alerts configured
- [ ] Alerting rules active
- [ ] Backup checkpoint configured

### Security
- [ ] TLS for Kafka
- [ ] Network Policies applied
- [ ] RBAC configured
- [ ] Secrets rotated
- [ ] Security headers checked

### Documentation
- [ ] Manifest documented
- [ ] Architecture diagram updated
- [ ] Runbook created
- [ ] Contact list for on-call
