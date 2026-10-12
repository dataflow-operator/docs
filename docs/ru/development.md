# Development

Руководство для разработчиков, желающих внести вклад в DataFlow Operator или настроить локальную среду разработки.

## Предварительные требования

- Go 1.25 или выше
- Docker и Docker Compose
- kubectl настроен для работы с кластером
- Helm 3.0+ (для тестирования установки)
- Task (опционально, для использования Taskfile)

## Настройка окружения

### Клонирование репозитория

```bash
git clone <repository-url>
cd dataflow
```

### Установка зависимостей

```bash
go mod download
go mod tidy
```

### Установка инструментов разработки

```bash
# Установка controller-gen
task controller-gen

# Установка envtest
task envtest
```

## Локальная разработка

### Запуск зависимостей

Запустите все необходимые сервисы через docker-compose:

```bash
docker-compose up -d
```

Это запустит:
- Kafka (порт 9092) с Kafka UI (порт 8080)
- PostgreSQL (порт 5432) с pgAdmin (порт 5050)

### Запуск оператора локально

```bash
# Генерация кода и манифестов
task generate
task manifests

# Установка CRD в кластер (если используете kind/minikube)
task install

# Запуск оператора
task run
```

Или используйте скрипт:

```bash
./scripts/run-local.sh
```

### Настройка kind кластера

Для полноценного тестирования используйте kind:

```bash
# Создать kind кластер
./scripts/setup-kind.sh

# Установить CRD
task install

# Запустить оператор локально
task run
```

## Структура проекта

```
dataflow/
├── api/v1/                    # CRD определения
│   ├── dataflow_types.go      # Типы DataFlow; конфиг коннектора — отдельная структура
│   ├── provider_registry.go   # Регистрация source: валидатор, checkpoint, Exhausts
│   ├── dataflow_validation.go # Валидация spec, в том числе switch трансформаций
│   └── groupversion_info.go   # Версия API
├── pkg/
│   ├── providers/             # Реестр типов source/sink (checkpoint, Exhausts, валидаторы)
│   ├── transformtypes/        # Канонические ключи трансформаций
│   └── run/                   # dataflow-cli run; SourceExhausts читает реестр providers
├── internal/
│   ├── connectors/            # Коннекторы для источников/приемников
│   │   ├── interface.go       # Интерфейсы коннекторов
│   │   ├── factory.go         # createSourceConnector / registerSourceConnector
│   │   ├── provider_registrations.go  # init: фабрики, сверка с каталогом providers
│   │   ├── kafka.go           # Kafka коннектор
│   │   ├── postgresql.go      # PostgreSQL коннектор
│   ├── transformers/          # Трансформации сообщений
│   │   ├── interface.go       # Интерфейс трансформаций
│   │   ├── factory.go         # transformerRegistry + createTransformer
│   │   ├── timestamp.go        # Timestamp трансформация
│   │   ├── flatten.go         # Flatten трансформация
│   │   ├── filter.go          # Filter трансформация
│   │   ├── mask.go            # Mask трансформация
│   │   ├── router.go          # Router трансформация
│   │   ├── select.go          # Select трансформация
│   │   └── remove.go          # Remove трансформация
│   ├── processor/             # Процессор сообщений
│   │   └── processor.go       # Оркестрация обработки
│   ├── controller/            # Kubernetes контроллер
│   │   └── dataflow_controller.go
│   └── types/                 # Внутренние типы
│       └── message.go         # Тип Message
├── config/                    # Конфигурация Kubernetes
│   ├── crd/                   # CRD манифесты
│   ├── rbac/                  # RBAC манифесты
│   └── samples/              # Примеры DataFlow ресурсов
├── helm/                      # Helm Chart
│   └── dataflow-operator/
├── docs/                      # Документация MkDocs
├── test/                      # Тесты
│   └── fixtures/             # Тестовые данные
├── scripts/                   # Вспомогательные скрипты
├── main.go                    # Точка входа
├── Taskfile                   # Команды сборки
└── go.mod                     # Зависимости Go
```

## Генерация кода

### Генерация CRD и RBAC

