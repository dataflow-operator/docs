# Kubernetes Events

The DataFlow Operator records [Kubernetes Events](https://kubernetes.io/docs/reference/kubernetes-api/cluster-resources/event-v1/) for DataFlow resources. Events are attached to the corresponding DataFlow object and can be viewed with `kubectl describe dataflow <name>` or `kubectl get events`.

## Overview

The controller uses a standard Kubernetes `EventRecorder` (via `mgr.GetEventRecorderFor("dataflow-controller")`). Events are emitted during reconcile for:

- Successful creation or update of ConfigMap and Deployment
- Cleanup on DataFlow deletion
- Failures (secrets, ConfigMap, Deployment, status update, cleanup)

RBAC for events is declared in the controller: the operator needs `create` and `patch` on `events` in the core API group.

## Event types

Kubernetes supports two event types: **Normal** (informational) and **Warning** (failure or attention needed).

### Normal events

| Reason | Message | When |
|--------|---------|------|
| `ConfigMapCreated` | Created ConfigMap \<name\> | ConfigMap for the DataFlow spec was created |
| `ConfigMapUpdated` | Updated ConfigMap \<name\> | ConfigMap for the DataFlow spec was updated |
| `DeploymentCreated` | Created Deployment \<name\> | Processor Deployment was created |
| `DeploymentUpdated` | Updated Deployment \<name\> | Processor Deployment was updated |
| `ResourcesDeleted` | Deleted Deployment and ConfigMap | Resources were removed during DataFlow deletion |

### Warning events

| Reason | Message | When |
|--------|---------|------|
| `FailedGet` | Unable to fetch DataFlow | The controller could not get the DataFlow object (e.g. not found or API error) |
| `CleanupFailed` | Failed to cleanup resources: \<error\> | Cleanup of Deployment/ConfigMap failed during deletion |
| `SecretResolutionFailed` | Failed to resolve secrets: \<error\> | Referenced secrets could not be resolved for the spec |
| `ConfigMapFailed` | Failed to create or update ConfigMap: \<error\> | ConfigMap create/update failed |
| `DeploymentFailed` | Failed to create or update Deployment: \<error\> | Deployment create/update failed |
| `StatusUpdateFailed` | Unable to update DataFlow status: \<error\> | Updating the DataFlow status field failed |

## Viewing events

```bash
# Events for a specific DataFlow (shown in describe)
kubectl describe dataflow -n <namespace> <name>

# Recent events in a namespace (includes DataFlow-related events)
kubectl get events -n <namespace> --sort-by='.lastTimestamp'

# Only events for a specific DataFlow (by involved object)
kubectl get events -n <namespace> --field-selector involvedObject.name=<dataflow-name>
```

Events are namespaced and tied to the DataFlow `involvedObject`, so they appear in `kubectl describe dataflow` and in namespace event lists.

## Relation to status and metrics

- **Status**: The DataFlow `.status.phase` and `.status.message` are updated on success and failure; events provide an audit trail of what happened and when.
- **Metrics**: For observability, see [Metrics](metrics.md). Events complement metrics by giving discrete, human-readable reasons for failures and key lifecycle changes.
