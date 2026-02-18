"""Celery task for weekly model threshold optimization."""

from app.tasks.celery_app import celery_app

import structlog

log = structlog.get_logger(__name__)


@celery_app.task(name="app.tasks.optimizer_tasks.run_weekly_optimization")
def run_weekly_optimization():
    """Run the weekly pattern confidence threshold optimization."""
    from app.engines.optimizer_engine import OptimizerEngine

    log.info("weekly_optimization_started")
    engine = OptimizerEngine()
    result = engine.run_weekly_optimization()
    log.info("weekly_optimization_complete", result=result.get("status"))
    return result
