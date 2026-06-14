# DataFlowCron Spec & Schedule

`DataFlowCronSpec` **embeds [`DataFlowSpec`](../dataflow/spec.md)** — all fields that exist on `DataFlow` (`source`, `sink`, `transformations`, `errors`, `resources`, `nodeSelector`, `affinity`, `tolerations`, `checkpointPersistence`, `channelBufferSize`, `processorImage` / `processorVersion`, `imagePullSecrets`, etc.) apply the same way.

## Cron-specific fields

| Field | Description |
|-------|-------------|
| **`schedule`** (required) | Cron expression with **5 or 6** fields (standard Kubernetes cron format). |
| **`concurrencyPolicy`** | `Allow`, `Forbid`, or `Replace` — same semantics as `CronJob.spec.concurrencyPolicy`. Default Kubernetes behavior applies if omitted. |
| **`successfulJobsHistoryLimit`** / **`failedJobsHistoryLimit`** | Passed through to the managed `CronJob`. |
| **`startingDeadlineSeconds`** | Passed through to the `CronJob`. |
| **`suspend`** | When set, suspends scheduling (CronJob `suspend`). |
| **`triggers`** | Ordered post-run steps. See [Triggers](triggers.md). |

Validation reuses **DataFlow** rules for source, sink, transformations, and resources, and adds checks for `schedule`, trigger `image`, and `concurrencyPolicy`. When the [validating webhook](../development.md#configuring-the-validating-webhook) is enabled (Helm: `webhook.enabled` and `webhook.caBundle`), admission validates both `DataFlowCron` and `DataFlow` before objects are stored.

## Objects created in the cluster

For a `DataFlowCron` named `<name>` in a namespace:

| Resource | Name | Role |
|----------|------|------|
| ConfigMap | `dfc-<name>-spec` | JSON spec for the processor (`spec.json`), same role as `df-<name>-spec` for `DataFlow`. |
| CronJob | `dfc-<name>` | Runs the **processor** workload on `schedule` (first step of each run). |
| Job(s) | `dfc-<name>-…` | The CronJob creates the processor Job; optional **trigger** Jobs are created by the operator after the processor succeeds. |

Processor pods use the same entrypoint as in the Deployment-based flow:

```
/processor --spec-path=/etc/dataflow/spec.json --namespace=… --name=…
```

The `name` argument is the **DataFlowCron** resource name.

## Job history and deadlines

Control CronJob child Job retention and missed schedules:

```yaml
  schedule: "15 */6 * * *"
  concurrencyPolicy: Forbid
  successfulJobsHistoryLimit: 2
  failedJobsHistoryLimit: 3
  startingDeadlineSeconds: 300   # skip if schedule slot missed by > 5 minutes
```

## Pausing the schedule

Set **`suspend: true`** to stop new Jobs without deleting the resource:

```yaml
spec:
  schedule: "0 * * * *"
  suspend: true
```

Remove `suspend` or set `suspend: false` to resume.

## See also

- [DataFlowCron Overview](index.md)
- [Triggers](triggers.md)
- [Examples](examples.md)
- [DataFlow Spec Reference](../dataflow/spec.md)
