"""Typed data models for the SENTINEL Machine Learning Engine."""

from datetime import datetime
from enum import Enum
from typing import Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class SeverityLevel(str, Enum):
    """Categorized severity for an anomaly."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class DetectionMethod(str, Enum):
    """Algorithm that identified the anomaly."""
    STATISTICAL_ZSCORE = "STATISTICAL_ZSCORE"
    ISOLATION_FOREST = "ISOLATION_FOREST"
    ENSEMBLE = "ENSEMBLE"


class MetricBaseline(BaseModel):
    """Statistical summary of a metric during the baseline period."""
    metric_name: str
    mean: float
    std: float
    min_value: float
    max_value: float
    sample_count: int


class AnomalyRecord(BaseModel):
    """Record of an individual metric anomaly evaluation."""
    metric_name: str
    timestamp: datetime
    observed_value: float
    expected_value: float
    anomaly_score: float = Field(
        description="Standardized anomaly score (absolute z-score or normalized anomaly metric)"
    )
    detection_method: DetectionMethod
    severity: SeverityLevel
    is_anomaly: bool
    explanation: str


class FeatureContribution(BaseModel):
    """Attribution of a single feature to a multivariate anomaly."""
    feature_name: str
    contribution_weight: float = Field(
        ge=0.0, le=1.0, description="Normalized relative contribution to the anomaly (0.0 to 1.0)"
    )
    deviation_sigma: float = Field(
        description="Number of standard deviations deviated from the baseline mean"
    )
    direction: Literal["above", "below"]


class MultivariateAnomalyRecord(BaseModel):
    """Multivariate anomaly evaluation produced by Isolation Forest."""
    timestamp: datetime
    raw_decision_score: float = Field(
        description="Raw scikit-learn decision function score (negative indicates anomaly)"
    )
    normalized_anomaly_score: float = Field(
        ge=0.0, le=1.0, description="Normalized score where 0.0 is normal and 1.0 is extreme anomaly"
    )
    is_anomaly: bool
    severity: SeverityLevel
    top_contributions: List[FeatureContribution] = Field(default_factory=list)
    explanation: str


class CorrelationPair(BaseModel):
    """Pairwise correlation metric result."""
    metric_a: str
    metric_b: str
    pearson_r: float = Field(ge=-1.0, le=1.0)
    spearman_rho: float = Field(ge=-1.0, le=1.0)
    abs_correlation: float = Field(ge=0.0, le=1.0)
    p_value: float = Field(ge=0.0, le=1.0)


class LaggedRelationship(BaseModel):
    """Cross-correlation relationship with lead-lag temporal shift."""
    lead_metric: str
    lag_metric: str
    optimal_lag_minutes: int = Field(
        description="Positive if lead_metric changes before lag_metric; negative if vice versa"
    )
    max_cross_correlation: float = Field(ge=-1.0, le=1.0)
    interpretation: str
    causation_disclaimer: str = (
        "Statistical Note: Temporal precedence and cross-correlation reflect empirical dynamics "
        "but do NOT prove causation or constitute mathematical proof of causal determination."
    )


class UnifiedAnomalyReport(BaseModel):
    """Comprehensive analytical report produced by the ML analysis pipeline."""
    service_id: str
    analysis_window_start: datetime
    analysis_window_end: datetime
    total_time_points: int
    univariate_anomalies_count: int
    multivariate_anomalies_count: int
    top_anomalous_metrics: List[str]
    univariate_anomalies: List[AnomalyRecord]
    multivariate_anomalies: List[MultivariateAnomalyRecord]
    top_correlations: List[CorrelationPair]
    lagged_relationships: List[LaggedRelationship]
    metric_baselines: Dict[str, MetricBaseline]
    summary_narrative: str
