# Getting Started

Это руководство поможет вам начать работу с DataFlow Operator. Вы узнаете, как установить оператор, создать первый поток данных и настроить локальную среду разработки.

## Предварительные требования

### Для production установки

- Kubernetes кластер (версия 1.24+)
- Helm 3.0+
- kubectl настроен для работы с кластером
- Доступ к источникам данных (Kafka, PostgreSQL)

### Для локальной разработки

- Go 1.25+
- Docker и Docker Compose
- Task (опционально, для использования команд Taskfile)
- Доступ к портам: 8080, 5050, 15672, 8081, 5432, 9092, 5672

## Установка { #installation }

### Управление CRD { #crd }

CRD (Custom Resource Definition) DataFlow определяет тип ресурса `DataFlow` в Kubernetes.

#### Автоматическая установка (через Helm)

При установке через Helm (рекомендуемый способ) CRD устанавливается и обновляется автоматически. Отдельный шаг `kubectl apply` не нужен — чарт управляет жизненным циклом CRD при `crds.install: true` (значение по умолчанию).

#### Ручная установка

Если вы управляете CRD отдельно (например, через ArgoCD, FluxCD или с `crds.install: false` в Helm values), установите CRD вручную:

```bash
kubectl apply -f https://raw.githubusercontent.com/dataflow-operator/dataflow/refs/heads/main/config/crd/bases/dataflow.dataflow.io_dataflows.yaml
```

Или из локального файла:

```bash
kubectl apply -f dataflow/config/crd/bases/dataflow.dataflow.io_dataflows.yaml
```

#### Конфигурация CRD в Helm

| Параметр | По умолчанию | Описание |
|----------|-------------|----------|
| `crds.install` | `true` | Устанавливать и обновлять CRD при `helm install` / `helm upgrade` |
| `crds.keep` | `true` | Добавить аннотацию `helm.sh/resource-policy: keep` для защиты CRD от удаления при `helm uninstall` |

**Поведение при обновлении**: CRD обновляется при каждом `helm upgrade`, изменения схемы применяются автоматически.

**Поведение при удалении**: При `crds.keep: true` (по умолчанию) CRD остаётся в кластере после `helm uninstall`. Это защищает от случайного удаления всех ресурсов `DataFlow`. Чтобы отключить установку CRD через Helm:

```yaml
crds:
  install: false
```

### Установка через Helm (рекомендуется)

#### Базовая установка

Самый простой способ установить оператор из OCI registry:

```bash
helm install dataflow-operator oci://ghcr.io/dataflow-operator/helm-charts/dataflow-operator
```

Эта команда установит оператор с настройками по умолчанию в namespace `default`.

#### Установка в конкретный namespace

```bash
helm install dataflow-operator oci://ghcr.io/dataflow-operator/helm-charts/dataflow-operator \
  --namespace dataflow-system \
  --create-namespace
```

**Примечание**: Для локальной разработки вы также можете использовать локальный chart:
```bash
helm install dataflow-operator ./helm-charts/dataflow-operator
```

#### Установка с кастомными настройками

Вы можете переопределить значения по умолчанию через флаги:

```bash
helm install dataflow-operator oci://ghcr.io/dataflow-operator/helm-charts/dataflow-operator \
  --set image.repository=your-registry/controller \
  --set image.tag=v1.0.0 \
  --set replicaCount=2 \
  --set resources.limits.memory=1Gi \
  --set resources.limits.cpu=500m \
  --set resources.requests.memory=256Mi \
  --set resources.requests.cpu=100m
```

#### Установка с файлом values

Для более сложных конфигураций создайте файл `my-values.yaml`:

```yaml
image:
  repository: your-registry/controller
  tag: v1.0.0

replicaCount: 2

resources:
  limits:
    cpu: 1000m
    memory: 1Gi
  requests:
    cpu: 500m
    memory: 512Mi

# Настройки для работы с Kubernetes API
serviceAccount:
  create: true
  annotations:
    eks.amazonaws.com/role-arn: arn:aws:iam::123456789012:role/dataflow-operator

# Настройки безопасности
securityContext:
  runAsNonRoot: true
  runAsUser: 1000
  fsGroup: 1000

# Опционально: Sentry для мониторинга ошибок и трейсинга
# sentry:
#   enabled: true
#   dsn: "https://xxx@o0.ingest.sentry.io/123"
#   environment: production
#   tracesSampleRate: 0.1
```

Затем установите:

```bash
helm install dataflow-operator oci://ghcr.io/dataflow-operator/helm-charts/dataflow-operator -f my-values.yaml
```

#### Проверка установки

После установки проверьте статус:

