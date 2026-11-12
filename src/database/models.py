"""Relational database models for SENTINEL.

Defines SQLAlchemy ORM models for services, metrics telemetry, system logs,
deployment events, incidents, and investigation audit trails.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Declarative base class for all SQLAlchemy entities."""
    pass


class Service(Base):
    """Monitored application or service entity."""

    __tablename__ = "services"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    tier: Mapped[str] = mapped_column(String(16), nullable=False, default="TIER-1")
    owner_team: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Relationships
    metrics: Mapped[List["MetricTelemetry"]] = relationship(
        "MetricTelemetry", back_populates="service", cascade="all, delete-orphan"
    )
    logs: Mapped[List["SystemLog"]] = relationship(
        "SystemLog", back_populates="service", cascade="all, delete-orphan"
    )
    deployments: Mapped[List["DeploymentEvent"]] = relationship(
        "DeploymentEvent", back_populates="service", cascade="all, delete-orphan"
    )
    incidents: Mapped[List["Incident"]] = relationship(
        "Incident", back_populates="service", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Service id={self.id!r} name={self.name!r} tier={self.tier!r}>"


class MetricTelemetry(Base):
    """Time-series telemetry metric data points."""

    __tablename__ = "metrics_telemetry"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    service_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("services.id", ondelete="CASCADE"), nullable=False, index=True
    )
    metric_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    metric_value: Mapped[float] = mapped_column(Float, nullable=False)
    tags: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # Relationships
    service: Mapped["Service"] = relationship("Service", back_populates="metrics")

    __table_args__ = (
        Index("idx_metric_service_name_time", "service_id", "metric_name", "timestamp"),
    )

    def __repr__(self) -> str:
        return (
            f"<MetricTelemetry service={self.service_id!r} "
            f"name={self.metric_name!r} value={self.metric_value} ts={self.timestamp.isoformat()}>"
        )


class SystemLog(Base):
    """Application and infrastructure log entries."""

    __tablename__ = "system_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    service_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("services.id", ondelete="CASCADE"), nullable=False, index=True
    )
    log_level: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    trace_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    attributes: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # Relationships
    service: Mapped["Service"] = relationship("Service", back_populates="logs")

    __table_args__ = (
        Index("idx_logs_service_time_level", "service_id", "timestamp", "log_level"),
    )

    def __repr__(self) -> str:
        return (
            f"<SystemLog service={self.service_id!r} level={self.log_level!r} "
            f"ts={self.timestamp.isoformat()} msg={self.message[:30]!r}>"
        )


class DeploymentEvent(Base):
    """CI/CD deployment and configuration change records."""

    __tablename__ = "deployment_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    service_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("services.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    deployed_by: Mapped[str] = mapped_column(String(64), nullable=False)
    config_diff: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="SUCCESS")
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    service: Mapped["Service"] = relationship("Service", back_populates="deployments")

    def __repr__(self) -> str:
        return (
            f"<DeploymentEvent service={self.service_id!r} version={self.version!r} "
            f"status={self.status!r} ts={self.timestamp.isoformat()}>"
        )


class Incident(Base):
    """Detected and triaged incident records."""

    __tablename__ = "incidents"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    service_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("services.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="DETECTED")
    severity: Mapped[str] = mapped_column(String(16), nullable=False, default="SEV-1")
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    anomaly_metric: Mapped[str] = mapped_column(String(128), nullable=False)
    anomaly_score: Mapped[float] = mapped_column(Float, nullable=False)
    root_cause_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confidence_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    report_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # Relationships
    service: Mapped["Service"] = relationship("Service", back_populates="incidents")
    audit_trails: Mapped[List["InvestigationAuditTrail"]] = relationship(
        "InvestigationAuditTrail", back_populates="incident", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return (
            f"<Incident id={self.id!r} service={self.service_id!r} "
            f"severity={self.severity!r} status={self.status!r}>"
        )


class InvestigationAuditTrail(Base):
    """Step-by-step investigation trail executed by the Sentinel agent."""

    __tablename__ = "investigation_audit_trail"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    incident_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    step_index: Mapped[int] = mapped_column(Integer, nullable=False)
    phase: Mapped[str] = mapped_column(String(64), nullable=False)
    tool_name: Mapped[str] = mapped_column(String(64), nullable=False)
    input_payload: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    output_payload: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    agent_reasoning: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Relationships
    incident: Mapped["Incident"] = relationship("Incident", back_populates="audit_trails")

    __table_args__ = (
        Index("idx_audit_incident_step", "incident_id", "step_index"),
    )

    def __repr__(self) -> str:
        return (
            f"<InvestigationAuditTrail incident={self.incident_id!r} "
            f"step={self.step_index} tool={self.tool_name!r}>"
        )
