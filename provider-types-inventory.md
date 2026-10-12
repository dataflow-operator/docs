# Provider Types Inventory and Drift

This document captures all current "lists of truth" where DataFlow provider/transformer types are enumerated.

**Machine-readable catalog (preferred for agents/CI):** [`schemas/catalog.json`](../schemas/catalog.json) — generated from Go (`task schemas` in `dataflow/`).  
CI: `.github/workflows/provider-types-drift.yml` + `scripts/check_provider_types_drift.py`.

## 1) Go runtime factories

### Source connectors

Registered in `dataflow/internal/connectors/provider_registrations.go` (`init`); lookup maps live in `dataflow/internal/connectors/factory.go` (`sourceConnectorRegistry`).

Types:
- `kafka`
- `postgresql`
- `postgresql-cdc`
- `trino`
- `clickhouse`
- `nessie`
- `iceberg`
- `hive`

### Sink connectors

Registered in `dataflow/internal/connectors/provider_registrations.go` (`init`); lookup maps live in `dataflow/internal/connectors/factory.go` (`sinkConnectorRegistry`).

Types:
- `kafka`
- `postgresql`
- `trino`
- `clickhouse`
- `nessie`
- `iceberg`
- `hive`

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
- `headersToPayload`
- `structFlatten`
- `extractField`
- `hoistField`
- `cast`
- `timezone`
- `insertField`

## 2) Admission validation (Kubernetes webhook / CRD validation)

### Connector types and config validators

Runtime lists and validators are registered in **`dataflow/pkg/providers`** (`RegisterSource`, `RegisterSink`, `ListSourceTypes`, `ListSinkTypes`, `SourceValidator`, `SinkValidator`).

Per-type `ValidateConfig` hooks are wired in **`dataflow/api/v1/provider_registry.go`** (`init`), delegating to the typed validators in **`dataflow/api/v1/dataflow_validation.go`** (e.g. `validateKafkaSource`, `validateKafkaSink`).

Admission logic in **`dataflow/api/v1/dataflow_validation.go`** (`validateSource`, `validateSink`):

- Resolves allowed source/sink types via `providers.ListSourceTypes()` / `providers.ListSinkTypes()`.
- Runs `providers.SourceValidator(type)` / `providers.SinkValidator(type)` on `spec.*.config` raw JSON.

Typed config structs (source of truth for **JSON Schema** under `schemas/connectors/`) live in **`dataflow/api/v1/dataflow_types.go`**.

### Transformation types

File: **`dataflow/pkg/transformtypes/transformtypes.go`**

- Allowed keys: `transformtypes.All()` / `transformtypes.IsRegistered(type)`.
- **`dataflow/api/v1/dataflow_validation.go`** (`validateTransformations`) checks membership then validates config per type (including nested sinks for `router`).

Notes:

- Connector runtime factories (`dataflow/internal/connectors/provider_registrations.go`) and provider validators (`provider_registry.go`) must agree on the same type strings.
- Transformation factory (`internal/transformers/factory.go`) and `transformtypes` must stay aligned.
- `dataflow/hack/genschemas` fails if its type→struct map drifts from `providers` / `transformtypes`.

## 3) Checkpoint and one-shot eligibility

Both flags are fields of the single source record in **`dataflow/api/v1/provider_registry.go`** (`providers.SourceDefinition`):

- `SupportsCheckpoint`
- `Exhausts` — the source closes its read channel after a finite snapshot (`dataflow-cli run --once`)

`providers.RegisterSource` panics on a duplicate type or a missing validator. Runtime factories in **`dataflow/internal/connectors/provider_registrations.go`** do not register metadata again. Process startup panics if those factories are not exactly `providers.ListSourceTypes()` / `ListSinkTypes()`.

| source | checkpoint | exhausts |
| --- | --- | --- |
| `kafka` | no | no |
| `postgresql` | yes | yes |
| `postgresql-cdc` | yes | no |
| `trino` | yes | yes |
| `clickhouse` | yes | yes |
| `nessie` | yes | yes |
| `iceberg` | yes | yes |
| `hive` | yes | yes |

