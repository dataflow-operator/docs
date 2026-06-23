# DataFlow Operator

<div class="md-hero" markdown="block">

Kubernetes-оператор для потоковых и scheduled-конвейеров между Kafka, PostgreSQL, ClickHouse, Trino, Nessie и Iceberg.

[Начало работы](getting-started.md){ .md-button .md-button--primary }
[Архитектура](architecture.md){ .md-button }

</div>

## Текущие версии

| Компонент | Версия |
|-----------|--------|
| DataFlow Operator | <span data-version-repo="dataflow-operator/dataflow">—</span> |
| Helm Charts | <span data-version-repo="dataflow-operator/helm-charts">—</span> |
| DataFlow MCP | <span data-version-repo="dataflow-operator/dataflow-mcp">—</span> |
| DataFlow Web | <span data-version-repo="dataflow-operator/dataflow-web">—</span> |

## Разделы документации

<div class="grid cards" markdown="block">

-   :material-play-circle:{ .lg .middle } **Начало работы**

    ---

    Установка через Helm и первый конвейер за минуты

    [:octicons-arrow-right-24: Начать](getting-started.md)

-   :material-source-branch:{ .lg .middle } **DataFlow**

    ---

    Непрерывные потоковые конвейеры (Deployment)

    [:octicons-arrow-right-24: Подробнее](dataflow/index.md)

-   :material-clock-outline:{ .lg .middle } **DataFlowCron**

    ---

    Запуск по расписанию с опциональными триггерами

    [:octicons-arrow-right-24: Подробнее](dataflow-cron/index.md)

-   :material-swap-horizontal:{ .lg .middle } **Типы нагрузки**

    ---

    Выбор между DataFlow и DataFlowCron

    [:octicons-arrow-right-24: Сравнить](concepts/workload-types.md)

-   :material-connection:{ .lg .middle } **Коннекторы**

    ---

    Kafka, PostgreSQL, ClickHouse, Trino, Nessie, Iceberg

    [:octicons-arrow-right-24: Справочник](connectors.md)

-   :material-auto-fix:{ .lg .middle } **Трансформации**

    ---

    Filter, mask, route, flatten и др.

    [:octicons-arrow-right-24: Справочник](transformations.md)

-   :material-robot:{ .lg .middle } **Agent Skills**

    ---

    Переносимые AI-инструкции для deploy, config и отказоустойчивости (любая IDE)

    [:octicons-arrow-right-24: Установка](agent-skills.md)

-   :material-help-circle:{ .lg .middle } **FAQ и Best Practices**

    ---

    Ответы на частые вопросы, troubleshooting и рекомендации по эксплуатации

    [:octicons-arrow-right-24: FAQ](faq.md) · [:octicons-arrow-right-24: Best Practices](best-practices.md)

</div>

## Обзор

!!! abstract ""
    DataFlow Operator позволяет декларативно определять потоки данных через Kubernetes CRD. Поддерживаются **непрерывные** (`DataFlow`) и **scheduled** (`DataFlowCron`) нагрузки.

## Быстрый старт

```bash
helm install dataflow-operator oci://ghcr.io/dataflow-operator/helm-charts/dataflow-operator
kubectl apply -f dataflow/config/samples/kafka-to-postgres.yaml
kubectl get dataflow kafka-to-postgres
```

## Карта документации

| Тема | Ссылка |
|------|--------|
| Установка | [Начало работы](getting-started.md) |
| DataFlow | [Обзор](dataflow/index.md) · [Spec](dataflow/spec.md) · [Жизненный цикл](dataflow/lifecycle.md) |
| DataFlowCron | [Обзор](dataflow-cron/index.md) · [Триггеры](dataflow-cron/triggers.md) · [Примеры](dataflow-cron/examples.md) |
| Эксплуатация | [Ошибки](errors.md) · [Отказоустойчивость](fault-tolerance.md) · [Метрики](metrics.md) |
| Инструменты | [Web GUI](gui.md) · [MCP](mcp.md) · [Agent Skills](agent-skills.md) |
| Руководства | [FAQ и Troubleshooting](faq.md) · [Best Practices](best-practices.md) · [Примеры](examples.md) |

## Лицензия

Apache License 2.0
