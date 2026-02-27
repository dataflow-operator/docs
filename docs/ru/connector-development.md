# Разработка коннекторов с baseConnector

Подробное руководство по добавлению нового коннектора в DataFlow Operator с использованием общего паттерна `baseConnector`.

## Обзор

Все коннекторы (ClickHouse, PostgreSQL, Kafka, Trino, Nessie) используют единый паттерн для синхронизации методов `Connect` и `Close`:

- `sync.Mutex` (или `sync.RWMutex`) для защиты состояния
- Флаг `closed` для идемпотентности `Close` и блокировки `Connect` после закрытия
- Одинаковая последовательность: `Lock` → проверка `closed` → логика → `Unlock`

Чтобы избежать дублирования, используется встраиваемый `baseConnector` или `baseConnectorRWMutex`.

## baseConnector и baseConnectorRWMutex

### baseConnector (sync.Mutex)

Используется для большинства коннекторов, где операции чтения не требуют отдельной блокировки.

**Методы:**

| Метод | Описание |
|-------|----------|
| `guardConnect() bool` | Захватывает lock. Возвращает `false`, если коннектор уже закрыт. При `true` вызывающий держит lock и должен вызвать `Unlock()` |
| `guardClose() bool` | Захватывает lock. Возвращает `true`, если уже закрыт (идемпотентность). При `false` устанавливает `closed=true`, вызывающий держит lock |
| `Unlock()` | Освобождает lock |
| `Lock()` | Захватывает lock вручную (для операций вроде `readRows`, где нужна длительная блокировка) |

### baseConnectorRWMutex (sync.RWMutex)

Используется, когда коннектор выполняет длительные операции чтения (например, SQL-запросы), и `Connect`/`Close` не должны блокироваться на время этих операций.

**Дополнительные методы:**

| Метод | Описание |
|-------|----------|
| `RLock()` | Захватывает read lock |
| `RUnlock()` | Освобождает read lock |
| `Closed() bool` | Возвращает `closed` (вызывать только под RLock) |

## Пошаговое руководство: добавление нового коннектора

### Шаг 1. Определение типов в API

Добавьте спецификацию в `api/v1/dataflow_types.go`:

```go
// MyDBSourceSpec defines MyDB source configuration
type MyDBSourceSpec struct {
    ConnectionString string `json:"connectionString"`
    Table            string `json:"table"`
    // ...
}

// В SourceSpec:
type SourceSpec struct {
    // ...
    MyDB *MyDBSourceSpec `json:"myDB,omitempty"`
}
```

### Шаг 2. Выбор baseConnector или baseConnectorRWMutex

**Используйте `baseConnector`**, если:

- Коннектор не выполняет длительные операции чтения под lock
- Или операции чтения модифицируют состояние (например, `lastReadID`) и требуют полной блокировки

**Используйте `baseConnectorRWMutex`**, если:

- Коннектор выполняет длительные read-операции (запросы к БД)
- Эти операции только читают `conn` и `closed`, не модифицируют их
- Нужно, чтобы `Connect`/`Close` не блокировались на время запроса

### Шаг 3. Реализация Source-коннектора

#### С baseConnector (простой случай)

```go
// internal/connectors/mydb.go

package connectors

import (
    "context"
    "fmt"
    v1 "github.com/dataflow-operator/dataflow/api/v1"
    "github.com/dataflow-operator/dataflow/internal/types"
    "github.com/go-logr/logr"
)

type MyDBSourceConnector struct {
    baseConnector
    config *v1.MyDBSourceSpec
    conn   *MyDBConnection
    logger logr.Logger
}

func NewMyDBSourceConnector(config *v1.MyDBSourceSpec) *MyDBSourceConnector {
    return &MyDBSourceConnector{
        config: config,
        logger: logr.Discard(),
    }
}

func (c *MyDBSourceConnector) SetLogger(logger logr.Logger) {
    c.logger = logger
}

func (c *MyDBSourceConnector) Connect(ctx context.Context) error {
    if !c.guardConnect() {
        return fmt.Errorf("connector is closed")
    }
    defer c.Unlock()

    c.logger.Info("Connecting to MyDB", "table", c.config.Table)
    conn, err := connectToMyDB(ctx, c.config.ConnectionString)
    if err != nil {
        return fmt.Errorf("failed to connect: %w", err)
    }
    c.conn = conn
    c.logger.Info("Successfully connected to MyDB", "table", c.config.Table)
    return nil
}

func (c *MyDBSourceConnector) Read(ctx context.Context) (<-chan *types.Message, error) {
    if c.conn == nil {
        return nil, fmt.Errorf("not connected, call Connect first")
    }
    // ... реализация чтения
    return msgChan, nil
}

func (c *MyDBSourceConnector) Close() error {
    if c.guardClose() {
        return nil
    }
    defer c.Unlock()

    c.logger.Info("Closing MyDB source connection", "table", c.config.Table)
    if c.conn != nil {
        return c.conn.Close()
    }
    return nil
}
```

#### С baseConnectorRWMutex (длительные read-операции)

Если `readRows` выполняет долгий запрос и не должен блокировать `Connect`/`Close`:

```go
type MyDBSourceConnector struct {
    baseConnectorRWMutex
    config *v1.MyDBSourceSpec
    conn   *MyDBConnection
    logger logr.Logger
}

func (c *MyDBSourceConnector) readRows(ctx context.Context, msgChan chan *types.Message) {
    // RLock — не блокирует Connect/Close
    c.RLock()
    if c.Closed() {
        c.RUnlock()
        return
    }
    conn := c.conn
    c.RUnlock()

    if conn == nil {
        return
    }

    // Долгий запрос выполняется БЕЗ удержания lock
    rows, err := conn.QueryContext(ctx, "SELECT * FROM ...")
    // ...
}
```

