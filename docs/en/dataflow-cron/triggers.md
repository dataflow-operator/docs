# DataFlowCron Triggers

`spec.triggers` is an **ordered list of extra steps** that run after the main data pipeline. Each item describes **exactly one container**, with the same core knobs as `Pod.spec.containers[]`: `image`, `command`, `args`, `env`, `resources`, `imagePullPolicy`.

## When and how they run

1. On schedule, the **CronJob** starts the **processor Job** (same `/processor` binary as `DataFlow`).
2. Triggers **do not start** until that Job is **successful** (`JobComplete=True`).
3. The controller creates **one Kubernetes Job per trigger**, **in list order**: `triggers[0]` first, then `triggers[1]` after the previous Job succeeds, and so on.
4. All Jobs from the same cron tick share a **run ID** (`dataflow.dataflow.io/run-id`), useful when filtering in `kubectl` or logs.
5. Each trigger pod has **a single container** and `restartPolicy: Never` — the container must exit **0** or the chain stops with a failed step.

Steps **do not run in parallel**, and there is **no** templating of arguments from pipeline output — think **sequential hooks**, not an internal DAG.

## `triggers[]` fields

| Field | Required | Description |
|-------|----------|-------------|
| **`image`** | Yes | Container image (same as for a normal Job). |
| **`name`** | No | Container name in the Pod; if empty, the controller uses `trigger-<index>`. |
| **`command`** | No | Entrypoint (overrides the image `ENTRYPOINT` when set). |
| **`args`** | No | Arguments to `command`. |
| **`env`** | No | Environment variables, including `valueFrom.secretKeyRef` / `configMapKeyRef` (core `EnvVar`). |
| **`resources`** | No | CPU/memory `requests` and `limits`. |
| **`imagePullPolicy`** | No | E.g. `IfNotPresent` or `Always`. |

!!! note "No volume mounts in API"
    The **`DataFlowCronTrigger` API has no `volumeMounts` or extra Pod volumes**. Files appear only if they are **baked into the image**, or the container fetches them (e.g. `kubectl apply -f https://...`). The path `/manifests/...` in `dataflowcron-example.yaml` only works if your image provides that path.

## Debugging

Labels on processor and trigger Jobs/Pods:

- `dataflow.dataflow.io/dataflow-cron=<DataFlowCron name>`
- `dataflow.dataflow.io/run-id=<run id>`
- `dataflow.dataflow.io/trigger-index=<index>` (processor Job from CronJob uses `-1`)

```bash
kubectl get jobs -l dataflow.dataflow.io/dataflow-cron=my-cron -o wide
kubectl logs job/<trigger-job-name> --all-containers=true
```

Use **`status.phase`**, **`currentTriggerIndex`**, **`activeJobName`**, **`lastFailedTime`** on the `DataFlowCron` for a high-level view.

## Examples

**Two-step chain: webhook, then another HTTP call** (if the first container exits non-zero, the second never runs):

```yaml
  triggers:
    - name: notify-slack
      image: curlimages/curl:8.8.0
      command: ["curl", "-fsS", "-X", "POST", "-H", "Content-Type: application/json"]
      args:
        - "-d"
        - '{"text":"ETL cron finished"}'
        - "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
    - name: refresh-bi-cache
      image: curlimages/curl:8.8.0
      args: ["-fsS", "-X", "POST", "http://bi-service:8080/internal/refresh"]
```

**Token from a Secret** (Airflow 2.x):

```yaml
  triggers:
    - name: start-airflow-dag
      image: curlimages/curl:8.8.0
      command: ["/bin/sh", "-c"]
      args:
        - 'curl -fsS -X POST -H "Authorization: Bearer ${AIRFLOW_TOKEN}" -H "Content-Type: application/json" --data "{}" http://airflow-webserver.dataflow.svc:8080/api/v1/dags/my_dag/dagRuns'
      env:
        - name: AIRFLOW_TOKEN
          valueFrom:
            secretKeyRef:
              name: airflow-token
              key: token
```

**`kubectl` against in-cluster resources**:

```yaml
  triggers:
    - name: annotate-last-run
      image: bitnami/kubectl:latest
      command: ["/bin/bash", "-ec"]
      args:
        - |
          kubectl annotate dataflowcron my-cron company.example.com/last-ok="$(date -Iseconds)" --overwrite
```

**Resources and pull policy** for a heavier CLI:

```yaml
  triggers:
    - name: run-spark-submit
      image: my-registry/spark-cli:v1
      imagePullPolicy: IfNotPresent
      command: ["/opt/spark/bin/spark-submit"]
      args: ["--master", "k8s://https://kubernetes.default.svc", "/app/batch.py"]
      resources:
        requests:
          cpu: "500m"
          memory: "512Mi"
        limits:
          memory: "1Gi"
```

## See also

- [DataFlowCron Overview](index.md)
- [Examples](examples.md) — full pipeline YAML with triggers
- [Spec & Schedule](spec.md)
