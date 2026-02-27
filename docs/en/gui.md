# Web GUI (dataflow-web)

Web interface for managing DataFlow from the browser without using `kubectl` or editing YAML manually.

## How It Works

The GUI has two parts:

1. **Backend (Go)** — A server in the `dataflow-web` component that:
   - Connects to the Kubernetes cluster (in-cluster or via `KUBECONFIG`);
   - Serves a REST API under the `/api` prefix;
   - Serves the built frontend static assets (SPA) for paths like `/`, `/manifests`, `/logs`, etc.

2. **Frontend (Vue 3 + Vite)** — A single-page application that:
   - Calls the backend at `/api` (or at `VITE_API_BASE` when set at build time);
   - Shows the dashboard, manifest list, logs, and metrics;
   - Supports language switching (Russian/English) and theme (light/dark).

All API requests go through the same host as the UI (e.g. when you open the GUI in a browser, requests hit the same address). The backend talks to the Kubernetes API and returns JSON.

## GUI Capabilities

### Dashboard

- Summary across namespaces: total DataFlow count and breakdown by phase (Running, Pending, Error, Stopped).
- List of namespaces with flow counts and quick links to manifests for each namespace.

### Manifests (DataFlow)

- **List** of DataFlow resources in the selected namespace with name, status (phase), processed message count, and error count.
- **Search** by manifest name.
- **Create** a new DataFlow: “Create new” opens a modal with a YAML editor and a template (source, sink, transformations).
- **Edit**: view and change an existing DataFlow as YAML (saved via PUT to the API).
- **Delete** a DataFlow with confirmation.

Namespace can be changed via a dropdown; the URL may include `?namespace=...`.

### Logs

- Choose namespace and a DataFlow from the list.
- Set the number of lines (tail lines) for a one-time load.
- **Load logs** — single API request, logs shown in a text area.
- **Follow logs** — stream via Server-Sent Events (SSE), live updates; “Stop following” closes the stream.
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

## Backend API

All endpoints return JSON except logs (plain text or SSE).

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
| GET | `/api/metrics?namespace=&name=` | Metrics for DataFlow (reserved for future use) |

CORS headers (`Access-Control-Allow-Origin: *`, etc.) are set so the API can be used from a different port during local development.

## Running the GUI

- **In cluster**: Deploy `dataflow-web` (e.g. via Helm or manifests). The server uses in-cluster config and listens on the configured `bind-address` (default `:8080`).
- **Locally**: Run backend and frontend separately from the repo root:
  - Backend: `go run ./cmd/server --bind-address=:8080` (set `KUBECONFIG` if needed).
  - Frontend: in `dataflow-web/web` run `npm install && npm run dev`; the app runs at http://localhost:5173 with API requests proxied to the backend (e.g. port 8080).

For build and frontend structure details see [dataflow-web/web/README.md](../../../dataflow-web/web/README.md).
