# Best Practices

Рекомендации по проектированию, развертыванию и эксплуатации DataFlow Operator для достижения оптимальной производительности, надежности и безопасности.

## Проектирование пайплайнов

### Выбор между DataFlow и DataFlowCron

**Используйте DataFlow когда:**
- Нужна непрерывная потоковая обработка
- Источник — Kafka (streaming)
- Требуется минимальная задержка (low latency)
- Нет явного "конца" потока данных

**Используйте DataFlowCron когда:**
- Задача должна выполняться по расписанию
- Источник — polling база данных (PostgreSQL, ClickHouse, Trino, Nessie)
- Нужны post-processing шаги (triggers)
- Процесс имеет начало и конец (batch processing)

### Архитектура пайплайнов

**1. Single Responsibility**
Каждый DataFlow должен решать одну задачу:
```yaml
# Хорошо: четкая цель
name: user-events-enrichment
source: kafka://user-events
sink: postgresql://analytics.users

# Плохо: смешение целей
name: everything-pipeline
source: kafka://all-topics  # Слишком широко
```

**2. Intermediate Topics**
Для сложных маршрутов используйте Kafka как промежуточный буфер:
```
DataFlow A: Source → Kafka Topic A
DataFlow B: Kafka Topic A → Transform → Kafka Topic B
DataFlow C: Kafka Topic B → Sink
```

**3. Error Handling Strategy**
```yaml
# Всегда настраивайте error sink для production
spec:
  errors:
    type: kafka
    config:
      brokers: [kafka:9092]
      topic: error-messages-${ENV}
    ackPolicy: afterWrite
```

## Безопасность

### Secrets Management

**Никогда не храните credentials в манифестах:**
```yaml
# Плохо: plaintext credentials
sink:
  config:
    connectionString: "postgres://user:password@host/db"  # ❌

# Хорошо: SecretRef
sink:
  config:
    connectionStringSecretRef:
      name: db-credentials
      key: connection-string
```

**Создание Secrets:**
```bash
# Создайте secret из файла
kubectl create secret generic db-credentials \
  --from-literal=connection-string="postgres://user:pass@host/db" \
  --from-literal=password="secure-password"

# Или из файла
echo -n "secure-password" > password.txt
kubectl create secret generic db-credentials \
  --from-file=password=password.txt
rm password.txt
```

### TLS/SSL Configuration

**Всегда используйте TLS для production Kafka:**
```yaml
source:
  type: kafka
  config:
    securityProtocol: SASL_SSL
    tls:
      caFile: /etc/certs/ca.crt
      certFile: /etc/certs/client.crt
      keyFile: /etc/certs/client.key
    sasl:
      mechanism: scram-sha-512
      usernameSecretRef:
        name: kafka-credentials
        key: username
      passwordSecretRef:
        name: kafka-credentials
        key: password
```

**Монтирование сертификатов:**
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: kafka-certs
type: Opaque
data:
  ca.crt: <base64-encoded>
  client.crt: <base64-encoded>
  client.key: <base64-encoded>
```

### Network Policies

**Ограничьте сетевой доступ:**
```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: dataflow-processor
spec:
  podSelector:
    matchLabels:
      app: dataflow-processor
  policyTypes:
    - Ingress
    - Egress
  egress:
    - to:
        - podSelector:
            matchLabels:
              app: kafka
      ports:
        - protocol: TCP
          port: 9092
    - to:
        - podSelector:
            matchLabels:
              app: postgresql
      ports:
        - protocol: TCP
          port: 5432
```

## Производительность

### Batch Size Optimization (SQL sinks)

Физический размер write-batch (`sink.config.batchSize`) и момент source ack (`spec.ackGranularity`) — **разные рычаги**. При default `collapseBatchOnMessageAck: true` значение `ackGranularity: message` всё ещё принудительно ставит `MaxBatchSize = 1` — задайте `collapseBatchOnMessageAck: false`, если нужны bulk SQL-записи **и** per-message commit источника. Подробнее: [Отказоустойчивость — развязка ack и sink batch](fault-tolerance.md#развязка-ack-и-sink-batch-speccollapsebatchonmessageack).

| Sink | Runtime default (если `batchSize` не задан) | Рекомендация | Admission warning если меньше |
|------|-------------------------|--------------|-------------------------------|
| PostgreSQL | **100** (`sinkbatch.DefaultPostgreSQLBatchSize`) | 100–500 (до ~1000) | &lt; 100 |
| ClickHouse | **500** (`sinkbatch.DefaultClickHouseBatchSize`) | 500–1000 | &lt; 500 |
| Trino | **10** (`sinkbatch.DefaultTrinoBatchSize`) | ≥ 10 (скромнее для крупного JSON / Iceberg) | &lt; 10 |

`sink.config` — неструктурированный `RawExtension`, поэтому эти значения подставляет **processor**, если поле опущено (не OpenAPI default CRD). Единый источник: `dataflow/pkg/sinkbatch`. `batchSize: 0` — flush **только по таймеру** (`batchFlushIntervalSeconds`, default **10** через `sinkbatch.DefaultBatchFlushIntervalSeconds`). Явные значения ниже рекомендованного порога дают admission **warning** (не reject).

#### Как пишет каждый SQL sink

**PostgreSQL**

- Копит до `batchSize` (или flush interval), затем **одна транзакция**.
- Путь flush (автоматически): `COPY FROM` для однородного plain `INSERT` (без `ON CONFLICT`); иначе один multi-row `INSERT … VALUES` (включая `ON CONFLICT` / upsert); смешанные `UPDATE`/гетерогенные формы — `pgx.Batch`.
- Source ack — **только после** успешного Commit (`AckAfterSuccessfulWrite`).
- Одно соединение на sink pod (`pgx.Connect`, не pool). Предпочтительнее укрупнять batch, чем плодить соединения.
- Soft-delete попадает в ту же batch TX (для такого flush — `pgx.Batch`).

```yaml
sink:
  type: postgresql
  config:
    batchSize: 500
    batchFlushIntervalSeconds: 10
    upsertMode: true
    conflictKey: id
