# Spec и расписание DataFlowCron

`DataFlowCronSpec` **встраивает [`DataFlowSpec`](../dataflow/spec.md)** — поля `source`, `sink`, `transformations`, `errors`, `resources`, `checkpointPersistence` и др. работают так же.

## Поля cron

| Поле | Описание |
|------|----------|
| **`schedule`** (обязательно) | Cron с **5 или 6** полями (формат Kubernetes). |
| **`concurrencyPolicy`** | `Allow`, `Forbid`, `Replace`. |
| **`successfulJobsHistoryLimit`** / **`failedJobsHistoryLimit`** | Пробрасываются в CronJob. |
| **`startingDeadlineSeconds`** | Пробрасывается в CronJob. |
| **`suspend`** | Приостановка расписания. |
| **`triggers`** | См. [Триггеры](triggers.md). |

Валидация повторно использует правила **DataFlow** и добавляет проверки `schedule`, `image` триггеров и `concurrencyPolicy`. См. [validating webhook](../development.md#настройка-validating-webhook).

## Объекты в кластере {#объекты-в-кластере}

Для `DataFlowCron` `<name>` в namespace:

| Ресурс | Имя | Назначение |
|--------|-----|------------|
| ConfigMap | `dfc-<name>-spec` | `spec.json` для процессора. |
| CronJob | `dfc-<name>` | Запуск процессора по `schedule`. |
| Job | `dfc-<name>-…` | Job процессора и триггерные Job. |

Entrypoint: `/processor --spec-path=/etc/dataflow/spec.json --namespace=… --name=…` (имя **DataFlowCron**).

## Лимиты истории и suspend

```yaml
  schedule: "15 */6 * * *"
  concurrencyPolicy: Forbid
  successfulJobsHistoryLimit: 2
  failedJobsHistoryLimit: 3
  startingDeadlineSeconds: 300
```

Приостановка: `suspend: true` — см. [Примеры](examples.md).

## См. также

- [Обзор DataFlowCron](index.md)
- [Триггеры](triggers.md)
