# RUNBOOK-INFRA-003: Triage High Host CPU and Memory Saturation

## Metadata
- **Runbook ID:** RUNBOOK-INFRA-003
- **Subsystem:** Infrastructure / Container Runtime / Compute
- **Applies To:** All services
- **Severity Trigger:** Alert on `cpu_utilization_percent > 85%` or `memory_utilization_percent > 90%`

---

## 1. Description & Symptoms
High CPU causes request queuing and thread contention. High memory causes aggressive GC thrashing and eventually OOM termination.

---

## 2. Diagnostic Steps
1. Review host/pod metrics to identify whether CPU or memory is saturated.
2. For CPU spikes: Check for infinite loops, cryptographic hashing contention, or sudden traffic surges.
3. For Memory spikes: Check heap dump or profile allocation rate for memory leaks.

---

## 3. Remediation Actions
- Scale replicas horizontally (`kubectl scale --replicas=...`).
- Vertical pod autoscaling (increase CPU/memory limits).
- Restart pods if leaked memory requires immediate flush.
