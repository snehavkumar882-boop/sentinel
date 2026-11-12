"""Unit tests for the RollingZScoreDetector."""

import numpy as np
import pandas as pd
import pytest

from src.ml.models import SeverityLevel
from src.ml.statistical import RollingZScoreDetector


def test_baseline_computation() -> None:
    """Verify baseline statistical summary computation."""
    detector = RollingZScoreDetector()
    series = pd.Series([10.0, 12.0, 10.5, 11.5, 11.0])
    baseline = detector.compute_baseline(series, "test_metric")

    assert baseline.metric_name == "test_metric"
    assert baseline.sample_count == 5
    assert 10.5 < baseline.mean < 11.5
    assert baseline.std > 0.0
    assert baseline.min_value == 10.0
    assert baseline.max_value == 12.0


def test_normal_baseline_produces_no_anomalies() -> None:
    """Verify clean gaussian noise around baseline produces no anomalies with Z >= 3.0."""
    rng = np.random.default_rng(42)
    values = pd.Series(rng.normal(loc=100.0, scale=2.0, size=60))
    timestamps = pd.date_range("2026-09-28 08:00:00", periods=60, freq="1min")

    detector = RollingZScoreDetector(window_size=20, z_threshold=3.0)
    baseline = detector.compute_baseline(values.iloc[:30], "test_metric")
    records = detector.detect(values, pd.Series(timestamps), "test_metric", baseline=baseline)

    assert len(records) == 60
    anomalies = [r for r in records if r.is_anomaly]
    # Normal baseline should have low anomaly scores with no critical or high severity false alarms
    assert len(anomalies) <= 1
    assert all(r.severity not in (SeverityLevel.HIGH, SeverityLevel.CRITICAL) for r in records)
    assert all(r.anomaly_score < 3.5 for r in records)


def test_spike_detection_and_severity() -> None:
    """Verify that a sudden 6-sigma spike is detected with CRITICAL severity."""
    values = pd.Series([10.0] * 30 + [75.0] + [10.0] * 10)
    timestamps = pd.date_range("2026-09-28 08:00:00", periods=41, freq="1min")

    detector = RollingZScoreDetector(window_size=15, z_threshold=3.0)
    baseline = detector.compute_baseline(values.iloc[:20], "test_metric")
    records = detector.detect(values, pd.Series(timestamps), "test_metric", baseline=baseline)

    spike_record = records[30]
    assert spike_record.observed_value == 75.0
    assert spike_record.is_anomaly is True
    assert spike_record.severity == SeverityLevel.CRITICAL
    assert spike_record.anomaly_score > 4.5


def test_zero_variance_constant_series() -> None:
    """Verify detector handles constant values without zero-division errors."""
    values = pd.Series([42.0] * 30)
    timestamps = pd.date_range("2026-09-28 08:00:00", periods=30, freq="1min")

    detector = RollingZScoreDetector(epsilon=1e-6)
    records = detector.detect(values, pd.Series(timestamps), "constant_metric")

    assert len(records) == 30
    for r in records:
        assert r.is_anomaly is False
        assert not np.isnan(r.anomaly_score)


def test_missing_values_and_empty_series() -> None:
    """Verify detector handles NaNs and empty series gracefully."""
    detector = RollingZScoreDetector()

    # Empty series
    records = detector.detect(pd.Series([], dtype=float), pd.Series([], dtype=str), "empty")
    assert records == []

    # Series with NaNs
    values = pd.Series([10.0, np.nan, 12.0, 11.0, np.nan])
    timestamps = pd.date_range("2026-09-28 08:00:00", periods=5, freq="1min")
    records = detector.detect(values, pd.Series(timestamps), "nan_metric")
    # NaNs should be skipped
    assert len(records) == 3