```

**ClickHouse**

- Default batch **500**. Flush: native `PrepareBatch`, если доступно; иначе один multi-row `INSERT … VALUES` через Exec.
- Source ack — **один раз** после успешного flush (не mid-batch). Так сохраняется at-least-once при частичном сбое.
- В raw mode в INSERT идёт `message.Data` as-is (без Unmarshal→Marshal на пути записи).
- Крупные batch снижают частоту insert и помогают избежать `TOO_MANY_PARTS`. Обычно `batchFlushIntervalSeconds: 5–10` при `batchSize` 500–1000.

```yaml
sink:
  type: clickhouse
  config:
    batchSize: 1000
    batchFlushIntervalSeconds: 5
    upsertMode: true
    conflictKey: id
```

**Trino**

- Default batch **10**. Каждый flush — один HTTP statement (multi-row `INSERT ... VALUES`) плюс polling `nextUri` до `FINISHED`.
- Upsert идёт через **`MERGE`** (каталоги Iceberg) — медленнее plain INSERT; admission предупреждает при `upsertMode: true`. Держите batch скромным и задавайте `queryTimeoutSeconds` на всё окно polling.
- Для throughput предпочитайте multi-row INSERT; MERGE — только когда нужны идемпотентные обновления.

```yaml
sink:
  type: trino
  config:
    batchSize: 10
    batchFlushIntervalSeconds: 10
    queryTimeoutSeconds: 600
    # upsertMode: true   # MERGE slow-path — только если нужен
    # conflictKey: id
```

#### Чеклист тюнинга

1. Начните с defaults выше; поднимайте PG/CH batch при устойчивой нагрузке, пока не упрётесь в latency/память.
2. Высокий Kafka volume: `ackGranularity: batch` **или** `message` + `collapseBatchOnMessageAck: false`.
3. При ClickHouse `TOO_MANY_PARTS` сначала увеличьте `batchSize` / flush interval.
4. Для Trino Iceberg/Nessie держите `batchSize` таким, чтобы один statement укладывался в `queryTimeoutSeconds`.
5. Для Nessie/Iceberg source включайте `incrementalBySnapshot` и при больших таблицах — `maxRowsPerPoll` / `maxBytesPerPoll`.

### Что настраивается в YAML, а что автоматически

| Рычаг | Где | Заметки |
|------|-----|---------|
| `channelBufferSize`, `transformWorkers`, `ackGranularity`, `collapseBatchOnMessageAck` | DataFlow `spec` | Backpressure и ack vs размер записи |
| `checkpointSyncOnAck`, `checkpointSaveInterval` | DataFlow `spec` | Политика flush checkpoint; sync-on-ack — **async/coalesced** (ack path не ждёт ConfigMap Patch) |
| Sink `batchSize`, `batchFlushIntervalSeconds` | sink `config` | Физический write batch |
| Kafka `async`, `compression`, `flush*` | Kafka sink `config` | Defaults: `async=true`, `compression=snappy`, flush 100 msgs / 100ms |
| `incrementalBySnapshot`, `maxRowsPerPoll`, `maxBytesPerPoll` | Nessie/Iceberg source `config` | Snapshot incremental + лимиты poll |
| PG `COPY` vs multi-VALUES vs `pgx.Batch` | Автоматически | По форме flush |
| CH `PrepareBatch` vs Exec | Автоматически | Native driver при наличии |
| Lakehouse file-delta / parquet fast path | Автоматически | В incremental при added files без deletes |

### Buffer Sizing

Каналы между source, transform и sink — **буферизованные и блокирующие** (по умолчанию 100). Больший буфер сглаживает короткие паузы sink. Смотрите `dataflow_channel_fill_ratio{channel="source|routing|…"}` при устойчивой насыщенности (CDC и lakehouse семплируют source channel). Flush sink уже перекрывается с накоплением следующего batch (double-buffer). Для CPU-тяжёлых transforms увеличьте `transformWorkers` (порядок emit сохраняется). Подробности: [Архитектура — concurrency пайплайна](architecture.md#pipeline-concurrency-implementation).

**Channel Buffer:**
```yaml
spec:
  # Для нормальной нагрузки
  channelBufferSize: 100  # default
  
  # Для высоконагруженных потоков
  channelBufferSize: 1000
  
  # Для ограниченной памяти
  channelBufferSize: 50
