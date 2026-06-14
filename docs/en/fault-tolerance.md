# Fault Tolerance and Data Consistency

DataFlow Operator processes messages with **at-least-once** delivery semantics. When the processor pod crashes or restarts, some messages may be re-read and written again. This document explains the behavior, risks of data desynchronization, and how to configure idempotent sinks to prevent duplicates.

## Delivery Semantics

- **At-least-once**: Each message is delivered at least once. Duplicates are possible on processor restart or crash.
- **Exactly-once**: Not supported natively. Use idempotent sinks to achieve effectively-once semantics.

## Source Behavior on Restart

| Source | State storage | On restart |
|--------|---------------|------------|
| **Kafka** | Consumer group (Kafka) | Resumes from last committed offset. No duplicates if offset was committed after sink write. |
| **PostgreSQL** | ConfigMap (default); in-memory when `checkpointPersistence: false` | By default resumes from last position. Without persistence: re-reads from beginning. |
| **ClickHouse** | ConfigMap (default); in-memory when `checkpointPersistence: false` | By default resumes from last position. Without persistence: re-reads from beginning. |
| **Trino** | ConfigMap (default); in-memory when `checkpointPersistence: false` | By default resumes from last position. Without persistence: re-reads from beginning. |
| **Nessie** | ConfigMap when `incrementalBySnapshot: true` and `checkpointPersistence` (default) | Incremental reads along the Iceberg snapshot chain; without `incrementalBySnapshot`, full scan on every poll (no checkpoint). |
| **Iceberg** | ConfigMap when `incrementalBySnapshot: true` and `checkpointPersistence` (default) | Same as Nessie; checkpoint store key is `iceberg`. |

### Horizontal scaling (`spec.replicas`)

- **Kafka**: you may set `spec.replicas > 1`. All pods share one consumer group; parallelism is capped by the topic **partition** count.
- **PostgreSQL, ClickHouse, Trino, Nessie**: `replicas` must be `1` (or unset). Multiple pods with a shared checkpoint ConfigMap will **duplicate** data.
- **DataFlowCron**: `replicas > 1` is not supported (one processor Job per schedule tick).

### Kafka Source

The Kafka consumer marks offset **only after** the message is successfully written to the sink (via `msg.Ack()`). With `ackGranularity: message` (see below), offsets are also committed to the consumer group immediately after each mark.

If the processor crashes:

- **Before sink write**: Offset not committed. On restart, message is re-read. No duplicate in sink.
- **After sink write, before Ack**: Data may be in sink, offset not committed. On restart, re-read → duplicate in sink.
- **After Ack**: Offset marked (and committed when `ackGranularity: message`). On restart, resume from next message. No duplicate.

### Nessie source (incremental mode)

When `source.config.incrementalBySnapshot: true`, the processor reads only **new** Iceberg snapshots since the last `Ack`. Checkpoint (`lastAckedSnapshotID`, `lastAckedSnapshotSequence`) is stored in a ConfigMap when `snapshotCheckpoints` (default) and `spec.checkpointPersistence` are enabled.

See [nessie-incremental-snapshots-design.md](nessie-incremental-snapshots-design.md).

### Polling Sources (PostgreSQL, ClickHouse, Trino)

**Checkpoint persistence** is enabled by default. The read position (`lastReadChangeTime`, `lastReadOrderByValue`) is persisted to ConfigMap `df-<name>-checkpoint`. On restart, the source resumes from the last committed position after sink `Ack`, reducing duplicates. Set `checkpointPersistence: false` in spec to store checkpoint only in memory (lost on pod crash).

Legacy checkpoint keys (`lastReadID`, `lastReadTime`) are migrated on load; see the migration table below.

!!! warning "Idempotent sink required"
    For polling sources, always configure an **idempotent sink** (UPSERT, ReplacingMergeTree) to handle duplicates safely.

## Batch Sink Behavior

PostgreSQL, ClickHouse, and Trino sinks write in batches. The flow is:

1. Accumulate messages in a batch
2. Execute the batch write (PostgreSQL wraps all statements in a single transaction and commits atomically)
3. Call `Ack()` for each message in the batch (commits Kafka offset / advances polling checkpoint)

If the processor crashes **after a successful batch commit but before Ack**:

