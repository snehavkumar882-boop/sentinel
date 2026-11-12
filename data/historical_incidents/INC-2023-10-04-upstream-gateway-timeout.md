# INC-2023-10-04: Upstream Payment Provider Network Latency Spike

## Incident Overview
- **Incident ID:** INC-2023-10-04
- **Service:** payment-api-service
- **Severity:** SEV-2
- **Status:** Resolved
- **Date:** 2023-10-04
- **Duration:** 52 minutes

---

## Executive Summary
On October 4, 2023, the `payment-api-service` observed elevated latency on external credit card processing endpoints (`/api/v1/payments/card`). The primary database connection pool was healthy (active connections at 22/100, pool wait time <5ms).

---

## Symptoms & Observed Telemetry
- Latency increased specifically on external processor egress socket calls.
- Internal database queries and connection wait times remained normal (`db_connection_pool_wait_ms < 6ms`).
- Error logs showed `SocketTimeoutException: Connect to external.processor.net timed out`.

---

## Root Cause
An external transit provider suffered packet loss along European peering routes, impacting egress API requests to the acquiring bank.

---

## Remediation
Egress payment traffic was rerouted to secondary acquiring bank fallback endpoints via feature flag toggle.
