# Data Model and Golden Path Incident Specification

## 1. Overview
This document defines the relational database architecture and the controlled synthetic "Golden Path" incident scenario for **SENTINEL**.

---

## 2. Relational Database Schema

The database is built on SQLAlchemy 2.0 and supports SQLite (zero-setup local development) and PostgreSQL.

```
+--------------------+        +-------------------------+
|     services       | 1    * |    metrics_telemetry    |
|--------------------|<-------|-------------------------|
| id (PK)            |        | id (PK)                 |
| name               |        | timestamp (IDX)         |
| tier               |        | service_id (FK, IDX)    |
| owner_team         |        | metric_name (IDX)       |
| created_at         |        | metric_value            |
+---------+----------+        | tags (JSON)             |
          |                   +-------------------------+
          | 1
          |                   +-------------------------+
          +------------------<|       system_logs       |
          |                   |-------------------------|
          |                   | id (PK)                 |
          |                   | timestamp (IDX)         |
          |                   | service_id (FK, IDX)    |
          |                   | log_level (IDX)         |
          |                   | message                 |
          |                   | trace_id (IDX)          |
          |                   | attributes (JSON)       |
          |                   +-------------------------+
          | 1
          |                   +-------------------------+
          +------------------<|    deployment_events    |
          |                   |-------------------------|
          |                   | id (PK)                 |
          |                   | timestamp (IDX)         |
          |                   | service_id (FK, IDX)    |
          |                   | version                 |
          |                   | deployed_by             |
          |                   | config_diff (JSON)      |
          |                   | status                  |
          |                   | description             |
          |                   +-------------------------+
          | 1
          |                   +-------------------------+
          +------------------<|        incidents        |
                              |-------------------------|
                              | id (PK)                 |
                              | service_id (FK, IDX)    |
                              | title                   |
                              | status                  |
                              | severity                |
                              | detected_at (IDX)       |
                              | resolved_at             |
                              | anomaly_metric          |
                              | anomaly_score           |
                              | root_cause_summary      |
                              | confidence_score        |
                              | report_json (JSON)      |
                              +------------+------------+
                                           | 1
                                           | *
                              +------------+------------+
                              |investigation_audit_trail|
                              |-------------------------|
                              | id (PK)                 |
                              | incident_id (FK, IDX)   |
                              | step_index              |
                              | phase                   |
                              | tool_name               |
                              | input_payload (JSON)    |
                              | output_payload (JSON)   |
                              | agent_reasoning         |
                              | created_at              |
                              +-------------------------+
```

### Table Definitions & Indexes
1. **`services`**: Master registry of monitored microservices and systems.
2. **`metrics_telemetry`**: Multi-metric time-series telemetry.
   - Composite Index: `idx_metric_service_name_time (service_id, metric_name, timestamp)`.
3. **`system_logs`**: Application events and exception traces.
   - Composite Index: `idx_logs_service_time_level (service_id, timestamp, log_level)`.
4. **`deployment_events`**: Record of CI/CD releases and configuration parameter modifications.
5. **`incidents`**: Incident records tracking state (`DETECTED`, `INVESTIGATING`, `VALIDATED`, `RESOLVED`).
6. **`investigation_audit_trail`**: Immutable audit logs of every tool call and agent reasoning step.

---

## 3. Golden Path Scenario: Database Connection Pool Saturation

### 3.1 Service Context
- **Service ID:** `payment-api-service`
- **Description:** Payment & Transaction Authorization Gateway
- **Tier:** `TIER-1` (Critical path service)
- **Normal Traffic:** ~1,000 requests per minute

### 3.2 Timeline (240 Minutes Total Duration)

| Minute Range | Phase | Description |
|---|---|---|
| **0 – 109** | **Baseline Normal** | Service is operating nominally with healthy baselines across all metrics and low error rates (<0.2%). |
| **110** | **Deployment Event** | Deployment `v1.8.2` by `cicd-pipeline`. Config diff: `db_connection_pool_size: 100 -> 15`, `db_pool_timeout_ms: 5000 -> 500`. |
| **110 – 119** | **Pre-Onset** | Slight internal connection pressure builds as concurrency limits take effect. |
| **120 – 154** | **Incident Active ($T_0$)** | The pool reaches capacity (15/15). Connection wait time surges to >3,000ms. Latency explodes to >4,000ms. HTTP 5xx error rate spikes to 16.5%. Application logs flood with `ConnectionPoolTimeoutException`. |
| **155** | **Recovery Rollback** | Deployment `v1.8.3-rollback` by `sre-oncall` restoring pool size to 100 and timeout to 5,000ms. |
| **156 – 239** | **Post-Incident Recovery** | Metrics decay exponentially back to baseline within 5 minutes and remain completely stable for the remaining 80+ minutes. |

### 3.3 Telemetry Metric Behaviors

| Metric Name | Baseline Value | Incident Peak | Units | Causal Role |
|---|---|---|---|---|
| `db_connection_pool_active` | 18 – 25 | **15.0 (Capped)** | count | Root bottleneck |
| `db_connection_pool_wait_ms` | 2 – 8 | **2,800 – 3,600** | ms | **Direct Root Cause Signal** |
| `db_connection_errors_rpm` | 0 | **35 – 55** | errors/min | Direct symptom |
| `api_latency_p95_ms` | 110 – 130 | **3,800 – 4,500** | ms | Customer-facing symptom |
| `http_5xx_rate` | 0.001 – 0.002 | **0.14 – 0.18** | ratio (14-18%) | Primary Alert Trigger |
| `http_5xx_count` | 0 – 2 | **130 – 170** | errors/min | Corroborating count |
| `request_volume_rpm` | 950 – 1050 | 920 – 1020 | req/min | Traffic is steady (not a DDoS) |
| `cpu_utilization_percent` | 30 – 42% | **32 – 40%** | percent | **Negative Control** (rules out CPU saturation) |
| `memory_utilization_percent` | 52 – 56% | **53 – 57%** | percent | **Negative Control** (rules out memory leak) |

### 3.4 Negative Controls (Why This Matters for AI/ML)
A common flaw in naive incident analysis is assuming high latency is caused by high CPU or a traffic surge. In Sentinel's Golden Path scenario:
- Traffic volume is normal (eliminating DDoS / load surge hypotheses).
- CPU and memory remain normal (eliminating compute starvation / memory leak hypotheses).
- The causal chain is uniquely: `Deployment v1.8.2` $\rightarrow$ `Pool Sizing Reduced` $\rightarrow$ `db_connection_pool_wait_ms` $\rightarrow$ `api_latency_p95_ms` $\rightarrow$ `http_5xx_rate`.
