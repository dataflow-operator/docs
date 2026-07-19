# Provider Types Inventory and Drift

This document captures all current "lists of truth" where DataFlow provider/transformer types are enumerated.

## 1) Go runtime factories

### Source connectors

Registered in `dataflow/internal/connectors/provider_registrations.go` (`init`); lookup maps live in `dataflow/internal/connectors/factory.go` (`sourceConnectorRegistry`).

Types:
- `kafka`
- `postgresql`
- `trino`
- `clickhouse`
- `nessie`

### Sink connectors

Registered in `dataflow/internal/connectors/provider_registrations.go` (`init`); lookup maps live in `dataflow/internal/connectors/factory.go` (`sinkConnectorRegistry`).

Types:
- `kafka`
- `postgresql`
- `trino`
- `clickhouse`
- `nessie`

### Transformers

File: `dataflow/internal/transformers/factory.go` (`transformerRegistry`)

Canonical keys also live in `dataflow/pkg/transformtypes/transformtypes.go` (`keys` / `All()`), shared with API validation.

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
- `debeziumUnwrap`
- `replaceField`

## 2) Admission validation (Kubernetes webhook / CRD validation)

### Connector types and config validators

Runtime lists and validators are registered in **`dataflow/pkg/providers`** (`RegisterSource`, `RegisterSink`, `ListSourceTypes`, `ListSinkTypes`, `SourceValidator`, `SinkValidator`).

Per-type `ValidateConfig` hooks are wired in **`dataflow/api/v1/provider_registry.go`** (`init`), delegating to the typed validators in **`dataflow/api/v1/dataflow_validation.go`** (e.g. `validateKafkaSource`, `validateKafkaSink`).

Admission logic in **`dataflow/api/v1/dataflow_validation.go`** (`validateSource`, `validateSink`):

- Resolves allowed source/sink types via `providers.ListSourceTypes()` / `providers.ListSinkTypes()`.
- Runs `providers.SourceValidator(type)` / `providers.SinkValidator(type)` on `spec.*.config` raw JSON.

### Transformation types

File: **`dataflow/pkg/transformtypes/transformtypes.go`**

- Allowed keys: `transformtypes.All()` / `transformtypes.IsRegistered(type)`.
- **`dataflow/api/v1/dataflow_validation.go`** (`validateTransformations`) checks membership then validates config per type (including nested sinks for `router`).

Notes:

- Connector runtime factories (`dataflow/internal/connectors/provider_registrations.go`) and provider validators (`provider_registry.go`) must agree on the same type strings.
- Transformation factory (`internal/transformers/factory.go`) and `transformtypes` must stay aligned.

## 3) Processor checkpoint eligibility

File: **`dataflow/internal/connectors/provider_registrations.go`** — third argument to `registerSourceConnector(..., supportsCheckpoint bool)`.

Checkpoint-enabled sources today:

- `postgresql`
- `trino`
- `clickhouse`

Not checkpoint-enabled:

- `kafka`
- `nessie`

At runtime, **`dataflow/internal/processor/options.go`** (`buildSourceConnectorOptions`) gates checkpoint wiring with **`providers.SourceSupportsCheckpoint(sourceType)`**, which reflects the merged registration metadata in **`dataflow/pkg/providers`**.

## 4) MCP reference and shallow YAML validation

### Connector / transformation reference JSON

File: **`dataflow-mcp/src/tools/reference.rs`**

- `default_connectors_raw()` — documented fields for **list_dataflow_connectors** (sources/sinks).
- `default_transformations_raw()` — **list_dataflow_transformations** (includes `debeziumUnwrap`, `replaceField`).

### Manifest tools

File: **`dataflow-mcp/src/tools/manifest.rs`**

- **`generate_dataflow_manifest`** — builds YAML from arbitrary `source_type` / `sink_type` strings plus optional JSON configs (`build_connector_spec` does not mirror operator provider lists).
- **`validate_dataflow_manifest`** — shallow checks only (`apiVersion`, `kind`, presence of `spec.source` / `spec.sink`, non-empty `type`, and presence of `config`); it does **not** reject unknown connector types or deep-validate connector fields like the operator webhook.

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

**MCP connector reference vs operator**

`nessie` is supported by the operator (connector registry + `provider_registry.go` validators + docs matrix), but **`reference.rs` `default_connectors_raw()`** does not document `nessie` under sources or sinks. **`list_dataflow_connectors`** can therefore under-report capabilities compared to the cluster webhook.

**MCP validation vs operator webhook**

**`validate_dataflow_manifest`** does not enforce the provider allow-list or field-level rules from **`dataflow_validation.go`**. Invalid manifests may pass MCP validation yet fail on `kubectl apply` when the validating webhook is enabled.

**Kafka Connect migration**

**`migrate_kafka_connect_to_dataflow`** targets Kafka ↔ JDBC-style PostgreSQL flows; other connector combinations still require manual manifests even when the operator supports them.
