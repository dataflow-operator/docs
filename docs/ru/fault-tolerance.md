# Отказоустойчивость и консистентность данных

DataFlow Operator обрабатывает сообщения с семантикой **at-least-once** (минимум один раз). При падении или перезапуске пода процессора некоторые сообщения могут быть прочитаны и записаны повторно. В этом документе описано поведение, риски рассинхрона данных и настройка идемпотентных sink для предотвращения дубликатов.

## Семантика доставки

- **At-least-once**: Каждое сообщение доставляется минимум один раз. Дубликаты возможны при перезапуске или падении процессора.
- **Exactly-once**: Не поддерживается нативно. Используйте идемпотентные sink для достижения effectively-once.

## Поведение источников при перезапуске

| Источник | Хранение состояния | При перезапуске |
|----------|-------------------|-----------------|
| **Kafka** | Consumer group (Kafka) | Продолжает с последнего закоммиченного offset. Без дубликатов, если offset закоммичен после записи в sink. |
| **PostgreSQL** | ConfigMap (по умолчанию); в памяти при `checkpointPersistence: false` | По умолчанию продолжает с последней позиции. Без персистенции: перечитывает с начала. |
| **ClickHouse** | ConfigMap (по умолчанию); в памяти при `checkpointPersistence: false` | По умолчанию продолжает с последней позиции. Без персистенции: перечитывает с начала. |
| **Trino** | ConfigMap (по умолчанию); в памяти при `checkpointPersistence: false` | По умолчанию продолжает с последней позиции. Без персистенции: перечитывает с начала. |
| **Nessie** | ConfigMap при `incrementalBySnapshot: true` и `checkpointPersistence` (по умолчанию) | Инкрементальное чтение по цепочке Iceberg snapshot; без `incrementalBySnapshot` — полный scan на каждом poll (checkpoint не используется). |
| **Iceberg** | ConfigMap при `incrementalBySnapshot: true` и `checkpointPersistence` (по умолчанию) | Как у Nessie; ключ checkpoint — `iceberg`. |

### Горизонтальное масштабирование (`spec.replicas`)

- **Kafka**: можно задать `spec.replicas > 1`. Все поды используют один consumer group; параллелизм ограничен числом **партиций** топика.
- **PostgreSQL, ClickHouse, Trino, Nessie**: `replicas` должен быть `1` (или не задан). Несколько подов с общим checkpoint ConfigMap приведут к **дублированию** данных.
- **DataFlowCron**: `replicas > 1` не поддерживается (один Job процессора на тик расписания).

### Kafka источник

Consumer Kafka помечает offset **только после** успешной записи сообщения в sink (через `msg.Ack()`). При `ackGranularity: message` (см. ниже) offset также сразу коммитится в consumer group.

При падении процессора:

- **До записи в sink**: Offset не закоммичен. При перезапуске сообщение перечитывается. Дубликата в sink нет.
- **После записи в sink, до Ack**: Данные могут быть в sink, offset не закоммичен. При перезапуске перечитывание → дубликат в sink.
- **После Ack**: Offset помечен (и закоммичен при `ackGranularity: message`). При перезапуске продолжение со следующего сообщения. Дубликата нет.

### Nessie источник (инкрементальный режим)

При `source.config.incrementalBySnapshot: true` процессор читает только **новые** Iceberg snapshot с момента последнего `Ack`. Checkpoint (`lastAckedSnapshotID`, `lastAckedSnapshotSequence`) сохраняется в ConfigMap, если включены `snapshotCheckpoints` (по умолчанию) и `spec.checkpointPersistence`.

Подробнее: [nessie-incremental-snapshots-design.md](nessie-incremental-snapshots-design.md).

### Polling источники (PostgreSQL, ClickHouse, Trino)

**Персистенция checkpoint включена по умолчанию.** Позиция чтения (`lastReadChangeTime`, `lastReadOrderByValue`) сохраняется в ConfigMap `df-<name>-checkpoint`. После перезапуска источник продолжает с последней позиции после `Ack` sink. Задайте `checkpointPersistence: false`, чтобы хранить checkpoint только в памяти (теряется при падении пода).

Legacy-ключи (`lastReadID`, `lastReadTime`) мигрируются при загрузке; см. таблицу миграции ниже.

При `checkpointPersistence: false` при падении пода:

- Состояние теряется.
- При перезапуске источник перечитывает с начала (или с неверной позиции).
- Возможны **дубликаты** или **пропуски** в зависимости от момента падения.

**Персистенция checkpoint** включена по умолчанию. Позиция сохраняется в ConfigMap. При перезапуске источник возобновляет чтение с последней закоммиченной позиции, уменьшая дубликаты. Задайте `checkpointPersistence: false` в spec, чтобы отключить.

!!! warning "Требуется идемпотентный sink"
    Для polling источников всегда настраивайте **идемпотентный sink** (UPSERT, ReplacingMergeTree) для безопасной обработки дубликатов.

## Поведение batch sink

PostgreSQL, ClickHouse и Trino sink пишут батчами. Последовательность:

