"""SENTINEL Application Entrypoint.

Provides a unified interface to run health checks or launch the API server.
Usage:
    python -m src.main --check
    python -m src.main --serve
"""

import argparse
import sys
import uvicorn

from src.api.health import perform_system_health_check
from src.config.logging_config import get_logger, setup_logging
from src.config.settings import get_settings


def run_health_check() -> int:
    """Run non-destructive CLI health checks and print results."""
    settings = get_settings()
    setup_logging(log_level=settings.LOG_LEVEL)
    logger = get_logger("sentinel.cli")

    logger.info("Executing SENTINEL platform preflight diagnostics...")
    result = perform_system_health_check()

    print("\n" + "=" * 60)
    print(f"SENTINEL SYSTEM HEALTH STATUS: {result.status.upper()}")
    print("=" * 60)
    print(f"  App Name:       {result.app_name}")
    print(f"  Version:        {result.version}")
    print(f"  Environment:    {result.environment}")
    print(f"  Python:         {result.python_version}")
    print(f"  Timestamp:      {result.timestamp.isoformat()}")
    print("\nSubsystem Components:")
    for comp in result.components:
        badge = "✓" if comp.status == "healthy" else ("!" if comp.status == "degraded" else "✗")
        print(f"  [{badge}] {comp.name:<20} : {comp.status:<10} - {comp.details}")
    print("=" * 60 + "\n")

    return 0 if result.status == "healthy" else 1


def start_server() -> None:
    """Start the FastAPI application via uvicorn."""
    settings = get_settings()
    setup_logging(log_level=settings.LOG_LEVEL)
    logger = get_logger("sentinel.server")

    logger.info(
        f"Booting {settings.APP_NAME} server on {settings.HOST}:{settings.PORT} "
        f"[env={settings.ENVIRONMENT}, debug={settings.DEBUG}]"
    )

    uvicorn.run(
        "src.api.app:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
    )


def main() -> None:
    """Parse arguments and route execution."""
    parser = argparse.ArgumentParser(
        description="SENTINEL – Autonomous Data & Incident Intelligence Platform"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Run system preflight health checks and exit.",
    )
    parser.add_argument(
        "--serve",
        action="store_true",
        help="Launch the FastAPI server.",
    )

    args = parser.parse_args()

    # Default to health check if no flags passed
    if args.serve:
        start_server()
    else:
        exit_code = run_health_check()
        sys.exit(exit_code)


if __name__ == "__main__":
    main()
