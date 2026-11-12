
"""Run Sentinel ML anomaly analysis and evaluate the synthetic incident."""

import sys
from datetime import timedelta
from pathlib import Path

import pandas as pd

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config.logging_config import get_logger, setup_logging
from src.data.repository import TelemetryRepository
from src.database.session import get_db_session, get_engine
from src.ml.pipeline import MLAnomalyPipeline


def safe_ratio(numerator: int, denominator: int) -> float:
    """Return a ratio safely when the denominator may be zero."""
    return numerator / denominator if denominator else 0.0


def main() -> None:
    setup_logging(log_level="INFO")
    logger = get_logger("sentinel.ml_runner")

    logger.info("Loading telemetry data for analysis...")
    engine = get_engine()

    with get_db_session(engine) as session:
        repo = TelemetryRepository(session)
        service = repo.get_service("payment-api-service")

        if not service:
            logger.error(
                "Service 'payment-api-service' not found in database. "
                "Seed data first."
            )
            sys.exit(1)

        service_id = service.id
        metrics = repo.get_metrics("payment-api-service")

        metric_rows = [
            {
                "timestamp": metric.timestamp,
                "metric_name": metric.metric_name,
                "metric_value": metric.metric_value,
            }
            for metric in metrics
        ]

    logger.info(
        "Loaded %s telemetry records for service %s.",
        len(metric_rows),
        service_id,
    )

    if not metric_rows:
        logger.error("No telemetry records were found.")
        sys.exit(1)

    df = pd.DataFrame(metric_rows)

    logger.info("Running ML Anomaly Detection Pipeline...")

    pipeline = MLAnomalyPipeline(
        service_id=service_id,
        baseline_duration_minutes=100,
        z_threshold=3.0,
        contamination=0.05,
        random_state=42,
    )

    report = pipeline.run(df)

    print("\n" + "=" * 70)
    print("SENTINEL ML ANOMALY ENGINE - ANALYSIS REPORT")
    print("=" * 70)
    print(f"Service:                {report.service_id}")
    print(
        f"Analysis Window:        {report.analysis_window_start} "
        f"-> {report.analysis_window_end}"
    )
    print(
        f"Total Observations:     {report.total_time_points} "
        "(1-minute intervals)"
    )
    print(
        f"Univariate Anomalies:   "
        f"{report.univariate_anomalies_count}"
    )
    print(
        f"Multivariate Anomalies: "
        f"{report.multivariate_anomalies_count}"
    )
    print(
        f"Top Anomalous Signals:  "
        f"{', '.join(report.top_anomalous_metrics[:5])}"
    )

    print("\n" + "-" * 70)
    print("STRONGEST EMPIRICAL CORRELATIONS (TOP 5)")
    print("-" * 70)

    for pair in report.top_correlations[:5]:
        print(
            f"  {pair.metric_a:<28} <-> {pair.metric_b:<28} "
            f"| r={pair.pearson_r:+.4f} "
            f"(p={pair.p_value:.2e})"
        )

    print("\n" + "-" * 70)
    print("LEAD-LAG CROSS-CORRELATION DYNAMICS")
    print("-" * 70)

    for relationship in report.lagged_relationships:
        print(
            f"  {relationship.lead_metric} -> "
            f"{relationship.lag_metric} "
            f"(lag={relationship.optimal_lag_minutes}m, "
            f"r={relationship.max_cross_correlation:.3f})"
        )
        print(f"    {relationship.interpretation}")

    # The ground-truth windows below correspond to the synthetic
    # generator's 240-minute scenario.
    if report.total_time_points != 240:
        logger.warning(
            "Skipping synthetic ground-truth evaluation: expected "
            "240 time points, received %s.",
            report.total_time_points,
        )
        print("\nGround-truth evaluation skipped.")
        print("This evaluation requires the 240-minute synthetic scenario.")
        return

    start_ts = report.analysis_window_start

    # Evaluation excludes the training baseline and recovery period.
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

    true_positives = len(
        predicted_anomaly_timestamps & incident_timestamps
    )
    false_positives = len(
        predicted_anomaly_timestamps & held_out_normal_timestamps
    )
    false_negatives = len(incident_timestamps) - true_positives
    true_negatives = len(held_out_normal_timestamps) - false_positives

    total_evaluated = (
        len(incident_timestamps) + len(held_out_normal_timestamps)
    )

    accuracy = safe_ratio(
        true_positives + true_negatives,
        total_evaluated,
    )
    precision = safe_ratio(
        true_positives,
        true_positives + false_positives,
    )
    recall = safe_ratio(
        true_positives,
        true_positives + false_negatives,
    )
    f1_score = safe_ratio(
        2 * true_positives,
        2 * true_positives + false_positives + false_negatives,
    )
    false_positive_rate = safe_ratio(
        false_positives,
        false_positives + true_negatives,
    )

    normal_f1 = safe_ratio(
        2 * true_negatives,
        2 * true_negatives + false_positives + false_negatives,
    )
    macro_f1 = (normal_f1 + f1_score) / 2

    first_detected = min(
        (
            timestamp
            for timestamp in predicted_anomaly_timestamps
            if timestamp in incident_timestamps
        ),
        default=None,
    )

    detection_latency = (
        int((first_detected - (start_ts + timedelta(minutes=120)))
            .total_seconds() // 60)
        if first_detected is not None
        else -1
    )

    print("\n" + "=" * 70)
    print("HELD-OUT GROUND-TRUTH EVALUATION")
    print("=" * 70)
    print("Training baseline:       Minutes 0-99")
    print("Held-out normal:         Minutes 100-119 and 160-239")
    print("Incident:                Minutes 120-154")
    print("Excluded recovery:       Minutes 155-159")
    print(f"Evaluation observations: {total_evaluated}")
    print()

    print("CLASSIFICATION METRICS")
    print("-" * 70)
    print(f"Accuracy:                {accuracy:.4f} ({accuracy * 100:.2f}%)")
    print(f"Precision:               {precision:.4f}")
    print(f"Recall:                  {recall:.4f}")
    print(f"F1-score:                {f1_score:.4f}")
    print(f"Macro-F1:                {macro_f1:.4f}")
    print(
        f"False Positive Rate:     "
        f"{false_positive_rate:.4f} "
        f"({false_positive_rate * 100:.2f}%)"
    )

    print("\nCONFUSION MATRIX")
    print("-" * 70)
    print("Rows = Actual, Columns = Predicted")
    print(f"{'':<22}{'Predicted Normal':>18}{'Predicted Incident':>20}")
    print(
        f"{'Actual Normal':<22}"
        f"{true_negatives:>18}"
        f"{false_positives:>20}"
    )
    print(
        f"{'Actual Incident':<22}"
        f"{false_negatives:>18}"
        f"{true_positives:>20}"
    )

    print("\nDETECTION LATENCY")
    print("-" * 70)
    print(
        f"First detection:         "
        f"{first_detected.isoformat() if first_detected else 'None'}"
    )
    print(f"Detection latency:       {detection_latency} minute(s)")

    print("\nNOTE")
    print(
        "These metrics evaluate one deterministic synthetic scenario. "
        "They are not evidence of production performance."
    )

    print("\n" + "=" * 70)
    print("EXECUTIVE NARRATIVE")
    print("=" * 70)
    print(report.summary_narrative)
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
