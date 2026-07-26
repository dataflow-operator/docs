# Helm Values Reference

Full reference for `dataflow-operator` chart values. Source of truth: [`values.yaml`](https://github.com/dataflow-operator/helm-charts/blob/main/charts/dataflow-operator/values.yaml) in the helm-charts repo (mirrored under `helm-charts/charts/dataflow-operator/` in the monorepo).

**When to read this:** tuning install beyond Getting Started defaults — images, webhook, GUI, Prometheus, Sentry, CRD lifecycle.

**See also:** [Getting Started](getting-started.md) · [Web GUI](gui.md) · [Metrics](metrics.md) · [Development](development.md) (log levels, webhook TLS)

## Install / upgrade

```bash
helm install dataflow-operator oci://ghcr.io/dataflow-operator/helm-charts/dataflow-operator \
  -f my-values.yaml

helm upgrade dataflow-operator oci://ghcr.io/dataflow-operator/helm-charts/dataflow-operator \
  -f my-values.yaml
```

Chart `appVersion` pins the default operator image tag when `image.tag` is unset.

---

## CRDs

| Parameter | Description | Default |
|-----------|-------------|---------|
| `crds.install` | Install/update CRDs (`DataFlow`, `DataFlowCron`) on `helm install` / `helm upgrade` | `true` |
| `crds.keep` | Annotate CRDs with `helm.sh/resource-policy: keep` so they survive `helm uninstall` | `true` |

Deleting CRDs removes all DataFlow / DataFlowCron resources. Keep `crds.keep: true` in production.

---

## Operator workload

| Parameter | Description | Default |
|-----------|-------------|---------|
| `replicaCount` | Operator Deployment replicas (leader election when > 1) | `1` |
| `image.repository` | Operator image | `ghcr.io/dataflow-operator/dataflow` |
| `image.pullPolicy` | Image pull policy | `IfNotPresent` |
| `image.tag` | Operator image tag (defaults to chart `appVersion`) | chart `appVersion` |
| `processorImage` | Processor pod image. Empty → `ghcr.io/dataflow-operator/dataflow-processor` with the same tag as the operator | `""` |
| `imagePullSecrets` | Pull secrets for operator/processor images | `[]` |
| `nameOverride` | Override chart name used in resource names | `""` |
| `fullnameOverride` | Override full resource name prefix | `""` |
| `podAnnotations` | Annotations on the operator pod | `{}` |
| `podSecurityContext` | Pod-level security context | `{}` |
| `securityContext` | Container security context | `{}` |
| `resources.limits.cpu` | CPU limit | `500m` |
| `resources.limits.memory` | Memory limit | `512Mi` |
| `resources.requests.cpu` | CPU request | `100m` |
| `resources.requests.memory` | Memory request | `128Mi` |
| `nodeSelector` | Node selector | `{}` |
| `tolerations` | Tolerations | `[]` |
| `affinity` | Affinity | `{}` |

---

## ServiceAccount and RBAC

| Parameter | Description | Default |
|-----------|-------------|---------|
| `serviceAccount.create` | Create a ServiceAccount for the operator | `true` |
| `serviceAccount.annotations` | Annotations (e.g. IRSA role ARN) | `{}` |
| `serviceAccount.name` | Existing SA name; empty → generated name | `""` |
| `rbac.create` | Create ClusterRole / ClusterRoleBinding (includes checkpoint persistence permissions) | `true` |

---

## Logging and processor runtime

| Parameter | Description | Default |
|-----------|-------------|---------|
| `logLevel` | Operator `LOG_LEVEL`: `debug`, `info`, `warn`, `error` | `info` |
| `processorLogLevel` | Passed to each processor pod as `LOG_LEVEL` | `info` |
| `processorProgressTimeoutSeconds` | Processor `/livez` progress timeout (seconds). Low-traffic Kafka needs headroom beyond batch interval | `3600` |

---

## Metrics, health, and service

| Parameter | Description | Default |
|-----------|-------------|---------|
| `metrics.enabled` | Expose Prometheus metrics | `true` |
| `metrics.port` | Metrics bind port | `9090` |
| `health.probePort` | Health probe port | `9091` |
| `service.type` | Kubernetes Service type | `ClusterIP` |
| `service.port` | Service port (metrics) | `9090` |

---

## Validating webhook

| Parameter | Description | Default |
|-----------|-------------|---------|
| `webhook.enabled` | Enable admission webhook for DataFlow specs | `false` |
| `webhook.caBundle` | Base64 PEM CA bundle for ValidatingWebhookConfiguration (required with `enabled`) | `""` |
| `webhook.certDir` | Mount path for TLS certs in the operator container | `""` |
| `webhook.secretName` | Secret with `tls.crt` / `tls.key` | `""` |

ValidatingWebhookConfiguration is created only when both `webhook.enabled` and `webhook.caBundle` are set (or CA is injected, e.g. by cert-manager). See [Development](development.md).

---

## Sentry

| Parameter | Description | Default |
|-----------|-------------|---------|
| `sentry.enabled` | Report errors/traces from operator and processors | `false` |
| `sentry.dsn` | Sentry DSN (required when enabled) | `""` |
| `sentry.environment` | Environment name | `production` |
| `sentry.tracesSampleRate` | Traces sample rate `0.0`–`1.0` | `0.1` |
| `sentry.debug` | Sentry SDK debug output | `false` |
| `sentry.release` | Release string (git commit or chart appVersion) | `""` |

---

## ServiceMonitor and monitoring

| Parameter | Description | Default |
|-----------|-------------|---------|
| `serviceMonitor.enabled` | Create ServiceMonitor for Prometheus Operator | `false` |
| `serviceMonitor.interval` | Scrape interval | `30s` |
| `serviceMonitor.scrapeTimeout` | Scrape timeout | `10s` |
| `serviceMonitor.additionalLabels` | Labels for Prometheus `serviceMonitorSelector` (e.g. `release: kube-prometheus-stack`) | `{}` |
| `monitoring.dashboard.enabled` | Install Grafana dashboard ConfigMap (`grafana_dashboard: "1"`) | `false` |
| `monitoring.dashboard.folder` | Grafana folder annotation | `DataFlow` |
| `monitoring.prometheusRule.enabled` | Install PrometheusRule alerts | `false` |
| `monitoring.prometheusRule.additionalLabels` | Labels for Prometheus `ruleSelector` | `{}` |

Example with kube-prometheus-stack:

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

Deep dive: [Web GUI](gui.md). Summary of chart keys:

| Parameter | Description | Default |
|-----------|-------------|---------|
| `gui.enabled` | Deploy dataflow-web | `false` |
| `gui.image.repository` | GUI image | `ghcr.io/dataflow-operator/dataflow-web` |
| `gui.image.tag` | GUI image tag | chart default (see `values.yaml`) |
| `gui.image.pullPolicy` | Pull policy | `IfNotPresent` |
| `gui.replicaCount` | GUI replicas | `1` |
| `gui.port` | Bind port | `8080` |
| `gui.logLevel` | `debug` / `info` / `warn` / `error`; empty → server default | `""` |
| `gui.extraEnv` | Extra env vars | `[]` |
| `gui.prometheus.url` | Prometheus base URL for historical charts | `""` |
| `gui.prometheus.bearerTokenSecret.name` | Secret name for bearer token | `""` |
| `gui.prometheus.bearerTokenSecret.key` | Secret key | `token` |
| `gui.resources` | Resource requests/limits | `{}` |
| `gui.serviceAccount.create` | Dedicated least-privilege SA for GUI | `true` |
| `gui.serviceAccount.name` | Existing SA; if set, chart does not create GUI SA/RBAC | `""` |
| `gui.ingress.enabled` | Expose GUI via Ingress | `false` |
| `gui.ingress.className` | Ingress class | `""` |
| `gui.ingress.annotations` | Ingress annotations | `{}` |
| `gui.ingress.hosts` | Hosts and paths | see `values.yaml` |
| `gui.ingress.tls` | TLS secrets | `[]` |

---

## Example production snippet

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
  # caBundle: leave empty if cert-manager injects CA

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
