# Architecture

This section describes how the DataFlow Operator works: its role in Kubernetes, the reconciliation model, and the runtime data flow inside each processor.

## Overview

The DataFlow Operator provides **declarative management of data pipelines** via Kubernetes Custom Resources. You define a pipeline with a source, optional transformations, and a sink; the operator ensures a **processor** workload runs in the cluster.

Two CRDs orchestrate pipelines differently:

| CRD | Workload | Doc |
|-----|----------|-----|
| **DataFlow** | Long-lived Deployment | [DataFlow](dataflow/index.md) |
| **DataFlowCron** | CronJob + Jobs per tick | [DataFlowCron](dataflow-cron/index.md) |

See [Workload Types](concepts/workload-types.md) for when to use each.

High-level flow for **DataFlow**:

1. You create or update a **DataFlow** (e.g. with `kubectl apply`).
2. The **operator** creates or updates a **ConfigMap** (resolved spec) and a **Deployment** (processor pod).
3. Each **processor pod** runs the pipeline: read → transform → write.

### Data Flow Pipeline (Conceptual)

The data flow in each processor follows a linear pipeline: **Source** → **Transformations** → **Sink**. Optionally, failed writes go to an **Error Sink**.

```mermaid
flowchart LR
  subgraph Input[" "]
    Source["Source\n(Kafka / PostgreSQL / Trino / ClickHouse / Nessie)"]
  end

  subgraph Transform[" "]
    T1["Transform 1"]
    T2["Transform 2"]
    TN["Transform N"]
    T1 --> T2 --> TN
  end

  subgraph Output[" "]
    MainSink["Main Sink"]
    ErrSink["Error Sink\n(optional)"]
  end

  Source -->|"read"| T1
  TN -->|"write"| MainSink
  TN -.->|"on failure"| ErrSink
```

