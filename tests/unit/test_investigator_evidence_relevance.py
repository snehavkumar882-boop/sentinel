
"""Regression tests for investigator evidence relevance."""

from datetime import datetime, timezone

from src.agent.investigator import SentinelInvestigator
from src.agent.models import EvidenceReference
from src.ml.models import SeverityLevel
from src.agent.evidence import EvidenceCollector


def make_anomaly(metric_name: str) -> EvidenceReference:
    return EvidenceReference(
        evidence_id=f"anomaly:{metric_name}",
        evidence_type="ml_anomaly",
        title=f"Anomaly: {metric_name}",
        content=f"{metric_name} was detected as anomalous.",
        metric_name=metric_name,
        observed_value=850.0,
        expected_value=100.0,
        severity=SeverityLevel.HIGH,
        timestamp=datetime.now(timezone.utc),
    )


def make_evidence(
    evidence_id: str,
    evidence_type: str,
    content: str,
) -> EvidenceReference:
    return EvidenceReference(
        evidence_id=evidence_id,
        evidence_type=evidence_type,
        title=evidence_id,
        content=content,
    )


def make_investigator() -> SentinelInvestigator:
    return SentinelInvestigator(EvidenceCollector())


def test_unrelated_historical_incident_does_not_support_hypothesis():
    anomaly = make_anomaly("db_connection_wait")

    historical = make_evidence(
        "rag:memory-incident",
        "historical_incident",
        "A previous incident involved memory exhaustion.",
    )

    investigator = make_investigator()

    hypotheses = investigator._generate_hypotheses(
        [anomaly],
        [anomaly, historical],
    )

    database_hypothesis = next(
        item for item in hypotheses
        if item.hypothesis_id == "HYP-DATABASE_CONNECTION_POOL"
    )

    assert "anomaly:db_connection_wait" in (
        database_hypothesis.supporting_evidence_ids
    )
    assert "rag:memory-incident" not in (
        database_hypothesis.supporting_evidence_ids
    )


def test_unrelated_correlation_does_not_support_hypothesis():
    anomaly = make_anomaly("db_connection_wait")

    correlation = make_evidence(
        "ml:correlation:cpu-memory",
        "ml_correlation",
        (
            "Metrics 'cpu_usage' and 'memory_usage' have a Pearson "
            "correlation of 0.95. Correlation does not prove causation."
        ),
    )

    investigator = make_investigator()

    hypotheses = investigator._generate_hypotheses(
        [anomaly],
        [anomaly, correlation],
    )

    database_hypothesis = next(
        item for item in hypotheses
        if item.hypothesis_id == "HYP-DATABASE_CONNECTION_POOL"
    )

    assert "ml:correlation:cpu-memory" not in (
        database_hypothesis.supporting_evidence_ids
    )


def test_relevant_correlation_supports_hypothesis():
    anomaly = make_anomaly("db_connection_wait")

    correlation = make_evidence(
        "ml:correlation:db-api",
        "ml_correlation",
        (
            "Metrics 'db_connection_wait' and 'api_latency' have a "
            "Pearson correlation of 0.95. Correlation does not prove causation."
        ),
    )

    investigator = make_investigator()

    hypotheses = investigator._generate_hypotheses(
        [anomaly],
        [anomaly, correlation],
    )

    database_hypothesis = next(
        item for item in hypotheses
        if item.hypothesis_id == "HYP-DATABASE_CONNECTION_POOL"
    )

    assert "ml:correlation:db-api" in (
        database_hypothesis.supporting_evidence_ids
    )


def test_hypothesis_confidence_remains_conservative():
    anomalies = [
        make_anomaly("db_connection_wait"),
        make_anomaly("db_connection_pool_usage"),
    ]

    investigator = make_investigator()

    hypotheses = investigator._generate_hypotheses(
        anomalies,
        anomalies,
    )

    database_hypothesis = next(
        item for item in hypotheses
        if item.hypothesis_id == "HYP-DATABASE_CONNECTION_POOL"
    )

    assert database_hypothesis.confidence_level == "LOW"
    assert database_hypothesis.causal_status == "UNVERIFIED"