1. Накопление сообщений в батч
2. Выполнение batch-записи (PostgreSQL оборачивает все statements одной транзакцией и коммитит атомарно)
3. Вызов `Ack()` для каждого сообщения батча (коммит Kafka offset / продвижение polling checkpoint)

Если процессор падает **после успешного commit батча, но до Ack**:

- Данные уже в sink
- Позиция источника / checkpoint может быть не продвинута
- При перезапуске: перечитывание → **дублирование записей в sink** (безопасно с идемпотентным sink)

!!! tip "Уменьшение окна дубликатов"
    Задайте `ackGranularity: message` для ack после каждого сообщения (эффективный `batchSize: 1` для batch sink) или уменьшите `batchSize` при `ackGranularity: batch` (по умолчанию).

## Гранулярность ack (`spec.ackGranularity`)

Управляет моментом коммита offset источника относительно записи в sink:

| Значение | Поведение |
|----------|-----------|
| `batch` (по умолчанию) | Batch sink ack'ает все сообщения после успешного flush. Kafka source полагается на auto-commit consumer group после `MarkMessage`. |
| `message` | Каждое сообщение ack'ается сразу после успешной записи. Batch sink сбрасывает по одному сообщению. Kafka source вызывает `Commit()` после каждого mark для быстрой фиксации offset. |

Рекомендуется для **Kafka → batch sink**, когда нужно сузить окно re-read без ручной настройки `batchSize`:

```yaml
spec:
  ackGranularity: message
  sink:
    type: postgresql
    config:
      upsertMode: true
      conflictKey: material_id
```

Kafka sink всегда ack'ает по сообщению независимо от этой настройки.

!!! tip "Длительные INSERT в Trino"
    Для крупных JSON и таблиц Iceberg/Nessie держите `batchSize` небольшим (часто `1`) и задавайте `sink.config.queryTimeoutSeconds` так, чтобы покрыть всё время выполнения запроса (включая polling `nextUri`).
    Таймаут на этапе `nextUri` может произойти уже после старта INSERT в Trino, поэтому повторный запуск может дать дубликаты.

## Настройка идемпотентного sink

### PostgreSQL sink

Включите UPSERT, чтобы дубликаты обновляли существующие строки. Batch-записи выполняются в явной транзакции (всё или ничего за flush).

```yaml
sink:
  type: postgresql
  config:
    connectionString: "postgres://..."
    table: output_table
    upsertMode: true
    conflictKey: id  # Опционально; по умолчанию PRIMARY KEY
    upsertStrategy: ifNewer   # always (по умолчанию) | ifNewer
    upsertVersionColumn: updated_at  # обязательно при upsertStrategy: ifNewer
```

Требуется PRIMARY KEY или UNIQUE на колонках конфликта. При `upsertStrategy: ifNewer` обновление выполняется только если `EXCLUDED.<version> > target.<version>`.

### ClickHouse sink

Включите `upsertMode` для идемпотентной записи через `ReplacingMergeTree` (при автосоздании таблицы этот движок используется при `upsertMode: true`):

```yaml
sink:
  type: clickhouse
  config:
    connectionString: "clickhouse://..."
    table: output_table
    upsertMode: true
    conflictKey: id
    replacingVersionColumn: updated_at
    tableEngine: ReplacingMergeTree
```

Или создайте таблицу вручную:

```sql
CREATE TABLE output_table (
  id UInt64,
  data String,
  created_at DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(created_at)
ORDER BY id;
```

Дубликаты могут быть видны до background merge; для чтения используйте `FINAL` или полагайтесь на merge.

### Trino sink

Для Iceberg-каталогов включите MERGE-based upsert:

```yaml
sink:
  type: trino
  config:
    serverURL: "http://trino:8080"
    catalog: iceberg   # имя каталога должно содержать "iceberg"
    schema: default
    table: output_table
    upsertMode: true
    conflictKey: id
```

При совпадении строка обновляется; `ifNewer` по колонке версии для Trino пока не поддерживается.

### Kafka sink

Producer Kafka использует `RequiredAcks = WaitForAll` и `Producer.Idempotent = true` для надёжности и предотвращения дубликатов при повторной отправке. Consumers по-прежнему должны обрабатывать возможные дубликаты (например, идемпотентной обработкой или дедупликацией по ключу) для end-to-end exactly-once.

## Рекомендации

1. **Используйте идемпотентные sink** для PostgreSQL (UPSERT), ClickHouse (`upsertMode` / ReplacingMergeTree) и Trino Iceberg (MERGE) при polling источниках или когда возможны дубликаты.
2. **Kafka источник**: Consumer group хранит offset; at-least-once сохраняется. Идемпотентный sink для batch sink. `ackGranularity: message` сужает окно re-read.
3. **batchSize** / **ackGranularity**: Меньшие батчи или `ackGranularity: message` уменьшают окно дубликатов. Баланс с throughput.
4. **Migration / cron**: `checkpointSyncOnAck: true`, идемпотентный sink, при наличии колонки версии — `upsertStrategy: ifNewer`.
5. **Trino `queryTimeoutSeconds`**: Таймаут с запасом под пиковую нагрузку.
6. **batchFlushIntervalSeconds**: Меньшие интервалы чаще сбрасывают батч.
7. **Error sink**: Настройте `spec.errors` для неудачных сообщений.

