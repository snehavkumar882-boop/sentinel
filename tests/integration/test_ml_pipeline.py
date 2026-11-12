
"""Integration tests for the complete ML anomaly detection pipeline."""

from datetime import timedelta

import pandas as pd

from src.data.synthetic_generator import (
    SyntheticScenarioConfig,
    SyntheticTelemetryGenerator,
)
from src.ml.pipeline import MLAnomalyPipeline


def test_pipeline_on_golden_path_telemetry() -> None:
    """Validate pipeline outputs against held-out synthetic ground truth."""

    config = SyntheticScenarioConfig(
        random_seed=42,
        duration_minutes=240,
    )

    data = SyntheticTelemetryGenerator(config).generate_all()

    df = pd.DataFrame(
        [
            {
                "timestamp": metric.timestamp,
                "metric_name": metric.metric_name,
                "metric_value": metric.metric_value,
            }
            for metric in data["metrics"]
        ]
    )

    pipeline = MLAnomalyPipeline(
        service_id=config.service_id,
        baseline_duration_minutes=100,
        z_threshold=3.0,
        contamination=0.05,
        random_state=42,
    )

    report = pipeline.run(df)

    # 1. Output structure
    assert report.service_id == "payment-api-service"
    assert report.total_time_points == 240
    assert report.univariate_anomalies_count > 0
    assert report.multivariate_anomalies_count > 0

    # 2. Primary incident signals
    top_signals = report.top_anomalous_metrics

    assert any(
        signal in top_signals[:4]
        for signal in [
            "http_5xx_rate",
            "db_connection_pool_wait_ms",
            "api_latency_p95_ms",
        ]
    )

    # 3. Negative controls
    assert "cpu_utilization_percent" not in top_signals[:4]
    assert "memory_utilization_percent" not in top_signals[:4]

    # 4. Correct held-out evaluation windows
    start_ts = report.analysis_window_start

    held_out_normal_minutes = (
        list(range(100, 120)) + list(range(160, 240))
    )
    incident_minutes = list(range(120, 155))

    held_out_normal_timestamps = {
        start_ts + timedelta(minutes=minute)
        for minute in held_out_normal_minutes
    }
    incident_timestamps = {
        start_ts + timedelta(minutes=minute)
        for minute in incident_minutes
    }

    predicted_anomaly_timestamps = {
        record.timestamp for record in report.multivariate_anomalies
    }

    # 5. Confusion matrix counts
    true_positives = len(
        predicted_anomaly_timestamps & incident_timestamps
    )
    false_positives = len(
        predicted_anomaly_timestamps & held_out_normal_timestamps
    )
    false_negatives = len(incident_timestamps) - true_positives
    true_negatives = len(held_out_normal_timestamps) - false_positives

    recall = true_positives / len(incident_timestamps)
    false_positive_rate = (
        false_positives / len(held_out_normal_timestamps)
    )

    # The incident contains exactly 35 minutes: 120 through 154.
    assert len(incident_timestamps) == 35
    assert len(held_out_normal_timestamps) == 100

    # 6. Detection quality
    assert recall >= 0.85
    assert false_positive_rate <= 0.08

    # 7. Detection latency
    first_flagged = min(
        (
            timestamp
            for timestamp in predicted_anomaly_timestamps
            if timestamp in incident_timestamps
        ),
        default=None,
    )

    assert first_flagged is not None

    incident_start = start_ts + timedelta(minutes=120)
    latency_minutes = int(
        (first_flagged - incident_start).total_seconds() // 60
    )

    assert latency_minutes <= 1

    # 8. Confusion matrix sanity checks
    assert true_positives + false_negatives == 35
    assert true_negatives + false_positives == 100

    # 9. Correlation verification
    correlation_lookup = {
        (correlation.metric_a, correlation.metric_b): correlation.pearson_r
        for correlation in report.top_correlations
    }

    for correlation in report.top_correlations:
        correlation_lookup[
            (correlation.metric_b, correlation.metric_a)
        ] = correlation.pearson_r

    pair_key = ("db_connection_pool_wait_ms", "http_5xx_rate")

    assert pair_key in correlation_lookup
    assert correlation_lookup[pair_key] > 0.80
