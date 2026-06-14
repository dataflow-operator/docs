# DataFlow

**DataFlow** — namespaced CRD (`dataflows`, kind `DataFlow`, group `dataflow.dataflow.io`) для **непрерывных** конвейеров данных. Оператор приводит каждый ресурс к **Deployment** с процессором, пока вы не удалите `DataFlow`.

## Что делает

Вы объявляете **источник**, **трансформации** и **приёмник**. Оператор:

1. Подставляет значения `SecretRef` из Kubernetes Secrets.
2. Записывает resolved spec в ConfigMap.
3. Создаёт или обновляет **Deployment** с подом процессора.
4. Отражает состояние Deployment в `DataFlow.status`.

Процессор выполняет тот же конвейер, что и у [DataFlowCron](../dataflow-cron/index.md): чтение → трансформация → запись (плюс опциональный error sink).

## Когда использовать

| Сценарий | DataFlow | DataFlowCron |
|----------|----------|--------------|
| Consumer Kafka, always on | ✓ | |
| Репликация в реальном времени | ✓ | |
| Ночная выгрузка таблицы | | ✓ |
| Почасовой batch + webhook после успеха | | ✓ |

См. [Типы нагрузки](../concepts/workload-types.md).

!!! tip "Запуск по расписанию"
    Для cron и пост-**triggers** используйте [DataFlowCron](../dataflow-cron/index.md).

## API

| Параметр | Значение |
|----------|----------|
| API group | `dataflow.dataflow.io` |
| Resource | `dataflows` |
| Kind | `DataFlow` |
| Scope | Namespaced |

## Разделы документации

- [Справочник spec](spec.md)
- [Жизненный цикл и status](lifecycle.md)

## Минимальный пример

```yaml
apiVersion: dataflow.dataflow.io/v1
kind: DataFlow
metadata:
  name: kafka-to-postgres
spec:
  source:
    type: kafka
    config:
      brokers: [kafka:9092]
      topic: input-topic
      consumerGroup: dataflow-group
  sink:
    type: postgresql
    config:
      connectionString: "postgres://user:pass@postgres:5432/db?sslmode=disable"
      table: output_table
      autoCreateTable: true
```

## См. также

- [Архитектура](../architecture.md)
- [Коннекторы](../connectors.md)
- [Начало работы](../getting-started.md)