```bash
task manifests
```

Эта команда генерирует:
- CRD манифесты в `dataflow/config/crd/bases/`

### Генерация DeepCopy методов

```bash
task generate
```

Генерирует методы `DeepCopy` для всех типов в `api/v1/`.

### Генерация JSON Schema

```bash
task schemas
```

Пишет машиночитаемые схемы в `schemas/` монорепозитория (CRD envelope + per-connector/transform config + `catalog.json`). Артефакты коммитятся; CI `provider-types-drift` перегенерирует и падает при diff. Проверка дрейфа:

```bash
python3 scripts/check_provider_types_drift.py
```

### Обновление controller-gen

Если возникают проблемы с генерацией:

```bash
# Обновить controller-gen
go install sigs.k8s.io/controller-tools/cmd/controller-gen@latest

# Затем
task generate
task manifests
```

## Логирование

### Структурированные поля

В логах оператора и процессора используются единые поля для корреляции:

| Поле | Где | Назначение |
|------|-----|------------|
| `dataflow_name` | Оператор, процессор, коннекторы | Имя ресурса DataFlow |
| `dataflow_namespace` | Оператор, процессор, коннекторы | Namespace DataFlow |
| `reconcile_id` | Оператор | Короткий идентификатор одного цикла реконсиляции (8 hex-символов) |
| `connector_type` | Процессор, коннекторы | Тип коннектора (например `kafka-source`, `trino-sink`) |
| `message_id` | Процессор, коннекторы | Идентификатор сообщения из метаданных (если есть) или partition/offset для Kafka |

По этим полям можно фильтровать логи в агрегаторе (например по `dataflow_name` и `reconcile_id`) и связывать ошибки с конкретным DataFlow и сообщением.

### Уровень лога (LOG_LEVEL)

Оператор и процессор читают переменную окружения **LOG_LEVEL**. Допустимые значения (без учёта регистра): `debug`, `info`, `warn`, `error`.

- **В проде**: задайте `LOG_LEVEL=info` (или не задавайте — по умолчанию в Helm используется `info`), чтобы уменьшить объём логов.
- **При отладке**: задайте `LOG_LEVEL=debug` для более детального вывода.

В Helm для оператора уровень задаётся через value **logLevel** (по умолчанию `"info"`); он подставляется в env `LOG_LEVEL` в поде оператора.

#### PROCESSOR_LOG_LEVEL

Оператор читает переменную окружения **PROCESSOR_LOG_LEVEL** и передаёт её в каждый под процессора как **LOG_LEVEL**. Поды процессора — это рабочие нагрузки, создаваемые для каждого DataFlow; в них выполняются сами пайплайны.

| Аспект | Описание |
|--------|----------|
| **По умолчанию** | `info` (если переменная не задана, поды процессора получают `LOG_LEVEL=info`) |
| **Допустимые значения** | Те же, что у LOG_LEVEL: `debug`, `info`, `warn`, `error` (регистр не важен) |
| **Где задавать** | В Deployment **оператора** (не в ресурсе DataFlow). Оператор подставляет это значение в env `LOG_LEVEL` каждого пода процессора. При установке через Helm задаётся value **processorLogLevel** (см. ниже). |

**Через Helm:** используйте value **processorLogLevel** (по умолчанию `"info"`). Пример для детальных логов процессоров:

```bash
helm upgrade dataflow-operator oci://ghcr.io/dataflow-operator/helm-charts/dataflow-operator \
  --set processorLogLevel=debug \
  --reuse-values
```

Или в `values.yaml`:

```yaml
processorLogLevel: "debug"   # поды процессора получают LOG_LEVEL=debug
```

**Без Helm:** задайте переменную окружения в Deployment оператора, например:

```bash
kubectl set env deployment/dataflow-operator PROCESSOR_LOG_LEVEL=debug -n <namespace-оператора>
```

После этого перезапустите или пересоздайте оператор, чтобы поды процессора пересоздались с новым уровнем.

## Настройка Validating Webhook { #настройка-validating-webhook }

