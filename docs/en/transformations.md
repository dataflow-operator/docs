# Transformations

DataFlow Operator supports message transformations that are applied sequentially to each message in the order specified in the configuration. Transformations use [gjson](https://github.com/tidwall/gjson) JSONPath for field access.

> **Note**: This is a simplified English version. For complete documentation, see the [Russian version](../ru/transformations.md).

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

## Timestamp

Adds a timestamp field to each message. Useful for tracking message processing time.

### Configuration

```yaml
transformations:
  - type: timestamp
    timestamp:
      # Field name for timestamp (optional, default: created_at)
      fieldName: created_at
      # Timestamp format (optional, default: RFC3339)
      format: RFC3339
```

### Format

The `format` value is a [Go time layout](https://pkg.go.dev/time#pkg-constants) string. Default is `RFC3339` (e.g. `2006-01-02T15:04:05Z07:00`). Examples: `RFC3339`, `RFC3339Nano`, or custom layouts like `2006-01-02 15:04:05`.

## Flatten

Expands an array into separate messages, preserving all other fields from the original message. Each array element is merged into the root; objects are flattened to top-level keys. If the field is not an array, the message is returned unchanged. Supports Avro-style arrays wrapped in an object with an `array` key.

### Configuration

```yaml
transformations:
  - type: flatten
    flatten:
      # JSONPath to the array to expand (required)
      field: items
```

## Filter

Keeps only messages where the field at the given JSONPath exists and is *truthy* (boolean `true`, non-empty string, non-zero number). Other messages are dropped. Comparison expressions (e.g. `==`) are not supported; use Router for value-based routing.

### Configuration

```yaml
transformations:
  - type: filter
    filter:
      # JSONPath to a field; message passes if field exists and is truthy (required)
      condition: "$.active"
```

## Mask

Masks sensitive data in specified fields. Supports preserving length or full character replacement.

### Configuration

```yaml
transformations:
  - type: mask
    mask:
      # List of JSONPath expressions to fields to mask (required)
      fields:
        - password
        - email
      # Character for masking (optional, default: *)
      maskChar: "*"
      # Preserve original length (optional, default: false)
      keepLength: true
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
    router:
      routes:
        - condition: "$.level == 'error'"
          sink:
            type: kafka
            kafka:
              brokers: ["localhost:9092"]
              topic: error-topic
        - condition: "$.level == 'warning'"
          sink:
            type: postgresql
            postgresql:
              connectionString: "postgres://..."
              table: warnings
```

## Select

Keeps only the specified fields; all others are dropped. Each field is taken by JSONPath; the last path segment is used as the key in the output (e.g. `user.name` → key `name`), so the result is flat.

### Configuration

```yaml
transformations:
  - type: select
    select:
      # List of JSONPath expressions for fields to keep (required)
      fields:
        - id
        - name
        - email
```

## Remove

Removes specified fields from a message. Useful for data cleanup before sending.

### Configuration

```yaml
transformations:
  - type: remove
    remove:
      # List of JSONPath expressions to fields to remove (required)
      fields:
        - password
        - internal_id
```

## Order of Application

Transformations are applied sequentially in the order specified in the `transformations` list. Each transformation receives the result of the previous one.

### Recommended Order

1. **Flatten** should be first if you need to expand arrays
2. **Filter** apply early to reduce the volume of processed data
3. **SnakeCase/CamelCase** apply after Select/Remove, but before sending to sink
4. **Mask/Remove** apply before Select for security
5. **Select** apply at the end for final cleanup
6. **Timestamp** can be applied anywhere, but usually at the beginning or end
7. **Router** usually applied at the end, after all other transformations

## SnakeCase

Converts all JSON object keys to `snake_case` format. Useful for normalizing field names when integrating with systems using snake_case (e.g., PostgreSQL, Python API).

### Configuration

```yaml
transformations:
  - type: snakeCase
    snakeCase:
      # Recursively convert nested objects (optional, default: false)
      deep: true
```

### Example

**Input:**
```json
{
  "firstName": "John",
  "lastName": "Doe",
  "isActive": true
}
```

**Output:**
```json
{
  "first_name": "John",
  "last_name": "Doe",
  "is_active": true
}
```

## CamelCase

Converts all JSON object keys to `CamelCase` (PascalCase) format. Useful for normalizing field names when integrating with systems using CamelCase (e.g., Java, C# API).

### Configuration

```yaml
transformations:
  - type: camelCase
    camelCase:
      # Recursively convert nested objects (optional, default: false)
      deep: true
```

### Example

**Input:**
```json
{
  "first_name": "John",
  "last_name": "Doe",
  "is_active": true
}
```

**Output:**
```json
{
  "FirstName": "John",
  "LastName": "Doe",
  "IsActive": true
}
```

## Planned transformations

The following are not yet available in the API (CRD):

- **ReplaceField** — rename fields (e.g. `old.path` → `new.path`)
- **HeaderFrom** — copy Kafka message headers into the message body

Use the [Connectors](connectors.md) and [Examples](examples.md) for current capabilities.

For complete transformation documentation with examples, see the [Russian version](../ru/transformations.md).

