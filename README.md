# SENTINEL: Autonomous Data & Incident Intelligence Platform

SENTINEL is an autonomous incident detection, correlation, and root-cause intelligence platform designed for high-availability systems and modern site reliability engineering (SRE).

---

## 1. Purpose & Value Proposition
When production incidents occur, engineers are overwhelmed with disconnected telemetry: raw metric alarms fire across services, application logs spike with stack traces, and relevant runbooks or historical postmortems are difficult to locate under pressure.

SENTINEL bridges:
1. **Explainable Machine Learning:** Real-time statistical and multi-variate anomaly detection, lead-lag metric cross-correlation, and changepoint isolation.
2. **Contextual Knowledge & RAG:** Automated hybrid semantic retrieval over operational runbooks and historical postmortems.
3. **Autonomous Agent Reasoning (LangGraph):** A deterministic, evidence-grounded agent workflow that queries telemetry, tests causal hypotheses, validates findings against deployment events, and produces verifiable incident reports with an audit trail.

---

## 2. Platform Architecture

```
Data Ingestion (Metrics, Logs, Deployments)
         │
         ▼
Data Processing & Validation (Pydantic, Cleaning, Feature Store)
         │
         ▼
ML Detection & Diagnostic Engine (Statistical Z-Score + Isolation Forest, Correlation Matrix)
         │
         ▼
Knowledge Layer (Hybrid BM25 + Vector RAG over Runbooks & Postmortems)
         │
         ▼
Sentinel Agent (LangGraph Autonomous Investigation State Machine)
         │
         ▼
Presentation (FastAPI REST Service + Streamlit SRE Cockpit Dashboard)
```

---

## 3. Current Development Phase

> **Phase 3: Machine Learning Engine** (Complete / Awaiting Phase 4 Approval)

### Development Roadmap:
- [x] **Phase 1: Environment Setup & Foundation:** Production directory structure, virtual environment, Pydantic Settings, structured logging, FastAPI application factory, and preflight health check.
- [x] **Phase 2: Ingestion & Telemetry Simulator:** Relational database schemas (SQLAlchemy 2.0 / SQLite / PostgreSQL), deterministic Golden Path synthetic telemetry generator, deployment event tracking, log streams, historical incident postmortems, and operational runbooks.
- [x] **Phase 3: Machine Learning Engine:** Unsupervised anomaly detection (Rolling Z-Score + Isolation Forest), empirical metric cross-correlation matrix, lead-lag cross-correlation analysis, interpretable feature attribution, and unified anomaly reporting.
- [ ] **Phase 4: Knowledge Base & RAG Layer:** Markdown runbook chunker, vector database indexing (ChromaDB), and hybrid dense/sparse retrieval.
- [ ] **Phase 5: Autonomous Sentinel Agent:** LangGraph state machine, tool integration (metrics, logs, runbooks, deployments), and hypothesis validation.
- [ ] **Phase 6: API Layer:** REST endpoints for incident triage, telemetry inspection, and investigation execution.
- [ ] **Phase 7: SRE Cockpit UI & E2E Validation:** Interactive Streamlit dashboard with Plotly telemetry visualizations, audit trail rendering, and end-to-end evaluation suite.

---

## 4. Setup Instructions

### Prerequisites
- Python 3.11+ (Python 3.13 supported)
- Virtual environment (`venv`)

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-org/sentinel.git
   cd sentinel
   ```

2. **Create and activate the virtual environment:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure Environment Variables:**
   ```bash
   cp .env.example .env
   ```
   Inspect and customize `.env` as appropriate.

---

## 5. How to Run the Application

### Run Platform Health Check & Preflight Diagnostics:
```bash
python -m src.main --check
```

### Generate Synthetic Telemetry & Seed Database:
```bash
python scripts/generate_telemetry.py --seed 42 --duration 240
```

### Run ML Anomaly Analysis Pipeline:
```bash
python scripts/run_ml_analysis.py
```

### Launch the FastAPI Server:
```bash
python -m src.main --serve
```
Access the interactive OpenAPI Swagger documentation at:
`http://127.0.0.1:8000/docs`

Or query the health check endpoint directly:
```bash
curl -X GET http://127.0.0.1:8000/api/v1/health
```

### Run the Test Suite:
```bash
pytest
```
Or with verbose output:
```bash
pytest -v
```

---

## 6. Directory Structure

```
sentinel/
├── config/                 # Pydantic settings & structured logging
├── data/                   # Raw/processed datasets, runbooks & postmortems
├── docs/                   # Architecture and technical documentation
├── src/
│   ├── agent/              # LangGraph investigation agent state & tools
│   ├── api/                # FastAPI application, routers & schemas
│   ├── database/           # Relational models and session handlers
│   ├── data/               # Ingestion, validation & feature store
│   ├── frontend/           # Streamlit SRE cockpit UI components
│   ├── knowledge/          # Embeddings, chunking & RAG vector store
│   ├── ml/                 # Anomaly detection & cross-correlation models
│   └── main.py             # CLI entrypoint & server runner
├── tests/
│   ├── unit/               # Config, logging, and unit tests
│   └── integration/        # Health and API endpoint integration tests
├── .env.example            # Environment variables template
├── pyproject.toml          # Package configuration & tool settings
└── requirements.txt        # Pinned production dependencies
```