```bash
# Проверьте статус подов
kubectl get pods -l app.kubernetes.io/name=dataflow-operator

# Проверьте CRD
kubectl get crd dataflows.dataflow.dataflow.io

# Проверьте логи оператора
kubectl logs -l app.kubernetes.io/name=dataflow-operator --tail=50

# Проверьте статус deployment
kubectl get deployment dataflow-operator
```

Ожидаемый вывод:

```
NAME                                  READY   STATUS    RESTARTS   AGE
dataflow-operator-7d8f9c4b5d-xxxxx   1/1     Running   0          1m
```

### Обновление

Для обновления оператора до новой версии:

```bash
helm upgrade dataflow-operator oci://ghcr.io/dataflow-operator/helm-charts/dataflow-operator
```

С кастомными значениями:

```bash
helm upgrade dataflow-operator oci://ghcr.io/dataflow-operator/helm-charts/dataflow-operator -f my-values.yaml
```

Для обновления до конкретной версии:

```bash
helm upgrade dataflow-operator oci://ghcr.io/dataflow-operator/helm-charts/dataflow-operator \
  --set image.tag=v1.1.0
```

### Удаление

Для удаления оператора:

```bash
helm uninstall dataflow-operator
```

**Поведение CRD при удалении**: При `crds.keep: true` (по умолчанию) CRD остаётся в кластере после `helm uninstall`. Существующие ресурсы `DataFlow` сохраняются, но перестают обрабатываться.

Для полного удаления CRD и **всех** ресурсов DataFlow в кластере:

```bash
# Сначала удалите все DataFlow ресурсы
kubectl delete dataflow --all --all-namespaces

# Затем удалите оператор
helm uninstall dataflow-operator

# Наконец, удалите CRD (только если crds.keep был true)
kubectl delete crd dataflows.dataflow.dataflow.io
```

!!! warning
    Удаление CRD удаляет **все** ресурсы `DataFlow` во всех namespace кластера. Убедитесь, что это намеренное действие.

## Первый DataFlow

### Простой пример: Kafka → PostgreSQL

Создайте простой DataFlow ресурс для передачи данных из Kafka в PostgreSQL:

```yaml
apiVersion: dataflow.dataflow.io/v1
kind: DataFlow
metadata:
  name: kafka-to-postgres
  namespace: default
spec:
  source:
    type: kafka
    config:
      brokers:
        - kafka-broker:9092
      topic: input-topic
      consumerGroup: dataflow-group
  sink:
    type: postgresql
    config:
      connectionString: "postgres://user:password@postgres-host:5432/dbname?sslmode=disable"
      table: output_table
      autoCreateTable: true
```

Примените ресурс:

```bash
kubectl apply -f dataflow/config/samples/kafka-to-postgres.yaml
```

