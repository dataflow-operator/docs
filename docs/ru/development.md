# Development

Руководство для разработчиков, желающих внести вклад в DataFlow Operator или настроить локальную среду разработки.

## Предварительные требования

- Go 1.21 или выше
- Docker и Docker Compose
- kubectl настроен для работы с кластером
- Helm 3.0+ (для тестирования установки)
- Make (опционально, для использования Makefile)

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
make controller-gen

# Установка envtest
make envtest
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
make generate
make manifests

# Установка CRD в кластер (если используете kind/minikube)
make install

# Запуск оператора
make run
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
make install

# Запустить оператор локально
make run
```

## Структура проекта

```
dataflow/
├── api/v1/                    # CRD определения
│   ├── dataflow_types.go      # Типы DataFlow ресурсов
│   └── groupversion_info.go    # Версия API
├── internal/
│   ├── connectors/            # Коннекторы для источников/приемников
│   │   ├── interface.go       # Интерфейсы коннекторов
│   │   ├── factory.go         # Фабрика коннекторов
│   │   ├── kafka.go           # Kafka коннектор
│   │   ├── postgresql.go      # PostgreSQL коннектор
│   ├── transformers/          # Трансформации сообщений
│   │   ├── interface.go       # Интерфейс трансформаций
│   │   ├── factory.go         # Фабрика трансформаций
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
├── Makefile                   # Команды сборки
└── go.mod                     # Зависимости Go
```

## Генерация кода

### Генерация CRD и RBAC

```bash
make manifests
```

Эта команда генерирует:
- CRD манифесты в `config/crd/bases/`
- RBAC манифесты в `config/rbac/`

### Генерация DeepCopy методов

```bash
make generate
```

Генерирует методы `DeepCopy` для всех типов в `api/v1/`.

### Обновление controller-gen

Если возникают проблемы с генерацией:

```bash
# Обновить controller-gen
go install sigs.k8s.io/controller-tools/cmd/controller-gen@latest

# Затем
make generate
make manifests
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

## Настройка Validating Webhook

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

После установки/обновления чарта с этими значениями создаётся ресурс ValidatingWebhookConfiguration; при следующем create/update DataFlow API-сервер будет вызывать оператор для валидации.

### Что проверяет webhook

- Обязательные поля: `spec.source`, `spec.sink`, типы source/sink из списка (`kafka`, `postgresql`, `trino`), наличие соответствующей конфигурации (например `source.kafka` при `source.type: kafka`).
- Для каждого типа source/sink — обязательные поля или SecretRef (например для Kafka: brokers или brokersSecretRef, topic или topicSecretRef).
- Список трансформаций: допустимые типы и наличие конфигурации для каждого типа; для router — валидация вложенных sink.
- Опционально: `spec.errors` (если задан — как SinkSpec), SecretRef (name и key), неотрицательные ресурсы.

При ошибке валидации API возвращает ответ с перечислением полей и сообщений (агрегат из `field.ErrorList`).

## Тестирование

### Unit тесты

```bash
# Запустить все unit тесты
make test-unit

# Запустить тесты с покрытием
make test

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
make test-integration
```

### Запуск тестов вручную

```bash
# Unit тесты без envtest
go test ./... -v

# Тесты с envtest (требует kubebuilder)
KUBEBUILDER_ASSETS="$(make envtest use 1.28.0 -p path)" go test ./... -coverprofile cover.out
```

## Сборка

### Локальная сборка

```bash
# Сборка бинарного файла
make build

# Бинарный файл будет в bin/manager
./bin/manager
```

### Сборка Docker образа

```bash
# Сборка образа
make docker-build IMG=your-registry/dataflow-operator:v1.0.0

# Отправка образа
make docker-push IMG=your-registry/dataflow-operator:v1.0.0
```

Или вручную:

```bash
docker build -t your-registry/dataflow-operator:v1.0.0 .
docker push your-registry/dataflow-operator:v1.0.0
```

## Добавление нового коннектора

### 1. Определение типов в API

Добавьте спецификацию в `api/v1/dataflow_types.go`:

```go
// NewConnectorSourceSpec defines new connector source configuration
type NewConnectorSourceSpec struct {
    // Configuration fields
    Endpoint string `json:"endpoint"`
    // ...
}

// Добавьте в SourceSpec
type SourceSpec struct {
    // ...
    NewConnector *NewConnectorSourceSpec `json:"newConnector,omitempty"`
}
```

