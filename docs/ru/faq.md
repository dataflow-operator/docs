# FAQ и Troubleshooting

Часто задаваемые вопросы и решения типичных проблем при работе с DataFlow Operator.

## Общие вопросы

### Какая разница между DataFlow и DataFlowCron?

| Характеристика | DataFlow | DataFlowCron |
|----------------|----------|--------------|
| Workload | Deployment (постоянный) | CronJob + Job (по расписанию) |
| Использование | Потоковая обработка, continuous sync | Scheduled batch ETL |
| Завершение | При удалении ресурса | Polling source exhausted → Job succeeded |
| Post-steps | Нет | Optional `triggers` после processor |
| `replicas > 1` | Только для Kafka source | Не поддерживается |

**Когда использовать DataFlow:**
- Непрерывная потоковая обработка Kafka событий
- Real-time репликация данных
- Обработка с минимальной задержкой

**Когда использовать DataFlowCron:**
- ETL задачи по расписанию (ежечасно, ежедневно)
- Миграции данных с началом и концом
- Задачи с post-processing шагами (triggers)

### Почему мой DataFlow не обрабатывает сообщения?

**Проверьте статус:**
```bash
kubectl get dataflow <name>
kubectl describe dataflow <name>
```

**Частые причины:**

1. **Нет сообщений в source**
   ```bash
   # Проверьте Kafka топик
   kafka-console-consumer --bootstrap-server localhost:9092 --topic <topic>
   ```

2. **Неправильные credentials**
   ```bash
   kubectl logs -l app=dataflow-processor -c processor
   # Ищите ошибки подключения
   ```

3. **Ошибки трансформаций**
   - Проверьте синтаксис JSONPath в filter/router
   - Проверьте, что поля существуют во входных данных

4. **Sink недоступен**
   ```bash
   # Проверьте сетевое подключение
   kubectl exec -it <processor-pod> -- nc -zv <sink-host> <port>
   ```

### Как отлаживать трансформации?

**1. Включите подробное логирование:**
```bash
kubectl logs -l app=dataflow-processor -c processor -f
```

**2. Используйте error sink для анализа:**
```yaml
errors:
  type: kafka
  config:
    brokers: [kafka:9092]
    topic: debug-errors
```

**3. Проверьте JSONPath выражения:**
```bash
# Используйте gjson playground или тестируйте локально
curl -X POST https://gjson.dev/validate \
  -d '{"condition": "$.user.active"}'
```

## Проблемы с Kafka

### Сообщения не читаются с начала топика

По умолчанию DataFlow использует `OffsetOldest` — читает с начала топика. Если вы видите только новые сообщения:

**Проверьте consumer group:**
```bash
kafka-consumer-groups.sh --bootstrap-server localhost:9092 \
  --group <consumer-group> --describe
```

**Сбросить offset:**
```bash
kafka-consumer-groups.sh --bootstrap-server localhost:9092 \
  --group <consumer-group> --reset-offsets --to-earliest --execute
```

### Дубликаты сообщений

DataFlow обеспечивает **at-least-once** семантику. Дубликаты возможны при:
- Перезапуске процессора
- Сетевых проблемах
- Длительной обработке

**Решения:**
1. **Используйте идемпотентный sink:**
   ```yaml
   sink:
     type: postgresql
     config:
       upsertMode: true
       conflictKey: id
   ```

2. **Уменьшите окно дубликатов:**
   ```yaml
   spec:
     ackGranularity: message
   ```

3. **Дедупликация на уровне приложения:**
   - Используйте unique constraints в БД
   - Проверяйте message ID перед обработкой

### Проблемы с consumer group

**"Consumer group is rebalancing"**
- Слишком много рестартов
- Неравномерное распределение partitions

**Решения:**
```yaml
spec:
  source:
    type: kafka
    config:
      # Увеличьте session timeout
      sessionTimeoutSeconds: 30
      # Увеличьте heartbeat interval
      heartbeatIntervalSeconds: 10
```

