# Заметки по дизайну: инкрементальное чтение Nessie по snapshot

Документ описывает опциональный режим инкрементального чтения для `nessie` source, чтобы не делать полный re-scan таблицы на каждом poll.

## Проблема

Текущее поведение `nessie` source:

- на каждом poll выполняется `Refresh` + полный `Scan().ToArrowTable`;
- уже выгруженные строки могут читаться повторно;
- для крупных Iceberg-таблиц это даёт лишнюю нагрузку и дубликаты.

Для append-heavy сценариев нужен режим "читать только новые snapshot".

## Цели

- Сохранить текущее поведение по умолчанию (без breaking changes).
- Добавить opt-in режим инкрементального чтения по Iceberg snapshot.
- Сохранять прогресс в существующем checkpoint store, чтобы переживать рестарты.
- Сохранить семантику at-least-once (продвижение checkpoint только после `Ack` sink-а).

## Не цели

- Exactly-once между source и sink.
- Полноценный row-level diff/CDC для update/delete в v1.
- Переработка write-path у Nessie sink.

## Предложение по API

Добавить в `NessieSourceSpec` опциональные поля:

- `incrementalBySnapshot` (`bool`, default `false`)  
  Включает инкрементальное чтение по цепочке snapshot.
- `startSnapshotID` (`string`, optional)  
  Стартовая точка для первого запуска при пустом checkpoint.
- `snapshotCheckpoints` (`bool`, default `true`)  
  Сохранять прогресс snapshot в checkpoint store.

Формат checkpoint (JSON):

```json
{
  "lastAckedSnapshotID": "1234567890123456789",
  "lastAckedSnapshotSequence": 42,
  "branch": "main",
  "namespace": "demo",
  "table": "events"
}
```

### Примеры конфигурации

Минимальный opt-in для инкрементального чтения:

```yaml
apiVersion: dataflow.oss.io/v1
kind: DataFlow
metadata:
  name: nessie-incremental-basic
spec:
  source:
    type: nessie
    config:
      baseURL: http://nessie:19120
      branch: main
      namespace: demo
      table: events
      incrementalBySnapshot: true
      pollInterval: 10
  sink:
    type: kafka
    config:
      brokers: ["kafka:9092"]
      topic: demo-events
```

Старт с заданного snapshot при первом запуске:

```yaml
apiVersion: dataflow.oss.io/v1
kind: DataFlow
metadata:
  name: nessie-incremental-from-snapshot
spec:
  source:
    type: nessie
    config:
      baseURL: http://nessie:19120
      branch: main
      namespace: demo
      table: events
      incrementalBySnapshot: true
      startSnapshotID: "1234567890123456789"
      snapshotCheckpoints: true
      pollInterval: 15
  sink:
    type: kafka
    config:
      brokers: ["kafka:9092"]
      topic: demo-events
```

## Модель чтения

### Обнаружение snapshot

На каждом poll:

1. `tbl.Refresh(ctx)`;
2. чтение metadata таблицы и текущего snapshot;
3. построение упорядоченной цепочки snapshot от `lastAckedSnapshotID` (exclusive) до текущего (inclusive);
4. если цепочка пустая: сразу выходим.

### Извлечение данных

Для каждого snapshot в порядке цепочки:

1. создать scan, ограниченный конкретным snapshot;
2. материализовать строки в Arrow;
3. отправить сообщения с metadata:
   - `snapshot_id`
   - `snapshot_sequence`
   - `namespace`
   - `table`
4. добавить `Ack` callback, который двигает in-memory checkpoint candidate.

### Фиксация checkpoint

- persisted checkpoint обновляется только на `Ack`;
- checkpoint обязан двигаться монотонно по `snapshot_sequence`;
- если sink упал до `Ack`, snapshot читается повторно (допустимо для at-least-once).

## Сбои и edge cases

- **Force-reset ветки / переписанная история**: если `lastAckedSnapshotID` не найден в lineage, логируем warning и:
  - стратегия по умолчанию: стартовать с `startSnapshotID` (если задан), иначе с текущей головы (без исторического backfill).
- **В таблице ещё нет snapshot**: poll без данных.
- **Крупный snapshot**: использовать текущий Arrow-to-message pipeline, с корректной отменой через context.
- **Checkpoint отключён**: инкрементальный режим работает только в пределах жизни процесса.

## Правила валидации

Если `incrementalBySnapshot=true`:

- `query` в v1 запрещается (пока не объединяем snapshot scan и predicate pushdown).
- `startSnapshotID` должен парситься как строка с unsigned integer.

## Совместимость и регистрация provider

- для source `nessie` включить `SupportsCheckpoint=true`;
- при `incrementalBySnapshot=false` оставить текущий full-scan путь;
- `nessie` sink не требует изменений.

## План реализации

1. Расширить `NessieSourceSpec` и валидацию.
2. Добавить обработку checkpoint в `NewNessieSourceConnectorWithOptions`.
3. Ввести struct состояния snapshot + helper-ы marshal/unmarshal.
4. Реализовать построение snapshot-chain и per-snapshot scan loop.
5. Добавить `Ack`-driven продвижение checkpoint.
6. Покрыть тестами (unit + интеграционные с mock progression snapshot).

## План тестирования

- **Unit**
  - парсинг/валидация `startSnapshotID`;
  - encode/decode checkpoint и монотонное продвижение;
  - resolver lineage для линейной истории, отсутствующего базового snapshot, пустой цепочки.
- **Поведение коннектора**
  - `incrementalBySnapshot=false` сохраняет текущий full scan;
  - `incrementalBySnapshot=true` выдаёт только snapshot новее checkpoint;
  - checkpoint обновляется только после `Ack`.
- **Regression**
  - factory/options не ломают старое поведение без checkpoint.

## Выкатка

- выпуск под opt-in флагом (`incrementalBySnapshot`);
- наблюдение за duplicate-rate и объёмом source read;
- в следующей фазе можно добавить delete/update semantics и predicate pushdown.
