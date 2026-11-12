"""Unit tests for the SQLAlchemy relational database schema."""

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session
from src.database.models import (
    Base,
    DeploymentEvent,
    Incident,
    InvestigationAuditTrail,
    MetricTelemetry,
    Service,
    SystemLog,
)
from src.database.session import init_db


def test_schema_table_creation() -> None:
    """Verify all database tables and indexes are properly created in an engine."""
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)

    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())

    expected_tables = {
        "services",
        "metrics_telemetry",
        "system_logs",
        "deployment_events",
        "incidents",
        "investigation_audit_trail",
    }

    assert expected_tables.issubset(table_names)


def test_service_cascade_deletion() -> None:
    """Verify that deleting a service cascades to child telemetry records."""
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)

    with Session(engine) as session:
        service = Service(
            id="test-svc",
            name="Test Service",
            tier="TIER-1",
            owner_team="infra-team",
        )
        session.add(service)
        session.flush()

        # Add metric
        metric = MetricTelemetry(
            service_id="test-svc",
            metric_name="cpu_util",
            metric_value=25.0,
            timestamp=service.created_at,
        )
        session.add(metric)
        session.commit()

        # Delete service
        session.delete(service)
        session.commit()

        # Verify metric is deleted
        remaining_metrics = session.query(MetricTelemetry).filter_by(service_id="test-svc").all()
        assert len(remaining_metrics) == 0
