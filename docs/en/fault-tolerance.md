# Fault Tolerance and Data Consistency

DataFlow Operator processes messages with **at-least-once** delivery semantics. When the processor pod crashes or restarts, some messages may be re-read and written again. This document explains the behavior, risks of data desynchronization, and how to configure idempotent sinks to prevent duplicates.

## Delivery Semantics

- **At-least-once**: Each message is delivered at least once. Duplicates are possible on processor restart or crash.
- **Exactly-once**: Not supported natively. Use idempotent sinks to achieve effectively-once semantics.

## Source Behavior on Restart

| Source | State storage | On restart |
|--------|---------------|------------|
| **Kafka** | Consumer group (Kafka) | Resumes from last committed offset. No duplicates if offset was committed after sink write. |
| **PostgreSQL** | In-memory (lastReadChangeTime) | State lost. Re-reads from beginning. Duplicates or gaps possible. |
| **ClickHouse** | In-memory (lastReadID, lastReadTime) | State lost. Re-reads from beginning. Duplicates possible. |
| **Trino** | In-memory (lastReadID) | State lost. Re-reads from beginning. Duplicates possible. |

### Kafka Source

The Kafka consumer commits offset **only after** the message is successfully written to the sink (via `msg.Ack()`). If the processor crashes:

- **Before sink write**: Offset not committed. On restart, message is re-read. No duplicate in sink.
- **After sink write, before Ack**: Data may be in sink, offset not committed. On restart, re-read → duplicate in sink.
- **After Ack**: Offset committed. On restart, resume from next message. No duplicate.

### Polling Sources (PostgreSQL, ClickHouse, Trino)

Read position (lastReadID, lastReadChangeTime) is stored **only in memory**. On pod crash:

- State is lost.
- On restart, the source re-reads from the beginning (or from a wrong position).
- **Duplicates** or **gaps** are possible depending on when the crash occurred.

!!! warning "Idempotent sink required"
    For polling sources, always configure an **idempotent sink** (UPSERT, ReplacingMergeTree) to handle duplicates safely.

## Batch Sink Behavior

PostgreSQL, ClickHouse, and Trino sinks write in batches. The flow is:

1. Accumulate messages in batch
2. Execute `Commit` (transaction)
3. Call `Ack()` for each message (commits Kafka offset, if applicable)

If the processor crashes **between Commit and the last Ack**:

- Data is already in the sink
- Kafka offset may not be committed
- On restart: re-read from Kafka → **duplicate writes to sink**

!!! tip "Reduce duplicate window"
    Use a smaller `batchSize` to reduce the number of messages at risk of duplication on crash.

## Idempotent Sink Configuration

### PostgreSQL Sink

Enable UPSERT mode so that duplicate inserts update existing rows instead of failing:

```yaml
sink:
  type: postgresql
  postgresql:
    connectionString: "postgres://..."
    table: output_table
    upsertMode: true
    conflictKey: ["id"]  # Optional; defaults to PRIMARY KEY
```

Requires the table to have a PRIMARY KEY or UNIQUE constraint on the conflict columns.

### ClickHouse Sink

Use `ReplacingMergeTree` engine for automatic deduplication by a version column:

```sql
CREATE TABLE output_table (
  id UInt64,
  data String,
  created_at DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(created_at)
ORDER BY id;
```

Or create the table with `autoCreateTable: true` and `rawMode: false` — the connector infers column types. For deduplication, create the table manually with `ReplacingMergeTree(version_column)` and `ORDER BY` on the deduplication key.

### Kafka Sink

The Kafka producer uses `RequiredAcks = WaitForAll` and `Producer.Idempotent = true` for durability and to prevent duplicate messages on retry. Consumers should still handle potential duplicates (e.g., by idempotent processing or deduplication by key) for end-to-end exactly-once semantics.

## Best Practices

1. **Use idempotent sinks** for PostgreSQL (UPSERT) and ClickHouse (ReplacingMergeTree) when using polling sources or when duplicates are possible.
2. **Kafka source**: Consumer group stores offset; at-least-once is preserved. Idempotent sink recommended for batch sinks.
3. **batchSize**: Smaller batches reduce the duplicate window on crash. Balance with throughput.
4. **batchFlushIntervalSeconds**: Shorter intervals flush more frequently, reducing in-flight data at risk.
5. **Error sink**: Configure `spec.errors` to capture failed messages for replay or analysis.

## Graceful Shutdown

On SIGTERM (e.g., pod eviction, node drain):

1. The processor receives the signal and cancels the context.
2. Sinks flush in-flight batches before exiting.
3. `PreStop: sleep 5` gives time for the load balancer to stop routing traffic.

Ensure `terminationGracePeriodSeconds` is sufficient for large batches to flush (default: 600 seconds).

## Checkpoint Persistence (Future)

Persisting source checkpoint (lastReadID, lastReadChangeTime) to external storage (ConfigMap or sink table) would allow polling sources to resume from the last committed position after a processor restart, reducing duplicates. This is planned for a future release. Until then, use idempotent sinks to handle duplicates safely.

## Summary Checklist

| Scenario | Recommendation |
|----------|-----------------|
| PostgreSQL sink | Enable `upsertMode: true` with PRIMARY KEY or `conflictKey` |
| ClickHouse sink | Use `ReplacingMergeTree` with `ORDER BY` on deduplication key |
| Kafka source | Consumer group persists offset; idempotent sink recommended |
| Polling sources | **Always** use idempotent sink; state is lost on crash |
| batchSize | Consider smaller values to reduce duplicate window |
