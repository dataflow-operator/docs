# Error Handling

DataFlow Operator allows you to send messages that failed to be written to the main sink to a separate **error sink**. This keeps the main pipeline running and gives you a place to inspect, replay, or archive failed messages.

## Overview

The `errors` section in the DataFlow spec defines the error sink. When a message cannot be written to the main sink (e.g., connection failure, validation error, constraint violation), it is written to the error sink instead. The same connector types supported as main sinks can be used for the error sink (e.g. Kafka, PostgreSQL).

!!! tip "When to use"
    Use an error sink when you need to avoid losing failed messages and want to reprocess or analyze them later.

## Configuration

Add an `errors` block to your DataFlow spec with `type` and the connector-specific configuration.

### Kafka as error sink

```yaml
spec:
  source:
    type: kafka
    kafka:
      brokers:
        - localhost:9092
      topic: input-topic
      consumerGroup: dataflow-group
  sink:
    type: postgresql
    postgresql:
      connectionString: "postgres://..."
      table: output_table
  errors:
    type: kafka
    kafka:
      brokers:
        - localhost:9092
      topic: error-topic
```

You can use the same Kafka options as for the main sink (e.g. `brokersSecretRef`, `topicSecretRef`, `sasl`, `tls`). See [Connectors](connectors.md) for full Kafka sink options.

### PostgreSQL as error sink

```yaml
  errors:
    type: postgresql
    postgresql:
      connectionString: "postgres://..."
      table: error_messages
      autoCreateTable: true
```

PostgreSQL error sink supports the same options as the main PostgreSQL sink (`connectionStringSecretRef`, `tableSecretRef`, `batchSize`, etc.).

## Error message structure

Each record written to the error sink has the following structure:

| Field | Description |
|-------|-------------|
| `error` | Object with error details |
| `error.message` | Error text (e.g. connection refused, constraint violation) |
| `error.timestamp` | ISO 8601 timestamp when the error occurred |
| `error.original_sink` | Connector type of the main sink (e.g. `postgresql`, `kafka`) |
| `error.metadata` | Optional metadata from the original message |
| `original_message` | The original payload (object for JSON, or `original_data` string) |

Example:

```json
{
  "error": {
    "message": "failed to send message: connection refused",
    "timestamp": "2026-01-24T12:34:56Z",
    "original_sink": "postgresql"
  },
  "original_message": {
    "id": 1,
    "name": "test",
    "value": 100
  }
}
```

## Metrics

Error handling is reflected in operator metrics:

- **Connector errors**: `dataflow_connector_errors_total` (labels: `namespace`, `name`, `connector_type`, `connector_name`, `operation`, `error_type`)
- **Task stages**: `dataflow_task_stage_duration_seconds` includes stage `error_sink_write` when an error sink is configured
- **Success rate**: `dataflow_task_success_rate` (0.0–1.0) for monitoring pipeline health

See [Metrics](metrics.md) for full details.

## Sample manifest

A full example with an error sink is available in the repository:

```bash
kubectl apply -f config/samples/kafka-to-postgres-with-errors.yaml
```

See also the [Examples](examples.md#error-handling-with-error-sink) section for more context.