```

**Transform workers (параллелизм внутри пода):**
```yaml
spec:
  transformWorkers: 4  # по умолчанию 1; диапазон 1–64
```

`replicas > 1` — только для источника **Kafka**. Для polling/CDC оставляйте `replicas: 1` и увеличивайте `readBatchSize` / `batchSize` / `resources` / `transformWorkers`.

### Resource Allocation

**Baseline Resources:**
```yaml
spec:
  resources:
    requests:
      cpu: "200m"
      memory: "256Mi"
    limits:
      cpu: "1000m"
      memory: "512Mi"
```

**High-Volume Processing:**
```yaml
spec:
  resources:
    requests:
      cpu: "1000m"
      memory: "1Gi"
    limits:
      cpu: "2000m"
      memory: "2Gi"
```

**Resource Guidelines:**
| Scenario | CPU Request | Memory Request | CPU Limit | Memory Limit |
|----------|-------------|----------------|-----------|--------------|
| Light load | 100m | 128Mi | 500m | 256Mi |
| Normal load | 200m | 256Mi | 1000m | 512Mi |
| Heavy load | 500m | 512Mi | 2000m | 1Gi |
| High volume | 1000m | 1Gi | 2000m | 2Gi |

### Polling Source Optimization

**PostgreSQL Source:**
```yaml
source:
  type: postgresql
  config:
    # Частый poll для real-time
    pollInterval: 5  # seconds
    
    # Редкий poll для batch
    pollInterval: 300  # 5 minutes
    
    # Размер читаемого batch
    readBatchSize: 1000
    
    # Колонка для отслеживания изменений
    changeTrackingColumn: updated_at
    orderByColumn: id
```

## Отказоустойчивость

### Idempotency Configuration

**Всегда настраивайте идемпотентность:**
```yaml
spec:
  sink:
    type: postgresql
    config:
      upsertMode: true
      conflictKey: id
```

**Different Upsert Strategies:**

PostgreSQL:
```yaml
sink:
  type: postgresql
  config:
    upsertMode: true
    conflictKey: id
    upsertStrategy: ifNewer  # или replace
    upsertVersionColumn: updated_at
```

ClickHouse:
```yaml
sink:
  type: clickhouse
  config:
    upsertMode: true
    conflictKey: id
    replacingVersionColumn: updated_at
    tableEngine: ReplacingMergeTree
```

### Checkpoint Configuration

**Polling Sources (PostgreSQL, ClickHouse, Trino):**
```yaml
spec:
  checkpointPersistence: true  # default
  checkpointSyncOnAck: true   # для критичных данных
  checkpointSaveInterval: 30s
```

**Kafka Source:**
```yaml
spec:
  # checkpointPersistence не нужен для Kafka
  # используется consumer group offset
  ackGranularity: message              # более быстрый commit offset
  collapseBatchOnMessageAck: false     # сохранить sink.config.batchSize для throughput
```

Подробнее: [Отказоустойчивость — развязка ack и sink batch](fault-tolerance.md#развязка-ack-и-sink-batch-speccollapsebatchonmessageack).

### Graceful Shutdown

**Termination Grace Period:**
```yaml
spec:
  # Достаточно времени для flush batch
  terminationGracePeriodSeconds: 600
```

**PreStop Hook:**
```yaml
lifecycle:
  preStop:
    exec:
      command: ["/bin/sh", "-c", "sleep 30"]
```

### Dead Letter Queue Pattern

```yaml
spec:
  errors:
    type: kafka
    config:
      brokers: [kafka:9092]
      topic: dlq-${ENV}
    ackPolicy: afterWrite
  transformations:
    - type: filter
      config:
        condition: "$.required_field"  # Проверка обязательных полей
```

## Мониторинг

### Key Metrics to Watch

**Throughput:**
```
dataflow_processed_messages_total
rate(dataflow_processed_messages_total[5m])
```

**Error Rate:**
```
dataflow_errors_total
rate(dataflow_errors_total[5m])
```

**Lag (для Kafka):**
```
kafka_consumer_group_lag
```

**Latency:**
```
dataflow_processing_duration_seconds
```

### Health Checks

**Liveness Probe:**
```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8080
  initialDelaySeconds: 30
  periodSeconds: 30