**Примечание**: Каждый ресурс DataFlow создает отдельный под (Deployment) для обработки данных. Вы можете настроить ресурсы, выбор нод, affinity и tolerations. Подробнее см. [Примеры](examples.md#настройка-ресурсов-и-размещения-подов).

### Пример с Kubernetes Secrets

Для безопасного хранения credentials используйте Kubernetes Secrets. См. пример:

```bash
kubectl apply -f dataflow/config/samples/kafka-to-postgres-secrets.yaml
```

Этот пример демонстрирует использование `SecretRef` для конфигурации коннекторов. Подробнее см. раздел [Использование Secrets в Kubernetes](connectors.md#использование-secrets-в-kubernetes) в документации по коннекторам.

## DataFlowCron (запуск по расписанию)

`DataFlowCron` позволяет запускать pipeline по cron-расписанию.

Ключевые особенности:

- `schedule` задаёт расписание в cron-формате.
- Основной `processor` (блок `source -> transformations -> sink`) запускается первым.
- `triggers` запускаются **после** успешного завершения `processor`.
- Для polling-источников (`postgresql`, `trino`, `clickhouse`, `nessie`) `processor` завершается, когда источник исчерпан (`source exhausted`).
- Для `kafka` источник считается потоковым (streaming) и обычно не завершается по `source exhausted`.

Пример:

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
      brokers: ["kafka:9092"]
      topic: input-topic
      consumerGroup: dataflow-group
  sink:
    type: nessie
    config:
      baseURL: "http://nessie:19120"
      namespace: analytics
      table: events
  triggers:
    - name: trigger-airflow
      image: curlimages/curl:8.8.0
      command: ["curl"]
      args: ["-X", "POST", "http://airflow-webserver:8080/api/v1/dags/example/dagRuns"]
```

### Проверка статуса

Проверьте статус созданного потока данных:

```bash
# Получить информацию о DataFlow
kubectl get dataflow kafka-to-postgres

# Детальная информация
kubectl describe dataflow kafka-to-postgres

# Посмотреть статус в формате YAML
kubectl get dataflow kafka-to-postgres -o yaml
```

Ожидаемый статус:

```yaml
status:
  phase: Running
  processedCount: 150
  errorCount: 0
  lastProcessedTime: "2024-01-15T10:30:00Z"
  message: "Processing messages successfully"
```

### Отправка тестового сообщения

Для тестирования потока данных отправьте сообщение в Kafka топик:

```bash
# Используя kafka-console-producer
kafka-console-producer --broker-list localhost:9092 --topic input-topic
# Введите JSON сообщение и нажмите Enter
{"id": 1, "name": "Test", "value": 100}
```

Или используйте скрипт из проекта:

```bash
./scripts/send-test-message.sh
```

### Проверка данных в PostgreSQL

Подключитесь к PostgreSQL и проверьте данные:

```bash
psql postgres://user:password@postgres-host:5432/dbname

# Проверьте таблицу
SELECT * FROM output_table;
```

## Локальная разработка

### Запуск зависимостей

Используйте docker-compose для запуска всех зависимостей локально:

```bash
docker-compose up -d
```

Эта команда запустит:

- **Kafka** (порт 9092) с Kafka UI (порт 8080)
- **PostgreSQL** (порт 5432) с pgAdmin (порт 5050)

### Доступ к UI интерфейсам

После запуска доступны следующие UI:

- **Kafka UI**: http://localhost:8080
  - Просмотр топиков, сообщений, consumer groups
- **pgAdmin**: http://localhost:5050
  - Логин: `admin@admin.com`, пароль: `admin`
  - Управление PostgreSQL базами данных

### Запуск оператора локально

Для разработки запустите оператор локально:

```bash
# Установите CRD в кластер (если используете kind или minikube)
task install

# Запустите оператор
task run
```

Или используйте скрипт:

```bash
./scripts/run-local.sh
```

### Настройка локального кластера (опционально)

Для полноценного тестирования используйте kind (Kubernetes in Docker):

```bash
# Создать kind кластер
./scripts/setup-kind.sh

# Установить CRD
task install

# Запустить оператор локально
task run
```

### Отладка

Для отладки используйте логи оператора:

```bash
# Если оператор запущен локально, логи выводятся в консоль
# Для оператора в кластере:
kubectl logs -l app.kubernetes.io/name=dataflow-operator -f
```

Проверьте события Kubernetes:

```bash
kubectl get events --sort-by='.lastTimestamp' | grep dataflow
```

## Следующие шаги

Теперь, когда вы установили оператор и создали первый поток данных:

1. Изучите [Connectors](connectors.md) для понимания всех доступных источников и приемников
2. Ознакомьтесь с [Transformations](transformations.md) для работы с трансформациями сообщений
3. Посмотрите [Examples](examples.md) для практических примеров использования
4. Прочитайте [Development](development.md) для участия в разработке

## Устранение неполадок

### Оператор не запускается

```bash
# Проверьте логи
kubectl logs -l app.kubernetes.io/name=dataflow-operator

# Проверьте события
kubectl describe pod -l app.kubernetes.io/name=dataflow-operator

# Проверьте CRD
kubectl get crd dataflows.dataflow.dataflow.io -o yaml
```

### DataFlow не обрабатывает сообщения

1. Проверьте статус DataFlow:
   ```bash
   kubectl describe dataflow <name>
   ```

2. Проверьте подключение к источнику данных:
   ```bash
   # Для Kafka
   kafka-console-consumer --bootstrap-server localhost:9092 --topic <topic>

   # Для PostgreSQL
   psql <connection-string> -c "SELECT * FROM <table> LIMIT 10;"
   ```

3. Проверьте логи оператора на наличие ошибок

### Проблемы с подключением

- Убедитесь, что источники данных доступны из кластера
- Проверьте сетевые политики Kubernetes
- Проверьте правильность connection strings и credentials
- Для локальной разработки используйте `localhost` или `host.docker.internal`

### Trino: REMOTE_TASK_ERROR (код 65542)

При использовании Trino sink может появиться ошибка:

```
Trino query failed: Expected response from http://.../v1/task/.../status is empty (Error: REMOTE_TASK_ERROR, Code: 65542)
```

Это означает, что воркер Trino не ответил координатору (перегрузка, перезапуск воркера или сетевая проблема). Оператор автоматически повторяет такие запросы (до 5 попыток с экспоненциальной задержкой).

**Если ошибки продолжаются:**

1. **Уменьшите размер батча** — установите `batchSize` в 3–5 в конфигурации Trino sink для больших сообщений (например, JSON с множеством полей)
2. **Проверьте кластер Trino** — проверьте логи воркеров, память и сетевое подключение
3. **Увеличьте таймауты** — при медленных воркерах увеличьте таймаут запроса в конфигурации коннектора



