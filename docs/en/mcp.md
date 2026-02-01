# MCP (Model Context Protocol)

DataFlow MCP server helps generate DataFlow manifests and migrate Kafka Connect configurations to DataFlow. It runs without access to Kubernetes or Prometheus — YAML generation and validation only. Use it in your IDE (e.g. Cursor) to create manifests and migrate connectors.

## Features

| Tool | Description |
|------|-------------|
| **generate_dataflow_manifest** | Generate a DataFlow YAML manifest from a description (source/sink type, optional configs and transformations). |
| **validate_dataflow_manifest** | Validate a YAML manifest (apiVersion, kind, spec.source, spec.sink). |
| **migrate_kafka_connect_to_dataflow** | Migrate a Kafka Connect configuration (one or two connectors: source + sink) into a DataFlow manifest with notes on migration boundaries. |
| **list_dataflow_connectors** | Reference of supported connectors (sources and sinks). |
| **list_dataflow_transformations** | Reference of transformations with examples. |

## Docker image

The server is published to GitHub Container Registry. Recommended image for production use:

**Image:** `ghcr.io/dataflow-operator/dataflow-mcp:25979c2`

You can also use `ghcr.io/dataflow-operator/dataflow-mcp:latest` for the latest build.

### Running with Docker

The server communicates over stdin/stdout, so the `-i` flag is required:

```bash
docker run -i --rm ghcr.io/dataflow-operator/dataflow-mcp:25979c2
```

## Connecting in Cursor

Add the server to MCP settings (e.g. `~/.cursor/mcp.json` or project settings).

### Via Docker (recommended)

```json
{
  "mcpServers": {
    "dataflow": {
      "command": "docker",
      "args": [
        "run",
        "-i",
        "--rm",
        "ghcr.io/dataflow-operator/dataflow-mcp:25979c2"
      ]
    }
  }
}
```

### Via local binary

If you built the server locally:

```json
{
  "mcpServers": {
    "dataflow": {
      "command": "/absolute/path/to/dataflow-mcp/target/release/dataflow-mcp",
      "args": []
    }
  }
}
```

### Via cargo (development)

```json
{
  "mcpServers": {
    "dataflow": {
      "command": "cargo",
      "args": ["run", "--release", "--manifest-path", "/path/to/dataflow-mcp/Cargo.toml"]
    }
  }
}
```

## Testing with MCP Inspector

[MCP Inspector](https://modelcontextprotocol.io/docs/tools/inspector) is an interactive browser-based tool for testing and debugging MCP servers.

```bash
npx @modelcontextprotocol/inspector /path/to/dataflow-mcp/target/release/dataflow-mcp
```

The web UI opens at <http://localhost:6274>. Select **stdio** transport and run tools with JSON parameters.

## Examples

### Generating a Kafka → PostgreSQL manifest

Use **generate_dataflow_manifest** with:

- `source_type`: `"kafka"`
- `sink_type`: `"postgresql"`
- `source_config`: `"{\"brokers\":[\"localhost:9092\"],\"topic\":\"input-topic\",\"consumerGroup\":\"dataflow-group\"}"`
- `sink_config`: `"{\"connectionString\":\"postgres://user:pass@host:5432/db\",\"table\":\"output_table\"}"`
- `name`: `"kafka-to-postgres"` (optional)

### Migrating a Kafka Connect JDBC Sink

Use **migrate_kafka_connect_to_dataflow** with the connector config as JSON:

```json
{
  "name": "jdbc-sink",
  "config": {
    "connector.class": "io.confluent.connect.jdbc.JdbcSinkConnector",
    "connection.url": "jdbc:postgresql://pg:5432/mydb",
    "table.name.format": "events",
    "topics": "events"
  }
}
```

The response includes a DataFlow YAML manifest and notes on migrated and unsupported options.

### Validating a manifest

Paste the YAML manifest into **validate_dataflow_manifest** (parameter `config`). The response indicates whether the config is valid or lists errors.