## Проблемы с PostgreSQL

### "Connection refused" или таймауты

**Проверьте:**
1. Доступность PostgreSQL:
   ```bash
   kubectl exec -it <processor-pod> -- pg_isready -h <postgres-host>
   ```

2. Сетевые политики:
   ```bash
   kubectl get networkpolicies
   ```

3. Connection pool:
   ```yaml
   sink:
     type: postgresql
     config:
       # Увеличьте таймаут
       connectionTimeout: 30
       # Уменьшите размер batch при проблемах
       batchSize: 50
   ```

### Долгие запросы INSERT

**Оптимизации:**
```yaml
sink:
  type: postgresql
  config:
    # Увеличьте batch size
    batchSize: 500
    # Автосоздание таблицы с индексами
    autoCreateTable: true
    # Используйте UPSERT для обновлений
    upsertMode: true
    conflictKey: id
```

### Logical replication slot неактивен

**Для PostgreSQL CDC:**
```bash
# Проверьте статус slot
SELECT * FROM pg_replication_slots WHERE slot_name = 'your_slot';

# Активные слоты
SELECT * FROM pg_stat_replication;
```

**Heartbeat для поддержания slot:**
```yaml
source:
  type: postgresql-cdc
  config:
    heartbeatIntervalSeconds: 30
```

## Проблемы с производительностью

### Медленная обработка

**Диагностика:**
```bash
# Мониторинг метрик
curl http://<processor-pod>:8080/metrics

# Просмотр логов
kubectl logs -l app=dataflow-processor --tail=100 -f
```

**Оптимизации:**

1. **Увеличьте ресурсы:**
   ```yaml
   resources:
     requests:
       cpu: "1000m"
       memory: "1Gi"
     limits:
       cpu: "2000m"
       memory: "2Gi"
   ```

2. **Настройте batch size:**
   ```yaml
   sink:
     type: postgresql
     config:
       batchSize: 500
       batchFlushIntervalSeconds: 5
   ```

3. **Увеличьте buffer:**
   ```yaml
   spec:
     channelBufferSize: 1000
   ```

### Высокое потребление памяти

**Причины:**
- Большие сообщения
- Массивные flatten трансформации
- Длинные batch intervals

**Решения:**
```yaml
spec:
  # Уменьшите buffer
  channelBufferSize: 100
  sink:
    type: postgresql
    config:
      # Уменьшите batch size
      batchSize: 50
      # Уменьшите интервал flush
      batchFlushIntervalSeconds: 1
```

## Проблемы с Trino

### Ошибка REMOTE_TASK_ERROR

```
Trino query failed: Expected response from http://.../v1/task/.../status is empty
(Error: REMOTE_TASK_ERROR, Code: 65542)
```

**Причины:**
- Перегрузка воркеров Trino
- Сетевая проблема
- Перезапуск воркера

**Решения:**
1. Уменьшите размер batch:
   ```yaml
   sink:
     type: trino
     config:
       batchSize: 3
   ```

2. Увеличьте таймауты:
   ```yaml
   sink:
     type: trino
     config:
       queryTimeoutSeconds: 300
   ```

3. Проверьте кластер Trino:
   ```bash
   # Проверьте доступность воркеров
   curl http://trino-coordinator:8080/v1/info
   ```

### Ошибки аутентификации OAuth2

**Проверьте конфигурацию Keycloak:**
```yaml
sink:
  type: trino
  config:
    auth:
      type: oauth2
      tokenUrl: "https://keycloak/realms/dataflow/protocol/openid-connect/token"
      clientId: "dataflow-client"
      clientSecretRef:
        name: trino-secrets
        key: client-secret
```

**Проверьте token:**
```bash
# Получите token вручную
curl -X POST https://keycloak/realms/dataflow/protocol/openid-connect/token \
  -d "grant_type=client_credentials" \
  -d "client_id=dataflow-client" \
  -d "client_secret=<secret>"
```

## Проблемы с Nessie/Iceberg

