# Transformations

DataFlow Operator supports message transformations that are applied sequentially to each message in the order specified in the configuration. Transformations use [gjson](https://github.com/tidwall/gjson) JSONPath for field access.

## Transformation Overview

| Transformation | Description | Input | Output |
|----------------|------------|-------|--------|
| Timestamp | Adds a timestamp field | 1 message | 1 message |
| Flatten | Expands an array into separate messages | 1 message | N messages |
| Filter | Keeps messages matching a condition (truthy / `==` / `!=`) | 1 message | 0 or 1 message |
| Mask | Masks sensitive fields | 1 message | 1 message |
| Router | Sends matching messages to alternate sinks | 1 message | 0 or 1 message |
| Select | Keeps only specified fields | 1 message | 1 message |
| Remove | Removes specified fields | 1 message | 1 message |
| SnakeCase | Converts keys to snake_case | 1 message | 1 message |
| CamelCase | Converts keys to CamelCase | 1 message | 1 message |
| DebeziumUnwrap | Unwraps Debezium envelope into row payload | 1 message | 0 or 1 message |
| ReplaceField | Renames fields; optional include/exclude without flattening | 1 message | 1 message |
| HeadersToPayload | Copies Kafka/message headers into JSON payload fields | 1 message | 1 message |
| StructFlatten | Flattens nested JSON objects into a single-level map | 1 message | 1 message |
| ExtractField | Replaces the payload with the value of one field | 1 message | 1 message |
| HoistField | Wraps the entire payload under a single top-level key | 1 message | 1 message |
| Cast | Converts field values to target types (`string` / `int64` / `float64` / `bool` / `null`) | 1 message | 1 message (or skip on cast error) |
| Timezone | Converts temporal fields to a target IANA timezone or UTC offset | 1 message | 1 message (or skip on parse error) |

## Timestamp

Adds a timestamp field to each message. Useful for tracking message processing time.

### Configuration

```yaml
transformations:
  - type: timestamp
    config:
      # Field name for timestamp (optional, default: created_at)
      fieldName: created_at
      # Timestamp format (optional, default: RFC3339)
      format: RFC3339
```

### Format

The `format` value is a [Go time layout](https://pkg.go.dev/time#pkg-constants) string. Default is `RFC3339` (e.g. `2006-01-02T15:04:05Z07:00`). Examples: `RFC3339`, `RFC3339Nano`, or custom layouts like `2006-01-02 15:04:05`.

### Examples

#### Basic usage

```yaml
transformations:
  - type: timestamp
    config:
      fieldName: processed_at
```

**Input message:**
```json
{
  "id": 1,
  "name": "Test"
}
```

**Output message:**
```json
{
  "id": 1,
  "name": "Test",
  "processed_at": "2024-01-15T10:30:00Z"
}
```

#### Custom format

```yaml
transformations:
  - type: timestamp
    config:
      fieldName: timestamp
      format: "2006-01-02 15:04:05"
```

**Output message:**
```json
{
  "id": 1,
  "timestamp": "2024-01-15 10:30:00"
}
```

#### Unix timestamp

```yaml
transformations:
  - type: timestamp
    config:
      fieldName: unix_time
      format: Unix
```

**Output message:**
```json
{
  "id": 1,
  "unix_time": "1705312200"
}
```

## Flatten

Expands an array into separate messages, preserving all other fields from the original message. Each array element is merged into the root; objects are flattened to top-level keys. If the field is not an array, the message is returned unchanged. Supports Avro-style arrays wrapped in an object with an `array` key.

### Configuration

```yaml
transformations:
  - type: flatten
    config:
      # JSONPath to the array to expand (required)
      field: items
```

### Examples

#### Simple flatten

```yaml
transformations:
  - type: flatten
    config:
      field: items
```

**Input message:**
```json
{
  "order_id": 12345,
  "customer": "John Doe",
  "items": [
    {"product": "Apple", "quantity": 5},
    {"product": "Banana", "quantity": 3}
  ]
}
```

**Output messages:**
```json
{
  "order_id": 12345,
  "customer": "John Doe",
  "product": "Apple",
  "quantity": 5
}
```

```json
{
  "order_id": 12345,
  "customer": "John Doe",
  "product": "Banana",
  "quantity": 3
}
```

#### Nested arrays

```yaml
transformations:
  - type: flatten
    config:
      field: orders.items
```

**Input message:**
```json
{
  "customer_id": 100,
  "orders": {
    "items": [
      {"sku": "SKU001", "price": 10.99},
      {"sku": "SKU002", "price": 5.99}
    ]
  }
}
```

**Output messages:**
```json
{
  "customer_id": 100,
  "orders": {},
  "sku": "SKU001",
  "price": 10.99
}
```

#### Combined with other transformations

```yaml
transformations:
  - type: flatten
    config:
      field: rowsStock
  - type: timestamp
    config:
      fieldName: created_at
```

This creates a separate message for each array element, each with an added timestamp.

## Filter

Keeps only messages that match the condition. Others are dropped.

### Condition syntax

Same as [Router](#router):

- **Truthiness**: `$.field` — passes if the field exists and is truthy (boolean `true`, non-empty string, non-zero number).
- **Equality**: `$.field == 'value'` or `$.field == "value"` — passes when the field equals the given value (unquoted literals like `true` / `5` are also accepted).
- **Inequality**: `$.field != 'value'` — passes when the field exists and is not equal to the given value.

Missing fields fail both truthiness and comparison checks.

### Configuration

```yaml
transformations:
  - type: filter
    config:
      # JSONPath truthiness, or comparison with == / != (required)
      condition: "$.status == 'active'"
```

### JSONPath

Uses the `gjson` library: `$.field`, `$.nested.field`, `$.array[0]`, etc. The `$.` prefix is optional.

### Examples

#### Simple filtering (truthiness)

```yaml
transformations:
  - type: filter
    config:
      condition: "$.active"
```

**Input messages:**
```json
{"id": 1, "active": true}   // ✅ Passes
{"id": 2, "active": false}  // ❌ Filtered out
{"id": 3}                   // ❌ Filtered out (no field)
```

#### Filtering by equality

```yaml
transformations:
  - type: filter
    config:
      condition: "$.status == 'active'"
```

**Input messages:**
```json
{"status": "active"}    // ✅ Passes
{"status": "inactive"}  // ❌ Filtered out
{"status": ""}          // ❌ Filtered out
{}                      // ❌ Filtered out (missing field)
```

#### Filtering by inequality

```yaml
transformations:
  - type: filter
    config:
      condition: "$.status != 'deleted'"
```

**Input messages:**
```json
{"status": "active"}   // ✅ Passes
{"status": "deleted"}  // ❌ Filtered out
{}                     // ❌ Filtered out (missing field)
```

#### Filtering by nested path

```yaml
transformations:
  - type: filter
    config:
      condition: "$.user.status == 'active'"
```

**Input message:**
```json
{
  "user": {
    "status": "active"
  }
}
```

**Result:** Message passes when `user.status` equals `active`.

## Mask

Masks sensitive data in specified fields. Supports preserving length or full character replacement.

### Configuration

```yaml
transformations:
  - type: mask
    config:
      # List of JSONPath expressions to fields to mask (required)
      fields:
        - password
        - email
      # Character for masking (optional, default: *)
      maskChar: "*"
      # Preserve original length (optional, default: false)
      keepLength: true
```

### Examples

#### Masking with length preservation

```yaml
transformations:
  - type: mask
    config:
      fields:
        - password
        - email
      keepLength: true
```

**Input message:**
```json
{
  "id": 1,
  "username": "john",
  "password": "secret123",
  "email": "john@example.com"
}
```

**Output message:**
```json
{
  "id": 1,
  "username": "john",
  "password": "*********",
  "email": "****************"
}
```

#### Masking with fixed length

```yaml
transformations:
  - type: mask
    config:
      fields:
        - password
      keepLength: false
      maskChar: "X"
```

**Input message:**
```json
{
  "password": "verylongpassword123"
}
```

**Output message:**
```json
{
  "password": "XXX"
}
```

#### Masking nested fields

```yaml
transformations:
  - type: mask
    config:
      fields:
        - user.password
        - payment.cardNumber
      keepLength: true
```

**Input message:**
```json
{
  "user": {
    "password": "secret"
  },
  "payment": {
    "cardNumber": "1234567890123456"
  }
}
```

**Output message:**
```json
{
  "user": {
    "password": "******"
  },
  "payment": {
    "cardNumber": "****************"
  }
}
```

## Router

Routes messages to different sinks based on conditions. The first matching route determines the sink; if none matches, the message goes to the main sink.

### Condition syntax

- **Truthiness**: `$.field` — the message matches if the field exists and is truthy (non-empty string, non-zero number, `true`).
- **Equality**: `$.field == 'value'` or `$.field == "value"` — matches when the field equals the given value (unquoted literals like `true` / `5` are also accepted).
- **Inequality**: `$.field != 'value'` — matches when the field exists and is not equal to the given value.

Conditions are evaluated in order; the first match wins.

### Configuration

```yaml
transformations:
  - type: router
    config:
      routes:
        - condition: "$.level == 'error'"
          sink:
            type: kafka
            config:
              brokers: ["localhost:9092"]
              topic: error-topic
        - condition: "$.level == 'warning'"
          sink:
            type: postgresql
            config:
              connectionString: "postgres://..."
              table: warnings
```

### Features

- Conditions are checked in order; the first match determines the sink
- If no condition matches, the message goes to the main sink

### Examples

#### Routing by log level

```yaml
transformations:
  - type: router
    config:
      routes:
        - condition: "$.level"
          sink:
            type: kafka
            config:
              brokers: ["localhost:9092"]
              topic: error-logs
```

**Input messages:**
```json
{"level": "error", "message": "Critical error"}     // → error-logs topic
{"level": "info", "message": "Info message"}       // → main sink
{"level": "warning", "message": "Warning"}         // → main sink
```

#### Multiple routes

```yaml
transformations:
  - type: router
    config:
      routes:
        - condition: "$.type"
          sink:
            type: kafka
            config:
              brokers: ["localhost:9092"]
              topic: events-topic
        - condition: "$.priority"
          sink:
            type: postgresql
            config:
              connectionString: "postgres://..."
              table: high_priority_events
```

**Input messages:**
```json
{"type": "event", "data": "..."}           // → events-topic
{"priority": "high", "data": "..."}        // → high_priority_events table
{"data": "..."}                            // → main sink
```

#### Combined with other transformations

```yaml
transformations:
  - type: timestamp
    config:
      fieldName: processed_at
  - type: router
    config:
      routes:
        - condition: "$.level"
          sink:
            type: kafka
            config:
              brokers: ["localhost:9092"]
              topic: errors
```

Timestamp is added first, then the message is routed.

## Select

Keeps only the specified fields; all others are dropped. Each field is taken by JSONPath; the last path segment is used as the key in the output (e.g. `user.name` → key `name`), so the result is flat.

### Configuration

```yaml
transformations:
  - type: select
    config:
      # List of JSONPath expressions for fields to keep (required)
      fields:
        - id
        - name
        - email
```

### Examples

#### Simple field selection

```yaml
transformations:
  - type: select
    config:
      fields:
        - id
        - name
        - email
```

**Input message:**
```json
{
  "id": 1,
  "name": "John Doe",
  "email": "john@example.com",
  "password": "secret",
  "internal_id": 999
}
```

**Output message:**
```json
{
  "id": 1,
  "name": "John Doe",
  "email": "john@example.com"
}
```

#### Selecting nested fields (result is flat)

```yaml
transformations:
  - type: select
    config:
      fields:
        - user.id
        - user.name
        - metadata.timestamp
```

**Input message:**
```json
{
  "user": {
    "id": 1,
    "name": "John",
    "email": "john@example.com"
  },
  "metadata": {
    "timestamp": "2024-01-15T10:30:00Z",
    "source": "api"
  }
}
```

**Output message** (keys are last path segments):
```json
{
  "id": 1,
  "name": "John",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

## Remove

Removes specified fields from a message. Useful for data cleanup before sending.

### Configuration

```yaml
transformations:
  - type: remove
    config:
      # List of JSONPath expressions to fields to remove (required)
      fields:
        - password
        - internal_id
```

### Examples

#### Removing sensitive fields

```yaml
transformations:
  - type: remove
    config:
      fields:
        - password
        - creditCard
        - ssn
```

**Input message:**
```json
{
  "id": 1,
  "name": "John Doe",
  "password": "secret",
  "creditCard": "1234-5678-9012-3456",
  "ssn": "123-45-6789"
}
```

**Output message:**
```json
{
  "id": 1,
  "name": "John Doe"
}
```

#### Removing nested fields

```yaml
transformations:
  - type: remove
    config:
      fields:
        - user.password
        - metadata.internal
```

**Input message:**
```json
{
  "user": {
    "id": 1,
    "name": "John",
    "password": "secret"
  },
  "metadata": {
    "timestamp": "2024-01-15",
    "internal": "secret"
  }
}
```

**Output message:**
```json
{
  "user": {
    "id": 1,
    "name": "John"
  },
  "metadata": {
    "timestamp": "2024-01-15"
  }
}
```

## Order of Application

Transformations are applied sequentially in the order specified in the `transformations` list. Each transformation receives the result of the previous one.

### Example sequence

```yaml
transformations:
  # 1. Expand array
  - type: flatten
    config:
      field: items

  # 2. Add timestamp
  - type: timestamp
    config:
      fieldName: created_at

  # 3. Filter inactive
  - type: filter
    config:
      condition: "$.active"

  # 4. Remove internal fields
  - type: remove
    config:
      fields:
        - internal_id
        - debug_info

  # 5. Select only needed fields
  - type: select
    config:
      fields:
        - id
        - name
        - created_at
```

### Recommended Order

1. **Flatten** should be first if you need to expand arrays
2. **Filter** apply early to reduce the volume of processed data
3. **SnakeCase/CamelCase** apply after Select/Remove, but before sending to sink
4. **Mask/Remove** apply before Select for security
5. **Select** apply at the end for final cleanup
6. **Timestamp** can be applied anywhere, but usually at the beginning or end
7. **Router** usually applied at the end, after all other transformations

## Combined examples

### Order processing

```yaml
transformations:
  # Expand items into separate messages
  - type: flatten
    config:
      field: items

  # Add timestamp
  - type: timestamp
    config:
      fieldName: processed_at

  # Filter paid orders only
  - type: filter
    config:
      condition: "$.status == 'paid'"

  # Remove sensitive data
  - type: remove
    config:
      fields:
        - customer.creditCard
        - customer.cvv
```

### Log processing

```yaml
transformations:
  # Add timestamp
  - type: timestamp
    config:
      fieldName: timestamp

  # Mask IP addresses
  - type: mask
    config:
      fields:
        - ip_address
      keepLength: true

  # Route errors
  - type: router
    config:
      routes:
        - condition: "$.level"
          sink:
            type: kafka
            config:
              brokers: ["localhost:9092"]
              topic: error-logs
```

### Field name normalization

```yaml
transformations:
  # Select needed fields
  - type: select
    config:
      fields:
        - firstName
        - lastName
        - email
        - address

  # Convert to snake_case for PostgreSQL
  - type: snakeCase
    config:
      deep: true
```

**Input message:**
```json
{
  "firstName": "John",
  "lastName": "Doe",
  "email": "john@example.com",
  "address": {
    "streetName": "Main St",
    "zipCode": "12345"
  }
}
```

**Output message:**
```json
{
  "first_name": "John",
  "last_name": "Doe",
  "email": "john@example.com",
  "address": {
    "street_name": "Main St",
    "zip_code": "12345"
  }
}
```

## JSONPath support

All transformations that work with fields support JSONPath syntax:

- `$.field` — root field
- `$.nested.field` — nested field
- `$.array[0]` — array element by index
- `$.array[*]` — all array elements
- `$.*` — all root-level fields

## Performance

- **Filter** — apply early to reduce data volume
- **Select** — reduces message size and improves performance
- **Flatten** — can increase message count; use with care
- **Router** — creates additional connections; minimize the number of routes

## SnakeCase

Converts all JSON object keys to `snake_case` format. Useful for normalizing field names when integrating with systems using snake_case (e.g., PostgreSQL, Python API).

### Configuration

```yaml
transformations:
  - type: snakeCase
    config:
      # Recursively convert nested objects (optional, default: false)
      deep: true
```

### Examples

#### Simple conversion

```yaml
transformations:
  - type: snakeCase
    config:
      deep: false
```

**Input message:**
```json
{
  "firstName": "John",
  "lastName": "Doe",
  "userName": "johndoe",
  "isActive": true,
  "itemCount": 42
}
```

**Output message:**
```json
{
  "first_name": "John",
  "last_name": "Doe",
  "user_name": "johndoe",
  "is_active": true,
  "item_count": 42
}
```

#### Recursive conversion

```yaml
transformations:
  - type: snakeCase
    config:
      deep: true
```

**Input message:**
```json
{
  "firstName": "John",
  "address": {
    "streetName": "Main St",
    "houseNumber": 123,
    "zipCode": "12345"
  },
  "items": [
    {
      "itemName": "Product",
      "itemPrice": 99.99
    }
  ]
}
```

**Output message:**
```json
{
  "first_name": "John",
  "address": {
    "street_name": "Main St",
    "house_number": 123,
    "zip_code": "12345"
  },
  "items": [
    {
      "item_name": "Product",
      "item_price": 99.99
    }
  ]
}
```

#### PascalCase conversion

```yaml
transformations:
  - type: snakeCase
    config:
      deep: false
```

**Input message:**
```json
{
  "FirstName": "John",
  "LastName": "Doe",
  "UserID": 123
}
```

**Output message:**
```json
{
  "first_name": "John",
  "last_name": "Doe",
  "user_id": 123
}
```

### Features

- Converts `camelCase` → `snake_case`
- Converts `PascalCase` → `snake_case`
- Handles consecutive capitals (e.g. `XMLHttpRequest` → `xml_http_request`)
- Leaves existing snake_case keys unchanged
- With `deep: false` converts only top-level keys
- With `deep: true` recursively converts all nested objects and arrays

## CamelCase

Converts all JSON object keys to `CamelCase` (PascalCase) format. Useful for normalizing field names when integrating with systems using CamelCase (e.g., Java, C# API).

### Configuration

```yaml
transformations:
  - type: camelCase
    config:
      # Recursively convert nested objects (optional, default: false)
      deep: true
```

### Examples

#### Simple conversion

```yaml
transformations:
  - type: camelCase
    config:
      deep: false
```

**Input message:**
```json
{
  "first_name": "John",
  "last_name": "Doe",
  "user_name": "johndoe",
  "is_active": true,
  "item_count": 42
}
```

**Output message:**
```json
{
  "FirstName": "John",
  "LastName": "Doe",
  "UserName": "johndoe",
  "IsActive": true,
  "ItemCount": 42
}
```

#### Recursive conversion

```yaml
transformations:
  - type: camelCase
    config:
      deep: true
```

**Input message:**
```json
{
  "first_name": "John",
  "address": {
    "street_name": "Main St",
    "house_number": 123,
    "zip_code": "12345"
  },
  "items": [
    {
      "item_name": "Product",
      "item_price": 99.99
    }
  ]
}
```

**Output message:**
```json
{
  "FirstName": "John",
  "Address": {
    "StreetName": "Main St",
    "HouseNumber": 123,
    "ZipCode": "12345"
  },
  "Items": [
    {
      "ItemName": "Product",
      "ItemPrice": 99.99
    }
  ]
}
```

#### Single word conversion

```yaml
transformations:
  - type: camelCase
    config:
      deep: false
```

**Input message:**
```json
{
  "name": "John",
  "id": 123
}
```

**Output message:**
```json
{
  "Name": "John",
  "Id": 123
}
```

### Features

- Converts `snake_case` → `CamelCase`
- All words start with capital letter (PascalCase)
- Leaves existing CamelCase keys unchanged
- With `deep: false` converts only top-level keys
- With `deep: true` recursively converts all nested objects and arrays

## DebeziumUnwrap

Converts Debezium Kafka events (`payload.before/after/op`) into a flat row-style message that can be processed by regular transformations and sinks.

### Configuration

```yaml
transformations:
  - type: debeziumUnwrap
    config:
      # Convert Kafka tombstones (empty value) into operation=delete using metadata.key JSON (optional, default: false)
      inferDeleteFromTombstone: true

      # Copy payload.source.* into metadata as source_<field> (optional, default: false)
      includeSourceInMetadata: true

      # Operation for Debezium snapshot records (op="r"): insert (default) or update
      snapshotOperation: insert
```

### Behavior

- `op=c` -> body from `payload.after`, `metadata.operation=insert`
- `op=u` -> body from `payload.after`, `metadata.operation=update`
- `op=r` -> body from `payload.after`, `metadata.operation=insert` (or `update` if `snapshotOperation: update`)
- `op=d` -> body from `payload.before`, `metadata.operation=delete`
- If a message does not contain Debezium envelope (`payload.op`), it is passed through unchanged.

### Kafka tombstones

When `inferDeleteFromTombstone: true` and message value is empty, the transformer tries to parse `metadata.key` as JSON (typically Debezium key) and produce a delete message.

If key parsing fails or key is missing, the message is dropped (without error).

### PostgreSQL sink compatibility

For `operation=delete`, the current PostgreSQL sink uses soft delete via `softDeleteColumn`. Enable `softDeleteColumn` in `sink.config` for delete handling.

### Debezium -> PostgreSQL example

```yaml
transformations:
  - type: debeziumUnwrap
    config:
      inferDeleteFromTombstone: true
      includeSourceInMetadata: true
      snapshotOperation: insert
```

## ReplaceField

Renames fields and optionally filters the payload via `include` / `exclude`. Unlike `select`, `include` preserves nested structure (no key flattening). Compatible with Kafka Connect `ReplaceField` migration patterns.

### Configuration

```yaml
transformations:
  - type: replaceField
    config:
      # Rename mappings oldPath:newPath (optional)
      renames:
        - oldName:newName
        - key.sku:sku

      # Keep only these paths, preserving nesting (optional; mutually exclusive with exclude)
      include:
        - user.id
        - status

      # Remove these paths (optional; mutually exclusive with include)
      # exclude:
      #   - password
```

At least one of `renames`, `include`, or `exclude` is required. `include` and `exclude` cannot be set together.

### Examples

#### Rename fields

```yaml
transformations:
  - type: replaceField
    config:
      renames:
        - oldName:newName
        - key.sku:sku
```

**Input message:**
```json
{
  "oldName": "value",
  "key": { "sku": "12345" },
  "other": "keep"
}
```

**Output message:**
```json
{
  "newName": "value",
  "sku": "12345",
  "other": "keep"
}
```

#### Include without flattening

```yaml
transformations:
  - type: replaceField
    config:
      include:
        - user.id
        - user.name
        - status
```

**Input message:**
```json
{
  "user": { "id": 1, "name": "John", "email": "john@example.com" },
  "status": "active",
  "extra": "drop-me"
}
```

**Output message:**
```json
{
  "user": { "id": 1, "name": "John" },
  "status": "active"
}
```

## HeadersToPayload

Copies Kafka (or other source) message headers from `Metadata["headers"]` into JSON payload fields. Useful for propagating tracing IDs, tenant keys, and other header values into the body before sinks that do not preserve Kafka headers.

The Kafka source populates `Metadata["headers"]` as a `map[string]string` when records have headers.

### Configuration

```yaml
transformations:
  - type: headersToPayload
    config:
      # headerName:fieldPath mappings (required; at least one)
      mappings:
        - X-Request-Id:requestId
        - X-Language:metadata.language
```

Missing headers are skipped (payload left unchanged for that mapping). Field paths support nested keys and optional `$.` prefix.

### Examples

#### Copy headers into payload

```yaml
transformations:
  - type: headersToPayload
    config:
      mappings:
        - X-Request-Id:requestId
        - X-Language:metadata.language
```

**Input message:**
```json
{
  "data": "value"
}
```

**Headers:** `X-Request-Id=req-123`, `X-Language=en`

**Output message:**
```json
{
  "data": "value",
  "requestId": "req-123",
  "metadata": {
    "language": "en"
  }
}
```

## StructFlatten

Flattens nested JSON **objects** into a single-level map (1→1). Unlike `flatten` (which expands an **array** into N messages), `structFlatten` keeps one message and joins nested key paths with a delimiter. Arrays are preserved as values and are not indexed. Compatible with Kafka Connect [`Flatten`](https://docs.confluent.io/platform/current/connect/transforms/flatten.html) migration patterns.

Non-object roots (arrays, primitives) and non-JSON payloads pass through unchanged. Empty nested objects `{}` produce no keys. Nesting deeper than 64 levels returns a transform error.

### Configuration

```yaml
transformations:
  - type: structFlatten
    config:
      # Delimiter between nested key segments (optional, default: ".")
      delimiter: "."
```

An empty `config: {}` is valid and uses `"."`. An explicitly empty `delimiter: ""` is rejected.

### Examples

#### Dot delimiter (default)

```yaml
transformations:
  - type: structFlatten
    config:
      delimiter: "."
```

**Input message:**
```json
{
  "content": {
    "id": 42,
    "name": {
      "first": "David",
      "middle": null,
      "last": "Wong"
    },
    "tags": ["a", "b"]
  },
  "active": true
}
```

**Output message:**
```json
{
  "content.id": 42,
  "content.name.first": "David",
  "content.name.middle": null,
  "content.name.last": "Wong",
  "content.tags": ["a", "b"],
  "active": true
}
```

#### Underscore delimiter (JDBC / Avro-friendly names)

```yaml
transformations:
  - type: structFlatten
    config:
      delimiter: "_"
```

**Output keys:** `content_id`, `content_name_first`, `content_name_middle`, `content_name_last`, `content_tags`, `active`.

Typical CDC chain: `debeziumUnwrap` → `structFlatten` → `snakeCase`.

## ExtractField

Replaces the message payload with the value of a single field (Kafka Connect [`ExtractField$Value`](https://docs.confluent.io/platform/current/connect/transforms/extractfield.html) style). Cardinality is always 1→1. Metadata is preserved. Non-JSON payloads and missing paths are passed through unchanged. The new root may be an object, array, primitive, or JSON `null`.

### Configuration

```yaml
transformations:
  - type: extractField
    config:
      # JSONPath to the field that becomes the new root (required)
      field: payload.after   # or $.payload.after
```

### Examples

#### Unwrap nested payload

```yaml
transformations:
  - type: extractField
    config:
      field: payload.after
```

**Input message:**
```json
{"payload":{"after":{"id":1}}}
```

**Output message:**
```json
{"id":1}
```

#### Extract a primitive or array

```yaml
transformations:
  - type: extractField
    config:
      field: items
```

`{"items":[1,2,3]}` → `[1,2,3]`

Typical chain before flattening/casting: `extractField` → `structFlatten` → `cast`.

## HoistField

Wraps the entire JSON payload under a single top-level key (inverse of `extractField`). Useful for normalizing envelopes before/after CDC transforms. Non-JSON payloads are unchanged. The wrapper key must be a simple name without dots (not a JSONPath).

### Configuration

```yaml
transformations:
  - type: hoistField
    config:
      # Top-level wrapper key (required; no dots)
      field: record
```

### Examples

#### Wrap a row

```yaml
transformations:
  - type: hoistField
    config:
      field: record
```

**Input message:**
```json
{"id":1}
```

**Output message:**
```json
{"record":{"id":1}}
```

#### Round-trip with extractField

```yaml
transformations:
  - type: hoistField
    config:
      field: record
  - type: extractField
    config:
      field: record
```

Restores the original payload.

## Cast

Converts field values to declared target types by JSONPath. Useful after `debeziumUnwrap` / `structFlatten` before JDBC or other schema-sensitive sinks. Cardinality is 1→1. Metadata is unchanged. Non-JSON payloads are passed through.

**Missing paths** are skipped (not an error). **Failed conversion of an existing value** returns a transform error: the processor logs it, increments `dataflow_transformer_errors_total`, and **skips** the message (it is not written to the sink). The operator does not restart. On Kafka, the failed offset is not acked by that message; a later successful write may advance the commit past it (skip-on-error, not infinite retry on the same offset).

### Configuration

```yaml
transformations:
  - type: cast
    config:
      # Map of JSONPath → target type (required, non-empty)
      # Types: string | int64 | float64 | bool | null
      spec:
        id: int64
        amount: float64
        active: bool
        note: string
        deleted_at: null    # force JSON null
```

### Conversion rules

| Target | Accepted inputs | Errors on |
|--------|-----------------|-----------|
| `string` | scalars (numbers, bools, strings) | object, array, JSON `null` |
| `int64` | integers, whole floats, numeric strings | fractional numbers, non-numeric values |
| `float64` | numbers, numeric strings | non-numeric values |
| `bool` | bool; strings `true`/`false` (case-insensitive); numbers `0`/`1` | other values |
| `null` | any existing value → JSON `null` | — |

### Examples

#### After unwrap / flatten

```yaml
transformations:
  - type: debeziumUnwrap
  - type: cast
    config:
      spec:
        id: int64
        amount: float64
        active: bool
```

**Input message:**
```json
{"id":"1","amount":"9.99","active":"true"}
```

**Output message:**
```json
{"id":1,"amount":9.99,"active":true}
```

Typical chain: `debeziumUnwrap` → `timezone` → `cast`, or `extractField` → `structFlatten` → `cast`.

## Timezone

Converts listed temporal fields to a target IANA timezone or fixed UTC offset (`±HH:MM`). Useful after `debeziumUnwrap` before JDBC sinks. Cardinality is 1→1. Metadata is unchanged. Non-JSON payloads are passed through.

Does **not** interact with `spec.maintenance.timezone` and is distinct from the `timestamp` transform (which inserts wall-clock time).

**Missing fields and JSON `null`** are skipped. **Unparseable values** return a transform error: the processor logs it, increments `dataflow_transformer_errors_total`, and **skips** the message (same skip-on-error semantics as `cast`).

### Configuration

```yaml
transformations:
  - type: timezone
    config:
      # Target IANA TZ or UTC offset (required)
      timezone: Europe/Moscow
      # Fields to convert (required, non-empty JSONPaths)
      fields: [created_at, updated_at]
      # Assumed source TZ when value has no offset (optional, default: UTC)
      sourceTimezone: UTC
      # Output layout (optional, default: RFC3339Nano). Also: RFC3339, UnixMilli
      format: RFC3339
```

### Input forms

| Input | Behavior |
|-------|----------|
| RFC3339 / RFC3339Nano string (with or without offset) | Parsed; offsetless values use `sourceTimezone` |
| Epoch number or numeric string | Milliseconds if `\|n\| >= 1e12`, otherwise seconds |
| Missing path / JSON `null` | Skipped |
| Other values | Transform error |

### Examples

#### After debeziumUnwrap

```yaml
transformations:
  - type: debeziumUnwrap
  - type: timezone
    config:
      timezone: Europe/Moscow
      fields: [created_at, updated_at]
      format: RFC3339
  - type: cast
    config:
      spec:
        id: int64
```

**Input message:**
```json
{"id":1,"created_at":"2024-01-15T12:00:00Z"}
```

**Output after timezone (Europe/Moscow):**
```json
{"id":1,"created_at":"2024-01-15T15:00:00+03:00"}
```

## Limitations

- **Filter**: supports truthiness (`$.field`), equality (`$.field == 'value'`), and inequality (`$.field != 'value'`). Missing fields fail the condition. Scripted expressions (AND/OR/Groovy/JS) are not supported.
- **Router**: conditions are checked in order; the first match determines the route. Same condition syntax as Filter (`$.field`, `==`, `!=`).
- **Flatten**: works only with arrays (including Avro-style wrapper with `array` key), not arbitrary objects. For nested-object flattening use `structFlatten`.
- **StructFlatten**: 1→1 object flatten; arrays are kept as values (use array `flatten` first to explode). Max nesting depth is 64.
- **ExtractField**: missing path and non-JSON → passthrough; root may become a non-object (later object-only transforms will passthrough).
- **HoistField**: wrapper key must be a simple top-level name (no dots); wraps any JSON value including arrays and primitives.
- **Cast**: missing path → skip; failed conversion of an existing value → transform error (message skipped, not written to sink; Kafka offset may advance past it on later success). Types: `string`, `int64`, `float64`, `bool`, `null`.
- **Timezone**: only listed `fields`; missing/null → skip; unparseable → transform error (same skip-on-error as cast). Formats: `RFC3339`, `RFC3339Nano` (default), `UnixMilli`. Not related to `maintenance.timezone` or the `timestamp` transform.
- **Select**: result is always flat; the key is the last JSONPath segment.
- **ReplaceField**: `include` preserves nesting (unlike `select`); `include` and `exclude` are mutually exclusive.
- **HeadersToPayload**: requires headers in `Metadata["headers"]` (Kafka source sets this); missing headers are skipped; non-JSON payloads are unchanged.
- **SnakeCase** and **CamelCase**: work only with valid JSON; binary data is returned unchanged.
- **DebeziumUnwrap**: supports Debezium JSON envelope (`payload.op/before/after`). For `operation=delete` in PostgreSQL sink, `softDeleteColumn` is required; otherwise delete events can be treated as regular insert/update writes.

