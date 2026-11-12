"""Synthetic telemetry and golden-path incident generator.

Generates reproducible, deterministic multi-variate telemetry, application logs,
and deployment records for a generic production payment/API service experiencing
database connection pool saturation.
"""

import csv
import json
import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from src.database.models import DeploymentEvent, MetricTelemetry, Service, SystemLog


@dataclass
class SyntheticScenarioConfig:
    """Configuration parameters for the synthetic incident scenario."""

    service_id: str = "payment-api-service"
    service_name: str = "Payment & Transaction API Service"
    owner_team: str = "payment-platform-eng"
    tier: str = "TIER-1"
    start_time: datetime = datetime(2026, 9, 28, 8, 0, 0, tzinfo=timezone.utc)
    duration_minutes: int = 240
    deployment_minute: int = 110
    incident_start_minute: int = 120
    incident_recovery_minute: int = 155
    random_seed: int = 42


class SyntheticTelemetryGenerator:
    """Generates realistic time-series metrics, logs, and events for incident analysis."""

    def __init__(self, config: Optional[SyntheticScenarioConfig] = None) -> None:
        self.config = config or SyntheticScenarioConfig()
        self.rng = random.Random(self.config.random_seed)

    def generate_all(self) -> Dict[str, Any]:
        """Generate service metadata, metrics, logs, and deployments."""
        service = self._create_service()
        deployments = self._generate_deployments()
        metrics = self._generate_metrics()
        logs = self._generate_logs()

        return {
            "service": service,
            "deployments": deployments,
            "metrics": metrics,
            "logs": logs,
            "config": self.config,
        }

    def _create_service(self) -> Service:
        return Service(
            id=self.config.service_id,
            name=self.config.service_name,
            tier=self.config.tier,
            owner_team=self.config.owner_team,
            created_at=self.config.start_time - timedelta(days=90),
        )

    def _generate_deployments(self) -> List[DeploymentEvent]:
        deploy_time = self.config.start_time + timedelta(minutes=self.config.deployment_minute)
        recovery_time = self.config.start_time + timedelta(
            minutes=self.config.incident_recovery_minute
        )

        deploy_event = DeploymentEvent(
            service_id=self.config.service_id,
            timestamp=deploy_time,
            version="v1.8.2",
            deployed_by="cicd-pipeline",
            config_diff={
                "db_connection_pool_size": {"previous": 100, "current": 15},
                "db_pool_timeout_ms": {"previous": 5000, "current": 500},
            },
            status="SUCCESS",
            description="Payment gateway update v1.8.2: performance tuning & connection pool limit reduction.",
        )

        recovery_event = DeploymentEvent(
            service_id=self.config.service_id,
            timestamp=recovery_time,
            version="v1.8.3-rollback",
            deployed_by="sre-oncall",
            config_diff={
                "db_connection_pool_size": {"previous": 15, "current": 100},
                "db_pool_timeout_ms": {"previous": 500, "current": 5000},
            },
            status="SUCCESS",
            description="Hotfix rollback restoring default DB pool capacity and timeout parameters.",
        )

        return [deploy_event, recovery_event]

    def _generate_metrics(self) -> List[MetricTelemetry]:
        metrics: List[MetricTelemetry] = []

        t_deploy = self.config.deployment_minute
        t_incident = self.config.incident_start_minute
        t_recovery = self.config.incident_recovery_minute

        for minute in range(self.config.duration_minutes):
            ts = self.config.start_time + timedelta(minutes=minute)

            # Determine operational state: 'baseline', 'incident', or 'recovering'
            if minute < t_incident:
                # Normal baseline
                request_vol = 1000.0 + self.rng.gauss(0, 35)
                db_pool_active = 18.0 + self.rng.gauss(0, 2.5)
                db_pool_wait_ms = 4.0 + self.rng.uniform(0.5, 3.5)
                db_conn_errors = 0.0
                api_latency_p95 = 115.0 + self.rng.gauss(0, 8.0)
                db_query_latency_p95 = 18.0 + self.rng.gauss(0, 2.0)
                http_5xx_rate = max(0.0, 0.001 + self.rng.uniform(0.0, 0.0015))
                cpu_util = 32.0 + self.rng.gauss(0, 3.0)
                mem_util = 54.0 + self.rng.gauss(0, 1.0)
            elif t_incident <= minute < t_recovery:
                # Incident phase: Connection pool saturated at 15
                # Latency and errors surge; CPU remains normal (proving no CPU throttling)
                request_vol = 980.0 + self.rng.gauss(0, 45)  # minor drop from client retries/giveups
                db_pool_active = 15.0  # Capped at new max pool size
                # Wait time surges to several seconds
                db_pool_wait_ms = 3200.0 + self.rng.gauss(0, 250)
                db_conn_errors = 42.0 + self.rng.gauss(0, 6)
                api_latency_p95 = 4100.0 + self.rng.gauss(0, 320)
                db_query_latency_p95 = 350.0 + self.rng.gauss(0, 45)
                http_5xx_rate = 0.165 + self.rng.gauss(0, 0.015)  # 15-18% error rate
                cpu_util = 34.0 + self.rng.gauss(0, 3.5)  # Normal
                mem_util = 55.5 + self.rng.gauss(0, 1.2)  # Normal
            else:
                # Recovery phase: exponential decay back to baseline within 5 mins
                decay_factor = max(0.0, 1.0 - (minute - t_recovery) / 5.0)

                request_vol = 1000.0 + self.rng.gauss(0, 35)
                db_pool_active = 20.0 + (15.0 * decay_factor) + self.rng.gauss(0, 2)
                db_pool_wait_ms = 4.0 + (3000.0 * decay_factor) + self.rng.uniform(0.5, 3.5)
                db_conn_errors = max(0.0, (40.0 * decay_factor) + self.rng.gauss(0, 1))
                api_latency_p95 = 115.0 + (3800.0 * decay_factor) + self.rng.gauss(0, 8.0)
                db_query_latency_p95 = 18.0 + (300.0 * decay_factor) + self.rng.gauss(0, 2.0)
                http_5xx_rate = max(0.0, 0.001 + (0.16 * decay_factor) + self.rng.uniform(0.0, 0.001))
                cpu_util = 32.0 + self.rng.gauss(0, 3.0)
                mem_util = 54.0 + self.rng.gauss(0, 1.0)

            http_5xx_count = round(request_vol * http_5xx_rate)

            # Assemble metric points
            datapoints = [
                ("request_volume_rpm", round(request_vol, 1)),
                ("http_5xx_rate", round(http_5xx_rate, 4)),
                ("http_5xx_count", float(http_5xx_count)),
                ("api_latency_p95_ms", round(api_latency_p95, 2)),
                ("db_query_latency_p95_ms", round(db_query_latency_p95, 2)),
                ("db_connection_pool_active", round(db_pool_active, 1)),
                ("db_connection_pool_wait_ms", round(db_pool_wait_ms, 2)),
                ("db_connection_errors_rpm", round(db_conn_errors, 1)),
                ("cpu_utilization_percent", round(cpu_util, 2)),
                ("memory_utilization_percent", round(mem_util, 2)),
            ]

            for name, val in datapoints:
                metrics.append(
                    MetricTelemetry(
                        timestamp=ts,
                        service_id=self.config.service_id,
                        metric_name=name,
                        metric_value=val,
                        tags={"environment": "production"},
                    )
                )

        return metrics

    def _generate_logs(self) -> List[SystemLog]:
        logs: List[SystemLog] = []

        t_incident = self.config.incident_start_minute
        t_recovery = self.config.incident_recovery_minute

        for minute in range(self.config.duration_minutes):
            ts = self.config.start_time + timedelta(minutes=minute)
            trace_id = f"trc-{self.rng.randint(100000, 999999)}"

            if minute < t_incident:
                # Normal operational logs (sample rate: every ~10 mins or random)
                if minute % 10 == 0:
                    logs.append(
                        SystemLog(
                            timestamp=ts,
                            service_id=self.config.service_id,
                            log_level="INFO",
                            message="HealthCheck completed successfully. All dependencies operational.",
                            trace_id=trace_id,
                            attributes={"status": 200, "component": "health_monitor"},
                        )
                    )
            elif t_incident <= minute < t_recovery:
                # High density error logs during incident
                logs.append(
                    SystemLog(
                        timestamp=ts + timedelta(seconds=12),
                        service_id=self.config.service_id,
                        log_level="ERROR",
                        message=(
                            "ConnectionPoolTimeoutException: Timeout waiting for idle connection "
                            "from pool 'PaymentDBPool' after 500ms (active=15, max=15, idle=0, pending=82)"
                        ),
                        trace_id=trace_id,
                        attributes={
                            "error_code": "ERR_DB_POOL_EXHAUSTED",
                            "pool_name": "PaymentDBPool",
                            "active_connections": 15,
                        },
                    )
                )
                logs.append(
                    SystemLog(
                        timestamp=ts + timedelta(seconds=28),
                        service_id=self.config.service_id,
                        log_level="ERROR",
                        message=(
                            f"HTTP 500 Internal Server Error: Failed to complete authorization for request {trace_id}. "
                            "Caused by: com.zaxxer.hikari.pool.PoolBase.getConnection(PoolBase.java:234)"
                        ),
                        trace_id=trace_id,
                        attributes={"status_code": 500, "endpoint": "/api/v1/payments/charge"},
                    )
                )
            else:
                # Post recovery logs
                if minute % 15 == 0:
                    logs.append(
                        SystemLog(
                            timestamp=ts,
                            service_id=self.config.service_id,
                            log_level="INFO",
                            message="Connection pool healthy. Active=22, idle=78, wait_time=3ms.",
                            trace_id=trace_id,
                            attributes={"status": 200, "component": "PaymentDBPool"},
                        )
                    )

        return logs