```

**Readiness Probe:**
```yaml
readinessProbe:
  httpGet:
    path: /ready
    port: 8080
  initialDelaySeconds: 10
  periodSeconds: 10
```

### Alerting Rules

**Prometheus Alerts:**
```yaml
groups:
  - name: dataflow
    rules:
      - alert: DataFlowHighErrorRate
        expr: rate(dataflow_errors_total[5m]) > 0.1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High error rate in DataFlow"
          
      - alert: DataFlowNoMessages
        expr: rate(dataflow_processed_messages_total[10m]) == 0
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "DataFlow stopped processing messages"
          
      - alert: DataFlowKafkaLagHigh
        expr: kafka_consumer_group_lag > 10000
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Kafka consumer lag is high"
```

## Эксплуатация

### Deployment Strategy

**Canary Deployment:**
```bash
# 1. Создайте новый DataFlow с другим именем
kubectl apply -f dataflow-canary.yaml

# 2. Проверьте метрики
kubectl top pods -l app=dataflow-processor

# 3. Удалите старый и переименуйте канареечный
kubectl delete dataflow old-pipeline
kubectl patch dataflow canary-pipeline -p '{"metadata":{"name":"new-pipeline"}}'
```

**Blue-Green Deployment:**
```yaml
# blue.yaml
metadata:
  name: pipeline-blue
  labels:
    version: blue

# green.yaml
metadata:
  name: pipeline-green
  labels:
    version: green
```

### Backup и Recovery

**Backup Checkpoint ConfigMap:**
```bash
# Экспорт checkpoint
kubectl get configmap df-<name>-checkpoint -o yaml > checkpoint-backup.yaml

# Восстановление
kubectl apply -f checkpoint-backup.yaml
```

**Reset Checkpoint:**
```yaml
# One-shot reset
spec:
  checkpointReset: true
```

### Maintenance Windows

**Scheduled Maintenance:**
```yaml
spec:
  maintenance:
    - startTime: "2024-01-15T02:00:00Z"
      duration: 2h
      repeat: weekly
      timezone: UTC
```

**Manual Suspension:**
```yaml
spec:
  suspended: true
```

## Тестирование

### Unit Testing Transformations

**Test JSONPath Expressions:**
```bash
# Используйте gjson cli или online playground
echo '{"user":{"active":true}}' | gjson "user.active"
# Output: true
```

### Integration Testing

**Test DataFlow:**
```bash
# 1. Создайте DataFlow для теста
kubectl apply -f test-dataflow.yaml

# 2. Отправьте тестовое сообщение
echo '{"test": true}' | kafka-console-producer --topic test-topic

# 3. Проверьте результат
kubectl logs -l app=dataflow-processor --tail=10

# 4. Очистите
kubectl delete dataflow test-dataflow
```

### Load Testing

**Generate Load:**
```bash
# Используйте kcat или kafka-producer-perf-test
kafka-producer-perf-test \
  --topic test-topic \
  --num-records 1000000 \
  --record-size 1000 \
  --throughput 10000 \
  --producer-props bootstrap.servers=localhost:9092
```

**Monitor Resources:**
```bash
watch kubectl top pods -l app=dataflow-processor
```

## Checklist для Production

### Pre-Deployment
- [ ] Версия Kind правильная (DataFlow vs DataFlowCron)
- [ ] Secrets через `*SecretRef` (не plaintext)
- [ ] Идемпотентный sink: `upsertMode: true` + `conflictKey`
- [ ] Для polling/cron: `checkpointSyncOnAck: true` + upsert
- [ ] `replicas: 1` для non-Kafka sources
- [ ] При CPU-тяжёлых transforms: настроен `transformWorkers` (оставьте `1`, если transforms дешёвые)
- [ ] Error sink настроен
- [ ] Resources (requests/limits) установлены
- [ ] `batchSize` / `ackGranularity` / `collapseBatchOnMessageAck` сбалансированы (message-ack не обязан означать `batchSize: 1`)
- [ ] Для Trino: `queryTimeoutSeconds` с запасом

### Post-Deployment
- [ ] Под в статусе Running
- [ ] Метрики processing/published сообщений
- [ ] Нет ошибок в логах
- [ ] Мониторинг и алерты настроены
- [ ] Alerting rules активны
- [ ] Backup checkpoint настроен

### Security
- [ ] TLS для Kafka
- [ ] Network Policies применены
- [ ] RBAC настроен
- [ ] Secrets ротированы
- [ ] Security headers проверены

### Documentation
- [ ] Манифест задокументирован
- [ ] Architecture diagram обновлен
- [ ] Runbook создан
- [ ] Contact list для on-call
