
"""Deterministic investigation engine for Sentinel."""

from __future__ import annotations

from datetime import datetime, timezone

from src.agent.evidence import EvidenceCollector
from src.agent.models import (
    EvidenceReference,
    InvestigationFinding,
    InvestigationHypothesis,
    InvestigationRecommendation,
    InvestigationReport,
    InvestigationRequest,
)
from src.ml.models import SeverityLevel, UnifiedAnomalyReport


class SentinelInvestigator:
    """Investigate anomalies using ML evidence and historical knowledge."""

    SEVERITY_ORDER = {
        SeverityLevel.LOW: 1,
        SeverityLevel.MEDIUM: 2,
        SeverityLevel.HIGH: 3,
        SeverityLevel.CRITICAL: 4,
    }

    def __init__(
        self,
        evidence_collector: EvidenceCollector,
    ) -> None:
        self.evidence_collector = evidence_collector

    def investigate(
        self,
        request: InvestigationRequest,
    ) -> InvestigationReport:
        """Run a complete deterministic investigation."""

        started_at = datetime.now(timezone.utc)
        anomaly_report = request.anomaly_report

        evidence = self.evidence_collector.collect_ml_evidence(
            anomaly_report
        )

        anomaly_evidence = [
            item
            for item in evidence
            if item.evidence_type == "ml_anomaly"
        ]

        has_anomalies = bool(anomaly_evidence)

        limitations: list[str] = [
            "Investigation uses deterministic rules, not autonomous "
            "causal verification.",
            "Correlation and temporal relationships do not establish "
            "causation.",
        ]

        if not has_anomalies:
            completed_at = datetime.now(timezone.utc)

            return InvestigationReport(
                investigation_id=self._investigation_id(
                    anomaly_report.service_id,
                    started_at,
                ),
                service_id=anomaly_report.service_id,
                status="NO_ANOMALY",
                started_at=started_at,
                completed_at=completed_at,
                overall_severity=None,
                summary=(
                    f"No anomalous ML records were found for service "
                    f"'{anomaly_report.service_id}'. "
                    f"{anomaly_report.summary_narrative}"
                ),
                evidence=evidence,
                limitations=limitations,
                causation_confirmed=False,
            )

        knowledge_error = False

        query = self._build_knowledge_query(
            anomaly_report,
            anomaly_evidence,
        )

        if (
            request.include_runbooks
            or request.include_historical_incidents
        ):
            try:
                knowledge_evidence = (
                    self.evidence_collector.collect_knowledge_evidence(
                        query=query,
                        max_results=request.max_knowledge_results,
                        include_runbooks=request.include_runbooks,
                        include_historical_incidents=(
                            request.include_historical_incidents
                        ),
                    )
                )
                evidence.extend(knowledge_evidence)

                if any(
                    item.evidence_type == "historical_incident"
                    for item in knowledge_evidence
                ):
                    limitations.append(
                        "Historical incidents provide context only. "
                        "Their presence does not establish that the "
                        "current incident has the same cause."
                    )

            except Exception as exc:
                knowledge_error = True
                limitations.append(
                    "Knowledge retrieval was unavailable during this "
                    f"investigation: {type(exc).__name__}: {exc}"
                )

        evidence = self.evidence_collector.validate_evidence(evidence)

        findings = self._generate_findings(evidence)

        hypotheses = self._generate_hypotheses(
            anomaly_evidence,
            evidence,
        )

        recommendations = self._generate_recommendations(evidence)

        overall_severity = self._calculate_severity(anomaly_evidence)

        source_documents = sorted({
            item.source_path
            for item in evidence
            if item.source_path
        })

        status = (
            "INVESTIGATION_INCOMPLETE"
            if knowledge_error
            else "INVESTIGATION_REQUIRED"
        )

        completed_at = datetime.now(timezone.utc)

        summary = self._build_summary(
            anomaly_report,
            anomaly_evidence,
            evidence,
            hypotheses,
            overall_severity,
        )

        return InvestigationReport(
            investigation_id=self._investigation_id(
                anomaly_report.service_id,
                started_at,
            ),
            service_id=anomaly_report.service_id,
            status=status,
            started_at=started_at,
            completed_at=completed_at,
            overall_severity=overall_severity,
            summary=summary,
            findings=findings,
            hypotheses=hypotheses,
            evidence=evidence,
            recommendations=recommendations,
            source_documents_consulted=source_documents,
            limitations=limitations,
            causation_confirmed=False,
        )

    @staticmethod
    def _investigation_id(
        service_id: str,
        started_at: datetime,
    ) -> str:
        """Create a unique investigation identifier."""

        timestamp = started_at.strftime("%Y%m%dT%H%M%S%f")
        return f"INV-{service_id}-{timestamp}"

    @staticmethod
    def _build_knowledge_query(
        report: UnifiedAnomalyReport,
        anomaly_evidence: list[EvidenceReference],
    ) -> str:
        """Build a retrieval query from observed anomaly information."""

        metric_names = sorted({
            item.metric_name
            for item in anomaly_evidence
            if item.metric_name
        })

        components = [
            report.summary_narrative,
            "Observed anomalous metrics: " + ", ".join(metric_names),
        ]

        return " ".join(components)

    def _generate_findings(
        self,
        evidence: list[EvidenceReference],
    ) -> list[InvestigationFinding]:
        """Convert collected evidence into traceable findings."""

        findings: list[InvestigationFinding] = []

        finding_types = {
            "ml_anomaly": "ANOMALY",
            "ml_correlation": "CORRELATION",
            "ml_lag": "TEMPORAL_PATTERN",
            "historical_incident": "HISTORICAL_MATCH",
            "runbook": "RUNBOOK_GUIDANCE",
        }

        for index, item in enumerate(evidence, start=1):
            finding_type = finding_types.get(item.evidence_type)

            if finding_type is None:
                continue

            findings.append(
                InvestigationFinding(
                    finding_id=f"FIND-{index:03d}",
                    title=item.title,
                    description=item.content,
                    evidence_ids=[item.evidence_id],
                    finding_type=finding_type,
                )
            )

        return findings

    @staticmethod
    def _evidence_mentions_metric(
        evidence: EvidenceReference,
        metric_name: str,
    ) -> bool:
        """Check whether relationship evidence explicitly names a metric."""

        if not metric_name:
            return False

        if evidence.evidence_type == "ml_correlation":
            # Correlation evidence contains quoted metric names.
            return f"'{metric_name}'" in evidence.content

        if evidence.evidence_type == "ml_lag":
            # Lag evidence explicitly identifies leading and following metrics.
            return (
                f"Leading metric: {metric_name}." in evidence.content
                or f"Following metric: {metric_name}." in evidence.content
            )

        return False

    def _generate_hypotheses(
        self,
        anomaly_evidence: list[EvidenceReference],
        all_evidence: list[EvidenceReference],
    ) -> list[InvestigationHypothesis]:
        """Generate conservative hypotheses with relevant evidence only."""

        patterns = {
            "database_connection_pool": {
                "keywords": (
                    "connection_pool",
                    "connection_wait",
                    "pool_wait",
                    "db_connection",
                ),
                "title": "Possible database connection pool saturation",
                "explanation": (
                    "Database connection-related metrics were flagged "
                    "as anomalous. Connection pool saturation is a "
                    "possible explanation that requires independent "
                    "verification."
                ),
            },
            "memory_pressure": {
                "keywords": (
                    "memory",
                    "oom",
                    "out_of_memory",
                    "heap",
                ),
                "title": "Possible memory pressure",
                "explanation": (
                    "Memory-related metrics were flagged as anomalous. "
                    "Memory pressure is a possible explanation, but "
                    "process-level and infrastructure evidence is "
                    "required to verify it."
                ),
            },
            "compute_saturation": {
                "keywords": (
                    "cpu",
                    "processor",
                    "load_average",
                ),
                "title": "Possible compute resource saturation",
                "explanation": (
                    "Compute-related metrics were flagged as anomalous. "
                    "Resource saturation is a possible explanation "
                    "requiring further investigation."
                ),
            },
            "api_degradation": {
                "keywords": (
                    "api_latency",
                    "http_5xx",
                    "error_rate",
                    "request_failure",
                ),
                "title": "Possible API service degradation",
                "explanation": (
                    "API latency or error-related metrics were flagged "
                    "as anomalous. Application degradation is a "
                    "possible symptom; the underlying cause is "
                    "not established."
                ),
            },
        }

        hypotheses: list[InvestigationHypothesis] = []

        for key, pattern in patterns.items():
            matched_anomalies = [
                item
                for item in anomaly_evidence
                if item.metric_name
                and any(
                    keyword in item.metric_name.lower()
                    for keyword in pattern["keywords"]
                )
            ]

            if not matched_anomalies:
                continue

            matched_metrics = {
                item.metric_name.lower()
                for item in matched_anomalies
                if item.metric_name
            }

            supporting_ids = {
                item.evidence_id
                for item in matched_anomalies
            }

            # Only relationship evidence explicitly involving one of
            # this hypothesis's anomalous metrics may support it.
            for item in all_evidence:
                if item.evidence_type not in {
                    "ml_correlation",
                    "ml_lag",
                }:
                    continue

                if any(
                    self._evidence_mentions_metric(item, metric)
                    for metric in matched_metrics
                ):
                    supporting_ids.add(item.evidence_id)

            # Historical incidents are deliberately excluded from
            # hypothesis support. They remain contextual findings.
            hypotheses.append(
                InvestigationHypothesis(
                    hypothesis_id=f"HYP-{key.upper()}",
                    title=pattern["title"],
                    explanation=pattern["explanation"],
                    confidence_level="LOW",
                    supporting_evidence_ids=sorted(supporting_ids),
                    contradicting_evidence_ids=[],
                    causal_status="UNVERIFIED",
                )
            )

        if not hypotheses:
            supporting_ids = [
                item.evidence_id
                for item in anomaly_evidence
            ]

            hypotheses.append(
                InvestigationHypothesis(
                    hypothesis_id="HYP-GENERAL-ANOMALY",
                    title="Unclassified anomalous behaviour",
                    explanation=(
                        "The ML pipeline detected anomalous behaviour, "
                        "but the available metric names do not match "
                        "the investigator's current rule patterns. "
                        "Additional evidence is needed."
                    ),
                    confidence_level="LOW",
                    supporting_evidence_ids=supporting_ids,
                    causal_status="UNVERIFIED",
                )
            )

        return hypotheses

    @staticmethod
    def _generate_recommendations(
        evidence: list[EvidenceReference],
    ) -> list[InvestigationRecommendation]:
        """Create human-reviewed actions based on retrieved runbooks."""

        recommendations: list[InvestigationRecommendation] = []

        runbooks = [
            item for item in evidence
            if item.evidence_type == "runbook"
        ]

        for index, item in enumerate(runbooks, start=1):
            section = f" — {item.section}" if item.section else ""
            similarity_text = (
                f"{item.similarity:.3f}"
                if item.similarity is not None
                else "unavailable"
            )

            recommendations.append(
                InvestigationRecommendation(
                    recommendation_id=f"REC-{index:03d}",
                    action=(
                        f"Review the runbook '{item.title}'{section} "
                        "and validate its guidance against current "
                        "service telemetry."
                    ),
                    rationale=(
                        "This runbook was retrieved as operational "
                        f"guidance with similarity {similarity_text}. "
                        "Retrieval similarity does not guarantee that "
                        "every instruction applies to the current "
                        "incident."
                    ),
                    priority="HIGH",
                    evidence_ids=[item.evidence_id],
                    requires_human_approval=True,
                )
            )

        return recommendations

    def _calculate_severity(
        self,
        anomaly_evidence: list[EvidenceReference],
    ) -> SeverityLevel:
        """Use the highest severity actually present in ML evidence."""

        severities = [
            item.severity
            for item in anomaly_evidence
            if item.severity is not None
        ]

        if not severities:
            return SeverityLevel.LOW

        return max(
            severities,
            key=lambda severity: self.SEVERITY_ORDER[severity],
        )

    @staticmethod
    def _build_summary(
        report: UnifiedAnomalyReport,
        anomaly_evidence: list[EvidenceReference],
        all_evidence: list[EvidenceReference],
        hypotheses: list[InvestigationHypothesis],
        severity: SeverityLevel,
    ) -> str:
        """Build a concise evidence-based investigation summary."""

        metrics = sorted({
            item.metric_name
            for item in anomaly_evidence
            if item.metric_name
        })

        runbook_count = sum(
            item.evidence_type == "runbook"
            for item in all_evidence
        )

        incident_count = sum(
            item.evidence_type == "historical_incident"
            for item in all_evidence
        )

        metric_text = (
            ", ".join(metrics)
            if metrics
            else "multivariate anomalies"
        )

        return (
            f"Service '{report.service_id}' has "
            f"{len(anomaly_evidence)} anomalous ML evidence records. "
            f"Overall severity: {severity.value}. "
            f"Metrics involved: {metric_text}. "
            f"Generated {len(hypotheses)} unverified hypothesis(es). "
            f"Retrieved {incident_count} historical incident "
            f"chunk(s) and {runbook_count} runbook chunk(s). "
            "No causal relationship has been independently confirmed."
        )
