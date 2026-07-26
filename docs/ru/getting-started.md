# Getting Started

Установка оператора, первый потоковый или scheduled-конвейер, либо локальная среда разработки.

**Когда читать:** первая установка или первый pipeline. Поля коннекторов — [Коннекторы](connectors.md); выбор DataFlow vs DataFlowCron — [Типы нагрузки](concepts/workload-types.md).

**См. также:** [FAQ](faq.md) · [Best Practices](best-practices.md) · [DataFlowCron](dataflow-cron/index.md) · [Helm Values](helm-values.md) · [CLI](cli.md)

## Пути

1. [Установка оператора](#установка-оператора) — Helm / CRD
2. [Первый потоковый конвейер](#первый-потоковый-конвейер) — `DataFlow` с `SecretRef`
3. [Первый cron-конвейер](#первый-cron-конвейер) — `DataFlowCron`
4. [Локальная разработка](#локальная-разработка) — Go, Docker, kind

---

## Установка оператора { #установка-оператора }

### Предварительные требования

- Kubernetes-кластер (1.24+)
- Helm 3.0+
- kubectl, настроенный на кластер
- Доступ к источникам данных (Kafka, PostgreSQL и т.д.)

### Управление CRD { #crd }

Оператор ставит два CRD: **`DataFlow`** (`dataflows`) и **`DataFlowCron`** (`dataflowcrons`).

#### Автоматическая установка (через Helm)

При установке через Helm (рекомендуется) CRD ставятся и обновляются автоматически при `crds.install: true` (по умолчанию). Отдельный `kubectl apply` не нужен.

#### Ручная установка

Если CRD управляются отдельно (ArgoCD, FluxCD или `crds.install: false`), примените **оба** CRD:

```bash
kubectl apply -f https://raw.githubusercontent.com/dataflow-operator/dataflow/refs/heads/main/config/crd/bases/dataflow.dataflow.io_dataflows.yaml
kubectl apply -f https://raw.githubusercontent.com/dataflow-operator/dataflow/refs/heads/main/config/crd/bases/dataflow.dataflow.io_dataflowcrons.yaml
```

Или из локального checkout:

```bash
kubectl apply -f dataflow/config/crd/bases/dataflow.dataflow.io_dataflows.yaml
kubectl apply -f dataflow/config/crd/bases/dataflow.dataflow.io_dataflowcrons.yaml
```

#### Конфигурация CRD в Helm

| Параметр | По умолчанию | Описание |
|----------|-------------|----------|
| `crds.install` | `true` | Устанавливать и обновлять CRD при `helm install` / `helm upgrade` |
| `crds.keep` | `true` | Аннотация `helm.sh/resource-policy: keep` — CRD не удаляются при `helm uninstall` |

**Обновление:** CRD обновляются при каждом `helm upgrade`.

**Удаление:** При `crds.keep: true` (по умолчанию) CRD остаются после `helm uninstall`. Чтобы отключить установку CRD через Helm:

```yaml
crds:
  install: false
```

### Установка через Helm (рекомендуется)

#### Базовая установка

```bash
helm install dataflow-operator oci://ghcr.io/dataflow-operator/helm-charts/dataflow-operator
```

Установка в namespace `default` с настройками чарта по умолчанию.

#### Конкретный namespace

```bash
helm install dataflow-operator oci://ghcr.io/dataflow-operator/helm-charts/dataflow-operator \
  --namespace dataflow-system \
  --create-namespace
```

Для локальной разработки чарта:

```bash
helm install dataflow-operator ./helm-charts/dataflow-operator
```

#### Кастомные настройки

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

#### Файл values

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

serviceAccount:
  create: true
  annotations:
    eks.amazonaws.com/role-arn: arn:aws:iam::123456789012:role/dataflow-operator

securityContext:
  runAsNonRoot: true
  runAsUser: 1000
  fsGroup: 1000

# Опционально: Sentry
# sentry:
#   enabled: true
#   dsn: "https://xxx@o0.ingest.sentry.io/123"
#   environment: production
#   tracesSampleRate: 0.1
```

```bash
helm install dataflow-operator oci://ghcr.io/dataflow-operator/helm-charts/dataflow-operator -f my-values.yaml
```

#### Проверка

```bash
kubectl get pods -l app.kubernetes.io/name=dataflow-operator

# Оба CRD
kubectl get crd dataflows.dataflow.dataflow.io dataflowcrons.dataflow.dataflow.io

kubectl logs -l app.kubernetes.io/name=dataflow-operator --tail=50
kubectl get deployment dataflow-operator
```

Ожидаемый вывод:

```
NAME                                  READY   STATUS    RESTARTS   AGE
dataflow-operator-7d8f9c4b5d-xxxxx   1/1     Running   0          1m
```

### Обновление

```bash
helm upgrade dataflow-operator oci://ghcr.io/dataflow-operator/helm-charts/dataflow-operator
```

С values:

```bash
helm upgrade dataflow-operator oci://ghcr.io/dataflow-operator/helm-charts/dataflow-operator -f my-values.yaml
```

Конкретная версия:

```bash
helm upgrade dataflow-operator oci://ghcr.io/dataflow-operator/helm-charts/dataflow-operator \
  --set image.tag=v1.1.0
```

### Удаление

```bash
helm uninstall dataflow-operator
```

При `crds.keep: true` CRD остаются; существующие ресурсы перестают реконсилироваться.

Чтобы удалить CRD и **все** ресурсы DataFlow / DataFlowCron:

```bash
kubectl delete dataflow --all --all-namespaces
kubectl delete dataflowcron --all --all-namespaces

helm uninstall dataflow-operator

kubectl delete crd dataflows.dataflow.dataflow.io
kubectl delete crd dataflowcrons.dataflow.dataflow.io
```

!!! warning
    Удаление CRD удаляет **все** ресурсы `DataFlow` и `DataFlowCron` во всех namespace.

---

## Первый потоковый конвейер { #первый-потоковый-конвейер }

Непрерывный `DataFlow` (Deployment). В кластере / production для credentials используйте **`SecretRef`**.

### Kafka → PostgreSQL с SecretRef

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: kafka-credentials
  namespace: default
type: Opaque
stringData:
  brokers: "kafka-broker:9092"
  topic: "input-topic"
  consumerGroup: "dataflow-group"
---
apiVersion: v1
kind: Secret
metadata:
  name: postgres-credentials
  namespace: default
type: Opaque
stringData:
  connectionString: "postgres://user:password@postgres-host:5432/dbname?sslmode=require"
  table: "output_table"
---
apiVersion: dataflow.dataflow.io/v1
kind: DataFlow
metadata:
  name: kafka-to-postgres
  namespace: default
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

Sample из репозитория (включая SASL SecretRef):

```bash
kubectl apply -f dataflow/config/samples/kafka-to-postgres-secrets.yaml
```

Подробнее: [Использование Secrets](connectors.md#использование-secrets-в-kubernetes). Ресурсы и placement подов: [Примеры](examples.md#настройка-ресурсов-и-размещения-подов).

### Проверка статуса

```bash
kubectl get dataflow kafka-to-postgres
kubectl describe dataflow kafka-to-postgres
kubectl get dataflow kafka-to-postgres -o yaml
```

Пример status:

```yaml
status:
  phase: Running
  processedCount: 150
  errorCount: 0
  lastProcessedTime: "2024-01-15T10:30:00Z"
  message: "Processing messages successfully"
```

### Отправка тестового сообщения

```bash
kafka-console-producer --broker-list kafka-broker:9092 --topic input-topic
# Введите JSON и нажмите Enter
{"id": 1, "name": "Test", "value": 100}
```

Или (локальный стек):

```bash
./scripts/send-test-message.sh
```

### Проверка PostgreSQL

```bash
psql "$CONNECTION_STRING" -c "SELECT * FROM output_table;"
```

---

## Первый cron-конвейер { #первый-cron-конвейер }

`DataFlowCron` запускает тот же Source → Transform → Sink по **cron-расписанию** (CronJob / Job), с опциональными post-run [триггерами](dataflow-cron/triggers.md).

Лучше всего подходит для **polling / batch** источников (`postgresql`, `trino`, `clickhouse`, `nessie`, `iceberg`). Kafka — streaming и обычно не завершается по исчерпанию источника — см. [DataFlowCron](dataflow-cron/index.md) и [Типы нагрузки](concepts/workload-types.md).

### Минимальный пример (PostgreSQL → PostgreSQL)

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: postgres-credentials
  namespace: default
type: Opaque
stringData:
  connectionString: "postgres://user:password@postgres:5432/db?sslmode=require"
---
apiVersion: dataflow.dataflow.io/v1
kind: DataFlowCron
metadata:
  name: pg-nightly-sync
spec:
  schedule: "0 2 * * *"
  concurrencyPolicy: Forbid
  source:
    type: postgresql
    config:
      connectionStringSecretRef:
        name: postgres-credentials
        key: connectionString
      table: public.orders_staging
      pollInterval: 5
  sink:
    type: postgresql
    config:
      connectionStringSecretRef:
        name: postgres-credentials
        key: connectionString
      table: public.orders_warehouse
      autoCreateTable: true
      batchSize: 200
```

```bash
kubectl apply -f pg-nightly-sync.yaml
kubectl get dataflowcron pg-nightly-sync
kubectl get cronjob,job -l dataflow.dataflow.io/dataflow-cron=pg-nightly-sync
```

Sample в репозитории (Kafka → Nessie + triggers): `dataflow/config/samples/dataflowcron-example.yaml`. Больше YAML: [Примеры DataFlowCron](dataflow-cron/examples.md).

---

## Локальная разработка { #локальная-разработка }

Для контрибьюторов: оператор против docker-compose / kind. Plaintext connection strings допустимы **только** в этом локальном пути.

### Предварительные требования

- Go 1.25+
- Docker и Docker Compose
- Task (опционально)
- Порты: 8080, 5050, 15672, 8081, 5432, 9092, 5672

### Запуск зависимостей

```bash
docker-compose up -d
```

Запускает Kafka (9092) + Kafka UI (8080), PostgreSQL (5432) + pgAdmin (5050).

- **Kafka UI:** http://localhost:8080
- **pgAdmin:** http://localhost:5050 — `admin@admin.com` / `admin`

### DataFlow только для local (plaintext)

!!! warning "Только локальная разработка"
    **Не** используйте plaintext credentials в shared или production-кластерах. Предпочтительнее [SecretRef](#первый-потоковый-конвейер).

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
        - localhost:9092
      topic: input-topic
      consumerGroup: dataflow-group
  sink:
    type: postgresql
    config:
      connectionString: "postgres://dataflow:dataflow@localhost:5432/dataflow?sslmode=disable"
      table: output_table
      autoCreateTable: true
```

```bash
kubectl apply -f dataflow/config/samples/kafka-to-postgres.yaml
```

### Запуск оператора локально

```bash
task install   # CRD (kind / minikube)
task run
```

Или:

```bash
./scripts/run-local.sh
```

### Опционально: kind-кластер

```bash
./scripts/setup-kind.sh
task install
task run
```

### Отладка

```bash
kubectl logs -l app.kubernetes.io/name=dataflow-operator -f
kubectl get events --sort-by='.lastTimestamp' | grep dataflow
```

---

## Следующие шаги

1. [Коннекторы](connectors.md) — источники и приёмники
2. [Трансформации](transformations.md) — преобразования сообщений
3. [Примеры](examples.md) — практические манифесты
4. [Agent Skills](agent-skills.md) — AI-помощь с deploy и манифестами
5. [Разработка](development.md) — участие в разработке

---

## Устранение неполадок

### Оператор не запускается

```bash
kubectl logs -l app.kubernetes.io/name=dataflow-operator
kubectl describe pod -l app.kubernetes.io/name=dataflow-operator
kubectl get crd dataflows.dataflow.dataflow.io dataflowcrons.dataflow.dataflow.io -o yaml
```

### DataFlow не обрабатывает сообщения

1. `kubectl describe dataflow <name>`
2. Проверьте доступность источника (Kafka consumer / запрос `psql`)
3. Логи оператора / процессора

### Проблемы с подключением

- Доступность из кластера (NetworkPolicies, DNS)
- Credentials и ключи Secret
- Локально: `localhost` или `host.docker.internal`

### Trino: REMOTE_TASK_ERROR (код 65542)

Воркер не ответил координатору. Оператор ретраит (до 5 попыток с backoff).

Если ошибки продолжаются: уменьшите `batchSize` Trino sink (например, 3–5), проверьте воркеры Trino, увеличьте таймауты запросов.
