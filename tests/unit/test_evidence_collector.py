
"""Unit tests for Sentinel's evidence collector."""

from datetime import datetime, timezone

import pytest

from src.agent.evidence import EvidenceCollector
from src.ml.models import (
    AnomalyRecord,
    CorrelationPair,
    DetectionMethod,
    FeatureContribution,
    LaggedRelationship,
    MultivariateAnomalyRecord,
    SeverityLevel,
    UnifiedAnomalyReport,
)


@pytest.fixture
def sample_report():
    timestamp = datetime(2026, 11, 12, 10, 0, tzinfo=timezone.utc)

    univariate_anomaly = AnomalyRecord(
        metric_name="api_latency",
        timestamp=timestamp,
        observed_value=850.0,
        expected_value=200.0,
        anomaly_score=6.5,
        detection_method=DetectionMethod.STATISTICAL_ZSCORE,
        severity=SeverityLevel.HIGH,
        is_anomaly=True,
        explanation="API latency is significantly above baseline.",
    )

    normal_record = AnomalyRecord(
        metric_name="cpu_usage",
        timestamp=timestamp,
        observed_value=45.0,
        expected_value=48.0,
        anomaly_score=0.3,
        detection_method=DetectionMethod.STATISTICAL_ZSCORE,
        severity=SeverityLevel.LOW,
        is_anomaly=False,
        explanation="CPU usage is within expected limits.",
    )

    multivariate_anomaly = MultivariateAnomalyRecord(
        timestamp=timestamp,
        raw_decision_score=-0.25,
        normalized_anomaly_score=0.85,
        is_anomaly=True,
        severity=SeverityLevel.HIGH,
        top_contributions=[
            FeatureContribution(
                feature_name="db_connection_wait",
                contribution_weight=0.8,
                deviation_sigma=4.2,
                direction="above",
            )
        ],
        explanation="Multiple database-related metrics are abnormal.",
    )

    correlation = CorrelationPair(
        metric_a="api_latency",
        metric_b="db_connection_wait",
        pearson_r=0.94,
        spearman_rho=0.91,
        abs_correlation=0.94,
        p_value=0.001,
    )

    lagged_relationship = LaggedRelationship(
        lead_metric="db_connection_wait",
        lag_metric="api_latency",
        optimal_lag_minutes=2,
        max_cross_correlation=0.88,
        interpretation=(
            "Database connection wait changes precede API latency changes."
        ),
        causation_disclaimer=(
            "Temporal association does not establish causation."
        ),
    )

    return UnifiedAnomalyReport(
        service_id="payment-api",
        analysis_window_start=timestamp,
        analysis_window_end=timestamp,
        total_time_points=1,
        univariate_anomalies_count=2,
        multivariate_anomalies_count=1,
        top_anomalous_metrics=["api_latency", "db_connection_wait"],
        univariate_anomalies=[
            univariate_anomaly,
            normal_record,
        ],
        multivariate_anomalies=[multivariate_anomaly],
        top_correlations=[correlation],
        lagged_relationships=[lagged_relationship],
        metric_baselines={},
        summary_narrative="API latency and database wait anomalies detected.",
    )


def test_collects_univariate_anomaly_evidence(sample_report):
    collector = EvidenceCollector()

    evidence = collector.collect_ml_evidence(sample_report)

    anomaly_evidence = [
        item for item in evidence
        if item.evidence_type == "ml_anomaly"
    ]

    univariate = [
        item for item in anomaly_evidence
        if item.metric_name == "api_latency"
    ]

    assert len(univariate) == 1
    assert univariate[0].observed_value == 850.0
    assert univariate[0].expected_value == 200.0
    assert univariate[0].severity == SeverityLevel.HIGH


def test_ignores_normal_univariate_records(sample_report):
    collector = EvidenceCollector()

    evidence = collector.collect_ml_evidence(sample_report)

    metric_names = [
        item.metric_name
        for item in evidence
        if item.evidence_type == "ml_anomaly"
    ]

    assert "cpu_usage" not in metric_names


def test_collects_multivariate_anomaly_evidence(sample_report):
    collector = EvidenceCollector()

    evidence = collector.collect_ml_evidence(sample_report)

    multivariate = [
        item for item in evidence
        if item.evidence_type == "ml_anomaly"
        and "Multivariate" in item.title
    ]

    assert len(multivariate) == 1
    assert "db_connection_wait" in multivariate[0].content


