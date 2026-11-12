"""Unified ML Anomaly Analysis Pipeline for SENTINEL."""

from datetime import datetime
from typing import Dict, List, Optional
import numpy as np
import pandas as pd

from src.ml.correlation import LaggedCorrelationAnalyzer, MetricCorrelationAnalyzer
from src.ml.explainer import FeatureAttributionExplainer
from src.ml.isolation_forest import IsolationForestDetector
from src.ml.models import (
    AnomalyRecord,
    CorrelationPair,
    LaggedRelationship,
    MetricBaseline,
    MultivariateAnomalyRecord,
    UnifiedAnomalyReport,
)
from src.ml.statistical import RollingZScoreDetector


class MLAnomalyPipeline:
    """Orchestrates end-to-end telemetry preprocessing, statistical anomaly detection,

    Isolation Forest inference, cross-correlation, lead-lag analysis, and attribution.
    """

    def __init__(
        self,
        service_id: str = "payment-api-service",
        baseline_duration_minutes: int = 100,
        z_threshold: float = 3.0,
        contamination: float = 0.05,
        random_state: int = 42,
        max_lag_minutes: int = 10,
    ) -> None:
        self.service_id = service_id
        self.baseline_duration_minutes = baseline_duration_minutes
        self.z_threshold = z_threshold
        self.contamination = contamination
        self.random_state = random_state
        self.max_lag_minutes = max_lag_minutes

        self.statistical_detector = RollingZScoreDetector(z_threshold=z_threshold)
        self.isolation_forest = IsolationForestDetector(
            contamination=contamination,
            random_state=random_state,
        )

    def run(
        self,
        telemetry_df: pd.DataFrame,
        feature_cols: Optional[List[str]] = None,
    ) -> UnifiedAnomalyReport:
        """Execute the end-to-end ML analysis pipeline.

        Args:
            telemetry_df: DataFrame in long format (timestamp, metric_name, metric_value)
                          or wide format (index=timestamp, columns=metrics).
            feature_cols: Explicit list of metric names to evaluate (optional).
        """
        # 1. Preprocessing
        wide_df = self._preprocess_to_wide(telemetry_df)
        if feature_cols:
            cols = [c for c in feature_cols if c in wide_df.columns]
        else:
            cols = [c for c in wide_df.columns if c != "timestamp"]

        if not cols:
            raise ValueError("No valid numerical metric columns found in telemetry data.")

        timestamps = wide_df["timestamp"] if "timestamp" in wide_df.columns else wide_df.index
        timestamps_series = pd.Series(pd.to_datetime(timestamps))

        # 2. Baseline Calculation
        baseline_split_idx = min(self.baseline_duration_minutes, len(wide_df) // 2)
        baseline_df = wide_df[cols].iloc[:baseline_split_idx]

        baselines: Dict[str, MetricBaseline] = {}
        baseline_stats_dict: Dict[str, Dict[str, float]] = {}
        for col in cols:
            base = self.statistical_detector.compute_baseline(baseline_df[col], col)
            baselines[col] = base
            baseline_stats_dict[col] = {"mean": base.mean, "std": base.std}

        # 3. Statistical Anomaly Detection (Univariate)
        all_univariate_records: List[AnomalyRecord] = []
        metric_anomaly_counts: Dict[str, int] = {c: 0 for c in cols}

        for col in cols:
            records = self.statistical_detector.detect(
                values=wide_df[col],
                timestamps=timestamps_series,
                metric_name=col,
                baseline=baselines[col],
            )
            all_univariate_records.extend(records)
            metric_anomaly_counts[col] = sum(1 for r in records if r.is_anomaly)

        # 4. Multivariate Isolation Forest
        self.isolation_forest.fit(baseline_df=baseline_df, feature_cols=cols)
        multivariate_records = self.isolation_forest.predict_and_score(
            df=wide_df[cols],
            timestamps=timestamps_series,
        )

        # 5. Metric Correlation Analysis
        correlations = MetricCorrelationAnalyzer.compute_pairwise_correlations(
            df=wide_df[cols],
            feature_cols=cols,
        )

        # 6. Lead-Lag Cross-Correlation Analysis
        lagged_relationships: List[LaggedRelationship] = []
        # Target high-interest pairs if present
        key_pairs = [
            ("db_connection_pool_wait_ms", "http_5xx_rate"),
            ("db_connection_pool_wait_ms", "api_latency_p95_ms"),
            ("api_latency_p95_ms", "http_5xx_rate"),
            ("cpu_utilization_percent", "http_5xx_rate"),
        ]
        for name_a, name_b in key_pairs:
            if name_a in wide_df.columns and name_b in wide_df.columns:
                lag_rel = LaggedCorrelationAnalyzer.analyze_lag(
                    series_a=wide_df[name_a],
                    series_b=wide_df[name_b],
                    name_a=name_a,
                    name_b=name_b,
                    max_lag=self.max_lag_minutes,
                )
                lagged_relationships.append(lag_rel)

        # 7. Feature Attribution & Ranking
        top_anomalous_metrics = sorted(
            [c for c in cols if metric_anomaly_counts[c] > 0],
            key=lambda c: metric_anomaly_counts[c],
            reverse=True,
        )

        # 8. Unified Anomaly Report Synthesis
        total_time_points = len(wide_df)
        univariate_anomaly_count = sum(1 for r in all_univariate_records if r.is_anomaly)
        multivariate_anomaly_count = sum(1 for r in multivariate_records if r.is_anomaly)

        summary_narrative = self._generate_summary_narrative(
            top_anomalous_metrics=top_anomalous_metrics,
            multivariate_count=multivariate_anomaly_count,
            correlations=correlations,
            lagged_relationships=lagged_relationships,
            metric_anomaly_counts=metric_anomaly_counts,
        )

        start_ts = pd.to_datetime(timestamps_series.iloc[0]).to_pydatetime()
        end_ts = pd.to_datetime(timestamps_series.iloc[-1]).to_pydatetime()

        return UnifiedAnomalyReport(
            service_id=self.service_id,
            analysis_window_start=start_ts,
            analysis_window_end=end_ts,
            total_time_points=total_time_points,
            univariate_anomalies_count=univariate_anomaly_count,
            multivariate_anomalies_count=multivariate_anomaly_count,
            top_anomalous_metrics=top_anomalous_metrics,
            univariate_anomalies=[r for r in all_univariate_records if r.is_anomaly],
            multivariate_anomalies=[r for r in multivariate_records if r.is_anomaly],
            top_correlations=correlations[:10],
            lagged_relationships=lagged_relationships,
            metric_baselines=baselines,
            summary_narrative=summary_narrative,
        )

    def _preprocess_to_wide(self, df: pd.DataFrame) -> pd.DataFrame:
        """Convert long format telemetry (timestamp, metric_name, metric_value) to wide format."""
        if "metric_name" in df.columns and "metric_value" in df.columns:
            pivoted = df.pivot_table(
                index="timestamp",
                columns="metric_name",
                values="metric_value",
                aggfunc="mean",
            ).reset_index()
            pivoted["timestamp"] = pd.to_datetime(pivoted["timestamp"])
            pivoted = pivoted.sort_values("timestamp").reset_index(drop=True)
            # Impute any sporadic missing values with forward fill then backward fill
            return pivoted.ffill().bfill()
        else:
            res = df.copy()
            if "timestamp" in res.columns:
                res["timestamp"] = pd.to_datetime(res["timestamp"])
                res = res.sort_values("timestamp").reset_index(drop=True)
            return res.ffill().bfill()

    def _generate_summary_narrative(
        self,
        top_anomalous_metrics: List[str],
        multivariate_count: int,
        correlations: List[CorrelationPair],
        lagged_relationships: List[LaggedRelationship],
        metric_anomaly_counts: Dict[str, int],
    ) -> str:
        """Generate human-readable summary of statistical and model findings."""
        if not top_anomalous_metrics:
            return "No anomalous behavior detected across monitored telemetry signals."

        lines = [
            f"Anomaly Detection Summary for {self.service_id}:",
            f"- Identified {multivariate_count} multivariate anomaly periods using Isolation Forest.",
            f"- Top anomalous signals by frequency: {', '.join(top_anomalous_metrics[:4])}.",
        ]

        # Top correlation
        if correlations:
            top_corr = correlations[0]
            lines.append(
                f"- Strongest empirical correlation: {top_corr.metric_a} <-> {top_corr.metric_b} "
                f"(Pearson r = {top_corr.pearson_r:.3f}, p = {top_corr.p_value:.2e})."
            )

        # Lag relationship
        for lag in lagged_relationships:
            if abs(lag.max_cross_correlation) > 0.70:
                lines.append(f"- Temporal pattern: {lag.interpretation}")

        # Negative control check
        cpu_anomalies = metric_anomaly_counts.get("cpu_utilization_percent", 0)
        mem_anomalies = metric_anomaly_counts.get("memory_utilization_percent", 0)
        if cpu_anomalies == 0 and mem_anomalies == 0:
            lines.append(
                "- Negative Controls Verified: CPU and Memory utilization remained within normal bounds "
                "throughout the anomaly window, indicating compute/memory starvation is not a primary driver."
            )

        lines.append(
            "- Disclaimer: Empirical cross-correlations and lead-lag timing identify relational signals "
            "but do not confirm causality without architectural verification."
        )

        return "\n".join(lines)
