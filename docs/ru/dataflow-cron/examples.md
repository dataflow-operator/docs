# Примеры DataFlowCron

Фрагменты YAML. В подах Job используйте DNS сервисов Kubernetes, не `localhost`.

## Поля status

- **`phase`**, **`currentRunID`**, **`currentTriggerIndex`**, **`activeJobName`**
- **`lastScheduleTime`**, **`lastSuccessfulTime`**, **`lastFailedTime`**

```bash
kubectl get dataflowcrons.dataflow.dataflow.io
kubectl describe dataflowcron <name>
kubectl get cronjob,job -l dataflow.dataflow.io/dataflow-cron=<name>
```

## Только процессор, без `triggers`

```yaml
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

## ClickHouse → ClickHouse

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

## Nessie → Kafka

См. [Nessie](../connectors.md#nessie).

## С трансформациями и одним trigger

См. полные примеры в [Примеры — DataFlowCron](../examples.md#dataflowcron-example) и `dataflow/config/samples/dataflowcron-example.yaml`.

## Приостановка расписания

```yaml
spec:
  schedule: "0 * * * *"
  suspend: true
```

## См. также

- [Обзор DataFlowCron](index.md)
- [Триггеры](triggers.md)
