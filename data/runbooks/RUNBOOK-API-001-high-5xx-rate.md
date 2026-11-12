# RUNBOOK-API-001: Triage API Gateway & Service HTTP 5xx Surge

## Metadata
- **Runbook ID:** RUNBOOK-API-001
- **Subsystem:** HTTP API / Reverse Proxy
- **Applies To:** All HTTP Microservices
- **Severity Trigger:** Alert on `http_5xx_rate > 2%` for > 3 consecutive minutes

---

## 1. Description & Symptoms
A high HTTP 5xx rate indicates application-layer failures, unhandled exceptions, or downstream dependency timeouts (500 Internal Server Error, 502 Bad Gateway, 503 Service Unavailable, 504 Gateway Timeout).

---

## 2. Diagnostic Flowchart
1. **Categorize Error Code:**
   - 500: Internal unhandled runtime exception or thread failure.
   - 502 / 504: Downstream database or third-party service timeout.
   - 503: Service overloaded / circuit breaker open.
2. **Correlate with Dependency Metrics:**
   - Check database connection pool wait time (`db_connection_pool_wait_ms`).
   - Check cache latency and hit ratio.
   - Check external API call latency.
3. **Trace Log Inspection:**
   - Query recent ERROR logs filtered by `status_code >= 500` to inspect stack traces.

---

## 3. Remediation Actions
- If downstream DB failure: Follow [RUNBOOK-DB-002](RUNBOOK-DB-002-connection-pool-saturation.md).
- If bad application code rollout: Execute deployment rollback.
- If upstream traffic spike: Enable rate limiting / shedding at API gateway.
