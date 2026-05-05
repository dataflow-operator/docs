# Transformations

DataFlow Operator supports message transformations that are applied sequentially to each message in the order specified in the configuration. Transformations use [gjson](https://github.com/tidwall/gjson) JSONPath for field access.

## Transformation Overview

| Transformation | Description | Input | Output |
|----------------|------------|-------|--------|
| Timestamp | Adds a timestamp field | 1 message | 1 message |
| Flatten | Expands an array into separate messages | 1 message | N messages |
| Filter | Keeps messages where a field is truthy | 1 message | 0 or 1 message |
| Mask | Masks sensitive fields | 1 message | 1 message |
| Router | Sends matching messages to alternate sinks | 1 message | 0 or 1 message |
| Select | Keeps only specified fields | 1 message | 1 message |
| Remove | Removes specified fields | 1 message | 1 message |
| SnakeCase | Converts keys to snake_case | 1 message | 1 message |
| CamelCase | Converts keys to CamelCase | 1 message | 1 message |
| DebeziumUnwrap | Unwraps Debezium envelope into row payload | 1 message | 0 or 1 message |

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

Keeps only messages where the field at the given JSONPath exists and is *truthy* (boolean `true`, non-empty string, non-zero number). Other messages are dropped. Comparison expressions (e.g. `==`) are not supported; use Router for value-based routing.

### Configuration

```yaml
transformations:
  - type: filter
    config:
      # JSONPath to a field; message passes if field exists and is truthy (required)
      condition: "$.active"
```

### JSONPath

Uses the `gjson` library: `$.field`, `$.nested.field`, `$.array[0]`, etc.

### Examples

#### Simple filtering

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

#### Filtering by value

```yaml
transformations:
  - type: filter
    config:
      condition: "$.level"
```

**Input messages:**
```json
{"level": "error"}    // ✅ Passes (non-empty string)
{"level": "warning"}  // ✅ Passes
{"level": ""}         // ❌ Filtered out
{"level": null}       // ❌ Filtered out
```

#### Filtering by numeric value

```yaml
transformations:
  - type: filter
    config:
      condition: "$.amount"
```

**Input messages:**
```json
{"amount": 100}  // ✅ Passes (non-zero)
{"amount": 0}    // ❌ Filtered out
{"amount": -5}   // ✅ Passes (non-zero)
```

#### Complex filtering

```yaml
transformations:
  - type: filter
    config:
      condition: "$.user.status"
```

**Input message:**
```json
{
  "user": {
    "status": "active"
  }
}
```

**Result:** Message passes if `user.status` exists and is non-empty.

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
- **Comparison**: `$.field == 'value'` or `$.field == "value"` — matches when the field equals the given string.

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
      condition: "$.status"

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

## Planned transformations

The following are not yet available in the API (CRD):

- **ReplaceField** — rename fields (e.g. `old.path` → `new.path`)
- **HeaderFrom** — copy Kafka message headers into the message body

Use the [Connectors](connectors.md) and [Examples](examples.md) for current capabilities.

## Limitations

- **Filter**: only field existence and truthiness are checked; comparisons (e.g. `==`) are not supported — use Router for value-based routing.
- **Router**: conditions are checked in order; the first match determines the route. Supported formats: `$.field` (truthiness) and `$.field == 'value'`.
- **Flatten**: works only with arrays (including Avro-style wrapper with `array` key), not arbitrary objects.
- **Select**: result is always flat; the key is the last JSONPath segment.
- **SnakeCase** and **CamelCase**: work only with valid JSON; binary data is returned unchanged.
- **DebeziumUnwrap**: supports Debezium JSON envelope (`payload.op/before/after`). For `operation=delete` in PostgreSQL sink, `softDeleteColumn` is required; otherwise delete events can be treated as regular insert/update writes.

