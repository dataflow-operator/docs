# Connector Development with baseConnector

A detailed guide for adding new connectors to DataFlow Operator using the shared `baseConnector` pattern.

## Overview

All connectors (ClickHouse, PostgreSQL, Kafka, Trino, Nessie) share a common pattern for synchronizing `Connect` and `Close` methods:

- `sync.Mutex` (or `sync.RWMutex`) to protect state
- A `closed` flag for idempotent `Close` and blocking `Connect` after close
- The same sequence: `Lock` → check `closed` → logic → `Unlock`

To avoid duplication, connectors embed `baseConnector` or `baseConnectorRWMutex`.

## baseConnector and baseConnectorRWMutex

### baseConnector (sync.Mutex)

Used for most connectors where read operations do not require a separate lock.

**Methods:**

| Method | Description |
|--------|-------------|
| `guardConnect() bool` | Acquires lock. Returns `false` if connector is already closed. When `true`, caller holds lock and must call `Unlock()` |
| `guardClose() bool` | Acquires lock. Returns `true` if already closed (idempotent). When `false`, sets `closed=true`, caller holds lock |
| `Unlock()` | Releases lock |
| `Lock()` | Manually acquires lock (for operations like `readRows` that need to hold the lock) |

### baseConnectorRWMutex (sync.RWMutex)

Used when the connector performs long-running read operations (e.g., SQL queries) and `Connect`/`Close` should not block during those operations.

**Additional methods:**

| Method | Description |
|--------|-------------|
| `RLock()` | Acquires read lock |
| `RUnlock()` | Releases read lock |
| `Closed() bool` | Returns `closed` (must be called while holding RLock) |

## Step-by-Step Guide: Adding a New Connector

### Step 1. Define Types

Define your connector's config struct. The factory unmarshals `Config` (`*runtime.RawExtension`) into it at runtime:

```go
// MyDBSourceSpec defines MyDB source configuration
type MyDBSourceSpec struct {
    ConnectionString string `json:"connectionString"`
    Table            string `json:"table"`
    // ...
}
```

Users specify the connector in a DataFlow manifest with `type` + `config`:

```yaml
source:
  type: mydb
  config:
    connectionString: "mydb://localhost:3306/db"
    table: my_table
```

`SourceSpec` and `SinkSpec` hold `Type string` and `Config *runtime.RawExtension`. The API has no `source.mydb` field: the factory and the webhook unmarshal `Config.Raw` into your spec struct. A new type ships only when the operator and CLI binaries are rebuilt.

### Step 2. Choose baseConnector or baseConnectorRWMutex

**Use `baseConnector`** when:

- The connector does not perform long-running read operations under lock
- Or read operations modify state (e.g., `lastReadID`) and require exclusive access

**Use `baseConnectorRWMutex`** when:

- The connector performs long-running read operations (DB queries)
- These operations only read `conn` and `closed`, do not modify them
- You need `Connect`/`Close` to not block during queries

### Step 3. Implement Source Connector

#### With baseConnector (simple case)

```go
// internal/connectors/mydb.go

package connectors

import (
    "context"
    "fmt"
    v1 "github.com/dataflow-operator/dataflow/api/v1"
    "github.com/dataflow-operator/dataflow/internal/types"
    "github.com/go-logr/logr"
)

type MyDBSourceConnector struct {
    baseConnector
    config *v1.MyDBSourceSpec
    conn   *MyDBConnection
    logger logr.Logger
}

func NewMyDBSourceConnector(config *v1.MyDBSourceSpec) *MyDBSourceConnector {
    return &MyDBSourceConnector{
        config: config,
        logger: logr.Discard(),
    }
}

func (c *MyDBSourceConnector) SetLogger(logger logr.Logger) {
    c.logger = logger
}

func (c *MyDBSourceConnector) Connect(ctx context.Context) error {
    if !c.guardConnect() {
        return fmt.Errorf("connector is closed")
    }
    defer c.Unlock()

    c.logger.Info("Connecting to MyDB", "table", c.config.Table)
    conn, err := connectToMyDB(ctx, c.config.ConnectionString)
    if err != nil {
        return fmt.Errorf("failed to connect: %w", err)
    }
    c.conn = conn
    c.logger.Info("Successfully connected to MyDB", "table", c.config.Table)
    return nil
}

func (c *MyDBSourceConnector) Read(ctx context.Context) (<-chan *types.Message, error) {
    if c.conn == nil {
        return nil, fmt.Errorf("not connected, call Connect first")
    }
    // ... read implementation
    return msgChan, nil
}

func (c *MyDBSourceConnector) Close() error {
    if c.guardClose() {
        return nil
    }
    defer c.Unlock()

    c.logger.Info("Closing MyDB source connection", "table", c.config.Table)
    if c.conn != nil {
        return c.conn.Close()
    }
    return nil
}
```

