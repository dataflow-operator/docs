# DataFlowCron (запуск по расписанию)

**DataFlowCron** — namespaced CRD (`dataflowcrons`, kind `DataFlowCron`, group `dataflow.dataflow.io`) для запуска того же конвейера **источник → трансформации → приёмник**, что и у [DataFlow](architecture.md), но **по cron-расписанию** через Kubernetes **CronJob** / **Job**, а не через постоянный Deployment.

Используйте его для **пакетных** или **периодических** сценариев (опрос таблицы, выгрузка окна и остановка) и когда после успешного прогона процессора нужны **дополнительные шаги** (`triggers`).

## Обзор spec

`DataFlowCronSpec` **встраивает [`DataFlowSpec`](architecture.md#структура-dataflow-crd)** — все поля `DataFlow` (`source`, `sink`, `transformations`, `errors`, `resources`, `nodeSelector`, `affinity`, `tolerations`, `checkpointPersistence`, `channelBufferSize`, `processorImage` / `processorVersion`, `imagePullSecrets` и т.д.) работают так же.

Дополнительно:

| Поле | Описание |
|------|----------|
| **`schedule`** (обязательно) | Cron-выражение с **5 или 6** полями (как у Kubernetes CronJob). |
| **`concurrencyPolicy`** | `Allow`, `Forbid` или `Replace` — те же смыслы, что у `CronJob.spec.concurrencyPolicy`. Если не задано, действует поведение Kubernetes по умолчанию. |
| **`successfulJobsHistoryLimit`** / **`failedJobsHistoryLimit`** | Пробрасываются в управляемый `CronJob`. |
| **`startingDeadlineSeconds`** | Пробрасывается в `CronJob`. |
| **`suspend`** | При установке приостанавливает расписание (`suspend` у CronJob). |
| **`triggers`** | См. [секцию `triggers`](#секция-triggers) — пост-шаги после успешного Job процессора. |

Валидация повторно использует правила **DataFlow** для source, sink, трансформаций и ресурсов и добавляет проверки `schedule`, `image` у триггеров и `concurrencyPolicy`. При включённом [validating webhook](development.md#настройка-validating-webhook) (Helm: `webhook.enabled` и `webhook.caBundle`) admission проверяет и `DataFlowCron`, и `DataFlow` до записи объектов в etcd.

## Объекты в кластере

Для `DataFlowCron` с именем `<name>` в namespace:

| Ресурс | Имя | Назначение |
|--------|-----|------------|
| ConfigMap | `dfc-<name>-spec` | JSON spec для процессора (`spec.json`), аналог `df-<name>-spec` у `DataFlow`. |
| CronJob | `dfc-<name>` | Запускает **процессор** по `schedule` (первый шаг каждого запуска). |
| Job | `dfc-<name>-…` | Job процессора создаёт CronJob; **триггерные** Job создаёт оператор после успеха процессора. |

Поды процессора запускаются так же, как в Deployment-сценарии: `/processor --spec-path=/etc/dataflow/spec.json --namespace=… --name=…` (в `name` передаётся имя ресурса **DataFlowCron**).

## Ход выполнения

1. По расписанию **CronJob** создаёт **Job**, под которого выполняет **процессор**, пока источник не исчерпан или процесс не завершится (зависит от типа источника).
2. Если задан список **`triggers`**, после **успеха** Job процессора оператор по очереди создаёт **Job триггеров** с образами из spec (например `kubectl`, `curl`, внутренняя утилита).
3. Поле **status** у `DataFlowCron` отражает фазы: работа триггеров (`RunningTriggers`), **`Completed`** после успешного прогона, **`Failed`** при падении Job.

### Тип источника и момент «конца» прогона

- **Polling-источники** (PostgreSQL, Trino, ClickHouse, Nessie и т.п.) обычно **завершаются**, когда источник **исчерпан** — тогда Job процессора может успешно завершиться и запустятся триггеры.
- **Kafka** — **потоковый** источник: процессор часто **не останавливается** сам, поэтому сценарий «cron → успех → триггеры» без дополнительной логики может не наступить. Для расписания с пост-триггерами надёжнее ориентироваться на источники с явным завершением опроса.

## Секция `triggers` {#секция-triggers}

`spec.triggers` — это **упорядоченный список дополнительных шагов** после основного конвейера данных. Каждый элемент описывает **ровно один контейнер** (как у `Pod.spec.containers[]` в части `image`, `command`, `args`, `env`, `resources`, `imagePullPolicy`).

### Когда и как выполняются

1. По расписанию **CronJob** запускает **Job процессора** (тот же бинарник `/processor`, что и у `DataFlow`).
2. Триггеры **вообще не стартуют**, пока этот Job не перейдёт в состояние **успешно завершён** (`JobComplete=True`).
3. Контроллер создаёт **отдельный Kubernetes Job на каждый триггер** — **строго по порядку** в массиве: сначала `triggers[0]`, после его успеха `triggers[1]`, и т.д.
4. У всех Job одного «тика» cron общий **run ID** (метка `dataflow.dataflow.io/run-id`); по нему удобно искать цепочку в логах или в `kubectl get jobs`.
5. У пода каждого такого Job **один контейнер** и `restartPolicy: Never`: контейнер должен завершиться с **кодом 0**, иначе шаг считается проваленным и цепочка останавливается.

Шаги **не параллелятся** и **не** подставляют аргументы из результата предыдущего конвейера — это не DAG внутри оператора, а последовательные «хуки».

### Поля элемента `triggers[]`

| Поле | Обязательность | Описание |
|------|----------------|----------|
| **`image`** | Да | Образ контейнера (как для обычного Job). |
| **`name`** | Нет | Имя контейнера в Pod; если пусто, используется `trigger-<индекс>`. |
| **`command`** | Нет | Entrypoint (`ENTRYPOINT` образа переопределяется, если задано). |
| **`args`** | Нет | Аргументы к `command`. |
| **`env`** | Нет | Переменные окружения, в т.ч. `valueFrom.secretKeyRef` / `configMapKeyRef` (как в corev1 `EnvVar`). |
| **`resources`** | Нет | `requests` / `limits` CPU и памяти для контейнера. |
| **`imagePullPolicy`** | Нет | Например `IfNotPresent` или `Always`. |

В **API `DataFlowCronTrigger` нет `volumeMounts` и дополнительных томов Pod**. Файлы на диске в триггере появятся только если они **уже внутри образа**, либо если контейнер сам качает манифест (например `kubectl apply -f https://...`). Пример в `dataflowcron-example.yaml` с локальным путём `/manifests/...` имеет смысл только с образом, где этот путь действительно существует, или после расширения CRD/контроллера под монтирование ConfigMap/Secret.

### Отладка

Полезные метки на Job и Pod триггеров (и процессора):

- `dataflow.dataflow.io/dataflow-cron=<имя DataFlowCron>`
- `dataflow.dataflow.io/run-id=<id прогона>`
- `dataflow.dataflow.io/trigger-index=<индекс>` (для шага процессора из CronJob значение `-1`)

```bash
kubectl get jobs -l dataflow.dataflow.io/dataflow-cron=my-cron -o wide
kubectl logs job/<имя-job-триггера> --all-containers=true
```

В статусе CR смотрите **`phase`**, **`currentTriggerIndex`**, **`activeJobName`**, **`lastFailedTime`**.

### Примеры `triggers`

**Цепочка: внешний webhook → вызов другого API** (два контейнера подряд; первый должен завершиться с 0, иначе второй не стартует):

```yaml
  triggers:
    - name: notify-slack
      image: curlimages/curl:8.8.0
      command: ["curl", "-fsS", "-X", "POST", "-H", "Content-Type: application/json"]
      args:
        - "-d"
        - '{"text":"ETL cron finished"}'
        - "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
    - name: refresh-bi-cache
      image: curlimages/curl:8.8.0
      args: ["-fsS", "-X", "POST", "http://bi-service:8080/internal/refresh"]
```

**Токен из Secret** (как в `dataflowcron-example.yaml`; для Airflow 2.x обычно ещё нужен заголовок `Authorization: Bearer …` — удобно собрать одну shell-команду):

```yaml
  triggers:
    - name: start-airflow-dag
      image: curlimages/curl:8.8.0
      command: ["/bin/sh", "-c"]
      args:
        - 'curl -fsS -X POST -H "Authorization: Bearer ${AIRFLOW_TOKEN}" -H "Content-Type: application/json" --data "{}" http://airflow-webserver.dataflow.svc:8080/api/v1/dags/my_dag/dagRuns'
      env:
        - name: AIRFLOW_TOKEN
          valueFrom:
            secretKeyRef:
              name: airflow-token
              key: token
```

**`kubectl` к объектам в кластере** (ServiceAccount пода по умолчанию — `default` в namespace ресурса; при необходимости добавьте `Role`/`RoleBinding` для `kubectl`):

```yaml
  triggers:
    - name: annotate-last-run
      image: bitnami/kubectl:latest
      command: ["/bin/bash", "-ec"]
      args:
        - |
          kubectl annotate dataflowcron my-cron company.example.com/last-ok="$(date -Iseconds)" --overwrite
```

**Ресурсы и политика pull** для тяжёлого CLI:

```yaml
  triggers:
    - name: run-spark-submit
      image: my-registry/spark-cli:v1
      imagePullPolicy: IfNotPresent
      command: ["/opt/spark/bin/spark-submit"]
      args: ["--master", "k8s://https://kubernetes.default.svc", "/app/batch.py"]
      resources:
        requests:
          cpu: "500m"
          memory: "512Mi"
        limits:
          memory: "1Gi"
```

## Status (полезные поля)

- **`phase`** — обобщённое состояние (`RunningTriggers`, `Completed`, `Failed` и др.).
- **`currentRunID`** — идентификатор логического запуска (имена Job триггеров).
- **`currentTriggerIndex`** — какой шаг триггера выполняется.
- **`activeJobName`** — имя связанного Kubernetes Job при сбое или шаге.
- **`lastScheduleTime`**, **`lastSuccessfulTime`**, **`lastFailedTime`** — метки времени.
- **`conditions`** — условия в стиле Kubernetes, если заполнены.

Проверка в кластере:

```bash
kubectl get dataflowcrons.dataflow.dataflow.io
kubectl describe dataflowcron <name>
kubectl get cronjob,job -l dataflow.dataflow.io/dataflow-cron=<name>
```

## Примеры

Ниже — фрагменты `spec` для типовых сценариев. Замените строки подключения, имена таблиц и host’ы сервисов на свои; в подах Job используйте DNS сервисов Kubernetes (например `postgres.default.svc.cluster.local`), а не `localhost`.

### Только процессор, без `triggers`

Ночной или почасовой **опрос PostgreSQL** и запись в другую таблицу. После исчерпания батча источника Job процессора завершается успешно — отдельных шагов нет.

```yaml
apiVersion: dataflow.dataflow.io/v1
kind: DataFlowCron
metadata:
  name: pg-nightly-sync
spec:
  schedule: "0 2 * * *"   # каждый день в 02:00 (timezone — зона kube-controller-manager)
  concurrencyPolicy: Forbid
  source:
    type: postgresql
    config:
      connectionString: "postgres://user:pass@postgres:5432/db?sslmode=disable"
      table: public.orders_staging
      pollInterval: 5
  sink:
    type: postgresql
    config:
      connectionString: "postgres://user:pass@postgres:5432/db?sslmode=disable"
      table: public.orders_warehouse
      autoCreateTable: true
      batchSize: 200
```

### Лимиты истории Job и дедлайн старта

Полезно, если не нужно хранить долгую историю **CronJob** в etcd:

```yaml
  schedule: "15 */6 * * *"
  concurrencyPolicy: Forbid
  successfulJobsHistoryLimit: 2
  failedJobsHistoryLimit: 3
  startingDeadlineSeconds: 300   # не стартовать, если слот расписания пропущен > 5 минут
```

### ClickHouse → ClickHouse по расписанию

Периодическое перелётывание данных между таблицами (тот же паттерн, что в `dataflow/config/samples/clickhouse-to-clickhouse.yaml`).

```yaml
apiVersion: dataflow.dataflow.io/v1
kind: DataFlowCron
metadata:
  name: ch-hourly-copy
spec:
  schedule: "0 * * * *"
  concurrencyPolicy: Forbid
  source:
    type: clickhouse
    config:
      connectionString: "clickhouse://default@clickhouse:9000/default?dial_timeout=10s"
      table: events_raw
      pollInterval: 10
  sink:
    type: clickhouse
    config:
      connectionString: "clickhouse://default@clickhouse:9000/default?dial_timeout=10s"
      table: events_hourly
      batchSize: 500
      autoCreateTable: true
```

### Nessie (Iceberg) → Kafka

Выгрузка таблицы из каталога Nessie в топик по расписанию (см. также [Nessie](connectors.md#nessie)).

```yaml
apiVersion: dataflow.dataflow.io/v1
kind: DataFlowCron
metadata:
  name: nessie-to-kafka-hourly
spec:
  schedule: "0 * * * *"
  source:
    type: nessie
    config:
      baseURL: "http://nessie:19120"
      branch: main
      authenticationType: BEARER
      bearerToken: "replace-with-token"
      namespace: analytics
      table: events
      pollInterval: 30
  sink:
    type: kafka
    config:
      brokers:
        - kafka:9092
      topic: iceberg-snapshot
```

### С трансформациями

Встроенный `DataFlowSpec` позволяет добавить цепочку **трансформаций** так же, как у `DataFlow`:

```yaml
  schedule: "*/30 * * * *"
  source:
    type: postgresql
    config:
      connectionString: "postgres://user:pass@postgres:5432/db?sslmode=disable"
      table: public.events
      pollInterval: 5
  transformations:
    - type: timestamp
      config: {}
    - type: select
      config:
        fields: ["id", "payload", "created_at"]
  sink:
    type: kafka
    config:
      brokers: [kafka:9092]
      topic: curated-events
```

### Один `trigger` после успешного прогона

Вызов HTTP-webhook после того, как процессор и sink отработали без ошибки (образ и URL замените на свои):

```yaml
  schedule: "0 6 * * *"
  concurrencyPolicy: Forbid
  source:
    type: postgresql
    config:
      connectionString: "postgres://user:pass@postgres:5432/db?sslmode=disable"
      table: public.daily_export
      pollInterval: 5
  sink:
    type: postgresql
    config:
      connectionString: "postgres://user:pass@postgres:5432/db?sslmode=disable"
      table: public.daily_export_archive
      batchSize: 1000
  triggers:
    - name: notify-done
      image: curlimages/curl:8.8.0
      command: ["curl", "-fsS", "-X", "POST"]
      args: ["https://hooks.example.com/job-done"]
```

### Готовый файл в репозитории

Два триггера (`kubectl` и `curl` с секретом), источник Kafka и sink Nessie:

```bash
kubectl apply -f dataflow/config/samples/dataflowcron-example.yaml
```

Файл: `dataflow/config/samples/dataflowcron-example.yaml`. Краткая выжимка — в [Примеры — DataFlowCron](examples.md#dataflowcron-example).

### Временно отключить расписание

Не удаляя ресурс, можно **приостановить** создание новых Job у `CronJob` (поле пробрасывается в Kubernetes как `suspend`):

```yaml
spec:
  schedule: "0 * * * *"
  suspend: true
  # ...
```

Для возобновления уберите `suspend` или задайте `suspend: false`.

## См. также

- [Архитектура](architecture.md)
- [Коннекторы](connectors.md)
- [Трансформации](transformations.md)
- [Примеры](examples.md)
