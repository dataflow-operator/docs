# MCP (Model Context Protocol)

MCP-сервер DataFlow помогает генерировать манифесты DataFlow и мигрировать конфигурации Kafka Connect в DataFlow. Он работает без доступа к Kubernetes или Prometheus — только генерация и валидация YAML. Используйте его в IDE (например, Cursor) для создания манифестов и миграции коннекторов.

## Возможности

| Инструмент | Описание |
|------------|----------|
| **generate_dataflow_manifest** | Генерация YAML-манифеста DataFlow по описанию (тип source/sink, опциональные конфиги и трансформации). |
| **validate_dataflow_manifest** | Валидация YAML-манифеста (apiVersion, kind, spec.source, spec.sink). |
| **migrate_kafka_connect_to_dataflow** | Миграция конфигурации Kafka Connect (один или два коннектора: source + sink) в манифест DataFlow с заметками о границах миграции. |
| **list_dataflow_connectors** | Справочник поддерживаемых коннекторов (sources и sinks). |
| **list_dataflow_transformations** | Справочник трансформаций с примерами. |

## Docker-образ

Сервер публикуется в GitHub Container Registry. Рекомендуемый образ для использования:

**Образ:** `ghcr.io/dataflow-operator/dataflow-mcp:25979c2`

Также можно использовать `ghcr.io/dataflow-operator/dataflow-mcp:latest` для последней сборки.

### Запуск через Docker

Сервер общается через stdin/stdout, поэтому флаг `-i` обязателен:

```bash
docker run -i --rm ghcr.io/dataflow-operator/dataflow-mcp:25979c2
```

## Подключение в Cursor

Добавьте сервер в настройки MCP (например, `~/.cursor/mcp.json` или настройки проекта).

### Через Docker (рекомендуется)

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

### Через локальный бинарник

Если вы собрали сервер локально:

```json
{
  "mcpServers": {
    "dataflow": {
      "command": "/абсолютный/путь/к/dataflow-mcp/target/release/dataflow-mcp",
      "args": []
    }
  }
}
```

### Через cargo (разработка)

```json
{
  "mcpServers": {
    "dataflow": {
      "command": "cargo",
      "args": ["run", "--release", "--manifest-path", "/путь/к/dataflow-mcp/Cargo.toml"]
    }
  }
}
```

## Тестирование с MCP Inspector

[MCP Inspector](https://modelcontextprotocol.io/docs/tools/inspector) — интерактивный браузерный инструмент для тестирования и отладки MCP-серверов.

```bash
npx @modelcontextprotocol/inspector /путь/к/dataflow-mcp/target/release/dataflow-mcp
```

Веб-интерфейс открывается по адресу <http://localhost:6274>. Выберите транспорт **stdio** и вызывайте инструменты с JSON-параметрами.

## Примеры

### Генерация манифеста Kafka → PostgreSQL

Используйте **generate_dataflow_manifest** с параметрами:

- `source_type`: `"kafka"`
- `sink_type`: `"postgresql"`
- `source_config`: `"{\"brokers\":[\"localhost:9092\"],\"topic\":\"input-topic\",\"consumerGroup\":\"dataflow-group\"}"`
- `sink_config`: `"{\"connectionString\":\"postgres://user:pass@host:5432/db\",\"table\":\"output_table\"}"`
- `name`: `"kafka-to-postgres"` (опционально)

### Миграция Kafka Connect JDBC Sink

Используйте **migrate_kafka_connect_to_dataflow** с конфигом коннектора в JSON:

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

Ответ содержит YAML-манифест DataFlow и заметки о перенесённых и неподдерживаемых опциях.

### Валидация манифеста

Вставьте YAML-манифест в **validate_dataflow_manifest** (параметр `config`). Ответ покажет, корректен ли конфиг или перечислит ошибки.
