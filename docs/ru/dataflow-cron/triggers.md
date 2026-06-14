# Триггеры DataFlowCron

`spec.triggers` — **упорядоченный список шагов** после основного конвейера. Каждый элемент — **один контейнер**: `image`, `command`, `args`, `env`, `resources`, `imagePullPolicy`.

## Когда и как выполняются

1. **CronJob** запускает **Job процессора**.
2. Триггеры **не стартуют**, пока Job не **успешен** (`JobComplete=True`).
3. **Один Job на триггер**, строго **по порядку** в массиве.
4. Общий **run ID** (`dataflow.dataflow.io/run-id`).
5. `restartPolicy: Never` — код выхода **0**, иначе цепочка останавливается.

Шаги **не параллелятся**, аргументы из вывода конвейера **не подставляются**.

## Поля `triggers[]`

| Поле | Обязательность | Описание |
|------|----------------|----------|
| **`image`** | Да | Образ контейнера. |
| **`name`** | Нет | Имя контейнера; иначе `trigger-<index>`. |
| **`command`** | Нет | Entrypoint. |
| **`args`** | Нет | Аргументы. |
| **`env`** | Нет | Переменные, в т.ч. из Secret/ConfigMap. |
| **`resources`** | Нет | CPU/память. |
| **`imagePullPolicy`** | Нет | `IfNotPresent`, `Always`. |

!!! note "Нет volumeMounts в API"
    В **API `DataFlowCronTrigger` нет `volumeMounts`**. Файлы — только из образа или загрузка контейнером.

## Отладка

Метки:

- `dataflow.dataflow.io/dataflow-cron=<имя>`
- `dataflow.dataflow.io/run-id=<id>`
- `dataflow.dataflow.io/trigger-index=<индекс>`

```bash
kubectl get jobs -l dataflow.dataflow.io/dataflow-cron=my-cron -o wide
kubectl logs job/<имя-job> --all-containers=true
```

## Примеры

**Webhook + второй HTTP-вызов:**

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

**Токен из Secret (Airflow):**

```yaml
  triggers:
    - name: start-airflow-dag
      image: curlimages/curl:8.8.0
      command: ["/bin/sh", "-c"]
      args:
        - 'curl -fsS -X POST -H "Authorization: Bearer ${AIRFLOW_TOKEN}" ...'
      env:
        - name: AIRFLOW_TOKEN
          valueFrom:
            secretKeyRef:
              name: airflow-token
              key: token
```

**`kubectl`:**

```yaml
  triggers:
    - name: annotate-last-run
      image: bitnami/kubectl:latest
      command: ["/bin/bash", "-ec"]
      args:
        - |
          kubectl annotate dataflowcron my-cron company.example.com/last-ok="$(date -Iseconds)" --overwrite
```

## См. также

- [Обзор DataFlowCron](index.md)
- [Примеры](examples.md)
