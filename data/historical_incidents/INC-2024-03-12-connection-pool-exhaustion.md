# INC-2024-03-12: Payment API Database Connection Starvation

## Incident Overview
- **Incident ID:** INC-2024-03-12
- **Service:** payment-api-service
- **Severity:** SEV-1 (Critical Revenue Impact)
- **Status:** Resolved
- **Date:** 2024-03-12
- **Duration:** 38 minutes

---

## Executive Summary
On March 12, 2024, the `payment-api-service` experienced an immediate degradation following release `v1.8.2`. HTTP 500 error rates surged to 16.5% and 95th percentile request latency increased from 115ms to 4,200ms. Transactions failed with connection pool timeout errors. 

Infrastructure metrics (CPU utilization at 33% and memory at 54%) remained completely normal throughout the event, ruling out compute or memory starvation.

The incident was mitigated by rolling back the deployment to restore the database connection pool maximum capacity from 15 back to 100.

---

## Symptoms & Observed Telemetry
1. **HTTP 5xx Errors:** Surged from baseline 0.1% to ~17% on `/api/v1/payments/charge`.
2. **Latency:** `api_latency_p95_ms` rose from 115ms to over 4,000ms.
3. **Database Metrics:**
   - `db_connection_pool_active` was pegged at 100% capacity (15/15).
   - `db_connection_pool_wait_ms` surged from 4ms to >3,000ms.
   - `db_connection_errors_rpm` jumped from 0 to ~45/min.
4. **Negative Signals:**
   - `cpu_utilization_percent` stayed steady at 32-35%.
   - `memory_utilization_percent` remained stable at 54-55%.

---

## Log Evidence
Structured error logs during the incident showed repeated occurrences of:
```
[ERROR] pool.HikariPool: Connection pool exhausted (active=15, max=15). Client timed out after 500ms waiting for connection.
[ERROR] payment.service: Failed to complete authorization. Caused by: ConnectionPoolTimeoutException
```

---

## Root Cause
A configuration change introduced in release `v1.8.2` reduced `db_connection_pool_size` from 100 to 15 and tightened `db_pool_timeout_ms` to 500ms. Under steady transaction volume (1,000 RPM), all 15 connections were quickly acquired by concurrent in-flight requests, causing new incoming payment requests to block and time out.

---

## Remediation & Recovery
- Deployed hotfix `v1.8.3-rollback` restoring `db_connection_pool_size=100` and `db_pool_timeout_ms=5000`.
- Connection acquisition latency returned to <5ms within 3 minutes of the rollback.
- Error rates dropped back to 0.1%.
