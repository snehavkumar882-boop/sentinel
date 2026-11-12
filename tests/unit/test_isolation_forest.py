"""Unit tests for the IsolationForestDetector."""

import tempfile
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from src.ml.isolation_forest import IsolationForestDetector
from src.ml.models import SeverityLevel


def test_fit_and_detect_on_clean_baseline() -> None:
    """Verify Isolation Forest trained on baseline flags synthetic out-of-distribution points."""
    rng = np.random.default_rng(42)

    # 100 normal observations across 3 metrics
    normal_data = pd.DataFrame(
        {
            "latency": rng.normal(100.0, 5.0, 100),
            "errors": rng.normal(1.0, 0.2, 100),
            "pool_wait": rng.normal(5.0, 1.0, 100),
        }
    )
    feature_cols = ["latency", "errors", "pool_wait"]

    detector = IsolationForestDetector(contamination=0.05, random_state=42)
    detector.fit(normal_data, feature_cols)

    # Test set: 20 normal points, then 10 severe anomaly points
    test_normal = pd.DataFrame(
        {
            "latency": rng.normal(100.0, 5.0, 20),
            "errors": rng.normal(1.0, 0.2, 20),
            "pool_wait": rng.normal(5.0, 1.0, 20),
        }
    )
    test_anomalies = pd.DataFrame(
        {
            "latency": [4000.0] * 10,
            "errors": [50.0] * 10,
            "pool_wait": [3000.0] * 10,
        }
    )
    test_combined = pd.concat([test_normal, test_anomalies], ignore_index=True)
    timestamps = pd.date_range("2026-09-28 08:00:00", periods=30, freq="1min")

    records = detector.predict_and_score(test_combined, pd.Series(timestamps))

    assert len(records) == 30

    # Normal points should have low anomaly scores
    for r in records[:20]:
        assert r.normalized_anomaly_score < 0.60

    # Anomalies should have high anomaly scores and be flagged
    for r in records[20:]:
        assert r.is_anomaly is True
        assert r.normalized_anomaly_score >= 0.70
        assert r.severity in (SeverityLevel.HIGH, SeverityLevel.CRITICAL)
        assert len(r.top_contributions) > 0


def test_deterministic_results_with_fixed_seed() -> None:
    """Verify identical random_state produces identical anomaly scores."""
    rng = np.random.default_rng(10)
    data = pd.DataFrame(
        {
            "m1": rng.normal(50.0, 5.0, 50),
            "m2": rng.normal(10.0, 1.0, 50),
        }
    )
    timestamps = pd.date_range("2026-09-28 08:00:00", periods=50, freq="1min")

    d1 = IsolationForestDetector(random_state=42).fit(data, ["m1", "m2"])
    r1 = d1.predict_and_score(data, pd.Series(timestamps))

    d2 = IsolationForestDetector(random_state=42).fit(data, ["m1", "m2"])
    r2 = d2.predict_and_score(data, pd.Series(timestamps))

    for rec1, rec2 in zip(r1, r2):
        assert rec1.raw_decision_score == rec2.raw_decision_score
        assert rec1.normalized_anomaly_score == rec2.normalized_anomaly_score
        assert rec1.is_anomaly == rec2.is_anomaly


def test_model_persistence_and_reload() -> None:
    """Verify saving and loading model produces identical predictions."""
    rng = np.random.default_rng(42)
    data = pd.DataFrame(
        {
            "m1": rng.normal(50.0, 5.0, 50),
            "m2": rng.normal(10.0, 1.0, 50),
        }
    )
    timestamps = pd.date_range("2026-09-28 08:00:00", periods=50, freq="1min")

    detector = IsolationForestDetector(random_state=42).fit(data, ["m1", "m2"])
    orig_records = detector.predict_and_score(data, pd.Series(timestamps))

    with tempfile.TemporaryDirectory() as tmp_dir:
        model_path = Path(tmp_dir) / "if_model.joblib"
        detector.save(model_path)

        loaded_detector = IsolationForestDetector.load(model_path)
        loaded_records = loaded_detector.predict_and_score(data, pd.Series(timestamps))

        for o, l in zip(orig_records, loaded_records):
            assert o.raw_decision_score == l.raw_decision_score
            assert o.normalized_anomaly_score == l.normalized_anomaly_score


def test_edge_cases_empty_and_insufficient_samples() -> None:
    """Verify appropriate exceptions for empty or insufficient baseline data."""
    detector = IsolationForestDetector()

    with pytest.raises(ValueError, match="Baseline DataFrame is empty"):
        detector.fit(pd.DataFrame(), ["m1"])

    with pytest.raises(ValueError, match="Insufficient baseline"):
        detector.fit(pd.DataFrame({"m1": [1.0, 2.0]}), ["m1"])