Validating Webhook проверяет spec ресурса DataFlow при создании и обновлении и отклоняет невалидные объекты до записи в кластер. Это даёт немедленную обратную связь (ошибка при `kubectl apply` или в GUI) и не создаёт лишние объекты и поды с заведомо нерабочей конфигурацией. Подробнее о роли webhook в архитектуре см. [Admission Webhook (Validating)](architecture.md#admission-webhook-validating).

### Включение через Helm

Webhook **опционален** и по умолчанию выключен. Чтобы включить его:

1. **Включите webhook и задайте CA для TLS:** в `values.yaml` или через `--set`:
   - `webhook.enabled: true`
   - `webhook.caBundle` — строка в base64 (PEM-сертификат CA, которым подписан сертификат оператора на порту 9443). Без неё ValidatingWebhookConfiguration не создаётся, так как API-сервер требует caBundle для вызова webhook по HTTPS.

2. **Настройте TLS для оператора:** API-сервер подключается к оператору по HTTPS. Задайте:
   - `webhook.certDir` — путь в контейнере, куда смонтированы сертификаты (например `/tmp/k8s-webhook-server/serving-certs`).
   - `webhook.secretName` — имя Secret с ключами `tls.crt` и `tls.key` (и при необходимости `ca.crt`). Этот Secret монтируется в под оператора по пути `webhook.certDir`; переменная окружения `WEBHOOK_CERT_DIR` в поде устанавливается в это значение.

Секрет с сертификатами можно создать вручную или через **cert-manager** (Certificate для сервиса оператора). CA из этого сертификата (или из выдавшего его CA) нужно подставить в `webhook.caBundle` в base64.

Пример фрагмента `values.yaml` при использовании cert-manager и уже известного caBundle:

```yaml
webhook:
  enabled: true
  caBundle: "LS0tLS1CRUdJTi..."   # base64 PEM CA
  certDir: /tmp/k8s-webhook-server/serving-certs
  secretName: dataflow-operator-webhook-cert
```

После установки/обновления чарта с этими значениями создаётся ресурс ValidatingWebhookConfiguration; при следующем create/update **DataFlow** или **DataFlowCron** API-сервер будет вызывать оператор для валидации.

### Что проверяет webhook

**DataFlow** (`dataflows`):

- Обязательные поля: `spec.source`, `spec.sink`, типы source/sink из реестра провайдеров (`kafka`, `postgresql`, `postgresql-cdc`, `trino`, `clickhouse`, `nessie`, `iceberg` — см. `dataflow/api/v1/provider_registry.go` и `pkg/providers`), наличие `source.config` / `sink.config` при заданном `type`.
- Для каждого типа source/sink — обязательные поля или SecretRef (например для Kafka: brokers или brokersSecretRef, topic или topicSecretRef).
- Список трансформаций: допустимые типы и наличие конфигурации для каждого типа; для router — валидация вложенных sink.
- Опционально: `spec.errors` (если задан — как SinkSpec), SecretRef (name и key), неотрицательные ресурсы.

**DataFlowCron** (`dataflowcrons`): встроенные поля в стиле DataFlow (`source`, `sink`, `transformations`, …) проверяются так же; дополнительно — непустой `schedule` с 5–6 полями cron, у каждого триггера задан `image`, при наличии `concurrencyPolicy` допустимы только `Allow`, `Forbid`, `Replace`.

При ошибке валидации API возвращает ответ с перечислением полей и сообщений (агрегат из `field.ErrorList`).

## Тестирование

### Unit тесты

```bash
# Запустить все unit тесты
task test-unit

# Запустить тесты с покрытием
task test

# Запустить тесты конкретного пакета
go test ./internal/connectors/... -v

# Запустить тесты с покрытием для конкретного пакета
go test ./internal/transformers/... -coverprofile=coverage.out
go tool cover -html=coverage.out
```

### Интеграционные тесты

```bash
# Настроить kind кластер
./scripts/setup-kind.sh

# Запустить интеграционные тесты
task test-integration
```

### Запуск тестов вручную

```bash
# Unit тесты без envtest
go test ./... -v

# Тесты с envtest (требует kubebuilder)
KUBEBUILDER_ASSETS="$(task envtest use 1.28.0 -p path)" go test ./... -coverprofile cover.out
```

## Сборка

### Локальная сборка

```bash
# Сборка бинарного файла
task build

# Бинарный файл будет в bin/manager
./bin/manager
```

### Сборка Docker образа

```bash
# Сборка образа
task docker-build IMG=your-registry/dataflow-operator:v1.0.0

# Отправка образа
task docker-push IMG=your-registry/dataflow-operator:v1.0.0
```

Или вручную. Если репозиторий — монорепо (есть папки `dataflow` и `dataflow-web`), сборка из **корня репозитория**:

```bash
docker build -f dataflow/Dockerfile -t your-registry/dataflow-operator:v1.0.0 .
docker push your-registry/dataflow-operator:v1.0.0
```

Если вы находитесь в каталоге `dataflow` и контекст сборки — только он (без `dataflow-web`), используйте прежний вариант: `docker build -t ... .`

## Добавление нового коннектора

Новый тип попадает в бинарник оператора и CLI только пересборкой. Внешней загрузки плагинов нет: манифест везде задаёт `type` и `config`, а `SourceSpec` / `SinkSpec` держат конфиг как `*runtime.RawExtension`. Поля вроде `source.kafka` в API нет.

> **Подробное руководство:** [Разработка коннекторов с baseConnector](connector-development.md) — `baseConnector`, два `init` и каталог схем.

### 1. Структура конфига

Добавьте spec в `api/v1/dataflow_types.go`. В `SourceSpec` и `SinkSpec` её не вкладывайте: фабрика и webhook разбирают `config` по `type`.

```go
type MyDBSourceSpec struct {
    ConnectionString string `json:"connectionString"`
    Table            string `json:"table"`
}
```

```yaml
source:
  type: mydb
  config:
    connectionString: "mydb://localhost:3306/db"
    table: my_table
```

### 2. Реализация

Файл `internal/connectors/mydb.go`. Встраивайте `baseConnector` или `baseConnectorRWMutex` и реализуйте `SourceConnector` / `SinkConnector`. Пример Connect/Close — в [руководстве по коннекторам](connector-development.md).

### 3. Одна регистрация метаданных и фабрика

Валидатор, `SupportsCheckpoint` и `Exhausts` задаются одним вызовом `providers.RegisterSource` в `api/v1/provider_registry.go`. Повторная регистрация того же типа вызывает panic, слияния флагов нет. Без валидатора source не регистрируется.

Пакет `api/v1` не импортирует реализации коннекторов, поэтому фабрика живёт рядом, в `internal/connectors/provider_registrations.go`. `registerSourceConnector` только сохраняет фабрику. В конце `init` набор фабрик сверяется с `providers.ListSourceTypes()` и `ListSinkTypes()`: лишняя фабрика или тип без фабрики останавливают процесс. Для sink то же самое через `providers.RegisterSink` и `registerSinkConnector`.

```go
providers.RegisterSource(providers.SourceDefinition{
    Type:               "mydb",
    SupportsCheckpoint: true,
    Exhausts:           true,
    ValidateConfig: func(raw []byte, path *field.Path) field.ErrorList {
        return validateSourceConfig(raw, "mydb", path, validateMyDBSource)
    },
})
```

```go
registerSourceConnector("mydb", createSourceConnectorWithOptions[v1.MyDBSourceSpec](
    "mydb source",
    func(cfg *v1.MyDBSourceSpec, opts *SourceConnectorOptions) SourceConnector {
        return NewMyDBSourceConnectorWithOptions(cfg, opts)
    },
))

registerSinkConnector("mydb", createSinkConnector[v1.MyDBSinkSpec](
    "mydb sink",
    func(cfg *v1.MyDBSinkSpec) SinkConnector { return NewMyDBSinkConnector(cfg) },
))
```

`Exhausts` означает, что чтение завершается. Это не то же самое, что checkpoint: у `postgresql-cdc` checkpoint включён, а `Exhausts` равен false. У `kafka` оба флага выключены.

`createSourceConnector` — если source не принимает `SourceConnectorOptions`. `CreateSourceConnector` / `CreateSinkConnector` в `factory.go` ищут тип в map и разворачивают `config`. Ветки `switch source.Type` в фабрике нет.

`dataflow-cli run` вызывает `pkg/run`, тот импортирует `internal/processor` → `internal/connectors`, поэтому отдельного списка типов в CLI нет. Валидаторы подключаются импортом `api/v1`. Процессор включает checkpoint через `providers.SourceSupportsCheckpoint`.

### 4. Одноразовый прогон (`run --once`)

`pkg/run.SourceExhausts` читает поле `Exhausts` той же записи. Отдельный `switch` в `exhaust.go` не нужен. Тест `TestSourceExhausts` обходит `providers.ListSourceTypes()`, поэтому новый source без явной классификации в тесте не пройдёт незаметно.

### 5. Схемы и списки для UI

В `dataflow/hack/genschemas/main.go` добавьте sample-struct в `sourceEntries` и, если есть sink, в `sinkEntries`. Затем из каталога `dataflow`:

```bash
task generate
task manifests
task schemas
```

`task schemas` сверяет эти слайсы с `providers.ListSourceTypes` / `ListSinkTypes` и пишет `schemas/catalog.json`. Дальше обновите обзорные таблицы `docs/docs/{ru,en}/connectors.md`, `docs/provider-types-inventory.md`, списки в `dataflow-mcp/src/tools/reference.rs` и `CONNECTOR_TYPES` в web (`dataflow-web/web/src/composables/useFlowManifest.js`). Проверка:

```bash
python3 scripts/check_provider_types_drift.py
```

### 6. Тесты

Тесты коннектора — в `internal/connectors/mydb_test.go`: идемпотентный `Close`, ошибка `Connect` после `Close`, разбор `config`.

## Добавление новой трансформации

Манифест задаёт `type` и `config` (`*runtime.RawExtension` на `TransformationSpec`). Отдельного поля `transformation.flatten` нет. Обёртка `when` навешивается в `CreateTransformer` и в список типов не входит.

Ключ живёт в трёх местах: константа в `pkg/transformtypes`, строка `transformerRegistry`, ветка `switch` в `validateTransformations`. Первые два связаны константой, третий — нет: пропущенный `case` пропускает тип в webhook без проверки полей.

### 1. Структура конфига

В `api/v1/dataflow_types.go`:

```go
type MyTransform struct {
    Field string `json:"field"`
}
```

### 2. Ключ типа

В `pkg/transformtypes/transformtypes.go` добавьте константу и допишите её в слайс `keys`:

```go
const MyTransform = "myTransform"

var keys = []string{
    // ...
    MyTransform,
}
```

`IsRegistered` и `All()` читают этот слайс. Webhook отклоняет тип, которого там нет.

### 3. Реализация и фабрика

Файл `internal/transformers/mytransform.go` с методом `Transform`. В map `transformerRegistry` в `internal/transformers/factory.go`:

```go
transformtypes.MyTransform: {create: createTransformer[v1.MyTransform](
    transformtypes.MyTransform,
    func(cfg *v1.MyTransform) Transformer { return NewMyTransformer(cfg) },
)},
```

`createTransformer` разворачивает `config`. `CreateTransformer` ищет запись в map и при непустом `when` оборачивает результат.

### 4. Валидатор

В `validateTransformations` (`api/v1/dataflow_validation.go`) добавьте `case` по константе: пустой `config` — `field.Required`, битый JSON — `field.Invalid`, дальше проверки полей spec.

### 5. Схемы и списки

Sample-struct — в `transformEntries` в `dataflow/hack/genschemas/main.go` (тип берите из `transformtypes`, как у соседних записей). Затем `task schemas`. Обновите таблицы `docs/docs/{ru,en}/transformations.md`, блок Transformers в `docs/provider-types-inventory.md`, `reference.rs` и `TRANSFORMATION_TYPES` в web. `task schemas` сверяет имена с `transformtypes.All()`; `scripts/check_provider_types_drift.py` сверяет каталог с docs, MCP, inventory и web.

### 6. Тесты

Тест трансформации и тест webhook на обязательные поля `config`.


### Логирование

Используйте структурированное логирование:

```go
import "github.com/go-logr/logr"

logger.Info("Processing message", "messageId", msg.ID)
logger.Error(err, "Failed to process", "messageId", msg.ID)
logger.V(1).Info("Debug information", "data", data)
```

### Отладка контроллера

```bash
# Запустить с детальным логированием
go run ./main.go --zap-log-level=debug
```

### Отладка коннекторов

Добавьте логирование в методы коннекторов:

```go
func (k *KafkaSourceConnector) Read(ctx context.Context) (<-chan *types.Message, error) {
    logger.Info("Starting to read from Kafka", "topic", k.config.Topic)
    // ...
}
```

## Форматирование и линтинг

### Форматирование кода

```bash
task fmt
```

Или вручную:

```bash
go fmt ./...
```

### Проверка кода

```bash
task vet
```

Или вручную:

```bash
go vet ./...
```

### Линтинг (опционально)

Установите golangci-lint:

```bash
go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest
```

Запустите:

```bash
golangci-lint run
```

## CI/CD

### GitHub Actions

Пример workflow для CI:

```yaml
name: CI

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-go@v4
        with:
          go-version: '1.25'
      - run: go mod download
      - run: task test-unit
      - run: task vet
      - run: task fmt
```

## Сборка документации

Документация собирается с помощью [MkDocs](https://www.mkdocs.org/) и темы Material. Диаграммы строятся на [Mermaid](https://mermaid.js.org/) через плагин `mkdocs-mermaid2-plugin`.

**Установка зависимостей** (из корня репозитория):

```bash
pip install -r docs/requirements.txt
```

Или вручную:

```bash
pip install "mkdocs-material[imaging]" pymdown-extensions mkdocs-mermaid2-plugin
```

**Сборка и просмотр** (из корня репозитория):

```bash
cd docs && mkdocs build
# или локальный сервер:
cd docs && mkdocs serve
```

При использовании `mkdocs serve` откройте в браузере `http://127.0.0.1:8000`.

## Вклад в проект

### Процесс разработки

1. Создайте issue для обсуждения изменений
2. Создайте feature branch: `git checkout -b feature/new-feature`
3. Внесите изменения и добавьте тесты
4. Убедитесь, что все тесты проходят: `task test`
5. Отформатируйте код: `task fmt`
6. Создайте Pull Request

### Стандарты кода

- Следуйте Go code review comments
- Добавляйте комментарии для публичных функций
- Пишите тесты для нового функционала
- Обновляйте документацию при необходимости

### Коммиты

Используйте понятные сообщения коммитов:

```
feat: add new connector for Redis
fix: handle connection errors in Kafka connector
docs: update getting started guide
test: add tests for filter transformation
```

## Полезные команды

```bash
# Просмотр всех доступных команд
task help

# Очистка сгенерированных файлов
task clean

# Обновление зависимостей
go mod tidy

# Просмотр зависимостей
go list -m all

# Проверка устаревших зависимостей
go list -u -m all
```

## Cursor Agent Skills (maintainer)

Клиентские skills разрабатываются в каталоге `skills/` monorepo и публикуются в **[github.com/dataflow-operator/skills](https://github.com/dataflow-operator/skills)**. Maintainer-расширения: `.cursor/skills/dataflow-*`. См. [Agent Skills](agent-skills.md).

## Ресурсы

- [Agent Skills](agent-skills.md) — публикация в [dataflow-operator/skills](https://github.com/dataflow-operator/skills)
- [Kubebuilder Book](https://book.kubebuilder.io/) - руководство по созданию Kubernetes операторов
- [controller-runtime](https://github.com/kubernetes-sigs/controller-runtime) - библиотека для контроллеров
- [Go Documentation](https://golang.org/doc/) - документация Go

## Получение помощи

- Создайте issue в репозитории
- Проверьте существующие issues и PR
- Изучите примеры в `dataflow/config/samples/`

