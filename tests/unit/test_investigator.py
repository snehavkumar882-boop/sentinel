
"""Unit tests for Sentinel's deterministic investigator."""

from datetime import datetime, timezone

import pytest

from src.agent.evidence import EvidenceCollector
from src.agent.investigator import SentinelInvestigator
from src.agent.models import InvestigationRequest
from src.ml.models import (
    AnomalyRecord,
    DetectionMethod,
    SeverityLevel,
    UnifiedAnomalyReport,
)


@pytest.fixture
def incident_report():
    timestamp = datetime(2026, 11, 12, 10, 0, tzinfo=timezone.utc)

    anomalies = [
        AnomalyRecord(
            metric_name="db_connection_wait",
            timestamp=timestamp,
            observed_value=850.0,
            expected_value=100.0,
            anomaly_score=7.5,
            detection_method=DetectionMethod.STATISTICAL_ZSCORE,
            severity=SeverityLevel.CRITICAL,
            is_anomaly=True,
            explanation="Database connection wait is critically elevated.",
        ),
        AnomalyRecord(
            metric_name="api_latency",
            timestamp=timestamp,
            observed_value=900.0,
            expected_value=200.0,
            anomaly_score=5.5,
            detection_method=DetectionMethod.STATISTICAL_ZSCORE,
            severity=SeverityLevel.HIGH,
            is_anomaly=True,
            explanation="API latency is significantly elevated.",
        ),
    ]

    return UnifiedAnomalyReport(
        service_id="payment-api",
        analysis_window_start=timestamp,
        analysis_window_end=timestamp,
        total_time_points=1,
        univariate_anomalies_count=2,
        multivariate_anomalies_count=0,
        top_anomalous_metrics=[
            "db_connection_wait",
            "api_latency",
        ],
        univariate_anomalies=anomalies,
        multivariate_anomalies=[],
        top_correlations=[],
        lagged_relationships=[],
        metric_baselines={},
        summary_narrative=(
            "Database connection wait and API latency anomalies detected."
        ),
    )


@pytest.fixture
def healthy_report():
    timestamp = datetime(2026, 11, 12, 10, 0, tzinfo=timezone.utc)

    return UnifiedAnomalyReport(
        service_id="healthy-api",
        analysis_window_start=timestamp,
        analysis_window_end=timestamp,
        total_time_points=1,
        univariate_anomalies_count=0,
        multivariate_anomalies_count=0,
        top_anomalous_metrics=[],
        univariate_anomalies=[],
        multivariate_anomalies=[],
        top_correlations=[],
        lagged_relationships=[],
        metric_baselines={},
        summary_narrative="No anomalies detected.",
    )


class FakeKnowledgeBase:
    """Fake knowledge base for controlled investigation tests."""

    def __init__(self, results=None):
        self.results = results or []
        self.last_query = None

    def search(self, query, top_k=None, where=None, min_similarity=None):
        self.last_query = query
        return self.results


class FailingKnowledgeBase:
    """Simulate a knowledge retrieval failure."""

    def search(self, query, top_k=None, where=None, min_similarity=None):
        raise RuntimeError("Simulated vector database failure")


@pytest.fixture
def knowledge_results():
    return [
        {
            "chunk_id": "runbook-001",
            "content": "Inspect active database connections and pool limits.",
            "similarity": 0.91,
            "document_id": "doc-runbook",
            "document_type": "runbook",
            "title": "Database Connection Pool Runbook",
            "section": "Troubleshooting",
            "source_path": "runbooks/database.md",
        },
        {
            "chunk_id": "incident-001",
            "content": "A previous incident involved database pool exhaustion.",
            "similarity": 0.86,
            "document_id": "doc-incident",
            "document_type": "historical_incident",
            "title": "Previous Database Incident",
            "section": "Root Cause Analysis",
            "source_path": "historical_incidents/database.md",
        },
    ]


