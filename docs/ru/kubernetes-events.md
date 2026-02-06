# События Kubernetes

DataFlow Operator записывает [события Kubernetes (Events)](https://kubernetes.io/docs/reference/kubernetes-api/cluster-resources/event-v1/) для ресурсов DataFlow. События привязываются к соответствующему объекту DataFlow и отображаются в выводе `kubectl describe dataflow <name>` или `kubectl get events`.

## Обзор

Контроллер использует стандартный Kubernetes `EventRecorder` (через `mgr.GetEventRecorderFor("dataflow-controller")`). События генерируются в процессе reconcile при:

- Успешном создании или обновлении ConfigMap и Deployment
- Очистке ресурсов при удалении DataFlow
- Ошибках (секреты, ConfigMap, Deployment, обновление статуса, очистка)

RBAC для событий объявлен в контроллере: оператору нужны права `create` и `patch` для ресурса `events` в core API group.

## Типы событий

В Kubernetes есть два типа событий: **Normal** (информационные) и **Warning** (ошибки или требующие внимания).

### События типа Normal

| Reason | Сообщение | Когда |
|--------|-----------|-------|
| `ConfigMapCreated` | Created ConfigMap \<имя\> | ConfigMap со spec DataFlow был создан |
| `ConfigMapUpdated` | Updated ConfigMap \<имя\> | ConfigMap со spec DataFlow был обновлён |
| `DeploymentCreated` | Created Deployment \<имя\> | Deployment процессора был создан |
| `DeploymentUpdated` | Updated Deployment \<имя\> | Deployment процессора был обновлён |
| `ResourcesDeleted` | Deleted Deployment and ConfigMap | Ресурсы удалены при удалении DataFlow |

### События типа Warning

| Reason | Сообщение | Когда |
|--------|-----------|-------|
| `FailedGet` | Unable to fetch DataFlow | Не удалось получить объект DataFlow (например, не найден или ошибка API) |
| `CleanupFailed` | Failed to cleanup resources: \<ошибка\> | Ошибка очистки Deployment/ConfigMap при удалении |
| `SecretResolutionFailed` | Failed to resolve secrets: \<ошибка\> | Не удалось разрешить ссылки на секреты для spec |
| `ConfigMapFailed` | Failed to create or update ConfigMap: \<ошибка\> | Ошибка создания или обновления ConfigMap |
| `DeploymentFailed` | Failed to create or update Deployment: \<ошибка\> | Ошибка создания или обновления Deployment |
| `StatusUpdateFailed` | Unable to update DataFlow status: \<ошибка\> | Не удалось обновить поле статуса DataFlow |

## Просмотр событий

```bash
# События по конкретному DataFlow (показываются в describe)
kubectl describe dataflow -n <namespace> <имя>

# Последние события в пространстве имён (включая события DataFlow)
kubectl get events -n <namespace> --sort-by='.lastTimestamp'

# Только события по конкретному DataFlow (по объекту involved)
kubectl get events -n <namespace> --field-selector involvedObject.name=<имя-dataflow>
```

События привязаны к пространству имён и к объекту DataFlow (`involvedObject`), поэтому они отображаются в `kubectl describe dataflow` и в списке событий пространства имён.

## Связь со статусом и метриками

- **Статус**: Поля `.status.phase` и `.status.message` DataFlow обновляются при успехе и при ошибках; события дают журнал того, что произошло и когда.
- **Метрики**: Для мониторинга см. [Метрики](metrics.md). События дополняют метрики дискретными, читаемыми причинами сбоев и ключевых изменений жизненного цикла.
