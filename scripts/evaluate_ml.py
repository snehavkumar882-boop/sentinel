
"""Evaluate Sentinel's Isolation Forest using labelled synthetic telemetry.

Training: minutes 0-99 (normal baseline)
Evaluation:
    Normal:   minutes 100-119 and 160-239
    Incident: minutes 120-154
    Recovery: minutes 155-159 (excluded)

This is a binary service-level anomaly evaluation, not a
supervised model training-accuracy measurement.
"""

import sys
from pathlib import Path

import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)

# Add project root to Python path.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.data.synthetic_generator import (
    SyntheticScenarioConfig,
    SyntheticTelemetryGenerator,
)
from src.ml.pipeline import MLAnomalyPipeline


def main() -> None:
    print("=" * 72)
    print("SENTINEL - ISOLATION FOREST EVALUATION")
    print("=" * 72)

    # 1. Generate deterministic labelled synthetic telemetry.
    config = SyntheticScenarioConfig(
        duration_minutes=240,
        incident_start_minute=120,
        incident_recovery_minute=155,
        random_seed=42,
    )

    generated = SyntheticTelemetryGenerator(config).generate_all()

    df = pd.DataFrame(
        [
            {
                "timestamp": metric.timestamp,
                "metric_name": metric.metric_name,
                "metric_value": metric.metric_value,
            }
            for metric in generated["metrics"]
        ]
    )

    print(f"\nGenerated telemetry records: {len(df)}")
    print(f"Total time points: {config.duration_minutes}")

    # 2. Train and run the existing pipeline.
    pipeline = MLAnomalyPipeline(
        service_id=config.service_id,
        baseline_duration_minutes=100,
        z_threshold=3.0,
        contamination=0.05,
        random_state=42,
    )

    pipeline.run(df)

    # 3. Obtain predictions for every time point.
    # The pipeline has fitted Isolation Forest on the first 100 minutes.
    wide_df = pipeline._preprocess_to_wide(df)

    timestamps = pd.Series(pd.to_datetime(wide_df["timestamp"]))

    predictions = pipeline.isolation_forest.predict_and_score(
        df=wide_df[pipeline.isolation_forest.feature_names],
        timestamps=timestamps,
    )

    results = pd.DataFrame(
        {
            "timestamp": timestamps,
            "predicted_anomaly": [int(r.is_anomaly) for r in predictions],
        }
    )

    results["minute"] = (
        (results["timestamp"] - config.start_time).dt.total_seconds() / 60
    ).astype(int)

    # 4. Construct ground-truth labels from the generator's scenario.
    # 0 = NORMAL
    # 1 = INCIDENT
    results["actual_anomaly"] = 0

    incident_mask = (
        (results["minute"] >= config.incident_start_minute)
        & (results["minute"] < config.incident_recovery_minute)
    )

    results.loc[incident_mask, "actual_anomaly"] = 1

    # 5. Define a strictly held-out evaluation window.
    # Exclude training minutes 0-99 and recovery transition 155-159.
    normal_test_mask = (
        ((results["minute"] >= 100) & (results["minute"] <= 119))
        | ((results["minute"] >= 160) & (results["minute"] <= 239))
    )

    evaluation_mask = normal_test_mask | incident_mask
    evaluation = results.loc[evaluation_mask].copy()

    y_true = evaluation["actual_anomaly"]
    y_pred = evaluation["predicted_anomaly"]

    # 6. Calculate evaluation metrics.
    accuracy = accuracy_score(y_true, y_pred)
    precision = precision_score(y_true, y_pred, zero_division=0)
    recall = recall_score(y_true, y_pred, zero_division=0)
    f1 = f1_score(y_true, y_pred, zero_division=0)
    macro_f1 = f1_score(y_true, y_pred, average="macro", zero_division=0)

    matrix = confusion_matrix(y_true, y_pred, labels=[0, 1])
    tn, fp, fn, tp = matrix.ravel()

    false_positive_rate = fp / (fp + tn) if (fp + tn) else 0.0

    # 7. Calculate incident detection latency.
    incident_predictions = results.loc[incident_mask]

    detected = incident_predictions[
        incident_predictions["predicted_anomaly"] == 1
    ]

    if not detected.empty:
        first_detection_minute = int(detected["minute"].min())
        detection_latency = (
            first_detection_minute - config.incident_start_minute
        )
    else:
        first_detection_minute = None
        detection_latency = None

    # 8. Print results.
    print("\nEVALUATION DATA")
    print("-" * 72)
    print("Training baseline:       Minutes 0-99")
    print("Held-out normal:          Minutes 100-119 and 160-239")
    print("Incident:                 Minutes 120-154")
    print("Excluded recovery:        Minutes 155-159")
    print(f"Evaluation observations:  {len(evaluation)}")
    print(f"Normal observations:      {(y_true == 0).sum()}")
    print(f"Incident observations:    {(y_true == 1).sum()}")

    print("\nCLASSIFICATION METRICS")
    print("-" * 72)
    print(f"Accuracy:                 {accuracy:.4f} ({accuracy * 100:.2f}%)")
    print(f"Precision:                {precision:.4f}")
    print(f"Recall:                   {recall:.4f}")
    print(f"F1-score:                 {f1:.4f}")
    print(f"Macro-F1:                 {macro_f1:.4f}")
    print(f"False Positive Rate:      {false_positive_rate:.4f}")

    print("\nCONFUSION MATRIX")
    print("-" * 72)
    print("Rows = Actual, Columns = Predicted")
    print("                 Predicted Normal   Predicted Incident")
    print(f"Actual Normal    {tn:>16}   {fp:>18}")
    print(f"Actual Incident  {fn:>16}   {tp:>18}")

    print("\nDETECTION LATENCY")
    print("-" * 72)

    if detection_latency is not None:
        print(f"First detection minute:   {first_detection_minute}")
        print(f"Detection latency:        {detection_latency} minute(s)")
    else:
        print("No anomaly detected during the incident window.")

    print("\nPER-CLASS REPORT")
    print("-" * 72)
    print(
        classification_report(
            y_true,
            y_pred,
            labels=[0, 1],
            target_names=["NORMAL", "INCIDENT"],
            zero_division=0,
        )
    )

    print("=" * 72)
    print("EVALUATION COMPLETE")
    print("=" * 72)
    print(
        "\nNote: These results evaluate one deterministic synthetic scenario. "
        "They are not evidence of production performance."
    )


if __name__ == "__main__":
    main()
