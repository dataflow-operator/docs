# Provider Types Inventory and Drift

This document captures all current "lists of truth" where DataFlow provider/transformer types are enumerated.

## 1) Go runtime factories

### Source connectors

File: `dataflow/internal/connectors/factory.go` (`sourceConnectorRegistry`)

Types:
- `kafka`
- `postgresql`
- `trino`
- `clickhouse`
- `nessie`

### Sink connectors

File: `dataflow/internal/connectors/factory.go` (`sinkConnectorRegistry`)

Types:
- `kafka`
- `postgresql`
- `trino`
- `clickhouse`
- `nessie`

### Transformers

File: `dataflow/internal/transformers/factory.go` (`transformerRegistry`)

Types:
- `timestamp`
- `flatten`
- `filter`
- `mask`
- `router`
- `select`
- `remove`
- `snakeCase`
- `camelCase`

## 2) Admission validation lists

File: `dataflow/api/v1/dataflow_validation.go`

- `validSourceTypes`: `kafka`, `postgresql`, `trino`, `clickhouse`, `nessie`
- `validSinkTypes`: `kafka`, `postgresql`, `trino`, `clickhouse`, `nessie`
- `validTransformationTypes`: `timestamp`, `flatten`, `filter`, `mask`, `router`, `select`, `remove`, `snakeCase`, `camelCase`

Notes:
- File comments already state "must match factory", confirming duplicated source-of-truth.
- Validation also duplicates per-type handling in `switch` blocks for source/sink/transformations.

## 3) Processor checkpoint type list

File: `dataflow/internal/processor/options.go` (`checkpointSourceTypes`)

Types currently checkpoint-enabled:
- `postgresql`
- `clickhouse`
- `trino`

Notes:
- This is a separate behavior list independent from connector registry.
- `kafka` and `nessie` are not checkpoint-enabled by this map.

## 4) MCP type lists

File: `dataflow-mcp/src/types.rs`

- `SOURCE_TYPES`: `kafka`, `postgresql`, `trino`, `clickhouse`
- `SINK_TYPES`: `kafka`, `postgresql`, `trino`, `clickhouse`

Consumer of these constants:
- `dataflow-mcp/src/tools/manifest.rs` (`generate_dataflow_manifest`, `validate_dataflow_manifest`)

## 5) Documentation type lists

Primary connector matrix docs:
- `docs/docs/en/connectors.md`
- `docs/docs/ru/connectors.md`

Current docs connector set:
- `kafka`
- `postgresql`
- `trino`
- `clickhouse`
- `nessie`

Related API commentary:
- `dataflow/api/v1/dataflow_types.go` comments mention `kafka`, `postgresql`, `trino`, `clickhouse`, `nessie`, "or plugin type".

## Current drift (confirmed)

`nessie` is present in:
- Go factories (`dataflow/internal/connectors/factory.go`)
- Admission validation (`dataflow/api/v1/dataflow_validation.go`)
- Documentation (`docs/docs/en/connectors.md`, `docs/docs/ru/connectors.md`)

But `nessie` is absent in MCP hardcoded lists:
- `dataflow-mcp/src/types.rs` (`SOURCE_TYPES`/`SINK_TYPES`)

Practical impact:
- MCP tooling rejects/omits `nessie` as source/sink type even though operator runtime and webhook validation support it.