#### With baseConnectorRWMutex (long-running reads)

When `readRows` runs a long query and should not block `Connect`/`Close`:

```go
type MyDBSourceConnector struct {
    baseConnectorRWMutex
    config *v1.MyDBSourceSpec
    conn   *MyDBConnection
    logger logr.Logger
}

func (c *MyDBSourceConnector) readRows(ctx context.Context, msgChan chan *types.Message) {
    // RLock — does not block Connect/Close
    c.RLock()
    if c.Closed() {
        c.RUnlock()
        return
    }
    conn := c.conn
    c.RUnlock()

    if conn == nil {
        return
    }

    // Long query runs WITHOUT holding the lock
    rows, err := conn.QueryContext(ctx, "SELECT * FROM ...")
    // ...
}
```

### Step 4. Implement Sink Connector

```go
type MyDBSinkConnector struct {
    baseConnector
    config *v1.MyDBSinkSpec
    conn   *MyDBConnection
    logger logr.Logger
}

func (c *MyDBSinkConnector) Connect(ctx context.Context) error {
    if !c.guardConnect() {
        return fmt.Errorf("connector is closed")
    }
    defer c.Unlock()

    c.logger.Info("Connecting to MyDB", "table", c.config.Table)
    conn, err := connectToMyDB(ctx, c.config.ConnectionString)
    if err != nil {
        return fmt.Errorf("failed to connect: %w", err)
    }
    c.conn = conn
    return nil
}

func (c *MyDBSinkConnector) Write(ctx context.Context, messages <-chan *types.Message) error {
    // ... write implementation
}

func (c *MyDBSinkConnector) Close() error {
    if c.guardClose() {
        return nil
    }
    defer c.Unlock()

    c.logger.Info("Closing MyDB sink connection", "table", c.config.Table)
    if c.conn != nil {
        return c.conn.Close()
    }
    return nil
}
```

### Step 5. Raw Mode Support (optional, sink connectors only)

For sink connectors, you can add raw mode — storing messages as `{"value": ..., "_metadata": {...}}`:

1. Add `RawMode *bool` field with tag `json:"rawMode,omitempty"` to the sink spec
2. When writing messages, check `config.RawMode != nil && *config.RawMode`
3. When rawMode is true, wrap plain incoming data using `msg.Metadata` for `_metadata` (see PostgreSQL/ClickHouse/Trino sink implementations)

Note: rawMode is supported only in sink connectors. Sources always emit plain columnar format.

### Step 6. Registration

`CreateSourceConnector` and `CreateSinkConnector` look up a map. Unmarshalling is done by `createSourceConnector`, `createSourceConnectorWithOptions`, and `createSinkConnector`. The factory has no `switch` on `source.Type`.

Source metadata is one call in the `init` of `api/v1/provider_registry.go`. Registering the same type again panics.

```go
providers.RegisterSource(providers.SourceDefinition{
    Type:               "mydb",
    SupportsCheckpoint: true,
    Exhausts:           true,
    ValidateConfig: func(raw []byte, path *field.Path) field.ErrorList {
        return validateSourceConfig(raw, "mydb", path, validateMyDBSource)
    },
})

providers.RegisterSink(providers.SinkDefinition{
    Type: "mydb",
    ValidateConfig: func(raw []byte, path *field.Path) field.ErrorList {
        return validateSinkConfig(raw, "mydb", path, validateMyDBSink)
    },
})
```

Add `validateMyDBSource` / `validateMyDBSink` next to the other validators in `dataflow_validation.go`.