- Data is already in the sink
- Source offset / checkpoint may not be advanced
- On restart: re-read → **duplicate writes to sink** (safe with an idempotent sink)

!!! tip "Reduce duplicate window"
    Set `ackGranularity: message` to ack after each message (effective `batchSize: 1` for batch sinks), or use a smaller `batchSize` with `ackGranularity: batch` (default).

## Ack Granularity (`spec.ackGranularity`)

Controls when source offsets are committed relative to sink writes:

| Value | Behavior |
|-------|----------|
| `batch` (default) | Batch sinks ack all messages after a successful batch flush. Kafka source relies on consumer auto-commit interval after `MarkMessage`. |
| `message` | Each message is acked immediately after a successful write. Batch sinks flush one message at a time. Kafka source calls `Commit()` after each mark for faster offset persistence. |

Recommended for **Kafka → batch sink** pipelines where you want a smaller re-read window without tuning `batchSize` manually:

```yaml
spec:
  ackGranularity: message
  sink:
    type: postgresql
    config:
      upsertMode: true
      conflictKey: material_id
```

Kafka sink always acks per message regardless of this setting.

!!! tip "Trino long-running INSERTs"
    For large JSON payloads and Iceberg/Nessie tables, keep `batchSize` low (often `1`) and set `sink.config.queryTimeoutSeconds` to cover the full Trino execution window (including `nextUri` polling).
    Timeouts during `nextUri` follow can happen after Trino already started processing the INSERT, so retries may produce duplicates.

## Idempotent Sink Configuration

### PostgreSQL Sink

Enable UPSERT mode so that duplicate inserts update existing rows instead of failing. Batch writes run inside an explicit transaction (all-or-nothing per flush).

```yaml
sink:
  type: postgresql
  config:
    connectionString: "postgres://..."
    table: output_table
    upsertMode: true
    conflictKey: id  # Optional; defaults to PRIMARY KEY
    # Optional: skip stale replays when a version column exists in the payload
    upsertStrategy: ifNewer   # always (default) | ifNewer
    upsertVersionColumn: updated_at  # required when upsertStrategy is ifNewer
```

Requires the table to have a PRIMARY KEY or UNIQUE constraint on the conflict columns. With `upsertStrategy: ifNewer`, updates apply only when `EXCLUDED.<version> > target.<version>`.

### ClickHouse Sink

Enable `upsertMode` for idempotent writes via `ReplacingMergeTree` (auto-created tables use this engine when `upsertMode: true`):

```yaml
sink:
  type: clickhouse
  config:
    connectionString: "clickhouse://..."
    table: output_table
    upsertMode: true
    conflictKey: id
    replacingVersionColumn: updated_at  # optional version column for ReplacingMergeTree
    tableEngine: ReplacingMergeTree     # optional; default when upsertMode is true
```

Or create the table manually:

```sql
CREATE TABLE output_table (
  id UInt64,
  data String,
  created_at DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(created_at)
ORDER BY id;
```

Duplicates may be visible until background merge; use `FINAL` or rely on merge for read-time deduplication.

### Trino Sink

For Iceberg catalogs, enable MERGE-based upsert:

```yaml
sink:
  type: trino
  config:
    serverURL: "http://trino:8080"
    catalog: iceberg   # catalog name must contain "iceberg"
    schema: default
    table: output_table
    upsertMode: true
    conflictKey: id
```

On match, rows are updated; there is no `ifNewer` version guard for Trino yet.

### Kafka Sink

The Kafka producer uses `RequiredAcks = WaitForAll` and `Producer.Idempotent = true` for durability and to prevent duplicate messages on retry. Consumers should still handle potential duplicates (e.g., by idempotent processing or deduplication by key) for end-to-end exactly-once semantics.

## Best Practices

1. **Use idempotent sinks** for PostgreSQL (UPSERT), ClickHouse (`upsertMode` / ReplacingMergeTree), and Trino Iceberg (MERGE) when using polling sources or when duplicates are possible.
2. **Kafka source**: Consumer group stores offset; at-least-once is preserved. Idempotent sink recommended for batch sinks. Use `ackGranularity: message` to shrink the re-read window.
3. **batchSize** / **ackGranularity**: Smaller batches or `ackGranularity: message` reduce the duplicate window on crash. Balance with throughput.
4. **Migration / cron workloads**: combine `checkpointSyncOnAck: true`, idempotent sink, and optionally `upsertStrategy: ifNewer` when a version column exists.
5. **Trino `queryTimeoutSeconds`**: Use a timeout large enough for peak load; too low values increase false failures on long INSERTs.
6. **batchFlushIntervalSeconds**: Shorter intervals flush more frequently, reducing in-flight data at risk.
7. **Error sink**: Configure `spec.errors` to capture failed messages for replay or analysis.

