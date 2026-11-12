# SENTINEL Architecture Overview

## Objective
SENTINEL is an autonomous data and incident intelligence platform designed to ingest system telemetry, isolate multi-variate anomalies using explainable machine learning models, search historical incident knowledge and operational runbooks, and formulate evidence-backed incident reports using an autonomous agent workflow.

## Target Architecture

```
Data Ingestion (Metrics, Logs, Deployments)
         │
         ▼
Data Processing & Validation (Feature Engine, EMA, Z-Scores)
         │
         ▼
ML Detection & Diagnostic Engine (Statistical + Isolation Forest, Correlation Matrix)
         │
         ▼
Knowledge Layer (Hybrid BM25 + Vector RAG over Runbooks & Postmortems)
         │
         ▼
Sentinel Agent (LangGraph Autonomous Investigation & Verification State Machine)
         │
         ▼
Output (FastAPI REST Service + Streamlit SRE Cockpit UI)
```

## Implementation Phases
- **Phase 1: Environment Setup & Project Foundation** (Current)
- **Phase 2: Ingestion & Synthetic Telemetry Generator**
- **Phase 3: ML Anomaly Detection & Metric Correlation Engine**
- **Phase 4: Knowledge Base & RAG Layer**
- **Phase 5: Autonomous Sentinel Agent (LangGraph)**
- **Phase 6: FastAPI Backend Services**
- **Phase 7: Streamlit SRE Cockpit Dashboard & E2E Validation**
