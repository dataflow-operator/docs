# Обработка ошибок

DataFlow Operator позволяет отправлять сообщения, которые не удалось записать в основной приёмник (sink), в отдельный **error sink**. Это не останавливает основной пайплайн и даёт место для разбора, повторной обработки или архивации неудачных сообщений.

## Обзор

Секция `errors` в спецификации DataFlow задаёт приёмник для ошибок. Когда сообщение не удаётся записать в основной sink (например, ошибка соединения, валидации или нарушения ограничения), оно записывается в error sink. Для error sink можно использовать те же типы коннекторов, что и для основного sink (Kafka, PostgreSQL, ClickHouse, Trino).

!!! tip "Когда использовать"
    Используйте error sink, когда нужно не терять неудачные сообщения и иметь возможность обработать или проанализировать их позже.

## Конфигурация

Добавьте блок `errors` в спецификацию DataFlow с полем `type` и конфигурацией выбранного коннектора.

### Kafka как приёмник ошибок

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

Для error sink можно использовать те же опции Kafka, что и для основного sink (`brokersSecretRef`, `topicSecretRef`, `sasl`, `tls`). Подробнее в [Коннекторы](connectors.md).

### PostgreSQL как приёмник ошибок

```yaml
  errors:
    type: postgresql
    postgresql:
      connectionString: "postgres://..."
      table: error_messages
      autoCreateTable: true
```

Поддерживаются те же опции, что и для основного PostgreSQL sink (`connectionStringSecretRef`, `tableSecretRef`, `batchSize` и др.).

## Структура сообщения об ошибке

Каждая запись, отправляемая в error sink, имеет следующую структуру:

| Поле | Описание |
|------|----------|
| `error` | Объект с данными об ошибке |
| `error.message` | Текст ошибки (например, connection refused, нарушение ограничения) |
| `error.timestamp` | Время ошибки в формате ISO 8601 |
| `error.original_sink` | Тип коннектора основного sink (например, `postgresql`, `kafka`) |
| `error.metadata` | Опциональные метаданные исходного сообщения |
| `original_message` | Исходное тело сообщения (объект для JSON или строка в `original_data`) |

Пример:

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

## Типы ошибок

Ошибки классифицируются по типу для метрик. Метка `error_type` в `dataflow_connector_errors_total`, `dataflow_transformer_errors_total` и `dataflow_task_stage_errors_total` может принимать следующие значения:

| Тип | Описание |
|-----|----------|
| `context_canceled` | Операция отменена (`context.Canceled`) |
| `timeout` | `context.DeadlineExceeded` или текст сообщения содержит "timeout", "deadline exceeded", "i/o timeout" |
| `connection_error` | Connection refused, not connected, failed to connect или connection failure |
| `constraint_violation` | Нарушение ограничения целостности PostgreSQL (SQLSTATE класс 23xx) |
| `invalid_data` | Ошибка парсинга JSON, схемы, валидации или синтаксиса |
| `transient` | Временные ошибки Trino (TOO_MANY_REQUESTS_FAILED, перегрузка worker, подсказки retry) |
| `auth_error` | Ошибка аутентификации, SASL или авторизации |
| `unknown` | Ошибка не удалось классифицировать |

## Метрики

Обработка ошибок отражается в метриках оператора:

- **Ошибки коннекторов**: `dataflow_connector_errors_total` (метки: `namespace`, `name`, `connector_type`, `connector_name`, `operation`, `error_type`)
- **Ошибки трансформеров**: `dataflow_transformer_errors_total` (метки: `namespace`, `name`, `transformer_type`, `transformer_index`, `error_type`)
- **Ошибки этапов задачи**: `dataflow_task_stage_errors_total` (метки: `namespace`, `name`, `stage`, `error_type`)
- **Этапы задачи**: в `dataflow_task_stage_duration_seconds` присутствует этап `error_sink_write`, если настроен error sink
- **Доля успешных задач**: `dataflow_task_success_rate` (0.0–1.0) для мониторинга состояния пайплайна

Подробнее см. [Метрики](metrics.md).

## Пример манифеста

Полный пример с приёмником ошибок есть в репозитории:

```bash
kubectl apply -f config/samples/kafka-to-postgres-with-errors.yaml
```

Дополнительный контекст — в разделе [Примеры](examples.md#обработка-ошибок-с-error-sink).
