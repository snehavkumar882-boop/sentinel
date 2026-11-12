# INC-2023-07-19: Payment Worker JVM Heap Memory Exhaustion

## Incident Overview
- **Incident ID:** INC-2023-07-19
- **Service:** payment-api-service
- **Severity:** SEV-1
- **Status:** Resolved
- **Date:** 2023-07-19
- **Duration:** 1 hour 15 minutes

---

## Executive Summary
On July 19, 2023, the `payment-api-service` suffered pod restarts due to OutOfMemory (OOMKilled) events. 

---

## Symptoms & Observed Telemetry
- `memory_utilization_percent` climbed monotonically from 42% to 99% over a 12-hour window.
- CPU spiked to 100% in the final 10 minutes due to aggressive Garbage Collection (GC) thrashing.
- Database metrics were completely nominal.

---

## Root Cause
An un-evicted static HashMap inside the idempotency validation interceptor retained transaction payload references indefinitely.

---

## Remediation
Configured an explicit TTL and maximum size (Guava / Caffeine LRU cache) with eviction metrics.
