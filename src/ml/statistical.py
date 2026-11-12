"""Statistical Anomaly Detector using rolling window baselines and Z-scores."""

from datetime import datetime
from typing import List, Optional
import numpy as np
import pandas as pd

from src.ml.models import AnomalyRecord, DetectionMethod, MetricBaseline, SeverityLevel


class RollingZScoreDetector:
    """Detects metric anomalies using rolling window statistics and adaptive Z-scores.

    A backward-looking window [t-W, t-1] is used to prevent the current observation
    from contaminating its own reference distribution.
    """

    def __init__(
        self,
        window_size: int = 20,
        z_threshold: float = 3.0,
        min_periods: int = 5,
        epsilon: float = 1e-6,
    ) -> None:
        self.window_size = window_size
        self.z_threshold = z_threshold
        self.min_periods = min_periods
        self.epsilon = epsilon

    def compute_baseline(self, values: pd.Series, metric_name: str) -> MetricBaseline:
        """Compute the statistical summary of a clean baseline period."""
        clean_values = values.dropna()
        if len(clean_values) == 0:
            return MetricBaseline(
                metric_name=metric_name,
                mean=0.0,
                std=0.0,
                min_value=0.0,
                max_value=0.0,
                sample_count=0,
            )

        mean_val = float(clean_values.mean())
        std_val = float(clean_values.std()) if len(clean_values) > 1 else 0.0

        return MetricBaseline(
            metric_name=metric_name,
            mean=round(mean_val, 4),
            std=round(std_val, 4),
            min_value=round(float(clean_values.min()), 4),
            max_value=round(float(clean_values.max()), 4),
            sample_count=len(clean_values),
        )

    def detect(
        self,
        values: pd.Series,
        timestamps: pd.Series,
        metric_name: str,
        baseline: Optional[MetricBaseline] = None,
    ) -> List[AnomalyRecord]:
        """Detect anomalies across the given time-series.

        Args:
            values: Series of numerical metric values.
            timestamps: Series of corresponding timestamps.
            metric_name: Identifier for the metric.
            baseline: Optional global baseline for fallback and expected values.
        """
        records: List[AnomalyRecord] = []
        n = len(values)
        if n == 0:
            return records

        vals_arr = values.to_numpy(dtype=float)
        ts_arr = pd.to_datetime(timestamps).tolist()

        # Compute rolling statistics over past values using shift(1) to avoid target leakage
        shifted = values.shift(1)
        rolling_mean = shifted.rolling(window=self.window_size, min_periods=self.min_periods).mean()
        rolling_std = shifted.rolling(window=self.window_size, min_periods=self.min_periods).std()

        fallback_mean = baseline.mean if baseline else float(np.nanmean(vals_arr))
        fallback_std = baseline.std if baseline and baseline.std > 0 else float(np.nanstd(vals_arr))
        if fallback_std <= 0:
            fallback_std = self.epsilon

        for i in range(n):
            obs_val = vals_arr[i]
            ts = ts_arr[i]

            if np.isnan(obs_val):
                continue

            r_mean = rolling_mean.iloc[i]
            r_std = rolling_std.iloc[i]

            # Use rolling stats if available and non-zero, otherwise fallback to baseline
            exp_val = r_mean if not np.isnan(r_mean) else fallback_mean
            denom_std = r_std if (not np.isnan(r_std) and r_std > self.epsilon) else fallback_std

            # Prevent denominator collapse when local rolling variance is artificially narrow
            if baseline and baseline.std > self.epsilon:
                denom_std = max(denom_std, baseline.std * 0.80)

            z_score = (obs_val - exp_val) / denom_std
            abs_z = abs(z_score)

            is_anomaly = bool(abs_z >= self.z_threshold)

            # Classify severity
            if abs_z >= 4.5:
                severity = SeverityLevel.CRITICAL
            elif abs_z >= 3.5:
                severity = SeverityLevel.HIGH
            elif abs_z >= 3.0:
                severity = SeverityLevel.MEDIUM
            else:
                severity = SeverityLevel.LOW

            direction = "above" if z_score > 0 else "below"
            explanation = (
                f"Observed value {obs_val:.2f} is {abs_z:.2f} standard deviations {direction} "
                f"expected reference mean {exp_val:.2f} (threshold: {self.z_threshold}σ)."
            )

            records.append(
                AnomalyRecord(
                    metric_name=metric_name,
                    timestamp=ts,
                    observed_value=round(obs_val, 4),
                    expected_value=round(exp_val, 4),
                    anomaly_score=round(abs_z, 4),
                    detection_method=DetectionMethod.STATISTICAL_ZSCORE,
                    severity=severity,
                    is_anomaly=is_anomaly,
                    explanation=explanation,
                )
            )

        return records
