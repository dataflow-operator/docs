# Справочник Helm values

Полный справочник values чарта `dataflow-operator`. Источник правды: [`values.yaml`](https://github.com/dataflow-operator/helm-charts/blob/main/charts/dataflow-operator/values.yaml) в репозитории helm-charts (в монорепо — `helm-charts/charts/dataflow-operator/`).

**Когда читать:** настройка установки сверх дефолтов Getting Started — образы, webhook, GUI, Prometheus, Sentry, жизненный цикл CRD.

**См. также:** [Начало работы](getting-started.md) · [Web GUI](gui.md) · [Метрики](metrics.md) · [Разработка](development.md) (уровни логов, TLS webhook)

## Установка / обновление

```bash
helm install dataflow-operator oci://ghcr.io/dataflow-operator/helm-charts/dataflow-operator \
  -f my-values.yaml

helm upgrade dataflow-operator oci://ghcr.io/dataflow-operator/helm-charts/dataflow-operator \
  -f my-values.yaml
```

`appVersion` чарта задаёт тег образа оператора по умолчанию, если `image.tag` не указан.

---

## CRD

| Параметр | Описание | По умолчанию |
|----------|----------|--------------|
| `crds.install` | Устанавливать/обновлять CRD (`DataFlow`, `DataFlowCron`) при `helm install` / `helm upgrade` | `true` |
| `crds.keep` | Аннотация `helm.sh/resource-policy: keep` — CRD остаются после `helm uninstall` | `true` |

Удаление CRD удаляет все ресурсы DataFlow / DataFlowCron. В проде оставляйте `crds.keep: true`.

---

## Workload оператора

| Параметр | Описание | По умолчанию |
|----------|----------|--------------|
| `replicaCount` | Реплики Deployment оператора (leader election при > 1) | `1` |
| `image.repository` | Образ оператора | `ghcr.io/dataflow-operator/dataflow` |
| `image.pullPolicy` | Политика загрузки образа | `IfNotPresent` |
| `image.tag` | Тег образа (по умолчанию — `appVersion` чарта) | `appVersion` чарта |
| `processorImage` | Образ процессора. Пусто → `ghcr.io/dataflow-operator/dataflow-processor` с тем же тегом, что у оператора | `""` |
| `imagePullSecrets` | Secrets для pull образов | `[]` |
| `nameOverride` | Переопределение имени чарта в именах ресурсов | `""` |
| `fullnameOverride` | Переопределение полного префикса имён | `""` |
| `podAnnotations` | Аннотации пода оператора | `{}` |
| `podSecurityContext` | Security context пода | `{}` |
| `securityContext` | Security context контейнера | `{}` |
| `resources.limits.cpu` | Лимит CPU | `500m` |
| `resources.limits.memory` | Лимит памяти | `512Mi` |
| `resources.requests.cpu` | Запрос CPU | `100m` |
| `resources.requests.memory` | Запрос памяти | `128Mi` |
| `nodeSelector` | Node selector | `{}` |
| `tolerations` | Tolerations | `[]` |
| `affinity` | Affinity | `{}` |

---

## ServiceAccount и RBAC

| Параметр | Описание | По умолчанию |
|----------|----------|--------------|
| `serviceAccount.create` | Создать ServiceAccount оператора | `true` |
| `serviceAccount.annotations` | Аннотации (например IRSA role ARN) | `{}` |
| `serviceAccount.name` | Имя существующего SA; пусто → сгенерированное | `""` |
| `rbac.create` | Создать ClusterRole / ClusterRoleBinding (включая права для checkpoint persistence) | `true` |

---

## Логирование и runtime процессора

| Параметр | Описание | По умолчанию |
|----------|----------|--------------|
| `logLevel` | `LOG_LEVEL` оператора: `debug`, `info`, `warn`, `error` | `info` |
| `processorLogLevel` | Передаётся в каждый под процессора как `LOG_LEVEL` | `info` |
| `processorProgressTimeoutSeconds` | Таймаут progress для `/livez` процессора (секунды). Низкотрафиковый Kafka нуждается в запасе сверх batch interval | `3600` |

---

## Метрики, health и Service

| Параметр | Описание | По умолчанию |
|----------|----------|--------------|
| `metrics.enabled` | Отдавать метрики Prometheus | `true` |
| `metrics.port` | Порт метрик | `9090` |
| `health.probePort` | Порт health probe | `9091` |
| `service.type` | Тип Kubernetes Service | `ClusterIP` |
| `service.port` | Порт Service (метрики) | `9090` |

---

## Validating webhook

| Параметр | Описание | По умолчанию |
|----------|----------|--------------|
| `webhook.enabled` | Включить admission webhook для DataFlow | `false` |
| `webhook.caBundle` | Base64 PEM CA bundle для ValidatingWebhookConfiguration (нужен вместе с `enabled`) | `""` |
| `webhook.certDir` | Путь монтирования TLS-сертификатов в контейнере оператора | `""` |
| `webhook.secretName` | Secret с `tls.crt` / `tls.key` | `""` |

ValidatingWebhookConfiguration создаётся только когда заданы и `webhook.enabled`, и `webhook.caBundle` (или CA инжектится, например cert-manager). См. [Разработка](development.md).

---

## Sentry

| Параметр | Описание | По умолчанию |
|----------|----------|--------------|
| `sentry.enabled` | Отправлять ошибки/трейсы с оператора и процессоров | `false` |
| `sentry.dsn` | DSN Sentry (обязателен при `enabled`) | `""` |
| `sentry.environment` | Имя окружения | `production` |
| `sentry.tracesSampleRate` | Sample rate трейсов `0.0`–`1.0` | `0.1` |
| `sentry.debug` | Debug-вывод SDK Sentry | `false` |
| `sentry.release` | Строка release (git commit или appVersion чарта) | `""` |

---

## ServiceMonitor и monitoring

| Параметр | Описание | По умолчанию |
|----------|----------|--------------|
| `serviceMonitor.enabled` | Создать ServiceMonitor для Prometheus Operator | `false` |
| `serviceMonitor.interval` | Интервал scrape | `30s` |
| `serviceMonitor.scrapeTimeout` | Таймаут scrape | `10s` |
| `serviceMonitor.additionalLabels` | Labels для `serviceMonitorSelector` Prometheus (напр. `release: kube-prometheus-stack`) | `{}` |
| `monitoring.dashboard.enabled` | Установить Grafana dashboard ConfigMap (`grafana_dashboard: "1"`) | `false` |
| `monitoring.dashboard.folder` | Папка Grafana (annotation) | `DataFlow` |
| `monitoring.prometheusRule.enabled` | Установить PrometheusRule с алертами | `false` |
| `monitoring.prometheusRule.additionalLabels` | Labels для `ruleSelector` Prometheus | `{}` |

Пример с kube-prometheus-stack:

```bash
helm upgrade --install dataflow-operator oci://ghcr.io/dataflow-operator/helm-charts/dataflow-operator \
  --set serviceMonitor.enabled=true \
  --set serviceMonitor.additionalLabels.release=kube-prometheus-stack \
  --set monitoring.prometheusRule.enabled=true \
  --set monitoring.prometheusRule.additionalLabels.release=kube-prometheus-stack \
  --set monitoring.dashboard.enabled=true
```

---

## Web GUI (`gui.*`)

Подробности: [Web GUI](gui.md). Кратко по ключам чарта:

| Параметр | Описание | По умолчанию |
|----------|----------|--------------|
| `gui.enabled` | Развернуть dataflow-web | `false` |
| `gui.image.repository` | Образ GUI | `ghcr.io/dataflow-operator/dataflow-web` |
| `gui.image.tag` | Тег образа GUI | default чарта (см. `values.yaml`) |
| `gui.image.pullPolicy` | Политика pull | `IfNotPresent` |
| `gui.replicaCount` | Реплики GUI | `1` |
| `gui.port` | Порт | `8080` |
| `gui.logLevel` | `debug` / `info` / `warn` / `error`; пусто → default сервера | `""` |
| `gui.extraEnv` | Доп. переменные окружения | `[]` |
| `gui.prometheus.url` | Base URL Prometheus для исторических графиков | `""` |
| `gui.prometheus.bearerTokenSecret.name` | Имя Secret с bearer token | `""` |
| `gui.prometheus.bearerTokenSecret.key` | Ключ в Secret | `token` |
| `gui.resources` | Requests/limits | `{}` |
| `gui.serviceAccount.create` | Отдельный least-privilege SA для GUI | `true` |
| `gui.serviceAccount.name` | Существующий SA; если задан — чарт не создаёт SA/RBAC GUI | `""` |
| `gui.ingress.enabled` | Открыть GUI через Ingress | `false` |
| `gui.ingress.className` | Ingress class | `""` |
| `gui.ingress.annotations` | Аннотации Ingress | `{}` |
| `gui.ingress.hosts` | Хосты и пути | см. `values.yaml` |
| `gui.ingress.tls` | TLS secrets | `[]` |

---

## Пример production-фрагмента

```yaml
replicaCount: 2

image:
  tag: "1.9.0"

logLevel: info
processorLogLevel: info

webhook:
  enabled: true
  certDir: /tmp/k8s-webhook-server/serving-certs
  secretName: dataflow-operator-webhook-cert
  # caBundle: оставьте пустым, если CA инжектит cert-manager

gui:
  enabled: true
  serviceAccount:
    create: true
  ingress:
    enabled: true
    className: nginx
    hosts:
      - host: dataflow.example.com
        paths:
          - path: /
            pathType: Prefix

serviceMonitor:
  enabled: true
  additionalLabels:
    release: kube-prometheus-stack

monitoring:
  dashboard:
    enabled: true
  prometheusRule:
    enabled: true
    additionalLabels:
      release: kube-prometheus-stack
```