def test_healthy_service_returns_no_anomaly(healthy_report):
    collector = EvidenceCollector()
    investigator = SentinelInvestigator(collector)

    result = investigator.investigate(
        InvestigationRequest(anomaly_report=healthy_report)
    )

    assert result.status == "NO_ANOMALY"
    assert result.overall_severity is None
    assert result.findings == []
    assert result.hypotheses == []
    assert result.recommendations == []
    assert result.causation_confirmed is False


def test_incident_generates_investigation_report(
    incident_report,
    knowledge_results,
):
    knowledge_base = FakeKnowledgeBase(knowledge_results)
    collector = EvidenceCollector(knowledge_base=knowledge_base)
    investigator = SentinelInvestigator(collector)

    result = investigator.investigate(
        InvestigationRequest(anomaly_report=incident_report)
    )

    assert result.status == "INVESTIGATION_REQUIRED"
    assert result.service_id == "payment-api"
    assert result.overall_severity == SeverityLevel.CRITICAL
    assert len(result.evidence) >= 4
    assert len(result.findings) > 0
    assert len(result.hypotheses) > 0
    assert len(result.recommendations) == 1


def test_database_anomaly_generates_relevant_hypothesis(
    incident_report,
):
    collector = EvidenceCollector()
    investigator = SentinelInvestigator(collector)

    result = investigator.investigate(
        InvestigationRequest(
            anomaly_report=incident_report,
            include_runbooks=False,
            include_historical_incidents=False,
        )
    )

    titles = [item.title for item in result.hypotheses]

    assert "Possible database connection pool saturation" in titles


def test_hypotheses_never_claim_verified_causation(
    incident_report,
    knowledge_results,
):
    collector = EvidenceCollector(
        knowledge_base=FakeKnowledgeBase(knowledge_results)
    )
    investigator = SentinelInvestigator(collector)

    result = investigator.investigate(
        InvestigationRequest(anomaly_report=incident_report)
    )

    assert result.causation_confirmed is False

    for hypothesis in result.hypotheses:
        assert hypothesis.causal_status == "UNVERIFIED"


def test_recommendations_require_human_approval(
    incident_report,
    knowledge_results,
):
    collector = EvidenceCollector(
        knowledge_base=FakeKnowledgeBase(knowledge_results)
    )
    investigator = SentinelInvestigator(collector)

    result = investigator.investigate(
        InvestigationRequest(anomaly_report=incident_report)
    )

    assert len(result.recommendations) > 0

    for recommendation in result.recommendations:
        assert recommendation.requires_human_approval is True


def test_retrieval_failure_marks_investigation_incomplete(
    incident_report,
):
    collector = EvidenceCollector(
        knowledge_base=FailingKnowledgeBase()
    )
    investigator = SentinelInvestigator(collector)

    result = investigator.investigate(
        InvestigationRequest(anomaly_report=incident_report)
    )

    assert result.status == "INVESTIGATION_INCOMPLETE"
    assert len(result.evidence) > 0
    assert any(
        "Knowledge retrieval was unavailable" in item
        for item in result.limitations
    )


def test_all_finding_evidence_references_are_valid(
    incident_report,
    knowledge_results,
):
    collector = EvidenceCollector(
        knowledge_base=FakeKnowledgeBase(knowledge_results)
    )
    investigator = SentinelInvestigator(collector)

    result = investigator.investigate(
        InvestigationRequest(anomaly_report=incident_report)
    )

    valid_evidence_ids = {
        item.evidence_id for item in result.evidence
    }

    for finding in result.findings:
        assert set(finding.evidence_ids).issubset(valid_evidence_ids)

    for hypothesis in result.hypotheses:
        assert set(
            hypothesis.supporting_evidence_ids
        ).issubset(valid_evidence_ids)

    for recommendation in result.recommendations:
        assert set(recommendation.evidence_ids).issubset(
            valid_evidence_ids
        )


def test_investigation_timestamps_are_valid(incident_report):
    collector = EvidenceCollector()
    investigator = SentinelInvestigator(collector)

    result = investigator.investigate(
        InvestigationRequest(
            anomaly_report=incident_report,
            include_runbooks=False,
            include_historical_incidents=False,
        )
    )

    assert result.completed_at >= result.started_at
    assert result.investigation_id.startswith("INV-payment-api-")
