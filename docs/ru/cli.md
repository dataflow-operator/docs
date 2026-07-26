# CLI (`dataflow-cli`)

Командная строка для DataFlow: работа с API [Web GUI](gui.md) или локальный запуск манифеста DataFlow без Kubernetes.

**Когда читать:** скрипты против web API, локальный smoke-тест пайплайна или day-2 операции без правки YAML через `kubectl`.

**См. также:** [Web GUI](gui.md) · [Начало работы](getting-started.md) · [Справочник Spec](dataflow/spec.md)

## Установка

Сборка из исходников (Go 1.25+):

```bash
cd dataflow-cli
go build -o dataflow-cli .
```

В монорепозитории в `go.mod` уже есть `replace github.com/dataflow-operator/dataflow => ../dataflow` для локальной разработки.

Готовые бинарники (когда публикуются): [GitHub Releases](https://github.com/dataflow-operator/dataflow-operator/releases).

Исходники: [`dataflow-cli/`](https://github.com/dataflow-operator/dataflow-operator/tree/main/dataflow-cli).

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

!!! warning "Учётные данные в локальных манифестах"
    В local-dev примерах допустимы plaintext connection strings. Для всего shared/prod-подобного используйте `SecretRef`. См. [Best Practices](best-practices.md).

### Пример манифеста

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
