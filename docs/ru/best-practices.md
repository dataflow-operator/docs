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

### Batch Size Optimization

**PostgreSQL Sink:**
```yaml
sink:
  type: postgresql
  config:
    # Начните с 100-500 для нормальной нагрузки
    batchSize: 500
    # При проблемах с памятью уменьшите
    # Для высокой нагрузки увеличьте до 1000
```

**ClickHouse Sink:**
```yaml
sink:
  type: clickhouse
  config:
    # ClickHouse эффективен с большими batches
    batchSize: 1000
    batchFlushIntervalSeconds: 5
```

**Trino Sink:**
```yaml
sink:
  type: trino
  config:
    # Trino менее эффективен с большими batches
    # Используйте маленькие batches
    batchSize: 10
```

### Buffer Sizing

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
  ackGranularity: message  # для минимальных дубликатов
```

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
- [ ] Error sink настроен
- [ ] Resources (requests/limits) установлены
- [ ] `batchSize` / `ackGranularity` сбалансированы
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
