# CLI (`dataflow-cli`)

Командная строка для DataFlow: работа с API [Web GUI](gui.md) или локальный запуск манифеста DataFlow без Kubernetes.

**Когда читать:** скрипты против web API, локальный smoke-тест пайплайна или day-2 операции без правки YAML через `kubectl`.

**См. также:** [Web GUI](gui.md) · [Начало работы](getting-started.md) · [Справочник Spec](dataflow/spec.md)

## Установка

### Готовый бинарник

Тег `v*` публикует бинарники и `SHA256SUMS` в [GitHub Releases](https://github.com/dataflow-operator/dataflow-operator/releases).

| ОС | Архитектура | Файл |
|----|-------------|------|
| Linux | amd64 | `dataflow-cli-linux-amd64` |
| Linux | arm64 | `dataflow-cli-linux-arm64` |
| Linux | armv7 | `dataflow-cli-linux-arm-v7` |
| macOS | amd64 | `dataflow-cli-darwin-amd64` |
| macOS | arm64 | `dataflow-cli-darwin-arm64` |
| Windows | amd64 | `dataflow-cli-windows-amd64.exe` |
| Windows | arm64 | `dataflow-cli-windows-arm64.exe` |

```bash
curl -fsSL -o dataflow-cli \
  "https://github.com/dataflow-operator/dataflow-operator/releases/download/vX.Y.Z/dataflow-cli-linux-amd64"
chmod +x dataflow-cli
```

Подставьте `vX.Y.Z` и имя файла под свою ОС.

### Docker

Образ: `ghcr.io/dataflow-operator/dataflow-cli` (`linux/amd64`, `linux/arm64`). `:latest` и тег версии появляются с релизом `v*`. `:main` обновляется из ветки `main`.

```bash
docker pull ghcr.io/dataflow-operator/dataflow-cli:latest

docker run --rm ghcr.io/dataflow-operator/dataflow-cli:latest --help

# На Linux --network host открывает source/sink на хосте.
# В Docker Desktop в манифесте указывайте host.docker.internal вместо localhost.
docker run --rm --network host \
  -v "$PWD:/work" -w /work \
  ghcr.io/dataflow-operator/dataflow-cli:latest \
  run manifest.yaml --once

# SecretRef читается из примонтированного kubeconfig.
docker run --rm --network host \
  -v "$HOME/.kube:/root/.kube:ro" \
  -v "$PWD:/work" -w /work \
  ghcr.io/dataflow-operator/dataflow-cli:latest \
  run manifest.yaml --once
```

Сборка из корня монорепозитория:

```bash
docker build -f dataflow-cli/Dockerfile -t dataflow-cli .
```

### Из исходников

Go 1.25+:

```bash
cd dataflow-cli
go build -o dataflow-cli .
```

В монорепозитории в `go.mod` уже есть `replace github.com/dataflow-operator/dataflow => ../dataflow` для локальной разработки.

Исходники: [`dataflow-cli/`](https://github.com/dataflow-operator/dataflow-operator/tree/main/dataflow-cli). CI: [`.github/workflows/dataflow-cli.yml`](https://github.com/dataflow-operator/dataflow-operator/blob/main/.github/workflows/dataflow-cli.yml).

## Глобальные флаги

| Флаг / env | Описание | По умолчанию |
|------------|----------|--------------|
| `--api-url` / `DATAFLOW_API_URL` | Базовый URL API dataflow-web | `http://localhost:8080/api` |
| `--namespace` | Kubernetes namespace для ресурсов DataFlow | `default` |

Укажите `--api-url` на port-forward или Ingress GUI, например:

```bash
kubectl port-forward svc/dataflow-operator-gui 8080:8080 -n dataflow-system
export DATAFLOW_API_URL=http://localhost:8080/api
```

## Команды Web API

Те же действия, что в браузерном UI:

```bash
# Namespaces
dataflow-cli namespaces

# DataFlows
dataflow-cli dataflows list
dataflow-cli dataflows list --namespace=my-ns
dataflow-cli dataflows get my-dataflow
dataflow-cli dataflows create --file=manifest.yaml
dataflow-cli dataflows update my-dataflow --file=manifest.yaml
dataflow-cli dataflows delete my-dataflow

# Логи (--follow / -f — поток в реальном времени)
dataflow-cli logs my-dataflow --tail=200
dataflow-cli logs my-dataflow -f

# Статус и метрики
dataflow-cli status my-dataflow
dataflow-cli metrics my-dataflow
```

Во всех командах можно указать `--namespace` (по умолчанию `default`).

## Локальный запуск (без Kubernetes)

Пайплайн выполняется внутри процесса CLI. Кластер и оператор не нужны; source и sink должны быть доступны (Kafka, PostgreSQL и т.д.).

```bash
dataflow-cli run manifest.yaml
dataflow-cli run manifest.yaml --log-level=debug
```

Остановка: Ctrl+C.

## One-shot migration

`--once` читает polling-источник, пока он не исчерпается, сбрасывает sink, пишет локальный checkpoint и завершается. Так делают разовый снимок (например PostgreSQL → PostgreSQL) без кластера. Допустим `kind: DataFlowCron`; `schedule` и `triggers` игнорируются.

Источники: `postgresql`, `clickhouse`, `trino`, `iceberg`, `nessie`. `kafka` и `postgresql-cdc` не закрываются, поэтому `--once` завершается ошибкой до подключения.

```bash
dataflow-cli run manifest.yaml --once
dataflow-cli run manifest.yaml --once --checkpoint-file .dataflow/pg-migration.json --reset
dataflow-cli run manifest.yaml --once --timeout 2h
```

| Флаг | Описание |
|------|----------|
| `--once` | Выход, когда источник исчерпан |
| `--checkpoint-file` | JSON checkpoint. Для `--once` по умолчанию: `.dataflow/<metadata.name>.json` |
| `--reset` | Очистить checkpoint этого источника перед стартом |
| `--timeout` | Предел времени (`2h`, `30m`). `0` — без предела |
| `--log-level` | `debug`, `info`, `warn`, `error` |

Ctrl+C или таймаут сбрасывают checkpoint на диск и завершают процесс с ненулевым кодом. Следующий запуск продолжит с файла. При успехе CLI печатает source, sink, processed, errors и путь checkpoint.

`checkpointPersistence: false` отключает файл. `SecretRef` читается из текущего kubeconfig (или in-cluster config) до старта пайплайна. Нет секрета или ключа — запуск прерывается до connect.

Манифест остаётся обычным DataFlow. На источнике задайте `changeTrackingColumn`, `orderByColumn` и `readBatchSize`, на sink — `upsertMode` и `conflictKey`.

```yaml
apiVersion: dataflow.dataflow.io/v1
kind: DataFlow
metadata:
  name: pg-migration
spec:
  checkpointSyncOnAck: true
  source:
    type: postgresql
    config:
      connectionString: "postgres://user:pass@localhost:5432/src?sslmode=disable"
      table: public.source_table
      changeTrackingColumn: id
      orderByColumn: id
      readBatchSize: 10000
      pollInterval: 5
  sink:
    type: postgresql
    config:
      connectionString: "postgres://user:pass@localhost:5432/dst?sslmode=disable"
      table: public.target_table
      upsertMode: true
      conflictKey: id
      batchSize: 1000
```

```bash
dataflow-cli run pg-migration.yaml --once --timeout 2h
```

!!! warning "Учётные данные в локальных манифестах"
    В local-dev примерах допустимы plaintext connection strings. Для всего shared/prod-подобного используйте `SecretRef`. См. [Best Practices](best-practices.md).

## Пример манифеста

Стандартный YAML CR DataFlow:

```yaml
apiVersion: dataflow.dataflow.io/v1
kind: DataFlow
metadata:
  name: kafka-to-postgres
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
      connectionString: "postgres://user:pass@localhost:5432/db?sslmode=disable"
      table: output_table
```

Эталонные samples: [config/samples](https://github.com/dataflow-operator/dataflow/tree/main/config/samples) (для apply в кластер предпочитайте паттерны `*-secrets.yaml`).

## Когда CLI, GUI или kubectl

| Цель | Предпочтительнее |
|------|------------------|
| Просмотр / правка в браузере | [Web GUI](gui.md) |
| Скрипты, CI, быстрые вызовы API | `dataflow-cli` |
| Полный контроль кластера, status CRD, events | `kubectl` |
| Черновик/валидация YAML с AI | [MCP](mcp.md) + [Agent Skills](agent-skills.md) |
