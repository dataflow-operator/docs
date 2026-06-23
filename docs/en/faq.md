# FAQ and Troubleshooting

Frequently asked questions and solutions to common problems when working with DataFlow Operator.

## General Questions

### What is the difference between DataFlow and DataFlowCron?

| Characteristic | DataFlow | DataFlowCron |
|----------------|----------|--------------|
| Workload | Deployment (permanent) | CronJob + Job (scheduled) |
| Usage | Streaming, continuous sync | Scheduled batch ETL |
| Termination | On resource deletion | Polling source exhausted → Job succeeded |
| Post-steps | No | Optional `triggers` after processor |
| `replicas > 1` | Only for Kafka source | Not supported |

**When to use DataFlow:**
- Continuous streaming of Kafka events
- Real-time data replication
- Processing with minimal latency

**When to use DataFlowCron:**
- Scheduled ETL tasks (hourly, daily)
- Data migrations with a start and end
- Tasks with post-processing steps (triggers)

### Why is my DataFlow not processing messages?

**Check the status:**
```bash
kubectl get dataflow <name>
kubectl describe dataflow <name>
```

**Common causes:**

1. **No messages in source**
   ```bash
   # Check Kafka topic
   kafka-console-consumer --bootstrap-server localhost:9092 --topic <topic>
   ```

2. **Incorrect credentials**
   ```bash
   kubectl logs -l app=dataflow-processor -c processor
   # Look for connection errors
   ```

3. **Transformation errors**
   - Check JSONPath syntax in filter/router
   - Check that fields exist in input data

4. **Sink unavailable**
   ```bash
   # Check network connection
   kubectl exec -it <processor-pod> -- nc -zv <sink-host> <port>
   ```

### How to debug transformations?

**1. Enable verbose logging:**
```bash
kubectl logs -l app=dataflow-processor -c processor -f
```

**2. Use error sink for analysis:**
```yaml
errors:
  type: kafka
  config:
    brokers: [kafka:9092]
    topic: debug-errors
```

**3. Check JSONPath expressions:**
```bash
# Use gjson playground or test locally
curl -X POST https://gjson.dev/validate \
  -d '{"condition": "$.user.active"}'
```

## Kafka Issues

### Messages are not read from the beginning of the topic

By default, DataFlow uses `OffsetOldest` - reads from the beginning of the topic. If you see only new messages:

**Check consumer group:**
```bash
kafka-consumer-groups.sh --bootstrap-server localhost:9092 \
  --group <consumer-group> --describe
```

**Reset offset:**
```bash
kafka-consumer-groups.sh --bootstrap-server localhost:9092 \
  --group <consumer-group> --reset-offsets --to-earliest --execute
```

### Duplicate messages

DataFlow provides **at-least-once** delivery semantics. Duplicates can occur during:
- Processor restarts
- Network issues
- Long processing

**Solutions:**
1. **Use idempotent sink:**
   ```yaml
   sink:
     type: postgresql
     config:
       upsertMode: true
       conflictKey: id
   ```

2. **Reduce duplicate window:**
   ```yaml
   spec:
     ackGranularity: message
   ```

3. **Application-level deduplication:**
   - Use unique constraints in the database
   - Check message ID before processing

### Consumer group issues

**"Consumer group is rebalancing"**
- Too many restarts
- Uneven partition distribution

**Solutions:**
```yaml
spec:
  source:
    type: kafka
    config:
      # Increase session timeout
      sessionTimeoutSeconds: 30
      # Increase heartbeat interval
      heartbeatIntervalSeconds: 10
```

## PostgreSQL Issues

### "Connection refused" or timeouts

**Check:**
1. PostgreSQL availability:
   ```bash
   kubectl exec -it <processor-pod> -- pg_isready -h <postgres-host>
   ```

2. Network policies:
   ```bash
   kubectl get networkpolicies
   ```

3. Connection pool:
   ```yaml
   sink:
     type: postgresql
     config:
       # Increase timeout
       connectionTimeout: 30
       # Reduce batch size for issues
       batchSize: 50
   ```

### Long INSERT queries

**Optimizations:**
```yaml
sink:
  type: postgresql
  config:
    # Increase batch size
    batchSize: 500
    # Auto table creation with indexes
    autoCreateTable: true
    # Use UPSERT for updates
    upsertMode: true
    conflictKey: id
```

### Logical replication slot inactive

**For PostgreSQL CDC:**
```bash
# Check slot status
SELECT * FROM pg_replication_slots WHERE slot_name = 'your_slot';

# Active slots
SELECT * FROM pg_stat_replication;
```

**Heartbeat to keep slot alive:**
```yaml
source:
  type: postgresql-cdc
  config:
    heartbeatIntervalSeconds: 30
```

## Performance Issues

### Slow processing

**Diagnostics:**
```bash
# Metrics monitoring
curl http://<processor-pod>:8080/metrics

# View logs
kubectl logs -l app=dataflow-processor --tail=100 -f
```

**Optimizations:**

1. **Increase resources:**
   ```yaml
   resources:
     requests:
       cpu: "1000m"
       memory: "1Gi"
     limits:
       cpu: "2000m"
       memory: "2Gi"
   ```

2. **Configure batch size:**
   ```yaml
   sink:
     type: postgresql
     config:
       batchSize: 500
       batchFlushIntervalSeconds: 5
   ```

3. **Increase buffer:**
   ```yaml
   spec:
     channelBufferSize: 1000
   ```

### High memory consumption