The factory is the `init` in `internal/connectors/provider_registrations.go`. Every current source receives `SourceConnectorOptions` (the checkpoint store). `registerSourceConnector` does not write `pkg/providers`: the admission registration already created the record. `init` panics when a type has no factory or a factory has no catalog entry.

```go
registerSourceConnector("mydb", createSourceConnectorWithOptions[v1.MyDBSourceSpec](
    "mydb source",
    func(cfg *v1.MyDBSourceSpec, opts *SourceConnectorOptions) SourceConnector {
        return NewMyDBSourceConnectorWithOptions(cfg, opts)
    },
))

registerSinkConnector("mydb", createSinkConnector[v1.MyDBSinkSpec](
    "mydb sink",
    func(cfg *v1.MyDBSinkSpec) SinkConnector { return NewMyDBSinkConnector(cfg) },
))
```

If the source does not use options, use `createSourceConnector[v1.MyDBSourceSpec]`.

The CLI has no separate type list. `dataflow-cli run` calls `pkg/run`, which imports the processor, which imports `internal/connectors`.

### Step 7. `run --once`

Mark a finite polling source with `Exhausts: true` on the same `SourceDefinition`. `pkg/run.SourceExhausts` reads that field. Checkpoint does not imply it: CDC checkpoints and sets `Exhausts` to false. `TestSourceExhausts` is built from `providers.ListSourceTypes()`.

### Step 8. Schema catalog and published lists

Add a sample to `sourceEntries` and `sinkEntries` in `hack/genschemas/main.go`. `task schemas` checks those slices against `providers.ListSourceTypes()` and `ListSinkTypes()`.

Update the tables in `docs/docs/{ru,en}/connectors.md`, `docs/provider-types-inventory.md`, `dataflow-mcp/src/tools/reference.rs`, and `CONNECTOR_TYPES` in `dataflow-web/web/src/composables/useFlowManifest.js`.

```bash
task generate
task manifests
task schemas
task test-unit
python3 scripts/check_provider_types_drift.py
```

## Important Notes

### Connect Call Order

```go
if !c.guardConnect() {
    return fmt.Errorf("connector is closed")
}
defer c.Unlock()
// ... connection logic
```

- `guardConnect()` returns `false` → connector is closed, return
- `guardConnect()` returns `true` → hold lock, always `defer c.Unlock()`

### Close Call Order

```go
if c.guardClose() {
    return nil  // already closed, idempotent
}
defer c.Unlock()
// ... close connection
```

- `guardClose()` returns `true` → already closed, return `nil`
- `guardClose()` returns `false` → sets `closed=true`, hold lock, close resources

### Using Lock() for readRows

When `readRows` modifies connector state (e.g., `lastReadID`) and needs exclusive access:

```go
func (p *PostgreSQLSourceConnector) readRows(ctx context.Context, msgChan chan *types.Message) {
    p.Lock()
    defer p.Unlock()
    // ... read and update lastReadID
}
```

### Testing

Add tests for:

- `Close` when already closed (idempotency)
- `Connect` after `Close` (should return error)
- Connector creation and initial state

```go
func TestMyDBSourceConnector_Close_WhenAlreadyClosed(t *testing.T) {
    conn := NewMyDBSourceConnector(spec)
    conn.SetLogger(logr.Discard())
    require.NoError(t, conn.Close())
    require.NoError(t, conn.Close()) // second call — no error
}

func TestMyDBSourceConnector_Connect_WhenClosed(t *testing.T) {
    conn := NewMyDBSourceConnector(spec)
    conn.SetLogger(logr.Discard())
    conn.closed = true
    err := conn.Connect(context.Background())
    require.Error(t, err)
    assert.Contains(t, err.Error(), "closed")
}
```

## See Also

- [Adding a New Connector](development.md#adding-a-new-connector) — general section in the development guide
- [Connector interfaces](https://github.com/dataflow-operator/dataflow/blob/main/internal/connectors/interface.go) — `SourceConnector` and `SinkConnector`
- [baseConnector](https://github.com/dataflow-operator/dataflow/blob/main/internal/connectors/base.go) — source code
