

"""Evidence collection and validation for Sentinel investigations."""

from __future__ import annotations

import json
from typing import Any

from src.agent.models import EvidenceReference
from src.ml.models import UnifiedAnomalyReport


class EvidenceCollector:
    """Collect traceable ML and knowledge-base evidence."""

    def __init__(
        self,
        knowledge_base: Any | None = None,
        min_similarity: float = 0.35,
    ) -> None:
        if not 0.0 <= min_similarity <= 1.0:
            raise ValueError("min_similarity must be between 0 and 1.")

        self.knowledge_base = knowledge_base
        self.min_similarity = min_similarity

    def collect_ml_evidence(
        self,
        report: UnifiedAnomalyReport,
    ) -> list[EvidenceReference]:
        """Convert ML anomalies, correlations and lag patterns into evidence."""

        evidence: list[EvidenceReference] = []

        # Univariate anomaly evidence
        for anomaly in report.univariate_anomalies:
            if not anomaly.is_anomaly:
                continue

            evidence.append(
                EvidenceReference(
                    evidence_id=(
                        f"ml:univariate:{anomaly.metric_name}:"
                        f"{anomaly.timestamp.isoformat()}"
                    ),
                    evidence_type="ml_anomaly",
                    title=f"Univariate anomaly: {anomaly.metric_name}",
                    content=(
                        f"{anomaly.explanation} "
                        f"Observed value: {anomaly.observed_value}. "
                        f"Expected value: {anomaly.expected_value}. "
                        f"Anomaly score: {anomaly.anomaly_score}. "
                        f"Detection method: {anomaly.detection_method.value}. "
                        f"Severity: {anomaly.severity.value}."
                    ),
                    metric_name=anomaly.metric_name,
                    observed_value=anomaly.observed_value,
                    expected_value=anomaly.expected_value,
                    severity=anomaly.severity,
                    timestamp=anomaly.timestamp,
                )
            )

        # Multivariate anomaly evidence
        for anomaly in report.multivariate_anomalies:
            if not anomaly.is_anomaly:
                continue

            contributions = [
                item.model_dump(mode="json")
                for item in anomaly.top_contributions
            ]

            evidence.append(
                EvidenceReference(
                    evidence_id=(
                        f"ml:multivariate:{anomaly.timestamp.isoformat()}"
                    ),
                    evidence_type="ml_anomaly",
                    title="Multivariate anomaly detected",
                    content=(
                        f"{anomaly.explanation} "
                        f"Normalized anomaly score: "
                        f"{anomaly.normalized_anomaly_score}. "
                        f"Raw decision score: {anomaly.raw_decision_score}. "
                        f"Severity: {anomaly.severity.value}. "
                        f"Top feature contributions: "
                        f"{json.dumps(contributions, default=str)}."
                    ),
                    severity=anomaly.severity,
                    timestamp=anomaly.timestamp,
                )
            )

        # Metric correlation evidence
        for index, correlation in enumerate(report.top_correlations):
            evidence.append(
                EvidenceReference(
                    evidence_id=f"ml:correlation:{index}",
                    evidence_type="ml_correlation",
                    title=(
                        f"Correlation: {correlation.metric_a} and "
                        f"{correlation.metric_b}"
                    ),
                    content=(
                        f"Metrics '{correlation.metric_a}' and "
                        f"'{correlation.metric_b}' have a Pearson "
                        f"correlation of {correlation.pearson_r:.4f} "
                        f"and Spearman correlation of "
                        f"{correlation.spearman_rho:.4f}. "
                        f"Absolute correlation: "
                        f"{correlation.abs_correlation:.4f}. "
                        f"P-value: {correlation.p_value:.6f}. "
                        "Correlation indicates association, not proof "
                        "of causation."
                    ),
                )
            )

        # Lead-lag relationship evidence
        for index, relationship in enumerate(report.lagged_relationships):
            evidence.append(
                EvidenceReference(
                    evidence_id=f"ml:lag:{index}",
                    evidence_type="ml_lag",
                    title=(
                        f"Temporal relationship: "
                        f"{relationship.lead_metric} and "
                        f"{relationship.lag_metric}"
                    ),
                    content=(
                        f"{relationship.interpretation} "
                        f"Leading metric: {relationship.lead_metric}. "
                        f"Following metric: {relationship.lag_metric}. "
                        f"Optimal lag: "
                        f"{relationship.optimal_lag_minutes} minutes. "
                        f"Maximum cross-correlation: "
                        f"{relationship.max_cross_correlation:.4f}. "
                        f"Causation disclaimer: "
                        f"{relationship.causation_disclaimer}"
                    ),
                )
            )

        return self.validate_evidence(evidence)

    def collect_knowledge_evidence(
        self,
        query: str,
        max_results: int = 5,
        include_runbooks: bool = True,
        include_historical_incidents: bool = True,
    ) -> list[EvidenceReference]:
        """Retrieve relevant runbook and historical incident chunks."""

        if self.knowledge_base is None:
            raise RuntimeError("Knowledge base is not configured.")

        if not query.strip():
            return []

        if max_results < 1:
            raise ValueError("max_results must be at least 1.")

        results = self.knowledge_base.search(
            query=query,
            top_k=max_results,
            min_similarity=self.min_similarity,
        )

        evidence: list[EvidenceReference] = []

        for result in results:
            document_type = result.get("document_type")
            similarity = float(result.get("similarity", 0.0))

            if similarity < self.min_similarity:
                continue

            if document_type == "runbook" and not include_runbooks:
                continue

            if (
                document_type == "historical_incident"
                and not include_historical_incidents
            ):
                continue

            if document_type not in {
                "runbook",
                "historical_incident",
            }:
                continue

            chunk_id = str(result.get("chunk_id", ""))
            content = str(result.get("content", "")).strip()

            if not chunk_id or not content:
                continue

            evidence_type = (
                "runbook"
                if document_type == "runbook"
                else "historical_incident"
            )

            evidence.append(
                EvidenceReference(
                    evidence_id=f"rag:{chunk_id}",
                    evidence_type=evidence_type,
                    title=str(result.get("title", "Untitled document")),
                    content=content,
                    source_path=result.get("source_path"),
                    document_id=result.get("document_id"),
                    chunk_id=chunk_id,
                    section=result.get("section"),
                    similarity=similarity,
                )
            )

        return self.validate_evidence(evidence)

    @staticmethod
    def validate_evidence(
        evidence: list[EvidenceReference],
    ) -> list[EvidenceReference]:
        """Remove duplicate or incomplete evidence records."""

        unique: dict[str, EvidenceReference] = {}

        for item in evidence:
            if not item.evidence_id or not item.content.strip():
                continue

            unique[item.evidence_id] = item

        return list(unique.values())
