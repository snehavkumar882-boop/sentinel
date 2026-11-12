"""Integration tests for database persistence and repository operations."""

from datetime import timedelta
from sqlalchemy import create_engine
from src.data.repository import TelemetryRepository
from src.data.synthetic_generator import (
    SyntheticScenarioConfig,
    SyntheticTelemetryGenerator,
    seed_scenario_to_db,
)
from src.database.models import Incident
from src.database.session import get_db_session, init_db


def test_database_seed_and_repository_queries() -> None:
    """Verify that synthetic telemetry seeds properly into SQLite and can be queried via repository."""
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)

    config = SyntheticScenarioConfig(duration_minutes=30, random_seed=42)
    data = SyntheticTelemetryGenerator(config).generate_all()

    with get_db_session(engine) as session:
        seed_scenario_to_db(data, session)

    with get_db_session(engine) as session:
        repo = TelemetryRepository(session)

        # 1. Query Service
        svc = repo.get_service("payment-api-service")
        assert svc is not None
        assert svc.name == config.service_name
        assert svc.tier == "TIER-1"

        # 2. Query Deployments
        deployments = repo.get_deployments("payment-api-service")
        assert len(deployments) == 2

        # 3. Query Metrics with Time Window and Filter
        start_ts = config.start_time
        end_ts = config.start_time + timedelta(minutes=10)
        metrics = repo.get_metrics(
            service_id="payment-api-service",
            metric_name="http_5xx_rate",
            start_time=start_ts,
            end_time=end_ts,
        )
        assert len(metrics) == 11  # 0 to 10 inclusive

        # 4. Query Logs
        logs = repo.get_logs("payment-api-service")
        assert len(logs) > 0

        # 5. Save and Query Incident
        incident = Incident(
            id="INC-TEST-001",
            service_id="payment-api-service",
            title="Database Connection Pool Saturation",
            status="DETECTED",
            severity="SEV-1",
            detected_at=config.start_time + timedelta(minutes=120),
            anomaly_metric="http_5xx_rate",
            anomaly_score=4.8,
            root_cause_summary="Connection pool max size drop",
            confidence_score=0.94,
        )
        repo.save_incident(incident)

        retrieved_inc = repo.get_incident("INC-TEST-001")
        assert retrieved_inc is not None
        assert retrieved_inc.severity == "SEV-1"
        assert retrieved_inc.anomaly_score == 4.8