Transformations are applied in list order on each message (`timestamp`, `flatten`, `filter`, …). Multiple messages may be transformed in parallel when `spec.transformWorkers > 1`; sink order is preserved. See [Pipeline concurrency](#pipeline-concurrency-implementation).

## Kubernetes Architecture

### Custom Resources

- **API group**: `dataflow.dataflow.io`
- **`DataFlow`** (`dataflows`) — continuous processor via Deployment. Details: [DataFlow Spec](dataflow/spec.md), [Lifecycle](dataflow/lifecycle.md).
- **`DataFlowCron`** (`dataflowcrons`) — scheduled runs via CronJob, optional [triggers](dataflow-cron/triggers.md). Details: [DataFlowCron Spec](dataflow-cron/spec.md).

Secrets are referenced via `SecretRef` in the spec; the operator resolves them before writing the spec into the ConfigMap.

### Operator Deployment

The operator runs as a **Deployment** in the cluster (e.g. installed via Helm). It uses **controller-runtime** with **DataFlowReconciler** and **DataFlowCronReconciler**. **Leader election** (ID `dataflow-operator.dataflow.io`) ensures only one active leader reconciles when multiple operator replicas run.

### Controllers

**DataFlowReconciler**:

- **Watches**: `DataFlow` (primary), owns `Deployment` and `ConfigMap`.
- Optionally watches the operator Deployment to roll processor images on operator upgrade.

**DataFlowCronReconciler**:

- **Watches**: `DataFlowCron`, manages `CronJob`, spec ConfigMap, processor Jobs, and trigger Jobs.

Reconciliation details: [DataFlow Lifecycle](dataflow/lifecycle.md), [DataFlowCron Spec](dataflow-cron/spec.md).

### RBAC

The operator **ClusterRole** allows read/write on CRDs and status, secret resolution, and create/update/delete of ConfigMaps, Deployments, CronJobs, Jobs, and processor RBAC. See Helm templates for exact rules.

### Optional: GUI

The Helm chart can deploy an optional **GUI** (separate Deployment, Service, Ingress) for viewing and managing data flows.

### Admission Webhook (Validating)

When enabled, the operator validates **DataFlow** and **DataFlowCron** specs at admission (port 9443) — rejecting invalid source/sink types, transformations, schedule, or triggers **before** resources are stored.

**Why it matters:** without the webhook, invalid specs fail at runtime in processor pods. With the webhook, `kubectl apply` gets an immediate error.

**Optional:** controlled by Helm `webhook.enabled` (default disabled). See [Configuring the Validating Webhook](development.md#configuring-the-validating-webhook).

---

## Architecture Diagram (Kubernetes)

```mermaid
flowchart LR
  User["User (kubectl)"]
  API["API Server"]
  CRD["DataFlow / DataFlowCron"]
  Operator["Operator Pod"]
  CMSpec["ConfigMap spec"]
  Workload["Deployment or CronJob"]
  Proc["Processor Pod"]
  Ext["Kafka / PostgreSQL / Trino / Nessie"]

  User -->|"apply CR"| API
  API --> CRD
  Operator -->|watch| CRD
  Operator -->|create/update| CMSpec
  Operator -->|create/update| Workload
  Workload --> Proc
  Proc -->|mount spec| CMSpec
  Proc -->|connect| Ext
```

---

## Data Processor (Runtime)

The **processor** moves data: read from source, apply transformations, write to sink(s). It runs in pods created by the operator (Deployment or CronJob Job).

### Entrypoint

The processor binary is started with:

- `--spec-path` (default `/etc/dataflow/spec.json`)
- `--namespace`, `--name` (resource namespace and name for logging and metrics)

It reads the spec, builds a **Processor**, and runs `Processor.Start(ctx)` until the context is cancelled or the source is exhausted.

### Processor Structure

The **Processor** contains:

- **Source**: SourceConnector (Kafka, PostgreSQL, Trino, ClickHouse, Nessie) — `Connect`, `Read`, `Close`.
- **Sink**: SinkConnector for the main destination.
- **Error sink** (optional): for failed writes.
- **Transformations**: ordered Transformer implementations.
- **Router sinks**: dynamic sinks when a `router` transformation is used.

Polling sources with checkpoint load/persist position from a ConfigMap when `checkpointPersistence` is enabled.

### Execution Flow

1. **Connect** — source, sink, optional error sink.
2. **Read** — `source.Read(ctx)` returns a channel of messages.
3. **Process** — apply transformations in order; filter/flatten/router may change message count or routing metadata.
4. **Write** — route to main sink, router sinks, or error sink on failure.

### Pipeline concurrency (implementation)

Inside a single processor pod the pipeline is **stage-pipelined via Go channels**. Transform CPU work can run on a worker pool; sink flush overlaps with the next batch accumulation (double-buffer).

```mermaid
flowchart LR
  Src[Source.Read]
  MsgChan["msgChan\n(buffered)"]
  Proc["transformWorkers\n(default 1, ordered emit)"]
  ProcChan["processedChan\n(buffered)"]
  Write["writeMessages\n(1 loop / route)"]
  Sink["RunBatchWriteLoop\n(double-buffer flush)"]

  Src --> MsgChan --> Proc --> ProcChan --> Write --> Sink
```

| Stage | Implementation | Concurrency |
|-------|----------------|-------------|
| Source → processor | `source.Read` fills `msgChan` | Source-owned; buffer from `channelBufferSize` (default **100**) |
| Transform | `processMessages` | `transformWorkers` goroutines (default **1**); chain `0..N` per message; **reorder buffer** preserves emit order |
| Processor → sink | `processedChan` | Blocking send: full buffer stops transform (backpressure) |
| Sink write | `RunBatchWriteLoop` | One write loop; **at most one** `OnFlush` in flight while the next batch accumulates |
| Router | Per-condition channel + goroutine | Fan-out across route sinks; **each** route still has one write loop |

**`transformWorkers`.** Raise above `1` for CPU-heavy transform chains. Output order to the sink matches input order. Keep `1` when transforms are cheap (pool overhead dominates). Valid range: 1–64.

**Backpressure.** Sends into `msgChan` / `processedChan` block when the buffer is full. There is no drop or unbounded queue. Raise `spec.channelBufferSize` (e.g. 500–1000 for high Kafka volume) only if memory allows. See [Best Practices — Buffer Sizing](best-practices.md#buffer-sizing).

**Ack / ordering.** Source ack is a **barrier**: the parent message is marked done only after every derived output is acked (1→N fan-out). Filter drops (0 outputs) ack immediately. With `transformWorkers > 1`, a reorder buffer ensures sink writes and ack eligibility still follow input sequence.

**Ack vs sink batch size.** `spec.ackGranularity` controls *when* source progress is committed (`batch` vs `message`). Separately, `spec.collapseBatchOnMessageAck` (default `true`) decides whether `message` ack also forces sink `MaxBatchSize = 1`. Set it to `false` to keep bulk sink writes while still acking each message after a successful flush. Details: [Fault Tolerance — decoupling ack and sink batch](fault-tolerance.md#decoupling-ack-and-sink-batch-speccollapsebatchonmessageack).

**Double-buffer flush.** While batch N is flushing, the loop continues reading into batch N+1 (memory bounded to one in-flight flush + one active batch). Flush/ack order is preserved. Connectors that use a custom write loop (e.g. PostgreSQL) are unchanged until they adopt the same pattern.

**SQL sink defaults.** When `batchSize` is omitted, the processor uses PostgreSQL **100**, ClickHouse **500**, Trino **10**. Admission warns when an explicit value is below the recommended floor. ClickHouse acks source offsets only after a successful `Commit`. Details: [Best Practices — Batch Size Optimization](best-practices.md#batch-size-optimization-sql-sinks).

**Horizontal scale (`replicas`).** Admission allows `replicas > 1` **only for Kafka** sources. Polling, CDC, Iceberg/Nessie, and plugin sources must stay at **1** replica — scale via `resources`, `channelBufferSize`, `transformWorkers`, and `readBatchSize` / `batchSize`. `DataFlowCron` always rejects `replicas > 1`.

**Code anchors:** `dataflow/internal/processor/process_transform.go`, `dataflow/internal/connectors/batch_writer.go` (`RunBatchWriteLoop`), `dataflow/api/v1/dataflow_types.go` (`transformWorkers`), `dataflow/api/v1/dataflow_validation.go`.

### Connector Execution Model (optional: subprocess)

When `DATAFLOW_USE_SUBPROCESS_CONNECTORS=1`, connectors run as separate binaries via stdin/stdout JSON Lines protocol. See [Connector Protocol](connector-protocol.md).

### Connectors and Transformations

- **Source/Sink types**: Kafka, PostgreSQL, Trino, ClickHouse, Nessie — see [Connectors](connectors.md).
- **Transformations** — see [Transformations](transformations.md).

### Data Flow in the Processor (Diagram)

```mermaid
flowchart LR
  Src[Source Connector]
  ReadChan[Read Channel]
  Trans[Transform 1 .. N]
  Write[writeMessages]
  MainSink[Main Sink]
  ErrSink[Error Sink]
  RouteSinks[Router Sinks]

  Src -->|Connect, Read| ReadChan
  ReadChan --> Trans
  Trans --> Write
  Write --> MainSink
  Write --> ErrSink
  Write --> RouteSinks
```

---

## Summary

- **DataFlow**: operator reconciles to ConfigMap + Deployment; processor runs continuously.
- **DataFlowCron**: operator reconciles to ConfigMap + CronJob; processor runs per schedule tick; optional trigger Jobs after success.
- **Runtime**: same processor pipeline — source → transformations → sinks; optional transform worker pool with ordered emit and double-buffered sink flush (see [Pipeline concurrency](#pipeline-concurrency-implementation)).

## See also

- [DataFlow](dataflow/index.md) · [DataFlowCron](dataflow-cron/index.md)
- [Workload Types](concepts/workload-types.md)
- [Getting Started](getting-started.md)
- [Best Practices](best-practices.md) — `channelBufferSize`, `transformWorkers`, batch sizes, `replicas`
