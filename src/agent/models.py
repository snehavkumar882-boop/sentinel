
"""Structured data models for Sentinel's investigation agent."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from src.ml.models import SeverityLevel, UnifiedAnomalyReport


EvidenceType = Literal[
    "ml_anomaly",
    "ml_correlation",
    "ml_lag",
    "runbook",
    "historical_incident",
]

ConfidenceLevel = Literal["LOW", "MODERATE", "HIGH"]

InvestigationStatus = Literal[
    "NO_ANOMALY",
    "INVESTIGATION_REQUIRED",
    "INVESTIGATION_INCOMPLETE",
]


class EvidenceReference(BaseModel):
    """A traceable piece of evidence used during an investigation."""

    evidence_id: str
    evidence_type: EvidenceType
    title: str
    content: str

    source_path: str | None = None
    document_id: str | None = None
    chunk_id: str | None = None
    section: str | None = None
    similarity: float | None = Field(default=None, ge=0.0, le=1.0)

    metric_name: str | None = None
    observed_value: float | None = None
    expected_value: float | None = None
    severity: SeverityLevel | None = None

    timestamp: datetime | None = None


class InvestigationFinding(BaseModel):
    """An observation directly supported by collected evidence."""

    finding_id: str
    title: str
    description: str
    evidence_ids: list[str] = Field(default_factory=list)

    finding_type: Literal[
        "ANOMALY",
        "CORRELATION",
        "TEMPORAL_PATTERN",
        "HISTORICAL_MATCH",
        "RUNBOOK_GUIDANCE",
    ]


class InvestigationHypothesis(BaseModel):
    """A possible explanation that must not be mistaken for confirmed cause."""

    hypothesis_id: str
    title: str
    explanation: str

    confidence_level: ConfidenceLevel = Field(
        description=(
            "Qualitative evidence-strength assessment, not a calibrated "
            "probability or statistical confidence interval."
        )
    )

    supporting_evidence_ids: list[str] = Field(default_factory=list)
    contradicting_evidence_ids: list[str] = Field(default_factory=list)

    causal_status: Literal[
        "UNVERIFIED",
        "PARTIALLY_SUPPORTED",
        "VERIFIED_EXTERNALLY",
    ] = "UNVERIFIED"


class InvestigationRecommendation(BaseModel):
    """An operational recommendation linked to supporting evidence."""

    recommendation_id: str
    action: str
    rationale: str

    priority: Literal["LOW", "MEDIUM", "HIGH", "URGENT"]

    evidence_ids: list[str] = Field(default_factory=list)

    requires_human_approval: bool = True


class InvestigationReport(BaseModel):
    """Complete structured output from the Sentinel investigation agent."""

    investigation_id: str
    service_id: str

    status: InvestigationStatus
    started_at: datetime
    completed_at: datetime

    overall_severity: SeverityLevel | None = None

    summary: str

    findings: list[InvestigationFinding] = Field(default_factory=list)
    hypotheses: list[InvestigationHypothesis] = Field(default_factory=list)
    evidence: list[EvidenceReference] = Field(default_factory=list)
    recommendations: list[InvestigationRecommendation] = Field(
        default_factory=list
    )

    source_documents_consulted: list[str] = Field(default_factory=list)

    limitations: list[str] = Field(default_factory=list)

    causation_confirmed: bool = Field(
        default=False,
        description=(
            "True only when independent external verification establishes "
            "causation. Correlation and retrieval similarity alone are "
            "insufficient."
        ),
    )


class InvestigationRequest(BaseModel):
    """Input contract for a Sentinel investigation."""

    anomaly_report: UnifiedAnomalyReport

    max_knowledge_results: int = Field(
        default=5,
        ge=1,
        le=20,
    )

    include_runbooks: bool = True
    include_historical_incidents: bool = True
