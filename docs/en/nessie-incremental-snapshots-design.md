# Design notes: incremental Nessie reads by snapshot

This document proposes an optional incremental mode for `nessie` source to avoid full-table re-scan on every poll.

## Problem

Current `nessie` source behavior:

- each poll executes `Refresh` + full `Scan().ToArrowTable`;
- already exported rows can be emitted again;
- large Iceberg tables create high read cost and duplicate traffic.

For append-heavy streams this is inefficient. We need a branch-aware "read only new snapshots" mode.

## Goals

- Keep existing behavior as default (no breaking changes).
- Add opt-in incremental mode based on Iceberg snapshot progression.
- Persist progress in the existing checkpoint store to survive restarts.
- Keep at-least-once delivery semantics (advance checkpoint only after sink `Ack`).

## Non-goals

- Exactly-once guarantees across source and sink.
- Row-level diff/CDC for updates and deletes in v1.
- Rework of Nessie sink write path.

## API proposal

Add optional fields to `NessieSourceSpec`:

- `incrementalBySnapshot` (`bool`, default `false`)  
  Enables incremental reads by snapshot lineage.
- `startSnapshotID` (`string`, optional)  
  Bootstrap point for first run when checkpoint is absent.
- `snapshotCheckpoints` (`bool`, default `true`)  
  Persist processed snapshot state to checkpoint store.

Checkpoint payload (JSON):

```json
{
  "lastAckedSnapshotID": "1234567890123456789",
  "lastAckedSnapshotSequence": 42,
  "branch": "main",
  "namespace": "demo",
  "table": "events"
}
```

### Configuration examples

Minimal opt-in for incremental reads:

```yaml
apiVersion: dataflow.oss.io/v1
kind: DataFlow
metadata:
  name: nessie-incremental-basic
spec:
  source:
    type: nessie
    config:
      baseURL: http://nessie:19120
      branch: main
      namespace: demo
      table: events
      incrementalBySnapshot: true
      pollInterval: 10
  sink:
    type: kafka
    config:
      brokers: ["kafka:9092"]
      topic: demo-events
```

Bootstrap from a specific snapshot on first run:

```yaml
apiVersion: dataflow.oss.io/v1
kind: DataFlow
metadata:
  name: nessie-incremental-from-snapshot
spec:
  source:
    type: nessie
    config:
      baseURL: http://nessie:19120
      branch: main
      namespace: demo
      table: events
      incrementalBySnapshot: true
      startSnapshotID: "1234567890123456789"
      snapshotCheckpoints: true
      pollInterval: 15
  sink:
    type: kafka
    config:
      brokers: ["kafka:9092"]
      topic: demo-events
```

## Read model

### Snapshot discovery

On each poll:

1. `tbl.Refresh(ctx)`;
2. read current table metadata and current snapshot;
3. build ordered snapshot chain from `lastAckedSnapshotID` (exclusive) to current snapshot (inclusive);
4. if chain is empty: return immediately.

### Data extraction

For each snapshot in chain order:

1. create a scan restricted to that snapshot;
2. materialize rows to Arrow;
3. emit messages with metadata:
   - `snapshot_id`
   - `snapshot_sequence`
   - `namespace`
   - `table`
4. attach `Ack` callback that advances in-memory checkpoint candidate.

### Checkpoint commit

- update persisted checkpoint only on `Ack`;
- checkpoint must be monotonic by `snapshot_sequence`;
- if sink fails before `Ack`, snapshot is re-read (acceptable at-least-once behavior).

## Failure and edge cases

- **Branch force-reset / history rewrite**: if `lastAckedSnapshotID` is missing in current lineage, log warning and:
  - default strategy: restart from `startSnapshotID` (if set), otherwise current head (skip historical backfill).
- **No snapshots yet**: no-op poll.
- **Large snapshot**: chunk via existing Arrow-to-message path; keep poll loop cancellable via context.
- **Checkpoint disabled**: incremental mode still works per process lifetime only.

## Validation rules

When `incrementalBySnapshot=true`:

- `query` is rejected for v1 (full-snapshot scan only, no predicate pushdown combination yet).
- `startSnapshotID` must parse as unsigned integer string.

## Provider registration and compatibility

- mark `nessie` source as `SupportsCheckpoint=true`;
- keep old full-scan path when `incrementalBySnapshot=false`;
- no changes required for `nessie` sink.

## Implementation plan

1. Extend `NessieSourceSpec` and validation.
2. Add checkpoint handling in `NessieSourceConnectorWithOptions`.
3. Introduce snapshot-state struct + marshal/unmarshal helpers.
4. Implement snapshot-chain resolution and per-snapshot scan loop.
5. Attach `Ack`-driven checkpoint advance.
6. Add tests (unit + integration-style with mocked snapshot progression).

## Test plan

- **Unit**
  - parse/validate `startSnapshotID`;
  - checkpoint encode/decode and monotonic advance;
  - lineage resolver behavior for linear history, missing base snapshot, empty chain.
- **Connector behavior**
  - `incrementalBySnapshot=false` keeps current full scan behavior;
  - `incrementalBySnapshot=true` emits only snapshots newer than checkpoint;
  - checkpoint advances only after `Ack`.
- **Regression**
  - source factory/options preserve old behavior for non-checkpoint setups.

## Rollout

- ship behind opt-in flag (`incrementalBySnapshot`);
- monitor duplicate rate and source read volume;
- later phase may add delete/update semantics and predicate pushdown.