## Graceful Shutdown

On SIGTERM (e.g., pod eviction, node drain):

1. The processor receives the signal and cancels the context.
2. Sinks flush in-flight batches before exiting.
3. `PreStop: sleep 5` gives time for the load balancer to stop routing traffic.

Ensure `terminationGracePeriodSeconds` is sufficient for large batches to flush (default: 600 seconds).

## Checkpoint Persistence

!!! note "Enabled by default"
    The `checkpointPersistence` field in the DataFlow spec defaults to `true`. You do not need to set it explicitly — checkpoint persistence is enabled for all DataFlows with polling sources.

Checkpoint persistence is **enabled by default**. The read position (`lastReadChangeTime`, `lastReadOrderByValue`) is persisted to ConfigMap `df-<name>-checkpoint`. On processor restart, polling sources (PostgreSQL, ClickHouse, Trino) resume from the last committed position, reducing duplicates.

Canonical checkpoint JSON per source type:

```json
{
  "lastReadChangeTime": "2024-06-01T12:00:00.123456789Z",
  "lastReadOrderByValue": 5042
}
```

Legacy formats are normalized on load:

| Legacy | Canonical |
|--------|-----------|
| Trino: `{"lastReadID": 100}` | `{"lastReadOrderByValue": 100}` |
| ClickHouse: `{"lastReadID": 100, "lastReadTime": "..."}` | composite fields above |
| Time-only: `{"lastReadChangeTime": "..."}` | unchanged (single-column WHERE until order key appears) |

After restart, Trino/ClickHouse checkpoints that only had `lastReadID` use order-key filtering (`WHERE orderByColumn > N`) until the first ack with a timestamp; then tuple filtering `(changeTrackingColumn, orderByColumn) > (time, key)` applies.

To disable, set `checkpointPersistence: false`:

```yaml
apiVersion: dataflow.dataflow.io/v1
kind: DataFlow
metadata:
  name: my-dataflow
spec:
  checkpointPersistence: false  # Disable (default: true)
  source:
    type: postgresql
    # ...
```

The controller creates the ConfigMap and RBAC (ServiceAccount, Role, RoleBinding) for the processor. Checkpoint is saved with debounce (every 30 seconds by default) and on graceful shutdown.

### Sync checkpoint on ack (`spec.checkpointSyncOnAck`)

By default, pending checkpoints are flushed to the ConfigMap on a debounce timer (`checkpointSaveInterval`, default `30s`) and on graceful shutdown. After a pod crash, polling sources may re-read up to one debounce interval of data.

Set `checkpointSyncOnAck: true` to flush the checkpoint immediately after each sink batch ack (coalesced, not more often than `checkpointSaveInterval`). Recommended for migration and cron workloads:

```yaml
spec:
  checkpointSyncOnAck: true
  checkpointSaveInterval: 5s
  source:
    type: postgresql
    # ...
  sink:
    type: postgresql
    config:
      upsertMode: true
      conflictKey: material_id
```

## Summary Checklist

| Scenario | Recommendation |
|----------|-----------------|
| PostgreSQL sink | `upsertMode: true` + `conflictKey`; `upsertStrategy: ifNewer` when version column exists |
| ClickHouse sink | `upsertMode: true` or manual `ReplacingMergeTree` + `ORDER BY` dedup key |
| Trino sink (Iceberg) | `upsertMode: true` + `conflictKey` |
| Kafka → batch sink | `ackGranularity: message` or smaller `batchSize` + idempotent sink |
| Kafka source | Idempotent sink; `ackGranularity: message` for faster offset commit |
| Polling sources | Idempotent sink; `checkpointSyncOnAck: true` for migration/cron |
| batchSize | Smaller values or `ackGranularity: message` to reduce duplicate window |