def export_scenario_to_csv(data: Dict[str, Any], output_dir: Path) -> Dict[str, Path]:
    """Export generated telemetry, logs, and deployment events to CSV files."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Export Metrics
    metrics_path = output_dir / "payment_service_telemetry.csv"
    with open(metrics_path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "service_id", "metric_name", "metric_value"])
        for m in data["metrics"]:
            writer.writerow([m.timestamp.isoformat(), m.service_id, m.metric_name, m.metric_value])

    # 2. Export Logs
    logs_path = output_dir / "payment_service_logs.csv"
    with open(logs_path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "service_id", "log_level", "message", "trace_id", "attributes"])
        for l in data["logs"]:
            writer.writerow(
                [
                    l.timestamp.isoformat(),
                    l.service_id,
                    l.log_level,
                    l.message,
                    l.trace_id,
                    json.dumps(l.attributes) if l.attributes else "",
                ]
            )

    # 3. Export Deployments
    deployments_path = output_dir / "deployment_events.csv"
    with open(deployments_path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            ["timestamp", "service_id", "version", "deployed_by", "config_diff", "status", "description"]
        )
        for d in data["deployments"]:
            writer.writerow(
                [
                    d.timestamp.isoformat(),
                    d.service_id,
                    d.version,
                    d.deployed_by,
                    json.dumps(d.config_diff) if d.config_diff else "",
                    d.status,
                    d.description,
                ]
            )

    return {
        "metrics_csv": metrics_path,
        "logs_csv": logs_path,
        "deployments_csv": deployments_path,
    }


def seed_scenario_to_db(data: Dict[str, Any], session: Session) -> None:
    """Populate the database with generated scenario entities."""
    from src.data.repository import TelemetryRepository

    repo = TelemetryRepository(session)
    repo.save_service(data["service"])

    for d in data["deployments"]:
        repo.save_deployment(d)

    repo.save_metrics(data["metrics"])
    repo.save_logs(data["logs"])