### Шаг 4. Реализация Sink-коннектора

```go
type MyDBSinkConnector struct {
    baseConnector
    config *v1.MyDBSinkSpec
    conn   *MyDBConnection
    logger logr.Logger
}

func (c *MyDBSinkConnector) Connect(ctx context.Context) error {
    if !c.guardConnect() {
        return fmt.Errorf("connector is closed")
    }
    defer c.Unlock()

    c.logger.Info("Connecting to MyDB", "table", c.config.Table)
    conn, err := connectToMyDB(ctx, c.config.ConnectionString)
    if err != nil {
        return fmt.Errorf("failed to connect: %w", err)
    }
    c.conn = conn
    return nil
}

func (c *MyDBSinkConnector) Write(ctx context.Context, messages <-chan *types.Message) error {
    // ... реализация записи
}

func (c *MyDBSinkConnector) Close() error {
    if c.guardClose() {
        return nil
    }
    defer c.Unlock()

    c.logger.Info("Closing MyDB sink connection", "table", c.config.Table)
    if c.conn != nil {
        return c.conn.Close()
    }
    return nil
}
```

### Шаг 5. Поддержка rawMode (опционально)

Для source-коннекторов можно добавить режим сырой записи — обёртку данных в `{"value": ..., "_metadata": {...}}`:

1. Добавьте в spec поле `RawMode *bool` с тегом `json:"rawMode,omitempty"`
2. При формировании сообщения проверяйте `config.RawMode != nil && *config.RawMode`
3. Используйте `buildRawModeJSON(value, metadata)` из пакета `connectors` для формирования JSON

Пример (PostgreSQL, ClickHouse, Trino, Nessie):
```go
if p.config.RawMode != nil && *p.config.RawMode {
    metadata := map[string]interface{}{"table": p.config.Table}
    if idIndex >= 0 { metadata["id"] = values[idIndex] }
    jsonData, err = buildRawModeJSON(rowMap, metadata)
}
```

### Шаг 6. Регистрация в фабрике

В `internal/connectors/factory.go`:

```go
func CreateSourceConnector(source *v1.SourceSpec) (SourceConnector, error) {
    switch source.Type {
    // ...
    case "mydb":
        if source.MyDB == nil {
            return nil, fmt.Errorf("mydb source configuration is required")
        }
        return NewMyDBSourceConnector(source.MyDB), nil
    default:
        return nil, fmt.Errorf("unknown source type: %s", source.Type)
    }
}

func CreateSinkConnector(sink *v1.SinkSpec) (SinkConnector, error) {
    switch sink.Type {
    // ...
    case "mydb":
        if sink.MyDB == nil {
            return nil, fmt.Errorf("mydb sink configuration is required")
        }
        return NewMyDBSinkConnector(sink.MyDB), nil
    default:
        return nil, fmt.Errorf("unknown sink type: %s", sink.Type)
    }
}
```

### Шаг 7. Генерация и тестирование

```bash
make generate
make manifests
make test-unit
```

## Важные замечания

### Порядок вызовов в Connect

```go
if !c.guardConnect() {
    return fmt.Errorf("connector is closed")
}
defer c.Unlock()
// ... логика подключения
```

- `guardConnect()` возвращает `false` → коннектор закрыт, вызываем `return`
- `guardConnect()` возвращает `true` → держим lock, обязательно `defer c.Unlock()`

### Порядок вызовов в Close

```go
if c.guardClose() {
    return nil  // уже закрыт, идемпотентность
}
defer c.Unlock()
// ... закрытие соединения
```

- `guardClose()` возвращает `true` → уже закрыт, возвращаем `nil`
- `guardClose()` возвращает `false` → устанавливаем `closed=true`, держим lock, закрываем ресурсы

### Использование Lock() для readRows

Если `readRows` модифицирует состояние коннектора (например, `lastReadID`) и требует эксклюзивного доступа:

```go
func (p *PostgreSQLSourceConnector) readRows(ctx context.Context, msgChan chan *types.Message) {
    p.Lock()
    defer p.Unlock()
    // ... чтение и обновление lastReadID
}
```

### Тестирование

Обязательно добавьте тесты:

- `Close` при уже закрытом коннекторе (идемпотентность)
- `Connect` после `Close` (должен возвращать ошибку)
- Создание коннектора и проверка начального состояния

```go
func TestMyDBSourceConnector_Close_WhenAlreadyClosed(t *testing.T) {
    conn := NewMyDBSourceConnector(spec)
    conn.SetLogger(logr.Discard())
    require.NoError(t, conn.Close())
    require.NoError(t, conn.Close()) // второй вызов — без ошибки
}

func TestMyDBSourceConnector_Connect_WhenClosed(t *testing.T) {
    conn := NewMyDBSourceConnector(spec)
    conn.SetLogger(logr.Discard())
    conn.closed = true
    err := conn.Connect(context.Background())
    require.Error(t, err)
    assert.Contains(t, err.Error(), "closed")
}
```

## Ссылки

- [Добавление нового коннектора](development.md#добавление-нового-коннектора) — общий раздел в руководстве по разработке
- [Интерфейсы коннекторов](https://github.com/dataflow-operator/dataflow/blob/main/internal/connectors/interface.go) — `SourceConnector` и `SinkConnector`
- [baseConnector](https://github.com/dataflow-operator/dataflow/blob/main/internal/connectors/base.go) — исходный код