**Causes:**
- Large messages
- Massive flatten transformations
- Long batch intervals

**Solutions:**
```yaml
spec:
  # Reduce buffer
  channelBufferSize: 100
  sink:
    type: postgresql
    config:
      # Reduce batch size
      batchSize: 50
      # Reduce flush interval
      batchFlushIntervalSeconds: 1
```

## Trino Issues

### REMOTE_TASK_ERROR error

```
Trino query failed: Expected response from http://.../v1/task/.../status is empty
(Error: REMOTE_TASK_ERROR, Code: 65542)
```

**Causes:**
- Trino worker overload
- Network problem
- Worker restart

**Solutions:**
1. Reduce batch size:
   ```yaml
   sink:
     type: trino
     config:
       batchSize: 3
   ```

2. Increase timeouts:
   ```yaml
   sink:
     type: trino
     config:
       queryTimeoutSeconds: 300
   ```

3. Check Trino cluster:
   ```bash
   # Check worker availability
   curl http://trino-coordinator:8080/v1/info
   ```

### OAuth2 authentication errors

**Check Keycloak configuration:**
```yaml
sink:
  type: trino
  config:
    auth:
      type: oauth2
      tokenUrl: "https://keycloak/realms/dataflow/protocol/openid-connect/token"
      clientId: "dataflow-client"
      clientSecretRef:
        name: trino-secrets
        key: client-secret
```

**Check token:**
```bash
# Get token manually
curl -X POST https://keycloak/realms/dataflow/protocol/openid-connect/token \
  -d "grant_type=client_credentials" \
  -d "client_id=dataflow-client" \
  -d "client_secret=<secret>"
```

## Nessie/Iceberg Issues

### Nessie: "Table not found"

**Check:**
1. Namespace exists:
   ```bash
   curl http://nessie:19120/api/v2/namespaces
   ```

2. Branch exists:
   ```bash
   curl http://nessie:19120/api/v2/trees
   ```

3. Correct configuration:
   ```yaml
   sink:
     type: nessie
     config:
       baseURL: "http://nessie:19120"
       branch: main
       namespace: analytics
       table: events
   ```

### Iceberg REST Catalog: 401 Unauthorized

**Check authentication:**
```yaml
sink:
  type: iceberg
  config:
    catalogURL: "https://iceberg-catalog.example.com/v1"
    auth:
      type: bearer
      tokenRef:
        name: iceberg-secrets
        key: token
```

## Kubernetes-Specific Issues

### Pod in CrashLoopBackOff state

**Diagnostics:**
```bash
kubectl describe pod <processor-pod>
kubectl logs <processor-pod> --previous
```

**Common causes:**
1. Incorrect CRD configuration
2. Insufficient resources (OOMKilled)
3. Initialization errors

### ConfigMap not updating

When changing DataFlow, ConfigMap updates automatically, but pod restarts only with `restartPolicy: Always`.

**Force restart:**
```bash
kubectl rollout restart deployment/<dataflow-name>
```

### RBAC Issues

**Error: "User cannot create resource"**
```bash
# Check permissions
kubectl auth can-i create dataflows --as <user>

# Create RoleBinding
kubectl create rolebinding dataflow-admin \
  --clusterrole=dataflow-admin \
  --user=<user> \
  --namespace=<namespace>
```

## Diagnostics

### Full debugging checklist

```bash
# 1. DataFlow Status
kubectl get dataflow <name> -o yaml

# 2. Pod Status
kubectl get pods -l app=dataflow-processor
kubectl describe pod <processor-pod>

# 3. Operator logs
kubectl logs -l app.kubernetes.io/name=dataflow-operator -f

# 4. Processor logs
kubectl logs <processor-pod> -c processor -f

# 5. Kubernetes events
kubectl get events --sort-by='.lastTimestamp' | grep dataflow

# 6. ConfigMap
kubectl get configmap df-<name>-spec -o yaml

# 7. Network access
kubectl exec -it <processor-pod> -- nc -zv <sink-host> <port>

# 8. Metrics
curl http://<processor-pod>:8080/metrics
```

### Collecting diagnostic information

```bash
#!/bin/bash
# save-debug-info.sh

NAME=$1
NAMESPACE=${2:-default}

echo "=== DataFlow Status ===" > debug.txt
kubectl get dataflow $NAME -n $NAMESPACE -o yaml >> debug.txt

echo -e "\n=== Pod Status ===" >> debug.txt
kubectl get pods -n $NAMESPACE -l app=dataflow-processor >> debug.txt

echo -e "\n=== Recent Logs ===" >> debug.txt
kubectl logs -n $NAMESPACE -l app=dataflow-processor --tail=100 >> debug.txt 2>&1

echo -e "\n=== Events ===" >> debug.txt
kubectl get events -n $NAMESPACE --sort-by='.lastTimestamp' | grep dataflow | tail -20 >> debug.txt

echo "Debug info saved to debug.txt"
```

## Getting Help

### Where to ask questions

1. **GitHub Issues**: https://github.com/dataflow-operator/dataflow/issues
2. **Documentation**: https://dataflow-operator.github.io/docs/
3. **Examples**: `dataflow/config/samples/`

### Information for bug report

When creating an issue, attach:
1. Operator version: `kubectl get deployment dataflow-operator -o yaml`
2. DataFlow manifest (without secrets)
3. Operator and processor logs
4. Output of `kubectl describe` for pod and DataFlow
5. Kubernetes version: `kubectl version`
