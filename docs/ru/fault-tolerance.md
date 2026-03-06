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

### Kafka источник

Consumer Kafka коммитит offset **только после** успешной записи сообщения в sink (через `msg.Ack()`). При падении процессора:

- **До записи в sink**: Offset не закоммичен. При перезапуске сообщение перечитывается. Дубликата в sink нет.
- **После записи в sink, до Ack**: Данные могут быть в sink, offset не закоммичен. При перезапуске перечитывание → дубликат в sink.
- **После Ack**: Offset закоммичен. При перезапуске продолжение со следующего сообщения. Дубликата нет.

### Polling источники (PostgreSQL, ClickHouse, Trino)

По умолчанию позиция чтения (lastReadID, lastReadChangeTime) хранится **только в памяти**. При падении пода:

- Состояние теряется.
- При перезапуске источник перечитывает с начала (или с неверной позиции).
- Возможны **дубликаты** или **пропуски** в зависимости от момента падения.

**Персистенция checkpoint** включена по умолчанию. Позиция сохраняется в ConfigMap. При перезапуске источник возобновляет чтение с последней закоммиченной позиции, уменьшая дубликаты. Задайте `checkpointPersistence: false` в spec, чтобы отключить.

!!! warning "Требуется идемпотентный sink"
    Для polling источников всегда настраивайте **идемпотентный sink** (UPSERT, ReplacingMergeTree) для безопасной обработки дубликатов.

## Поведение batch sink

PostgreSQL, ClickHouse и Trino sink пишут батчами. Последовательность:

1. Накопление сообщений в батч
2. Выполнение `Commit` (транзакция)
3. Вызов `Ack()` для каждого сообщения (коммит Kafka offset, если применимо)

Если процессор падает **между Commit и последним Ack**:

- Данные уже в sink
- Kafka offset может быть не закоммичен
- При перезапуске: перечитывание из Kafka → **дублирование записей в sink**

!!! tip "Уменьшение окна дубликатов"
    Используйте меньший `batchSize`, чтобы сократить число сообщений в зоне риска дублирования при падении.

## Настройка идемпотентного sink

### PostgreSQL sink

Включите режим UPSERT, чтобы дубликаты обновляли существующие строки вместо ошибки:

```yaml
sink:
  type: postgresql
  postgresql:
    connectionString: "postgres://..."
    table: output_table
    upsertMode: true
    conflictKey: ["id"]  # Опционально; по умолчанию PRIMARY KEY
```

Требуется PRIMARY KEY или UNIQUE constraint на колонках конфликта.

### ClickHouse sink

Используйте движок `ReplacingMergeTree` для автоматической дедупликации по колонке версии:

```sql
CREATE TABLE output_table (
  id UInt64,
  data String,
  created_at DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(created_at)
ORDER BY id;
```

Или создайте таблицу с `autoCreateTable: true` и `rawMode: false` — коннектор выводит типы колонок. Для дедупликации создайте таблицу вручную с `ReplacingMergeTree(version_column)` и `ORDER BY` по ключу дедупликации.

### Kafka sink

Producer Kafka использует `RequiredAcks = WaitForAll` и `Producer.Idempotent = true` для надёжности и предотвращения дубликатов при повторной отправке. Consumers по-прежнему должны обрабатывать возможные дубликаты (например, идемпотентной обработкой или дедупликацией по ключу) для end-to-end exactly-once.

## Рекомендации

1. **Используйте идемпотентные sink** для PostgreSQL (UPSERT) и ClickHouse (ReplacingMergeTree) при polling источниках или когда возможны дубликаты.
2. **Kafka источник**: Consumer group хранит offset; at-least-once сохраняется. Рекомендуется идемпотентный sink для batch sink.
3. **batchSize**: Меньшие батчи уменьшают окно дубликатов при падении. Баланс с пропускной способностью.
4. **batchFlushIntervalSeconds**: Меньшие интервалы чаще сбрасывают батч, уменьшая объём данных в зоне риска.
5. **Error sink**: Настройте `spec.errors` для сохранения неудачных сообщений для повторной обработки или анализа.

## Graceful shutdown

При SIGTERM (например, eviction пода, drain ноды):

1. Процессор получает сигнал и отменяет контекст.
2. Sink сбрасывают in-flight батчи перед выходом.
3. `PreStop: sleep 5` даёт время load balancer перестать направлять трафик.

Убедитесь, что `terminationGracePeriodSeconds` достаточен для сброса больших батчей (по умолчанию: 600 секунд).

## Персистенция checkpoint

!!! note "По умолчанию включено"
    Поле `checkpointPersistence` в spec DataFlow по умолчанию равно `true`. Явно указывать его не требуется — персистенция checkpoint включена для всех DataFlow с polling-источниками.

Персистенция checkpoint **включена по умолчанию**. Позиция чтения (lastReadID, lastReadChangeTime) сохраняется в ConfigMap `dataflow-<name>-checkpoint`. При перезапуске процессора polling источники (PostgreSQL, ClickHouse, Trino) возобновляют чтение с последней закоммиченной позиции, уменьшая дубликаты.

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

Контроллер создаёт ConfigMap и RBAC (ServiceAccount, Role, RoleBinding) для процессора. Checkpoint сохраняется с debounce (раз в 30 секунд) и при graceful shutdown.

## Чеклист

| Сценарий | Рекомендация |
|----------|--------------|
| PostgreSQL sink | Включить `upsertMode: true` с PRIMARY KEY или `conflictKey` |
| ClickHouse sink | Использовать `ReplacingMergeTree` с `ORDER BY` по ключу дедупликации |
| Kafka источник | Consumer group сохраняет offset; рекомендуется идемпотентный sink |
| Polling источники | **Всегда** использовать идемпотентный sink; checkpoint persistence включён по умолчанию |
| batchSize | Рассмотреть меньшие значения для уменьшения окна дубликатов |
