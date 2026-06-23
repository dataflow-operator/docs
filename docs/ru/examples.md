# Examples

Практические примеры использования DataFlow Operator для различных сценариев обработки данных.

Поток данных в каждом конвейере следует схеме **Источник → Трансформации → Приёмник**. См. [Архитектура — Поток данных](architecture.md#поток-данных-концептуально) для концептуальной диаграммы.

## Простой Kafka → PostgreSQL поток

Базовый пример передачи данных из Kafka топика в PostgreSQL таблицу.

```yaml
apiVersion: dataflow.dataflow.io/v1
kind: DataFlow
metadata:
  name: kafka-to-postgres
spec:
  source:
    type: kafka
    config:
      brokers:
        - localhost:9092
      topic: input-topic
      consumerGroup: dataflow-group
  sink:
    type: postgresql
    config:
      connectionString: "postgres://dataflow:dataflow@postgres:5432/dataflow?sslmode=disable"
      table: output_table
      autoCreateTable: true
```

**Применение:**
```bash
kubectl apply -f dataflow/config/samples/kafka-to-postgres.yaml
```

## Kafka → Nessie

Пример выгрузки событий из Kafka в таблицу Iceberg через sink `nessie`.

**Применение:**
```bash
kubectl apply -f dataflow/config/samples/kafka-to-nessie.yaml
```

Подробности по настройке коннектора смотрите в разделе [Коннекторы — Nessie](connectors.md#nessie).

## DataFlowCron с триггерами после processor {#dataflowcron-example}

Полное описание: [DataFlowCron — обзор](dataflow-cron/index.md).

Пример запуска pipeline по расписанию, где сначала выполняется основной `processor`, а затем запускаются `triggers`.

```yaml
apiVersion: dataflow.dataflow.io/v1
kind: DataFlowCron
metadata:
  name: kafka-to-nessie-cron
spec:
  schedule: "*/10 * * * *"
  concurrencyPolicy: Forbid
  source:
    type: kafka
    config:
      brokers:
        - kafka:9092
      topic: input-topic
      consumerGroup: dataflow-group
  sink:
    type: nessie
    config:
      baseURL: "http://nessie:19120"
      branch: main
      namespace: analytics
      table: events
  triggers:
    - name: start-spark
      image: bitnami/kubectl:latest
      command: ["kubectl"]
      args: ["apply", "-f", "/manifests/spark-application.yaml"]
```

Примечания по завершению:

- polling-источники (`postgresql`, `trino`, `clickhouse`, `nessie`) завершают run при `source exhausted`;
- `kafka` является streaming-источником и по умолчанию не завершает run по exhausted.

## Nessie → Kafka

Пример чтения из Iceberg-таблицы через Nessie source и публикации строк в Kafka-топик.

**Применение:**
```bash
kubectl apply -f dataflow/config/samples/nessie-to-kafka.yaml
```

Подробности по настройке коннектора смотрите в разделе [Коннекторы — Nessie](connectors.md#nessie).

## Kafka с режимом сырой записи (rawMode)

Пример сохранения полного контекста Kafka-сообщения: payload + метаданные (offset, partition, timestamp, key, topic). Используйте `rawMode: true` в sink для сохранения сообщений в колонках `data` и `_metadata` (PostgreSQL/Trino/ClickHouse/Nessie).

```yaml
apiVersion: dataflow.dataflow.io/v1
kind: DataFlow
metadata:
  name: kafka-raw-to-clickhouse
spec:
  source:
    type: kafka
    config:
      brokers:
        - localhost:9092
      topic: input-topic
      consumerGroup: dataflow-group
  sink:
    type: clickhouse
    config:
      connectionString: "clickhouse://default@clickhouse:9000/default"
      table: raw_events
      autoCreateTable: true
      rawMode: true  # Сохраняет каждое сообщение как {"value": ..., "_metadata": {...}}
```

**Формат выходного сообщения при rawMode (sink оборачивает используя msg.Metadata):**
```json
{
  "value": {"id": 1, "event": "user_login"},
  "_metadata": {
    "offset": 100,
    "partition": 0,
    "timestamp": "2024-02-27T10:13:20.000Z",
    "key": "user-123",
    "topic": "input-topic"
  }
}
```

Для sink, ожидающего только данные без обёртки, добавьте трансформацию select с полем `value`:
```yaml
transformations:
  - type: select
    config:
      fields: ["value"]
```

## С трансформациями (Flatten + Timestamp)

Пример обработки сообщений с массивом товаров, развертывание в отдельные сообщения и добавление временной метки.

```yaml
apiVersion: dataflow.dataflow.io/v1
kind: DataFlow
metadata:
  name: stock-flatten
spec:
  source:
    type: kafka
    config:
      brokers:
        - localhost:9092
      topic: stock-topic
      consumerGroup: dataflow-group
  sink:
    type: postgresql
    config:
      connectionString: "postgres://dataflow:dataflow@postgres:5432/dataflow?sslmode=disable"
      table: stock_items
      autoCreateTable: true
      batchSize: 50
  transformations:
    # Развернуть массив rowsStock в отдельные сообщения
    - type: flatten
      config:
        field: rowsStock
    # Добавить временную метку
    - type: timestamp
      config:
        fieldName: created_at
```

**Входное сообщение:**
```json
{
  "type": "stock",
  "version": 32476984,
  "rowsStock": [
    {"sku": 400125868, "section": "A015"},
    {"sku": 400125868, "section": "A001"}
  ]
}
```

**Выходные сообщения:**
```json
{
  "type": "stock",
  "version": 32476984,
  "sku": 400125868,
  "section": "A015",
  "created_at": "2024-01-15T10:30:00Z"
}
```

```json
{
  "type": "stock",
  "version": 32476984,
  "sku": 400125868,
  "section": "A001",
  "created_at": "2024-01-15T10:30:00Z"
}
```

## Обработка ошибок с error sink

Пример настройки отдельного приёмника для сообщений, которые не удалось записать в основной sink.

```yaml
apiVersion: dataflow.dataflow.io/v1
kind: DataFlow
metadata:
  name: kafka-to-postgres-with-errors
spec:
  source:
    type: kafka
    config:
      brokers:
        - localhost:9092
      topic: input-topic
      consumerGroup: dataflow-group
  sink:
    type: postgresql
    config:
      connectionString: "postgres://dataflow:dataflow@postgres:5432/dataflow?sslmode=disable"
      table: output_table
      autoCreateTable: true
  errors:
    type: kafka
    config:
      brokers:
        - localhost:9092
      topic: error-topic
```

**Применение:**
```bash
kubectl apply -f dataflow/config/samples/kafka-to-postgres-with-errors.yaml
```

Структура сообщений об ошибках и детали конфигурации — в разделе [Обработка ошибок](errors.md).

## С роутером для множественных приемников

Пример маршрутизации сообщений в разные приемники на основе условий.

```yaml
apiVersion: dataflow.dataflow.io/v1
kind: DataFlow
metadata:
  name: router-example
spec:
  source:
    type: kafka
    config:
      brokers:
        - localhost:9092
      topic: events
      consumerGroup: dataflow-group
  # Основной приемник для сообщений, не соответствующих условиям
  sink:
    type: kafka
    config:
      brokers:
        - localhost:9092
      topic: default-events
  transformations:
    - type: router
      config:
        routes:
          # Ошибки → отдельный топик
          - condition: "$.level"
            sink:
              type: kafka
              config:
                brokers:
                  - localhost:9092
                topic: error-events
          # Предупреждения → PostgreSQL
          - condition: "$.priority"
            sink:
              type: postgresql
              config:
                connectionString: "postgres://dataflow:dataflow@postgres:5432/dataflow?sslmode=disable"
                table: warnings
                autoCreateTable: true
```

**Входные сообщения:**
```json
{"level": "error", "message": "Critical error"}     // → error-events топик
{"priority": "high", "message": "Warning"}          // → warnings таблица
{"message": "Info"}                                 // → default-events топик
```

## С фильтрацией и маскированием

Пример обработки пользовательских данных с фильтрацией активных пользователей, маскированием чувствительных данных и удалением внутренних полей.

```yaml
apiVersion: dataflow.dataflow.io/v1
kind: DataFlow
metadata:
  name: secure-pipeline
spec:
  source:
    type: postgresql
    config:
      connectionString: "postgres://dataflow:dataflow@postgres:5432/dataflow?sslmode=disable"
      table: users
      query: "SELECT * FROM users WHERE updated_at > NOW() - INTERVAL '1 hour'"
      pollInterval: 300
  sink:
    type: kafka
    config:
      brokers:
        - localhost:9092
      topic: public-users
  transformations:
    # Фильтровать только активных пользователей
    - type: filter
      config:
        condition: "$.active"

    # Маскировать чувствительные данные
    - type: mask
      config:
        fields:
          - password
          - email
        keepLength: true

    # Удалить внутренние поля
    - type: remove
      config:
        fields:
          - internal_id
          - secret_token
          - debug_info

    # Добавить временную метку экспорта
    - type: timestamp
      config:
        fieldName: exported_at
```

**Входное сообщение:**
```json
{
  "id": 1,
  "username": "john",
  "email": "john@example.com",
  "password": "secret123",
  "active": true,
  "internal_id": 999,
  "secret_token": "abc123"
}
```

**Выходное сообщение:**
```json
{
  "id": 1,
  "username": "john",
  "email": "***********",
  "password": "*********",
  "active": true,
  "exported_at": "2024-01-15T10:30:00Z"
}
```

## PostgreSQL → Kafka с выбором полей

Пример чтения из PostgreSQL, выборки определенных полей и отправки в Kafka.

```yaml
apiVersion: dataflow.dataflow.io/v1
kind: DataFlow
metadata:
  name: postgres-to-kafka-select
spec:
  source:
    type: postgresql
    config:
      connectionString: "postgres://dataflow:dataflow@postgres:5432/dataflow?sslmode=disable"
      table: orders
      query: "SELECT * FROM orders WHERE created_at > NOW() - INTERVAL '1 day'"
      pollInterval: 60
  sink:
    type: kafka
    config:
      brokers:
        - localhost:9092
      topic: order-events
  transformations:
    - type: select
      config:
        fields:
          - order_id
          - customer_id
          - total
          - status
          - created_at
    - type: timestamp
      config:
        fieldName: processed_at
```

## PostgreSQL → PostgreSQL (репликация / ETL)

Пример чтения данных из одной PostgreSQL базы и записи преобразованных данных в другую PostgreSQL базу.

```yaml
apiVersion: dataflow.dataflow.io/v1
kind: DataFlow
metadata:
  name: postgres-to-postgres
spec:
  source:
    type: postgresql
    config:
      connectionString: "postgres://dataflow:dataflow@source-postgres:5432/source_db?sslmode=disable"
      table: source_orders
      query: "SELECT * FROM source_orders WHERE updated_at > NOW() - INTERVAL '5 minutes'"
      pollInterval: 60
  sink:
    type: postgresql
    config:
      connectionString: "postgres://dataflow:dataflow@target-postgres:5432/target_db?sslmode=disable"
      table: target_orders
      autoCreateTable: true
      batchSize: 100
      upsertMode: true  # Включает обновление существующих записей вместо пропуска
  transformations:
    # Оставляем только нужные поля
    - type: select
      config:
        fields:
          - id
          - customer_id
          - total
          - status
          - updated_at
    # Добавляем время синхронизации
    - type: timestamp
      config:
        fieldName: synced_at
```

**Варианты использования:**

- **Онлайн-репликация**: периодическое копирование обновленных записей из операционной БД в аналитическую
- **ETL-пайплайн**: подготовка и очистка данных при переносе между схемами/кластерами PostgreSQL

**Важно:** При использовании `upsertMode: true` существующие записи в целевой таблице будут обновляться при конфликте по PRIMARY KEY (или указанному `conflictKey`). Без `upsertMode` обновленные записи из источника будут пропускаться, если они уже существуют в целевой таблице.


## Комплексный пример: ETL пайплайн

Полноценный ETL пайплайн с множественными трансформациями.

```yaml
apiVersion: dataflow.dataflow.io/v1
kind: DataFlow
metadata:
  name: etl-pipeline
spec:
  source:
    type: kafka
    config:
      brokers:
        - kafka1:9092
        - kafka2:9092
      topic: raw-events
      consumerGroup: etl-group
  sink:
    type: postgresql
    config:
      connectionString: "postgres://dataflow:dataflow@postgres:5432/analytics?sslmode=disable"
      table: processed_events
      autoCreateTable: true
      batchSize: 100
  transformations:
    # 1. Развернуть вложенные массивы
    - type: flatten
      config:
        field: items

    # 2. Добавить временную метку обработки
    - type: timestamp
      config:
        fieldName: processed_at
        format: RFC3339

    # 3. Фильтровать только валидные события
    - type: filter
      config:
        condition: "$.valid"

    # 4. Маскировать PII данные
    - type: mask
      config:
        fields:
          - user.email
          - user.phone
        keepLength: true

    # 5. Удалить отладочную информацию
    - type: remove
      config:
        fields:
          - debug
          - internal_metadata
          - test_flag

    # 6. Выбрать только нужные поля для финального результата
    - type: select
      config:
        fields:
          - event_id
          - user.id
          - item.sku
          - item.quantity
          - processed_at
```

## Kafka → Kafka с роутингом по типам

Пример чтения из одного Kafka топика и маршрутизации в разные топики на основе типа события.

```yaml
apiVersion: dataflow.dataflow.io/v1
kind: DataFlow
metadata:
  name: kafka-router
spec:
  source:
    type: kafka
    config:
      brokers:
        - localhost:9092
      topic: all-events
      consumerGroup: router-group
  sink:
    type: kafka
    config:
      brokers:
        - localhost:9092
      topic: default-events
  transformations:
    - type: router
      config:
        routes:
          - condition: "$.type"
            sink:
              type: kafka
              config:
                brokers:
                  - localhost:9092
                topic: user-events
          - condition: "$.category"
            sink:
              type: kafka
              config:
                brokers:
                  - localhost:9092
                topic: product-events
```

## Использование Secrets для credentials

DataFlow Operator поддерживает конфигурацию коннекторов из Kubernetes Secrets через поля `*SecretRef`.

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: kafka-credentials
  namespace: default
type: Opaque
stringData:
  brokers: "kafka1:9092,kafka2:9092"
  topic: "input-topic"
  consumerGroup: "dataflow-group"
  username: "kafka-user"
  password: "kafka-password"
---
apiVersion: v1
kind: Secret
metadata:
  name: postgres-credentials
  namespace: default
type: Opaque
stringData:
  connectionString: "postgres://user:password@postgres:5432/dbname?sslmode=disable"
  table: "output_table"
---
apiVersion: dataflow.dataflow.io/v1
kind: DataFlow
metadata:
  name: secure-dataflow
spec:
  source:
    type: kafka
    config:
      brokersSecretRef:
        name: kafka-credentials
        key: brokers
      topicSecretRef:
        name: kafka-credentials
        key: topic
      consumerGroupSecretRef:
        name: kafka-credentials
        key: consumerGroup
      securityProtocol: SASL_PLAINTEXT
      sasl:
        mechanism: scram-sha-256
        usernameSecretRef:
          name: kafka-credentials
          key: username
        passwordSecretRef:
          name: kafka-credentials
          key: password
  sink:
    type: postgresql
    config:
      connectionStringSecretRef:
        name: postgres-credentials
        key: connectionString
      tableSecretRef:
        name: postgres-credentials
        key: table
      autoCreateTable: true
```

**Применение:**
```bash
kubectl apply -f dataflow/config/samples/kafka-to-postgres-secrets.yaml
```

Поддерживаемые поля, TLS сертификаты и устранение неполадок — в разделе [Использование Secrets в Kubernetes](connectors.md#использование-secrets-в-kubernetes).

## Мониторинг и отладка

### Проверка статуса DataFlow

```bash
# Получить список всех DataFlow
kubectl get dataflow

# Детальная информация
kubectl describe dataflow <name>

# Статус в формате YAML
kubectl get dataflow <name> -o yaml
```

### Просмотр логов

```bash
# Логи оператора
kubectl logs -l app.kubernetes.io/name=dataflow-operator -f

# События Kubernetes
kubectl get events --sort-by='.lastTimestamp' | grep dataflow
```

### Проверка обработанных сообщений

Статус DataFlow содержит метрики:

```yaml
status:
  phase: Running
  processedCount: 1500
  errorCount: 2
  lastProcessedTime: "2024-01-15T10:30:00Z"
  message: "Processing messages successfully"
```

## Рекомендации

### Производительность

- Используйте `batchSize` для PostgreSQL приемников
- Настройте правильный `pollInterval` для PostgreSQL источников
- Используйте несколько инстансов оператора для масштабирования

### Безопасность

- Используйте Kubernetes Secrets для credentials
- Включайте TLS для Kafka соединений
- Маскируйте чувствительные данные перед отправкой

### Надежность

- Настройте правильные consumer groups для Kafka
- Мониторьте статус DataFlow ресурсов

## Высоконагруженный Kafka-пайплайн

При высокой скорости сообщений Kafka (десятки тысяч msg/s) увеличьте `channelBufferSize` и `batchSize` в sink:

```yaml
spec:
  channelBufferSize: 500   # по умолчанию 100; снижает блокировки, когда sink медленнее source
  source:
    type: kafka
    config:
      brokers: [localhost:9092]
      topic: high-volume-topic
      consumerGroup: dataflow-group
  sink:
    type: postgresql
    config:
      connectionString: "..."
      table: events
      batchSize: 500
      batchFlushIntervalSeconds: 2
```

## Настройка ресурсов и размещения подов

Каждый ресурс DataFlow создает отдельный под (Deployment) для обработки данных. Вы можете настроить ресурсы, выбор нод, affinity и tolerations для этих подов.

### Пример: Кастомные ресурсы и выбор нод

```yaml
apiVersion: dataflow.dataflow.io/v1
kind: DataFlow
metadata:
  name: kafka-to-postgres-with-resources
spec:
  source:
    type: kafka
    config:
      brokers:
        - localhost:9092
      topic: input-topic
      consumerGroup: dataflow-group
  sink:
    type: postgresql
    config:
      connectionString: "postgres://dataflow:dataflow@postgres:5432/dataflow?sslmode=disable"
      table: output_table
  # Настройка ресурсов для пода процессора
  resources:
    requests:
      cpu: "200m"
      memory: "256Mi"
    limits:
      cpu: "1000m"
      memory: "1Gi"
  # Выбор нод для размещения пода
  nodeSelector:
    node-type: compute
    zone: us-east-1
  # Правила affinity для более точного контроля размещения
  affinity:
    nodeAffinity:
      requiredDuringSchedulingIgnoredDuringExecution:
        nodeSelectorTerms:
        - matchExpressions:
          - key: kubernetes.io/arch
            operator: In
            values:
            - amd64
      preferredDuringSchedulingIgnoredDuringExecution:
      - weight: 100
        preference:
          matchExpressions:
          - key: node-type
            operator: In
            values:
            - compute
    podAffinity:
      preferredDuringSchedulingIgnoredDuringExecution:
      - weight: 50
        podAffinityTerm:
          labelSelector:
            matchExpressions:
            - key: app
              operator: In
              values:
              - dataflow-processor
          topologyKey: kubernetes.io/hostname
  # Tolerations для работы с tainted нодами
  tolerations:
  - key: dedicated
    operator: Equal
    value: dataflow
    effect: NoSchedule
  - key: workload-type
    operator: Equal
    value: batch
    effect: NoSchedule
```

**Применение:**
```bash
kubectl apply -f dataflow/config/samples/kafka-to-postgres-with-resources.yaml
```

### Настройка ресурсов

- **resources**: Определяет запросы и лимиты CPU и памяти для пода процессора
  - Если не указано, используются значения по умолчанию: `100m` CPU / `128Mi` памяти (requests), `500m` CPU / `512Mi` памяти (limits)
  - Используйте это для обеспечения достаточных ресурсов для высоконагруженной обработки

### Выбор нод

- **nodeSelector**: Простые пары ключ-значение для выбора конкретных нод
  - Пример: `node-type: compute` гарантирует, что поды будут запускаться только на нодах с меткой `node-type=compute`

### Правила Affinity

- **affinity**: Продвинутые правила размещения с использованием Kubernetes affinity
  - **nodeAffinity**: Контроль того, на каких нодах могут запускаться поды
  - **podAffinity**: Предпочтение запуска подов рядом с другими подами (например, другими процессорами dataflow)
  - **podAntiAffinity**: Избегание запуска подов рядом с другими подами (например, распределение по нодам)

### Tolerations

- **tolerations**: Позволяют подам запускаться на tainted нодах
  - Полезно для выделенных compute нод или специализированного оборудования
  - Пример: Запуск процессоров dataflow на нодах, выделенных для batch workloads

### Поведение по умолчанию

Если ресурсы, nodeSelector, affinity или tolerations не указаны:
- Применяются ресурсы по умолчанию (100m CPU / 128Mi памяти requests, 500m CPU / 512Mi памяти limits)
- Поды могут запускаться на любой ноде (нет nodeSelector)
- Не применяются правила affinity
- Поды не могут запускаться на tainted нодах (нет tolerations)

### Проверка статуса подов

После создания DataFlow с кастомными ресурсами проверьте под:

```bash
# Список подов, созданных DataFlow
kubectl get pods -l app=dataflow-processor

# Описание конкретного пода
kubectl describe pod df-<name>-<hash>

# Проверка использования ресурсов
kubectl top pod df-<name>-<hash>
```

## Высоконагруженный Kafka → ClickHouse

Пример для обработки высокого объема сообщений Kafka в ClickHouse с оптимизированными настройками производительности.

```yaml
apiVersion: dataflow.dataflow.io/v1
kind: DataFlow
metadata:
  name: kafka-to-clickhouse-high-volume
spec:
  # Увеличиваем буфер канала для высокой нагрузки
  channelBufferSize: 1000
  # Message-level ack для сужения окна возможных дубликатов
  ackGranularity: message
  source:
    type: kafka
    config:
      brokers:
        - kafka:9092
      topic: high-volume-events
      consumerGroup: dataflow-high-volume-group
  sink:
    type: clickhouse
    config:
      connectionString: "clickhouse://default@clickhouse:9000/default?dial_timeout=30s"
      table: events_high_volume
      # Большой batch size для высокой пропускной способности
      batchSize: 1000
      batchFlushIntervalSeconds: 5
      autoCreateTable: true
      upsertMode: true
      conflictKey: event_id
  resources:
    requests:
      cpu: "500m"
      memory: "512Mi"
    limits:
      cpu: "2000m"
      memory: "2Gi"
```

**Применение:**
```bash
kubectl apply -f dataflow/config/samples/kafka-to-clickhouse-high-volume.yaml
```

**Ключевые настройки для высокой нагрузки:**
- `channelBufferSize: 1000` — увеличенный буфер между source и sink
- `batchSize: 1000` — большие batches для эффективной записи в ClickHouse
- `ackGranularity: message` — быстрый commit offset для уменьшения дубликатов
- Увеличенные CPU/memory limits для обработки больших batches

## Dead Letter Queue (DLQ) Pattern

Пример реализации паттерна Dead Letter Queue для обработки ошибочных сообщений. Невалидные или ошибочные сообщения направляются в отдельный Kafka топик для последующего анализа.

```yaml
apiVersion: dataflow.dataflow.io/v1
kind: DataFlow
metadata:
  name: pipeline-with-dlq
spec:
  ackGranularity: message
  source:
    type: kafka
    config:
      brokers:
        - kafka:9092
      topic: main-events
      consumerGroup: dataflow-dlq-group
  sink:
    type: postgresql
    config:
      connectionString: "postgres://dataflow:dataflow@postgres:5432/dataflow?sslmode=disable"
      table: processed_events
      upsertMode: true
      conflictKey: event_id
      batchSize: 100
  # Dead Letter Queue для ошибочных сообщений
  errors:
    type: kafka
    config:
      brokers:
        - kafka:9092
      topic: dead-letter-queue
    ackPolicy: afterWrite
  transformations:
    # Валидация: только сообщения с обязательными полями
    - type: filter
      config:
        condition: "$.event_id && $.user_id && $.timestamp"
    - type: timestamp
      config:
        fieldName: processed_at
```

**Применение:**
```bash
kubectl apply -f dataflow/config/samples/dead-letter-queue-example.yaml
```

**Поведение DLQ:**
- Сообщения, не прошедшие фильтрацию или вызвавшие ошибку, отправляются в `dead-letter-queue`
- `ackPolicy: afterWrite` — коммит offset после записи в DLQ
- Можно использовать `never` для повторной обработки после исправления ошибки

## PostgreSQL CDC → Kafka (Change Data Capture)

Пример потоковой репликации изменений из PostgreSQL в Kafka с использованием logical replication (CDC). Поддерживает INSERT, UPDATE, DELETE события с маршрутизацией по таблицам.

```yaml
apiVersion: dataflow.dataflow.io/v1
kind: DataFlow
metadata:
  name: postgres-cdc-to-kafka
spec:
  ackGranularity: message
  checkpointPersistence: true
  source:
    type: postgresql-cdc
    config:
      connectionString: "postgres://repl_user:repl_pass@postgres:5432/production?sslmode=disable"
      slotName: cdc_to_kafka_slot
      publicationName: cdc_to_kafka_pub
      tables:
        - public.users
        - public.orders
        - public.products
      snapshotMode: initial
      createSlotIfNotExists: true
      createPublicationIfNotExists: true
      heartbeatIntervalSeconds: 30
  sink:
    type: kafka
    config:
      brokers:
        - kafka:9092
      topic: cdc-events-default
  transformations:
    - type: timestamp
      config:
        fieldName: cdc_processed_at
    # Маршрутизация событий по таблицам в разные топики
    - type: router
      config:
        routes:
          - condition: "$.source.table == 'users'"
            sink:
              type: kafka
              config:
                brokers: [kafka:9092]
                topic: cdc.users
          - condition: "$.source.table == 'orders'"
            sink:
              type: kafka
              config:
                brokers: [kafka:9092]
                topic: cdc.orders
          - condition: "$.source.table == 'products'"
            sink:
              type: kafka
              config:
                brokers: [kafka:9092]
                topic: cdc.products
```

**Применение:**
```bash
kubectl apply -f dataflow/config/samples/postgres-cdc-to-kafka.yaml
```

**Предварительная настройка PostgreSQL:**
```sql
-- Создание пользователя для репликации
CREATE USER repl_user WITH REPLICATION LOGIN PASSWORD 'repl_pass';

-- Настройка publication для CDC
CREATE PUBLICATION cdc_to_kafka_pub FOR TABLE users, orders, products;

-- Предоставление прав на таблицы
GRANT SELECT ON ALL TABLES IN SCHEMA public TO repl_user;
```

**Особенности:**
- `snapshotMode: initial` — сначала копирует существующие данные, затем потоковые изменения
- `heartbeatIntervalSeconds` — поддерживает replication slot активным
- Автоматическое создание slot и publication если не существуют

## Миграция данных со сменой схемы (Schema Evolution)

Пример постепенной миграции данных из legacy системы в новую схему с преобразованием полей, flatten вложенных структур и добавлением метаданных.

```yaml
apiVersion: dataflow.dataflow.io/v1
kind: DataFlow
metadata:
  name: schema-evolution-pipeline
spec:
  ackGranularity: message
  checkpointPersistence: true
  source:
    type: postgresql
    config:
      connectionString: "postgres://dataflow:dataflow@source-postgres:5432/legacy?sslmode=disable"
      table: legacy_events
      query: "SELECT id, old_data, created_at, version FROM legacy_events WHERE migrated = false"
      pollInterval: 10
      changeTrackingColumn: created_at
      orderByColumn: id
  sink:
    type: postgresql
    config:
      connectionString: "postgres://dataflow:dataflow@target-postgres:5432/modern?sslmode=disable"
      table: modern_events
      autoCreateTable: true
      upsertMode: true
      conflictKey: legacy_id
      batchSize: 200
  transformations:
    # Преобразуем старую схему в новую
    - type: select
      config:
        fields:
          - id
          - old_data
          - created_at
          - version
    # Разворачиваем вложенные данные
    - type: flatten
      config:
        field: old_data.items
    # Преобразуем в camelCase для новой схемы
    - type: camelCase
    # Добавляем метаданные миграции
    - type: timestamp
      config:
        fieldName: migrated_at
    # Фильтруем только валидные записи
    - type: filter
      config:
        condition: "$.eventType && $.userId"
```

**Применение:**
```bash
kubectl apply -f dataflow/config/samples/schema-evolution-migration.yaml
```

**Сценарии использования:**
- Постепенная миграция legacy данных без downtime
- Преобразование схемы (snake_case → camelCase)
- Разворачивание денормализованных JSON структур
- Фильтрация некорректных записей

## Multi-Source Aggregation Pattern

Пример паттерна агрегации данных из нескольких источников. В production используйте отдельные DataFlow для каждого источника с общим sink или Kafka как intermediate buffer.

```yaml
apiVersion: dataflow.dataflow.io/v1
kind: DataFlow
metadata:
  name: multi-source-aggregator
spec:
  # Читаем агрегированные события из Kafka
  source:
    type: kafka
    config:
      brokers:
        - kafka:9092
      topic: aggregated-events
      consumerGroup: aggregator-group
  sink:
    type: postgresql
    config:
      connectionString: "postgres://dataflow:dataflow@postgres:5432/dataflow?sslmode=disable"
      table: aggregated_metrics
      upsertMode: true
      conflictKey: metric_id
      batchSize: 500
  transformations:
    # Обогащение: выбираем нужные поля
    - type: select
      config:
        fields:
          - metric_id
          - source_system
          - metric_value
          - timestamp
          - metadata
    # Нормализация ключей для БД
    - type: snakeCase
    # Добавляем время агрегации
    - type: timestamp
      config:
        fieldName: aggregated_at
```

**Применение:**
```bash
kubectl apply -f dataflow/config/samples/multi-source-aggregation.yaml
```

**Архитектура multi-source:**
```
Source 1 (PostgreSQL) → Kafka Topic 1 ─┐
Source 2 (ClickHouse) → Kafka Topic 2 ─┼→ Aggregator DataFlow → PostgreSQL
Source 3 (Trino)      → Kafka Topic 3 ─┘
```

## Дополнительные примеры

Больше примеров можно найти в директории `dataflow/config/samples/`:

| Пример | Описание |
|--------|----------|
| `kafka-to-postgres.yaml` | Базовый Kafka → PostgreSQL |
| `kafka-to-clickhouse.yaml` | Базовый Kafka → ClickHouse |
| `kafka-to-clickhouse-high-volume.yaml` | Высоконагруженный поток Kafka → ClickHouse |
| `kafka-to-postgres-secrets.yaml` | Использование Kubernetes Secrets |
| `kafka-debezium-to-postgres.yaml` | Kafka (Debezium envelope) → PostgreSQL через `debeziumUnwrap` |
| `kafka-to-postgres-with-resources.yaml` | Настройка ресурсов и размещения |
| `kafka-to-postgres-with-errors.yaml` | Обработка ошибок с error sink |
| `kafka-to-postgres-raw.yaml` | Kafka с rawMode для сохранения метаданных |
| `kafka-to-nessie.yaml` | Kafka → Nessie/Iceberg |
| `kafka-to-trino.yaml` | Kafka → Trino |
| `kafka-to-trino-secrets.yaml` | Kafka → Trino с Secrets |
| `kafka-to-iceberg.yaml` | Kafka → Iceberg REST Catalog |
| `nessie-to-kafka.yaml` | Nessie → Kafka |
| `flatten-example.yaml` | Flatten трансформация |
| `router-example.yaml` | Router трансформация |
| `postgres-to-kafka-router.yaml` | PostgreSQL → Kafka с роутингом |
| `postgresql-cdc-to-postgres.yaml` | PostgreSQL CDC → PostgreSQL |
| `postgres-cdc-to-kafka.yaml` | PostgreSQL CDC → Kafka |
| `clickhouse-to-clickhouse.yaml` | ClickHouse → ClickHouse |
| `clickhouse-to-clickhouse2.yaml` | ClickHouse → ClickHouse (вариант) |
| `dataflowcron-example.yaml` | DataFlowCron с триггерами |
| `pg-to-pg-test.yaml` | PostgreSQL → PostgreSQL |
| `pg-to-pg-test2.yaml` | PostgreSQL → PostgreSQL (вариант) |
| `dead-letter-queue-example.yaml` | Dead Letter Queue паттерн |
| `schema-evolution-migration.yaml` | Миграция со сменой схемы |
| `multi-source-aggregation.yaml` | Агрегация из нескольких источников |
