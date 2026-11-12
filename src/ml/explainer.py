"""Feature attribution and explainability for anomaly scores."""

from typing import Dict, List
import numpy as np
import pandas as pd

from src.ml.models import FeatureContribution


class FeatureAttributionExplainer:
    """Interpretable feature attribution based on standardized baseline deviations.

    Quantifies the degree and proportion to which each telemetry signal drives an anomaly.
    """

    def __init__(self, baseline_stats: Dict[str, Dict[str, float]]) -> None:
        """Initialize explainer with pre-computed baseline distributions.

        Args:
            baseline_stats: Dictionary mapping feature_name -> {"mean": float, "std": float}
        """
        self.baseline_stats = baseline_stats

    def explain_observation(self, observation: pd.Series) -> List[FeatureContribution]:
        """Explain an individual observation vector."""
        contributions: List[Dict[str, Any]] = []
        total_abs_sigma = 0.0

        for col, val in observation.items():
            col_name = str(col)
            val_float = float(val)

            stats = self.baseline_stats.get(col_name, {"mean": 0.0, "std": 1.0})
            mean = stats["mean"]
            std = stats["std"] if stats["std"] > 1e-6 else 1e-6

            sigma = (val_float - mean) / std
            abs_sigma = abs(sigma)
            total_abs_sigma += abs_sigma

            contributions.append(
                {
                    "name": col_name,
                    "abs_sigma": abs_sigma,
                    "sigma": sigma,
                    "direction": "above" if sigma >= 0 else "below",
                }
            )

        denom = total_abs_sigma if total_abs_sigma > 1e-6 else 1.0
        contributions.sort(key=lambda c: c["abs_sigma"], reverse=True)

        results: List[FeatureContribution] = []
        for c in contributions:
            weight = c["abs_sigma"] / denom
            results.append(
                FeatureContribution(
                    feature_name=c["name"],
                    contribution_weight=round(weight, 4),
                    deviation_sigma=round(c["abs_sigma"], 2),
                    direction=c["direction"],
                )
            )

        return results

    def aggregate_window_attributions(self, window_df: pd.DataFrame) -> List[FeatureContribution]:
        """Aggregate feature contributions across a multi-point time window (e.g. incident window)."""
        if window_df.empty:
            return []

        feature_cols = [c for c in window_df.columns if c in self.baseline_stats]
        if not feature_cols:
            return []

        avg_abs_sigmas: Dict[str, float] = {}
        directions: Dict[str, str] = {}

        for col in feature_cols:
            stats = self.baseline_stats[col]
            mean = stats["mean"]
            std = stats["std"] if stats["std"] > 1e-6 else 1e-6

            vals = window_df[col].dropna().to_numpy(dtype=float)
            if len(vals) == 0:
                continue

            sigmas = (vals - mean) / std
            mean_sigma = float(np.mean(sigmas))
            avg_abs_sigmas[col] = float(np.mean(np.abs(sigmas)))
            directions[col] = "above" if mean_sigma >= 0 else "below"

        total = sum(avg_abs_sigmas.values())
        denom = total if total > 1e-6 else 1.0

        sorted_cols = sorted(avg_abs_sigmas.keys(), key=lambda k: avg_abs_sigmas[k], reverse=True)

        results: List[FeatureContribution] = []
        for col in sorted_cols:
            results.append(
                FeatureContribution(
                    feature_name=col,
                    contribution_weight=round(avg_abs_sigmas[col] / denom, 4),
                    deviation_sigma=round(avg_abs_sigmas[col], 2),
                    direction=directions[col],
                )
            )

        return results
