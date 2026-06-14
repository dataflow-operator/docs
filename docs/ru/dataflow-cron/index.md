# DataFlowCron

**DataFlowCron** — namespaced CRD (`dataflowcrons`, kind `DataFlowCron`, group `dataflow.dataflow.io`) для запуска того же конвейера **источник → трансформации → приёмник**, что и у [DataFlow](../dataflow/index.md), но **по cron-расписанию** через Kubernetes **CronJob** / **Job**.

Используйте для **пакетных** или **периодических** сценариев и когда после успешного прогона нужны [триггеры](triggers.md).

## Отличие от DataFlow

| | DataFlow | DataFlowCron |
|---|----------|--------------|
| Оркестрация | Deployment (always on) | CronJob → Job на тик |
| Пост-шаги | — | Опциональные `triggers` |
| Лучшие источники | Kafka streaming | Polling / batch |

См. [Типы нагрузки](../concepts/workload-types.md).

## Ход выполнения

1. **CronJob** создаёт **Job** с процессором до исчерпания источника или завершения процесса.
2. После **успеха** Job — очередь **Job триггеров**.
3. **Status**: `RunningTriggers`, `Completed`, `Failed`.

## Тип источника и завершение прогона

- **Polling-источники** обычно **завершаются** при исчерпании — триггеры могут стартовать.
- **Kafka** часто **не останавливается** сам — для cron с триггерами используйте polling.

## Разделы документации

- [Spec и расписание](spec.md)
- [Триггеры](triggers.md)
- [Примеры](examples.md)

## См. также

- [DataFlow](../dataflow/index.md)
- [Архитектура](../architecture.md)
- [Примеры](../examples.md#dataflowcron-example)