### Nessie: "Table not found"

**Проверьте:**
1. Namespace существует:
   ```bash
   curl http://nessie:19120/api/v2/namespaces
   ```

2. Branch существует:
   ```bash
   curl http://nessie:19120/api/v2/trees
   ```

3. Правильная конфигурация:
   ```yaml
   sink:
     type: nessie
     config:
       baseURL: "http://nessie:19120"
       branch: main
       namespace: analytics
       table: events
   ```

### Iceberg REST Catalog: 401 Unauthorized

**Проверьте аутентификацию:**
```yaml
sink:
  type: iceberg
  config:
    catalogURL: "https://iceberg-catalog.example.com/v1"
    auth:
      type: bearer
      tokenRef:
        name: iceberg-secrets
        key: token
```

## Kubernetes специфичные проблемы

### Pod в состоянии CrashLoopBackOff

**Диагностика:**
```bash
kubectl describe pod <processor-pod>
kubectl logs <processor-pod> --previous
```

**Частые причины:**
1. Неверная конфигурация CRD
2. Недостаточно ресурсов (OOMKilled)
3. Ошибки инициализации

### ConfigMap не обновляется

При изменении DataFlow ConfigMap обновляется автоматически, но под перезапускается только при `restartPolicy: Always`.

**Принудительный перезапуск:**
```bash
kubectl rollout restart deployment/<dataflow-name>
```

### Проблемы с RBAC

**Ошибка: "User cannot create resource"**
```bash
# Проверьте права
kubectl auth can-i create dataflows --as <user>

# Создайте RoleBinding
kubectl create rolebinding dataflow-admin \
  --clusterrole=dataflow-admin \
  --user=<user> \
  --namespace=<namespace>
```

## Диагностика

### Полный чеклист отладки

```bash
# 1. Статус DataFlow
kubectl get dataflow <name> -o yaml

# 2. Статус пода
kubectl get pods -l app=dataflow-processor
kubectl describe pod <processor-pod>

# 3. Логи оператора
kubectl logs -l app.kubernetes.io/name=dataflow-operator -f

# 4. Логи процессора
kubectl logs <processor-pod> -c processor -f

# 5. События Kubernetes
kubectl get events --sort-by='.lastTimestamp' | grep dataflow

# 6. ConfigMap
kubectl get configmap df-<name>-spec -o yaml

# 7. Сетевой доступ
kubectl exec -it <processor-pod> -- nc -zv <sink-host> <port>

# 8. Метрики
curl http://<processor-pod>:8080/metrics
```

### Сбор диагностической информации

```bash
#!/bin/bash
# save-debug-info.sh

NAME=$1
NAMESPACE=${2:-default}

echo "=== DataFlow Status ===" > debug.txt
kubectl get dataflow $NAME -n $NAMESPACE -o yaml >> debug.txt

echo -e "\n=== Pod Status ===" >> debug.txt
kubectl get pods -n $NAMESPACE -l app=dataflow-processor >> debug.txt

echo -e "\n=== Recent Logs ===" >> debug.txt
kubectl logs -n $NAMESPACE -l app=dataflow-processor --tail=100 >> debug.txt 2>&1

echo -e "\n=== Events ===" >> debug.txt
kubectl get events -n $NAMESPACE --sort-by='.lastTimestamp' | grep dataflow | tail -20 >> debug.txt

echo "Debug info saved to debug.txt"
```

## Получение помощи

### Где задать вопрос

1. **GitHub Issues**: https://github.com/dataflow-operator/dataflow/issues
2. **Документация**: https://dataflow-operator.github.io/docs/
3. **Примеры**: `dataflow/config/samples/`

### Информация для bug report

При создании issue приложите:
1. Версию оператора: `kubectl get deployment dataflow-operator -o yaml`
2. Манифест DataFlow (без secrets)
3. Логи оператора и процессора
4. Вывод `kubectl describe` для пода и DataFlow
5. Версию Kubernetes: `kubectl version`