**`dataflow/internal/processor/options.go`** (`buildSourceConnectorOptions`) gates checkpoint wiring with **`providers.SourceSupportsCheckpoint`**. **`dataflow/pkg/run/exhaust.go`** (`SourceExhausts`) reads **`providers.SourceExhausts`**.

## 4) MCP reference and shallow YAML validation

### Connector / transformation reference JSON

File: **`dataflow-mcp/src/tools/reference.rs`**

- `default_connectors_raw()` — documented fields for **list_dataflow_connectors** (sources/sinks). Must match `schemas/catalog.json` keys.
- `default_transformations_raw()` — **list_dataflow_transformations**.

### Manifest tools

File: **`dataflow-mcp/src/tools/manifest.rs`**

- **`generate_dataflow_manifest`** — builds YAML from arbitrary `source_type` / `sink_type` strings plus optional JSON configs (`build_connector_spec` does not mirror operator provider lists).
- **`validate_dataflow_manifest`** — shallow checks only (`apiVersion`, `kind`, presence of `spec.source` / `spec.sink`, non-empty `type`, and presence of `config`); it does **not** reject unknown connector types or deep-validate connector fields like the operator webhook.

## 5) Documentation type lists

Primary connector matrix docs:
- `docs/docs/en/connectors.md`
- `docs/docs/ru/connectors.md`

Transformation reference (Wave 1 + Wave 2 types):
- `docs/docs/en/transformations.md`
- `docs/docs/ru/transformations.md`

Current docs connector set (overview table):
- `kafka`
- `postgresql`
- `postgresql-cdc`
- `trino`
- `clickhouse`
- `nessie`
- `iceberg`
- `hive`

Related API commentary:
- `dataflow/api/v1/dataflow_types.go` comments mention `kafka`, `postgresql`, `trino`, `clickhouse`, `nessie`, "or plugin type".

JSON Schemas for agents/IDE:
- `schemas/dataflow.json`, `schemas/dataflowcron.json` (CRD OpenAPI export)
- `schemas/connectors/{sources,sinks}/<type>.json`
- `schemas/transforms/<type>.json`

## 6) Web UI flow constructor

File: **`dataflow-web/web/src/composables/useFlowManifest.js`** (`TRANSFORM_TYPES`, `CONNECTOR_TYPES`)

Must stay aligned with `transformtypes.All()` / MCP `default_transformations_raw()` / `schemas/catalog.json`:

- `timestamp`, `flatten`, `filter`, `mask`, `router`, `select`, `remove`, `snakeCase`, `camelCase`
- `debeziumUnwrap`, `replaceField`, `headersToPayload`, `structFlatten`
- `extractField`, `hoistField`, `cast`, `timezone`, `insertField`

Related UI surfaces (forms + locales):

- `dataflow-web/web/src/components/config-forms/TransformationConfigForm.vue`
- `dataflow-web/web/src/components/config-forms/useConfigForm.js`
- `dataflow-web/web/src/locales/en.js` / `ru.js`

## Drift policy

1. Change Go registries / typed structs.
2. Run `cd dataflow && task schemas` (updates `schemas/`).
3. Update MCP `reference.rs`, docs overview tables, and this inventory if needed.
4. CI `provider-types-drift` must pass (catalog ↔ docs ↔ MCP ↔ inventory ↔ web).

**MCP validation vs operator webhook**

**`validate_dataflow_manifest`** does not enforce the provider allow-list or field-level rules from **`dataflow_validation.go`**. Invalid manifests may pass MCP validation yet fail on `kubectl apply` when the validating webhook is enabled. Prefer JSON Schemas + `kubectl apply --dry-run=server`.

**Kafka Connect migration**

**`migrate_kafka_connect_to_dataflow`** targets Kafka ↔ JDBC-style PostgreSQL flows; other connector combinations still require manual manifests even when the operator supports them.
