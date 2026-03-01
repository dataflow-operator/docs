# Web GUI (dataflow-web)

Веб-интерфейс для управления DataFlow через браузер без необходимости использовать `kubectl` или редактировать YAML вручную.

## Как это устроено

GUI состоит из двух частей:

1. **Backend (Go)** — сервер в составе `dataflow-web`, который:
   - подключается к кластеру Kubernetes (in-cluster или по `KUBECONFIG`);
   - отдаёт REST API по префиксу `/api`;
   - раздаёт статику собранного фронтенда (SPA) для путей вида `/`, `/manifests`, `/logs` и т.д.

2. **Frontend (Vue 3 + Vite)** — одностраничное приложение, которое:
   - обращается к backend по `/api` (или по настроенному `VITE_API_BASE` при сборке);
   - отображает дашборд, список манифестов, логи и метрики;
   - поддерживает смену языка (русский/английский) и темы (светлая/тёмная).

Запросы к API идут через тот же хост, что и интерфейс (например, при открытии GUI в браузере все вызовы уходят на тот же адрес). Backend по запросу обращается к Kubernetes API и возвращает данные в JSON.

## Возможности GUI

### Дашборд

- Сводка по всем namespace: общее число DataFlow, разбивка по фазам (Running, Pending, Error, Stopped).
- Список namespace с количеством потоков в каждом и быстрым переходом к манифестам выбранного namespace.

### Манифесты (DataFlow)

- **Список** DataFlow в выбранном namespace с отображением имени, статуса (phase), счётчиков обработанных сообщений и ошибок.
- **Поиск** по имени манифеста.
- **Создание** нового DataFlow: кнопка «Создать новый» открывает модальное окно с YAML-редактором и шаблоном манифеста (source, sink, transformations).
- **Редактирование**: просмотр и изменение существующего DataFlow в YAML (сохранение через PUT в API).
- **Удаление** DataFlow с подтверждением.

Переключение namespace выполняется через выпадающий список; при необходимости в URL подставляется `?namespace=...`.

### Логи

- Выбор namespace и конкретного DataFlow из списка.
- Настройка количества строк (tail lines) для однократной загрузки.
- **Загрузка логов** — разовый запрос к API, отображение логов в текстовом блоке.
- **Подписка на логи (follow)** — поток логов через Server-Sent Events (SSE), обновление в реальном времени; кнопка «Остановить» отключает подписку.
- Кнопка **Копировать** для копирования текущего текста логов в буфер обмена.

Логи читаются из пода процессора DataFlow (контейнер `processor`), при необходимости — по label'ам `dataflow.dataflow.io/name` или `app=dataflow-processor`.

### Метрики и статус

- Выбор namespace и DataFlow.
- Отображение **статуса** потока: фаза (phase), сообщение (message), количество обработанных сообщений, количество ошибок, время последней обработки.
- Данные берутся из `status` ресурса DataFlow и из эндпоинта `/api/status` (и при необходимости `/api/metrics`).

### Прочее

- **Переключение namespace** — на дашборде, на странице манифестов, логов и метрик доступен выбор namespace; список namespace запрашивается через `/api/namespaces`.
- **Локализация** — интерфейс на русском и английском (vue-i18n).
- **Тема** — светлая и тёмная (переключатель в интерфейсе).

## API backend

Все эндпоинты отдаются в JSON (кроме логов — текст или SSE, и метрик — Prometheus text format при настроенном URL оператора).

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/api/namespaces` | Список namespace кластера |
| GET | `/api/dataflows?namespace=<ns>` | Список DataFlow в namespace |
| GET | `/api/dataflows/<name>?namespace=<ns>` | Один DataFlow |
| POST | `/api/dataflows?namespace=<ns>` | Создать DataFlow (тело — JSON манифест) |
| PUT | `/api/dataflows/<name>?namespace=<ns>` | Обновить spec DataFlow |
| DELETE | `/api/dataflows/<name>?namespace=<ns>` | Удалить DataFlow |
| GET | `/api/logs?namespace=&name=&tailLines=&follow=true\|false` | Логи пода процессора (текст или SSE при `follow=true`) |
| GET | `/api/status?namespace=&name=` | Статус DataFlow (phase, message, processedCount, errorCount, lastProcessedTime) |
| GET | `/api/metrics?namespace=&name=` | Prometheus-метрики по DataFlow (проксируются с оператора при заданном `OPERATOR_METRICS_URL`; иначе — пустая заглушка) |

Для CORS заданы заголовки `Access-Control-Allow-Origin: *`, `Access-Control-Allow-Methods`, `Access-Control-Allow-Headers`, чтобы к API можно было обращаться с другого порта при локальной разработке.

## Запуск

- **В кластере**: развернуть `dataflow-web` (например, через Helm или манифесты). Сервер использует in-cluster конфиг и слушает на указанном `bind-address` (по умолчанию `:8080`).
- **Локально**: из корня репозитория запустить backend и фронтенд отдельно:
  - Backend: `go run ./cmd/server --bind-address=:8080` (при необходимости задать `KUBECONFIG`).
  - Frontend: в `dataflow-web/web` выполнить `npm install && npm run dev`; приложение откроется на http://localhost:5173, запросы к API проксируются на backend (например, 8080).

Подробнее о сборке и структуре фронтенда см. [dataflow-web/web/README.md](../../../dataflow-web/web/README.md).
