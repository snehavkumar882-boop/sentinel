"""Isolation Forest anomaly detector trained strictly on normal baseline telemetry."""

from pathlib import Path
from typing import Dict, List, Optional
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

from src.ml.models import (
    FeatureContribution,
    MultivariateAnomalyRecord,
    SeverityLevel,
)


class IsolationForestDetector:
    """Multivariate anomaly detector based on scikit-learn's IsolationForest.

    Strictly trained only on normal baseline operational data to learn the nominal
    hyper-dimensional manifold of system telemetry.
    """

    def __init__(
        self,
        contamination: float = 0.05,
        random_state: int = 42,
        n_estimators: int = 100,
    ) -> None:
        self.contamination = contamination
        self.random_state = random_state
        self.n_estimators = n_estimators
        self.model: Optional[IsolationForest] = None
        self.feature_names: List[str] = []
        self.baseline_stats: Dict[str, Dict[str, float]] = {}

    def fit(self, baseline_df: pd.DataFrame, feature_cols: List[str]) -> "IsolationForestDetector":
        """Fit the Isolation Forest model on clean baseline data only.

        Args:
            baseline_df: DataFrame containing baseline observations.
            feature_cols: List of column names representing telemetry signals.
        """
        if baseline_df.empty:
            raise ValueError("Baseline DataFrame is empty. Cannot train Isolation Forest.")

        self.feature_names = list(feature_cols)
        X = baseline_df[self.feature_names].dropna().to_numpy(dtype=float)

        if len(X) < 10:
            raise ValueError(
                f"Insufficient baseline training samples ({len(X)} found, minimum 10 required)."
            )

        # Store baseline distributions for feature attribution
        self.baseline_stats = {}
        for col in self.feature_names:
            col_series = baseline_df[col].dropna()
            self.baseline_stats[col] = {
                "mean": float(col_series.mean()),
                "std": float(col_series.std()) if len(col_series) > 1 else 1.0,
            }

        self.model = IsolationForest(
            n_estimators=self.n_estimators,
            contamination=self.contamination,
            random_state=self.random_state,
            n_jobs=1,
        )
        self.model.fit(X)
        return self

    def predict_and_score(
        self,
        df: pd.DataFrame,
        timestamps: pd.Series,
    ) -> List[MultivariateAnomalyRecord]:
        """Evaluate observations and produce multivariate anomaly scores and feature attributions."""
        if self.model is None:
            raise RuntimeError("IsolationForestDetector must be fitted before predict_and_score.")

        X = df[self.feature_names].to_numpy(dtype=float)
        ts_list = pd.to_datetime(timestamps).tolist()

        # scikit-learn: lower decision_function = more anomalous. Negative means outlier.
        raw_scores = self.model.decision_function(X)
        preds = self.model.predict(X)  # -1 for anomaly, 1 for inlier

        records: List[MultivariateAnomalyRecord] = []

        for i in range(len(X)):
            raw_s = float(raw_scores[i])
            is_anomaly = bool(preds[i] == -1)
            ts = ts_list[i]
            row_vals = X[i]

            # Normalize raw decision function to [0.0, 1.0] where 1.0 is most anomalous.
            # Decision function typically spans [-0.35, +0.25].
            # Formula maps raw_s <= -0.30 to 1.0, raw_s >= 0.20 to 0.0.
            normalized_score = float(np.clip((0.20 - raw_s) / 0.50, 0.0, 1.0))

            # Compute per-feature deviation from baseline distribution
            feature_contributions = self._compute_feature_attributions(row_vals)

            if is_anomaly:
                if normalized_score >= 0.75:
                    severity = SeverityLevel.CRITICAL
                elif normalized_score >= 0.60:
                    severity = SeverityLevel.HIGH
                else:
                    severity = SeverityLevel.MEDIUM
            else:
                severity = SeverityLevel.LOW

            # Construct human-readable explanation
            if is_anomaly and feature_contributions:
                top_feat = feature_contributions[0]
                explanation = (
                    f"Multivariate anomaly detected (normalized score: {normalized_score:.2f}, "
                    f"raw decision: {raw_s:.3f}). Primary driver: {top_feat.feature_name} "
                    f"({top_feat.deviation_sigma:.1f}σ {top_feat.direction} baseline, "
                    f"weight: {top_feat.contribution_weight * 100:.1f}%)."
                )
            else:
                explanation = (
                    f"Nominal observation (normalized score: {normalized_score:.2f}, "
                    f"raw decision: {raw_s:.3f})."
                )

            records.append(
                MultivariateAnomalyRecord(
                    timestamp=ts,
                    raw_decision_score=round(raw_s, 4),
                    normalized_anomaly_score=round(normalized_score, 4),
                    is_anomaly=is_anomaly,
                    severity=severity,
                    top_contributions=feature_contributions,
                    explanation=explanation,
                )
            )

        return records

    def _compute_feature_attributions(self, row_vals: np.ndarray) -> List[FeatureContribution]:
        """Compute relative feature contributions to an observation's deviation from baseline."""
        deviations: List[Dict[str, Any]] = []
        total_abs_sigma = 0.0

        for idx, col in enumerate(self.feature_names):
            val = float(row_vals[idx])
            stats = self.baseline_stats.get(col, {"mean": 0.0, "std": 1.0})
            std = stats["std"] if stats["std"] > 1e-6 else 1e-6
            sigma = (val - stats["mean"]) / std
            abs_sigma = abs(sigma)
            total_abs_sigma += abs_sigma

            deviations.append(
                {
                    "name": col,
                    "abs_sigma": abs_sigma,
                    "sigma": sigma,
                    "direction": "above" if sigma >= 0 else "below",
                }
            )

        contributions: List[FeatureContribution] = []
        denom = total_abs_sigma if total_abs_sigma > 1e-6 else 1.0

        # Sort by absolute deviation descending
        deviations.sort(key=lambda d: d["abs_sigma"], reverse=True)

        for d in deviations:
            weight = d["abs_sigma"] / denom
            contributions.append(
                FeatureContribution(
                    feature_name=d["name"],
                    contribution_weight=round(weight, 4),
                    deviation_sigma=round(d["abs_sigma"], 2),
                    direction=d["direction"],
                )
            )

        return contributions

    def save(self, file_path: Path) -> None:
        """Persist fitted model and baseline statistics to disk."""
        file_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "model": self.model,
            "feature_names": self.feature_names,
            "baseline_stats": self.baseline_stats,
            "contamination": self.contamination,
            "random_state": self.random_state,
            "n_estimators": self.n_estimators,
        }
        joblib.dump(payload, file_path)

    @classmethod
    def load(cls, file_path: Path) -> "IsolationForestDetector":
        """Load a persisted model from disk."""
        payload = joblib.load(file_path)
        detector = cls(
            contamination=payload["contamination"],
            random_state=payload["random_state"],
            n_estimators=payload["n_estimators"],
        )
        detector.model = payload["model"]
        detector.feature_names = payload["feature_names"]
        detector.baseline_stats = payload["baseline_stats"]
        return detector
