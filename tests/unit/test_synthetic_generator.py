"""Unit tests for deterministic synthetic telemetry generation."""

import tempfile
from pathlib import Path
from src.data.synthetic_generator import (
    SyntheticScenarioConfig,
    SyntheticTelemetryGenerator,
    export_scenario_to_csv,
)


def test_deterministic_generation_with_identical_seed() -> None:
    """Verify that runs with identical random seed yield identical metric values."""
    config1 = SyntheticScenarioConfig(random_seed=42, duration_minutes=30)
    config2 = SyntheticScenarioConfig(random_seed=42, duration_minutes=30)

    data1 = SyntheticTelemetryGenerator(config1).generate_all()
    data2 = SyntheticTelemetryGenerator(config2).generate_all()

    assert len(data1["metrics"]) == len(data2["metrics"])

    for m1, m2 in zip(data1["metrics"], data2["metrics"]):
        assert m1.metric_name == m2.metric_name
        assert m1.timestamp == m2.timestamp
        assert m1.metric_value == m2.metric_value


def test_seed_variation() -> None:
    """Verify different seeds produce varied values."""
    config1 = SyntheticScenarioConfig(random_seed=42, duration_minutes=20)
    config2 = SyntheticScenarioConfig(random_seed=999, duration_minutes=20)

    data1 = SyntheticTelemetryGenerator(config1).generate_all()
    data2 = SyntheticTelemetryGenerator(config2).generate_all()

    values1 = [m.metric_value for m in data1["metrics"]]
    values2 = [m.metric_value for m in data2["metrics"]]

    assert values1 != values2


def test_expected_metric_count() -> None:
    """Verify metric data point count matches duration * number of metric series."""
    duration = 60
    config = SyntheticScenarioConfig(duration_minutes=duration)
    data = SyntheticTelemetryGenerator(config).generate_all()

    # 10 metrics per minute
    expected_count = duration * 10
    assert len(data["metrics"]) == expected_count


def test_csv_export() -> None:
    """Verify scenario exporter creates valid CSV files with non-zero size."""
    config = SyntheticScenarioConfig(duration_minutes=15)
    data = SyntheticTelemetryGenerator(config).generate_all()

    with tempfile.TemporaryDirectory() as tmp_dir:
        output_dir = Path(tmp_dir)
        files = export_scenario_to_csv(data, output_dir)

        assert files["metrics_csv"].exists()
        assert files["logs_csv"].exists()
        assert files["deployments_csv"].exists()

        assert files["metrics_csv"].stat().st_size > 0
        assert files["logs_csv"].stat().st_size > 0
        assert files["deployments_csv"].stat().st_size > 0
