"""Script to generate synthetic telemetry and seed the database.

Usage:
    python scripts/generate_telemetry.py [--seed 42] [--duration 240]
"""

import argparse
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config.logging_config import get_logger, setup_logging
from src.config.settings import get_settings
from src.data.synthetic_generator import (
    SyntheticScenarioConfig,
    SyntheticTelemetryGenerator,
    export_scenario_to_csv,
    seed_scenario_to_db,
)
from src.database.session import get_db_session, get_engine, init_db


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic telemetry and seed database.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for deterministic generation")
    parser.add_argument("--duration", type=int, default=240, help="Total scenario duration in minutes")
    args = parser.parse_args()

    settings = get_settings()
    setup_logging(log_level="INFO")
    logger = get_logger("sentinel.generator")

    logger.info("Initializing database schema...")
    engine = get_engine()
    init_db(engine)

    config = SyntheticScenarioConfig(
        random_seed=args.seed,
        duration_minutes=args.duration,
    )

    logger.info(
        f"Generating deterministic synthetic telemetry (seed={config.random_seed}, duration={config.duration_minutes}m)..."
    )
    generator = SyntheticTelemetryGenerator(config)
    data = generator.generate_all()

    # Export to CSV
    raw_dir = settings.DATA_DIR / "raw"
    exported_files = export_scenario_to_csv(data, raw_dir)
    logger.info(f"Exported metrics CSV: {exported_files['metrics_csv']}")
    logger.info(f"Exported logs CSV: {exported_files['logs_csv']}")
    logger.info(f"Exported deployments CSV: {exported_files['deployments_csv']}")

    # Seed Database
    logger.info(f"Seeding scenario data to database ({settings.DATABASE_URL})...")
    with get_db_session(engine) as session:
        seed_scenario_to_db(data, session)

    logger.info("=" * 60)
    logger.info("TELEMETRY GENERATION COMPLETE")
    logger.info("=" * 60)
    logger.info(f"Service:             {data['service'].id} ({data['service'].name})")
    logger.info(f"Metrics Generated:   {len(data['metrics'])} data points")
    logger.info(f"Logs Generated:      {len(data['logs'])} log events")
    logger.info(f"Deployments:         {len(data['deployments'])} events")
    logger.info(f"Incident Window:     Minute {config.incident_start_minute} -> {config.incident_recovery_minute}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
