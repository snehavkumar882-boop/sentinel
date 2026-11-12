"""Data repository for querying and persisting Sentinel domain entities."""

from datetime import datetime
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.database.models import (
    DeploymentEvent,
    Incident,
    InvestigationAuditTrail,
    MetricTelemetry,
    Service,
    SystemLog,
)


class TelemetryRepository:
    """Repository handling persistence and queries for telemetry, logs, and events."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def save_service(self, service: Service) -> Service:
        """Persist or merge a Service record."""
        merged = self.session.merge(service)
        self.session.flush()
        return merged

    def get_service(self, service_id: str) -> Optional[Service]:
        """Fetch service by identifier."""
        stmt = select(Service).where(Service.id == service_id)
        return self.session.scalar(stmt)

    def save_metrics(self, metrics: List[MetricTelemetry]) -> None:
        """Bulk persist time-series metric data points."""
        self.session.add_all(metrics)
        self.session.flush()

    def get_metrics(
        self,
        service_id: str,
        metric_name: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> List[MetricTelemetry]:
        """Query metrics by service, optional metric name, and time range."""
        stmt = select(MetricTelemetry).where(MetricTelemetry.service_id == service_id)

        if metric_name:
            stmt = stmt.where(MetricTelemetry.metric_name == metric_name)
        if start_time:
            stmt = stmt.where(MetricTelemetry.timestamp >= start_time)
        if end_time:
            stmt = stmt.where(MetricTelemetry.timestamp <= end_time)

        stmt = stmt.order_by(MetricTelemetry.timestamp.asc())
        return list(self.session.scalars(stmt).all())

    def save_logs(self, logs: List[SystemLog]) -> None:
        """Bulk persist system log entries."""
        self.session.add_all(logs)
        self.session.flush()

    def get_logs(
        self,
        service_id: str,
        log_level: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 200,
    ) -> List[SystemLog]:
        """Query system logs with filtering and time constraints."""
        stmt = select(SystemLog).where(SystemLog.service_id == service_id)

        if log_level:
            stmt = stmt.where(SystemLog.log_level == log_level.upper())
        if start_time:
            stmt = stmt.where(SystemLog.timestamp >= start_time)
        if end_time:
            stmt = stmt.where(SystemLog.timestamp <= end_time)

        stmt = stmt.order_by(SystemLog.timestamp.asc()).limit(limit)
        return list(self.session.scalars(stmt).all())

    def save_deployment(self, deployment: DeploymentEvent) -> DeploymentEvent:
        """Persist a deployment event."""
        self.session.add(deployment)
        self.session.flush()
        return deployment

    def get_deployments(
        self,
        service_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> List[DeploymentEvent]:
        """Query deployment events for a service within a time window."""
        stmt = select(DeploymentEvent).where(DeploymentEvent.service_id == service_id)

        if start_time:
            stmt = stmt.where(DeploymentEvent.timestamp >= start_time)
        if end_time:
            stmt = stmt.where(DeploymentEvent.timestamp <= end_time)

        stmt = stmt.order_by(DeploymentEvent.timestamp.asc())
        return list(self.session.scalars(stmt).all())

    def save_incident(self, incident: Incident) -> Incident:
        """Persist or merge an incident record."""
        merged = self.session.merge(incident)
        self.session.flush()
        return merged

    def get_incident(self, incident_id: str) -> Optional[Incident]:
        """Retrieve an incident by identifier."""
        stmt = select(Incident).where(Incident.id == incident_id)
        return self.session.scalar(stmt)
