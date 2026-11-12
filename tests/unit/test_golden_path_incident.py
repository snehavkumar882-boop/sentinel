"""Unit tests verifying the Golden Path incident scenario dynamics."""

from datetime import timedelta
from src.data.synthetic_generator import (
    SyntheticScenarioConfig,
    SyntheticTelemetryGenerator,
)


def test_golden_path_incident_dynamics() -> None:
    """Validate baseline, incident spike, negative controls, and post-recovery behavior."""
    config = SyntheticScenarioConfig(
        duration_minutes=240,
        incident_start_minute=120,
        incident_recovery_minute=155,
        random_seed=42,
    )
    generator = SyntheticTelemetryGenerator(config)
    data = generator.generate_all()

    # Index metrics by (metric_name, minute_offset)
    start_time = config.start_time
    metric_lookup = {}
    for m in data["metrics"]:
        minute = int((m.timestamp - start_time).total_seconds() // 60)
        metric_lookup[(m.metric_name, minute)] = m.metric_value

    # 1. Baseline Checks (Minute 30, well before incident)
    assert metric_lookup[("http_5xx_rate", 30)] < 0.01  # Normal error rate < 1%
    assert metric_lookup[("db_connection_pool_wait_ms", 30)] < 15.0  # Normal wait time < 15ms
    assert metric_lookup[("api_latency_p95_ms", 30)] < 200.0  # Normal latency < 200ms
    assert 25.0 <= metric_lookup[("cpu_utilization_percent", 30)] <= 50.0

    # 2. Incident Peak Checks (Minute 135, middle of incident)
    assert metric_lookup[("http_5xx_rate", 135)] > 0.12  # Spikes above 12%
    assert metric_lookup[("db_connection_pool_wait_ms", 135)] > 2500.0  # Spikes > 2.5 seconds
    assert metric_lookup[("api_latency_p95_ms", 135)] > 3000.0  # Spikes > 3 seconds
    assert metric_lookup[("db_connection_pool_active", 135)] == 15.0  # Saturated at 15
    assert metric_lookup[("db_connection_errors_rpm", 135)] > 25.0  # High error count

    # 3. Negative Controls during Incident (Minute 135)
    # CPU and memory must remain normal (proving it is NOT compute starvation)
    assert metric_lookup[("cpu_utilization_percent", 135)] < 50.0
    assert metric_lookup[("memory_utilization_percent", 135)] < 65.0

    # 4. Recovery Checks (Minute 180, well after rollback at minute 155)
    assert metric_lookup[("http_5xx_rate", 180)] < 0.01  # Dropped back to baseline
    assert metric_lookup[("db_connection_pool_wait_ms", 180)] < 15.0  # Dropped back to baseline
    assert metric_lookup[("api_latency_p95_ms", 180)] < 200.0  # Dropped back to baseline


def test_golden_path_deployment_events() -> None:
    """Verify deployment events contain the expected causal configuration diffs."""
    config = SyntheticScenarioConfig(random_seed=42)
    data = SyntheticTelemetryGenerator(config).generate_all()

    deployments = data["deployments"]
    assert len(deployments) == 2

    # Deployment 1 (The Trigger at Minute 110)
    d1 = deployments[0]
    assert d1.version == "v1.8.2"
    assert d1.config_diff["db_connection_pool_size"]["current"] == 15
    assert d1.config_diff["db_connection_pool_size"]["previous"] == 100

    # Deployment 2 (The Recovery Rollback at Minute 155)
    d2 = deployments[1]
    assert "rollback" in d2.version
    assert d2.config_diff["db_connection_pool_size"]["current"] == 100


def test_golden_path_log_signatures() -> None:
    """Verify error logs during incident contain connection pool exception signatures."""
    config = SyntheticScenarioConfig(random_seed=42)
    data = SyntheticTelemetryGenerator(config).generate_all()

    error_logs = [log for log in data["logs"] if log.log_level == "ERROR"]
    assert len(error_logs) > 0

    pool_exhaustion_logs = [
        l for l in error_logs if "ERR_DB_POOL_EXHAUSTED" in str(l.attributes)
    ]
    assert len(pool_exhaustion_logs) > 0
    assert "ConnectionPoolTimeoutException" in pool_exhaustion_logs[0].message
