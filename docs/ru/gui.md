# Web GUI (dataflow-web)

Веб-интерфейс для управления DataFlow через браузер без необходимости использовать `kubectl` или редактировать YAML вручную.

## Обзор

GUI состоит из двух частей:

1. **Backend (Go)** — сервер в составе `dataflow-web`, который подключается к кластеру Kubernetes (in-cluster или по `KUBECONFIG`), отдаёт REST API по префиксу `/api` и раздаёт статику собранного фронтенда (SPA).

2. **Frontend (Vue 3 + Vite)** — одностраничное приложение, которое обращается к backend по `/api`, отображает дашборд, список манифестов, логи и метрики, поддерживает смену языка (русский/английский) и темы (светлая/тёмная).

Запросы к API идут через тот же хост, что и интерфейс. Backend по запросу обращается к Kubernetes API и возвращает данные в JSON.

## Возможности

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

## Конфигурация

GUI настраивается через Helm values при развёртывании чарта dataflow-operator. Основные параметры:

| Параметр | Описание | По умолчанию |
|----------|----------|--------------|
| `gui.enabled` | Включить веб-интерфейс | `false` |
| `gui.image.repository` | Образ сервера GUI (отдельно от оператора) | `ghcr.io/dataflow-operator/dataflow-web` |
| `gui.image.tag` | Тег образа | `v0.1.0` |
| `gui.image.pullPolicy` | Политика загрузки образа | `IfNotPresent` |
| `gui.replicaCount` | Количество реплик сервера GUI | `1` |
| `gui.port` | Порт для сервера GUI | `8080` |
| `gui.logLevel` | Уровень логирования: `debug`, `info`, `warn`, `error` | (пусто, используется по умолчанию) |
| `gui.extraEnv` | Дополнительные переменные окружения (напр. `KUBECONFIG`, переопределение `OPERATOR_METRICS_URL`) | `[]` |
| `gui.resources` | Лимиты и запросы ресурсов | `{}` |
| `gui.serviceAccount.name` | Отдельный ServiceAccount (если пусто — используется SA оператора) | `""` |

### Ingress

| Параметр | Описание | По умолчанию |
|----------|----------|--------------|
| `gui.ingress.enabled` | Включить Ingress для GUI | `false` |
| `gui.ingress.className` | Имя класса Ingress | `""` |
| `gui.ingress.annotations` | Аннотации Ingress | `{}` |
| `gui.ingress.hosts` | Конфигурация хоста и путей | `[{ host: dataflow-gui.local, paths: [{ path: /, pathType: Prefix }] }]` |
| `gui.ingress.tls` | Конфигурация TLS | `[]` |

### Проксирование метрик

GUI проксирует метрики Prometheus с оператора, когда задан `OPERATOR_METRICS_URL`. В Helm это настраивается автоматически на сервис оператора в том же release. Если оператор работает в другом namespace, переопределите через `gui.extraEnv`:

```yaml
gui:
  extraEnv:
    - name: OPERATOR_METRICS_URL
      value: "http://dataflow-operator.dataflow-system:9090/metrics"
```

## Развёртывание

### В кластере (Helm)

Включите GUI при установке или обновлении оператора:

```bash
helm install dataflow-operator oci://ghcr.io/dataflow-operator/helm-charts/dataflow-operator \
  --set gui.enabled=true
```

С Ingress (например, nginx):

```yaml
# custom-values.yaml
gui:
  enabled: true
  ingress:
    enabled: true
    className: nginx
    hosts:
      - host: dataflow.example.com
        paths:
          - path: /
            pathType: Prefix
```

```bash
helm install dataflow-operator oci://ghcr.io/dataflow-operator/helm-charts/dataflow-operator -f custom-values.yaml
```

Доступ к GUI — через Service (port-forward) или URL Ingress.

### Port-forward (быстрый доступ)

Без Ingress используйте port-forward:

```bash
kubectl port-forward svc/dataflow-operator-gui 8080:8080 -n <namespace>
```

Откройте http://localhost:8080 в браузере.

### Локальная разработка

Запустите backend и frontend отдельно из каталога `dataflow-web`:

- **Backend**: `go run ./cmd/server --bind-address=:8080` (при необходимости задать `KUBECONFIG`).
- **Frontend**: в `dataflow-web/web` выполнить `npm install && npm run dev`; приложение откроется на http://localhost:5173, запросы к API проксируются на backend (порт 8080).

Подробнее о сборке и структуре фронтенда см. [dataflow-web/README.md](../../../dataflow-web/README.md).

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
| GET | `/api/metrics?namespace=&name=` | Prometheus-метрики (проксируются с оператора при заданном `OPERATOR_METRICS_URL`) |

Для CORS заданы заголовки, чтобы к API можно было обращаться с другого порта при локальной разработке.