### 2. Реализация коннектора

Создайте файл `internal/connectors/newconnector.go`:

```go
package connectors

import (
    "context"
    v1 "github.com/dataflow-operator/dataflow/api/v1"
    "github.com/dataflow-operator/dataflow/internal/types"
)

type NewConnectorSourceConnector struct {
    config *v1.NewConnectorSourceSpec
    // connection fields
}

func NewNewConnectorSourceConnector(config *v1.NewConnectorSourceSpec) *NewConnectorSourceConnector {
    return &NewConnectorSourceConnector{config: config}
}

func (n *NewConnectorSourceConnector) Connect(ctx context.Context) error {
    // Implement connection logic
    return nil
}

func (n *NewConnectorSourceConnector) Read(ctx context.Context) (<-chan *types.Message, error) {
    // Implement read logic
    return nil, nil
}

func (n *NewConnectorSourceConnector) Close() error {
    // Implement close logic
    return nil
}
```

### 3. Регистрация в фабрике

Добавьте в `internal/connectors/factory.go`:

```go
func CreateSourceConnector(source *v1.SourceSpec) (SourceConnector, error) {
    switch source.Type {
    // ...
    case "newconnector":
        if source.NewConnector == nil {
            return nil, fmt.Errorf("newconnector source configuration is required")
        }
        return NewNewConnectorSourceConnector(source.NewConnector), nil
    // ...
    }
}
```

### 4. Генерация кода

```bash
make generate
make manifests
```

### 5. Тестирование

Создайте тесты в `internal/connectors/newconnector_test.go`:

```go
func TestNewConnectorSourceConnector(t *testing.T) {
    // Test implementation
}
```

## Добавление новой трансформации

### 1. Определение типов в API

Добавьте в `api/v1/dataflow_types.go`:

```go
// NewTransformation defines new transformation configuration
type NewTransformation struct {
    Field string `json:"field"`
    // ...
}

// Добавьте в TransformationSpec
type TransformationSpec struct {
    // ...
    NewTransformation *NewTransformation `json:"newTransformation,omitempty"`
}
```

### 2. Реализация трансформации

Создайте файл `internal/transformers/newtransformation.go`:

```go
package transformers

import (
    "context"
    v1 "github.com/dataflow-operator/dataflow/api/v1"
    "github.com/dataflow-operator/dataflow/internal/types"
)

type NewTransformer struct {
    config *v1.NewTransformation
}

func NewNewTransformer(config *v1.NewTransformation) *NewTransformer {
    return &NewTransformer{config: config}
}

func (n *NewTransformer) Transform(ctx context.Context, message *types.Message) ([]*types.Message, error) {
    // Implement transformation logic
    return []*types.Message{message}, nil
}
```

### 3. Регистрация в фабрике

Добавьте в `internal/transformers/factory.go`:

```go
func CreateTransformer(transformation *v1.TransformationSpec) (Transformer, error) {
    switch transformation.Type {
    // ...
    case "newtransformation":
        if transformation.NewTransformation == nil {
            return nil, fmt.Errorf("newtransformation configuration is required")
        }
        return NewNewTransformer(transformation.NewTransformation), nil
    // ...
    }
}
```

### 4. Генерация и тестирование

```bash
make generate
make test
```

## Отладка

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
make fmt
```

Или вручную:

```bash
go fmt ./...
```

### Проверка кода

```bash
make vet
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
          go-version: '1.21'
      - run: go mod download
      - run: make test-unit
      - run: make vet
      - run: make fmt
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
4. Убедитесь, что все тесты проходят: `make test`
5. Отформатируйте код: `make fmt`
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
make help

# Очистка сгенерированных файлов
make clean

# Обновление зависимостей
go mod tidy

# Просмотр зависимостей
go list -m all

# Проверка устаревших зависимостей
go list -u -m all
```

## Ресурсы

- [Kubebuilder Book](https://book.kubebuilder.io/) - руководство по созданию Kubernetes операторов
- [controller-runtime](https://github.com/kubernetes-sigs/controller-runtime) - библиотека для контроллеров
- [Go Documentation](https://golang.org/doc/) - документация Go

## Получение помощи

- Создайте issue в репозитории
- Проверьте существующие issues и PR
- Изучите примеры в `config/samples/`