## Graceful shutdown

При SIGTERM (например, eviction пода, drain ноды):

1. Процессор получает сигнал и отменяет контекст.
2. Sink сбрасывают in-flight батчи перед выходом.
3. `PreStop: sleep 5` даёт время load balancer перестать направлять трафик.

Убедитесь, что `terminationGracePeriodSeconds` достаточен для сброса больших батчей (по умолчанию: 600 секунд).

## Персистенция checkpoint

!!! note "По умолчанию включено"
    Поле `checkpointPersistence` в spec DataFlow по умолчанию равно `true`. Явно указывать его не требуется — персистенция checkpoint включена для всех DataFlow с polling-источниками.

Персистенция checkpoint **включена по умолчанию**. Позиция чтения (`lastReadChangeTime`, `lastReadOrderByValue`) сохраняется в ConfigMap `df-<name>-checkpoint`. При перезапуске процессора polling источники (PostgreSQL, ClickHouse, Trino) возобновляют чтение с последней закоммиченной позиции, уменьшая дубликаты.

Канонический JSON checkpoint для каждого типа источника:

```json
{
  "lastReadChangeTime": "2024-06-01T12:00:00.123456789Z",
  "lastReadOrderByValue": 5042
}
```

Legacy-форматы нормализуются при загрузке:

| Legacy | Canonical |
|--------|-----------|
| Trino: `{"lastReadID": 100}` | `{"lastReadOrderByValue": 100}` |
| ClickHouse: `{"lastReadID": 100, "lastReadTime": "..."}` | composite поля выше |
| Только time: `{"lastReadChangeTime": "..."}` | без изменений (одноколоночный WHERE до появления order key) |

После перезапуска checkpoint Trino/ClickHouse только с `lastReadID` использует фильтр по order key (`WHERE orderByColumn > N`) до первого ack с timestamp; затем включается tuple `(changeTrackingColumn, orderByColumn) > (time, key)`.

Чтобы отключить, задайте `checkpointPersistence: false`:

```yaml
apiVersion: dataflow.dataflow.io/v1
kind: DataFlow
metadata:
  name: my-dataflow
spec:
  checkpointPersistence: false  # Отключить (по умолчанию: true)
  source:
    type: postgresql
    # ...
```

Контроллер создаёт ConfigMap и RBAC (ServiceAccount, Role, RoleBinding) для процессора. Checkpoint сохраняется с debounce (по умолчанию раз в 30 секунд) и при graceful shutdown.

### Синхронизация checkpoint при ack (`spec.checkpointSyncOnAck`)

По умолчанию pending checkpoint сбрасывается в ConfigMap по таймеру debounce (`checkpointSaveInterval`, по умолчанию `30s`) и при graceful shutdown. После падения пода polling-источники могут перечитать данные за один интервал debounce.

При `checkpointSyncOnAck: true` checkpoint сбрасывается сразу после ack батча sink (с coalescing, не чаще `checkpointSaveInterval`). Рекомендуется для migration и cron:

```yaml
spec:
  checkpointSyncOnAck: true
  checkpointSaveInterval: 5s
  source:
    type: postgresql
  sink:
    type: postgresql
    config:
      upsertMode: true
      conflictKey: material_id
```

## Сброс checkpoint

Для повторного полного прогона migration/cron без ручного редактирования `df-<name>-checkpoint`:

```yaml
spec:
  checkpointReset: true   # one-shot; контроллер сбрасывает флаг после reconcile
```

Или annotation на DataFlow:

```yaml
metadata:
  annotations:
    dataflow.dataflow.io/reset-checkpoint: "true"
```

Процессор очищает checkpoint для типа источника при старте и читает с начала.

## Strict idempotency (`spec.strictIdempotency`)

При `strictIdempotency: true` admission отклоняет polling-источники с неидемпотентным main sink (без `upsertMode`). По умолчанию (`false`) выдаётся warning.

## Чеклист

| Сценарий | Рекомендация |
|----------|--------------|
| PostgreSQL sink | `upsertMode: true` + `conflictKey`; `upsertStrategy: ifNewer` при колонке версии |
| ClickHouse sink | `upsertMode: true` или ручной `ReplacingMergeTree` + `ORDER BY` |
| Trino sink (Iceberg) | `upsertMode: true` + `conflictKey` |
| Kafka → batch sink | `ackGranularity: message` или меньший `batchSize` + идемпотентный sink |
| Kafka источник | Идемпотентный sink; `ackGranularity: message` для быстрого commit offset |
| Polling источники | Идемпотентный sink; `checkpointSyncOnAck: true` для migration/cron |
| batchSize | Меньшие значения или `ackGranularity: message` |