def test_collects_correlation_evidence(sample_report):
    collector = EvidenceCollector()

    evidence = collector.collect_ml_evidence(sample_report)

    correlations = [
        item for item in evidence
        if item.evidence_type == "ml_correlation"
    ]

    assert len(correlations) == 1
    assert "0.9400" in correlations[0].content
    assert "not proof of causation" in correlations[0].content


def test_collects_lag_evidence(sample_report):
    collector = EvidenceCollector()

    evidence = collector.collect_ml_evidence(sample_report)

    lag_evidence = [
        item for item in evidence
        if item.evidence_type == "ml_lag"
    ]

    assert len(lag_evidence) == 1
    assert "2 minutes" in lag_evidence[0].content
    assert "does not establish causation" in lag_evidence[0].content


def test_empty_report_produces_no_evidence():
    timestamp = datetime(2026, 11, 12, 10, 0, tzinfo=timezone.utc)

    report = UnifiedAnomalyReport(
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

    collector = EvidenceCollector()

    evidence = collector.collect_ml_evidence(report)

    assert evidence == []


class FakeKnowledgeBase:
    """Controlled knowledge-base response for unit testing."""

    def __init__(self, results):
        self.results = results
        self.last_query = None
        self.last_top_k = None
        self.last_min_similarity = None

    def search(self, query, top_k=None, where=None, min_similarity=None):
        self.last_query = query
        self.last_top_k = top_k
        self.last_min_similarity = min_similarity
        return self.results


def test_collects_relevant_rag_evidence():
    knowledge_base = FakeKnowledgeBase([
        {
            "chunk_id": "chunk-001",
            "content": "Check database connection pool saturation.",
            "similarity": 0.82,
            "document_id": "doc-001",
            "document_type": "runbook",
            "title": "Database Runbook",
            "section": "Troubleshooting",
            "source_path": "runbooks/db.md",
        }
    ])

    collector = EvidenceCollector(knowledge_base=knowledge_base)

    evidence = collector.collect_knowledge_evidence(
        query="database connection pool saturation",
        max_results=5,
    )

    assert len(evidence) == 1
    assert evidence[0].evidence_type == "runbook"
    assert evidence[0].similarity == 0.82
    assert evidence[0].chunk_id == "chunk-001"
    assert knowledge_base.last_top_k == 5


def test_rejects_below_threshold_rag_evidence():
    knowledge_base = FakeKnowledgeBase([
        {
            "chunk_id": "chunk-002",
            "content": "Weakly related document.",
            "similarity": 0.20,
            "document_type": "historical_incident",
            "title": "Unrelated Incident",
        }
    ])

    collector = EvidenceCollector(knowledge_base=knowledge_base)

    evidence = collector.collect_knowledge_evidence(
        query="database connection errors"
    )

    assert evidence == []


def test_respects_document_type_filters():
    knowledge_base = FakeKnowledgeBase([
        {
            "chunk_id": "chunk-003",
            "content": "Runbook instructions.",
            "similarity": 0.90,
            "document_type": "runbook",
            "title": "Runbook",
        },
        {
            "chunk_id": "chunk-004",
            "content": "Historical incident details.",
            "similarity": 0.88,
            "document_type": "historical_incident",
            "title": "Incident",
        },
    ])

    collector = EvidenceCollector(knowledge_base=knowledge_base)

    evidence = collector.collect_knowledge_evidence(
        query="database problem",
        include_runbooks=False,
        include_historical_incidents=True,
    )

    assert len(evidence) == 1
    assert evidence[0].evidence_type == "historical_incident"


def test_rejects_invalid_similarity_threshold():
    with pytest.raises(ValueError):
        EvidenceCollector(min_similarity=1.5)


def test_rejects_missing_knowledge_base():
    collector = EvidenceCollector()

    with pytest.raises(RuntimeError):
        collector.collect_knowledge_evidence("database problem")


def test_removes_duplicate_evidence():
    knowledge_base = FakeKnowledgeBase([])

    collector = EvidenceCollector(knowledge_base=knowledge_base)

    from src.agent.models import EvidenceReference

    item = EvidenceReference(
        evidence_id="test-001",
        evidence_type="ml_anomaly",
        title="Test anomaly",
        content="Test evidence.",
    )

    result = collector.validate_evidence([item, item])

    assert len(result) == 1
