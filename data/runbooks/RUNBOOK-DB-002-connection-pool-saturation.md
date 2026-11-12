# RUNBOOK-DB-002: Triage and Remediate Database Connection Pool Saturation

## Metadata
- **Runbook ID:** RUNBOOK-DB-002
- **Subsystem:** Database / HikariCP / Connection Pooling
- **Applies To:** payment-api-service, order-service, api-gateway
- **Severity Trigger:** SEV-1 or SEV-2 alert on `db_connection_pool_wait_ms > 500ms` or `http_5xx_rate > 5%`

---

## 1. Description & Symptoms
When an application exhausts its database connection pool:
- Incoming threads block waiting for an idle connection.
- Requests exceed client timeout limits, returning HTTP 500 or 504 errors.
- System CPU and Memory typically remain **low or normal**, while latency surges by orders of magnitude.
- Log error pattern: `ConnectionPoolTimeoutException` or `Timeout waiting for idle connection`.

---

## 2. Diagnostic Procedure
Follow these steps in sequence:

### Step 1: Verify Connection Pool Utilization
Execute metrics query:
```promql
db_connection_pool_active{service="payment-api-service"} / db_connection_pool_max
```
- If ratio == 1.0 (100%), pool is fully saturated.

### Step 2: Correlate With Connection Wait Time
```promql
rate(db_connection_pool_wait_ms[5m])
```
- Normal wait time is <10ms. During saturation, wait time spikes to >1,000ms.

### Step 3: Inspect Recent Deployments & Configuration Changes
Check whether a deployment occurred within the last 30 minutes:
```bash
sentinel deployment list --service payment-api-service --window 30m
```
Examine `config_diff` for parameter reductions in:
- `db_connection_pool_size` (or `maxPoolSize`)
- `db_pool_timeout_ms` (or `connectionTimeout`)

### Step 4: Verify Infrastructure Sanity (Negative Control)
Verify that `cpu_utilization_percent` is below 70%. If CPU is normal, the issue is internal connection pool sizing, not database host starvation.

---

## 3. Mitigation & Remediation Playbook

### Option A: Configuration Rollback (Recommended if preceded by deployment)
If a deployment modified pool parameters, trigger an immediate rollback:
```bash
kubectl rollout undo deployment/payment-api-service
```
Or patch environment variables directly:
```bash
kubectl set env deployment/payment-api-service DB_CONNECTION_POOL_SIZE=100 DB_POOL_TIMEOUT_MS=5000
```

### Option B: Horizontal Pod Autoscaling (If traffic surge caused exhaustion)
If traffic volume (`request_volume_rpm`) increased by >300%:
```bash
kubectl scale deployment/payment-api-service --replicas=10
```

### Option C: Database Backend Inspection
Verify PostgreSQL/MySQL max connections setting has not been reached on the database host:
```sql
SELECT count(*), state FROM pg_stat_activity GROUP BY state;
```
