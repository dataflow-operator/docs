# Web GUI (dataflow-web)

Web interface for managing DataFlow from the browser without using `kubectl` or editing YAML manually.

## Overview

The GUI has two parts:

1. **Backend (Go)** — A server in the `dataflow-web` component that connects to the Kubernetes cluster (in-cluster or via `KUBECONFIG`), serves a REST API under `/api`, and serves the built frontend static assets (SPA).

2. **Frontend (Vue 3 + Vite)** — A single-page application that calls the backend at `/api`, shows the dashboard, manifest list, logs, and metrics, and supports language switching (Russian/English) and theme (light/dark).

All API requests go through the same host as the UI. The backend talks to the Kubernetes API and returns JSON.

## Capabilities

### Dashboard

- Summary across namespaces: total DataFlow count and breakdown by phase (Running, Pending, Error, Stopped).
- List of namespaces with flow counts and quick links to manifests for each namespace.

### Manifests (DataFlow)

- **List** of DataFlow resources in the selected namespace with name, status (phase), processed message count, and error count.
- **Search** by manifest name.
- **Create** a new DataFlow: "Create new" opens a modal with a YAML editor and a template (source, sink, transformations).
- **Edit**: view and change an existing DataFlow as YAML (saved via PUT to the API).
- **Delete** a DataFlow with confirmation.

Namespace can be changed via a dropdown; the URL may include `?namespace=...`.

### Logs

- Choose namespace and a DataFlow from the list.
- Set the number of lines (tail lines) for a one-time load.
- **Load logs** — single API request, logs shown in a text area.
- **Follow logs** — stream via Server-Sent Events (SSE), live updates; "Stop following" closes the stream.
- **Copy** button to copy the current log text to the clipboard.

Logs are read from the DataFlow processor pod (container `processor`), using labels such as `dataflow.dataflow.io/name` or `app=dataflow-processor` when needed.

### Metrics and Status

- Select namespace and DataFlow.
- **Status** for the flow: phase, message, processed count, error count, last processed time.
- Data comes from the DataFlow resource `status` and from the `/api/status` endpoint (and optionally `/api/metrics`).

### Other

- **Namespace switching** — on the dashboard, manifests, logs, and metrics pages you can pick a namespace; the list is loaded from `/api/namespaces`.
- **Localization** — UI in Russian and English (vue-i18n).
- **Theme** — light and dark (toggle in the UI).

## Configuration

GUI is configured via Helm values when deploying with the dataflow-operator chart. Key parameters:

| Parameter | Description | Default |
|-----------|-------------|---------|
| `gui.enabled` | Enable web GUI | `false` |
| `gui.image.repository` | Image for the GUI server (separate from operator) | `ghcr.io/dataflow-operator/dataflow-web` |
| `gui.image.tag` | Image tag | `v0.1.0` |
| `gui.image.pullPolicy` | Image pull policy | `IfNotPresent` |
| `gui.replicaCount` | Number of GUI server replicas | `1` |
| `gui.port` | Bind port for the GUI server | `8080` |
| `gui.logLevel` | Log level: `debug`, `info`, `warn`, `error` | (empty, uses default) |
| `gui.extraEnv` | Extra environment variables (e.g. `KUBECONFIG`, `OPERATOR_METRICS_URL` override) | `[]` |
| `gui.resources` | Resource limits and requests | `{}` |
| `gui.serviceAccount.name` | Dedicated service account (if empty, uses operator SA) | `""` |

### Ingress

| Parameter | Description | Default |
|-----------|-------------|---------|
| `gui.ingress.enabled` | Enable Ingress for GUI | `false` |
| `gui.ingress.className` | Ingress class name | `""` |
| `gui.ingress.annotations` | Ingress annotations | `{}` |
| `gui.ingress.hosts` | Host and path configuration | `[{ host: dataflow-gui.local, paths: [{ path: /, pathType: Prefix }] }]` |
| `gui.ingress.tls` | TLS configuration | `[]` |

### Metrics proxy

The GUI proxies Prometheus metrics from the operator when `OPERATOR_METRICS_URL` is set. In Helm, this is set automatically to the operator service in the same release. If the operator runs in a different namespace, override via `gui.extraEnv`:

```yaml
gui:
  extraEnv:
    - name: OPERATOR_METRICS_URL
      value: "http://dataflow-operator.dataflow-system:9090/metrics"
```

## Deployment

### In cluster (Helm)

Enable GUI when installing or upgrading the operator:

```bash
helm install dataflow-operator oci://ghcr.io/dataflow-operator/helm-charts/dataflow-operator \
  --set gui.enabled=true
```

With Ingress (e.g. nginx):

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

Access the GUI via the Service (port-forward) or Ingress URL.

### Port-forward (quick access)

Without Ingress, use port-forward:

```bash
kubectl port-forward svc/dataflow-operator-gui 8080:8080 -n <namespace>
```

Open http://localhost:8080 in a browser.

### Local development

Run backend and frontend separately from the `dataflow-web` directory:

- **Backend**: `go run ./cmd/server --bind-address=:8080` (set `KUBECONFIG` if needed).
- **Frontend**: in `dataflow-web/web` run `npm install && npm run dev`; the app runs at http://localhost:5173 with API requests proxied to the backend (port 8080).

For build and frontend structure details see [dataflow-web/README.md](../../../dataflow-web/README.md).

## Backend API

All endpoints return JSON except logs (plain text or SSE) and metrics (Prometheus text format when operator URL is configured).

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/namespaces` | List cluster namespaces |
| GET | `/api/dataflows?namespace=<ns>` | List DataFlow resources in namespace |
| GET | `/api/dataflows/<name>?namespace=<ns>` | Single DataFlow |
| POST | `/api/dataflows?namespace=<ns>` | Create DataFlow (body: JSON manifest) |
| PUT | `/api/dataflows/<name>?namespace=<ns>` | Update DataFlow spec |
| DELETE | `/api/dataflows/<name>?namespace=<ns>` | Delete DataFlow |
| GET | `/api/logs?namespace=&name=&tailLines=&follow=true\|false` | Processor pod logs (text or SSE when `follow=true`) |
| GET | `/api/status?namespace=&name=` | DataFlow status (phase, message, processedCount, errorCount, lastProcessedTime) |
| GET | `/api/metrics?namespace=&name=` | Prometheus metrics (proxied from operator when `OPERATOR_METRICS_URL` is set) |

CORS headers are set so the API can be used from a different port during local development.
