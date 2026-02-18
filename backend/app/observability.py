"""
Bubby Vision — LangSmith Observability

Provides tracing, logging, and evaluation for LLM calls via LangSmith.
Activates automatically when LANGCHAIN_TRACING_V2=true is set in environment.

Usage:
  1. Set env vars: LANGCHAIN_TRACING_V2=true, LANGCHAIN_API_KEY=..., LANGCHAIN_PROJECT=Bubby Vision
  2. All LangChain/LangGraph calls are auto-traced
  3. Use manual tracing for custom spans around non-LangChain code
"""

from __future__ import annotations

import functools
import os
import time
from contextlib import contextmanager
from typing import Any, Callable, Optional

import structlog

logger = structlog.get_logger(__name__)


# ──────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────

def is_tracing_enabled() -> bool:
    """Check if LangSmith tracing is enabled."""
    return os.getenv("LANGCHAIN_TRACING_V2", "").lower() == "true"


def configure_langsmith(
    project_name: str = "Bubby Vision",
    api_key: Optional[str] = None,
):
    """Configure LangSmith tracing environment.

    Sets environment variables that LangChain/LangGraph
    auto-detect to enable tracing.
    """
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_PROJECT"] = project_name

    if api_key:
        os.environ["LANGCHAIN_API_KEY"] = api_key

    logger.info(
        "langsmith_configured",
        project=project_name,
        tracing_enabled=True,
    )


def disable_langsmith():
    """Disable LangSmith tracing."""
    os.environ["LANGCHAIN_TRACING_V2"] = "false"
    logger.info("langsmith_disabled")


# ──────────────────────────────────────────────
# Manual Tracing for Non-LangChain Code
# ──────────────────────────────────────────────

@contextmanager
def trace_span(
    name: str,
    run_type: str = "chain",
    metadata: Optional[dict] = None,
    tags: Optional[list[str]] = None,
):
    """Context manager for manual tracing of code blocks.

    When LangSmith tracing is enabled, this creates a traced run.
    When disabled, it behaves as a no-op timer.

    Args:
        name: Name of the span (e.g., "ta_engine.compute_indicators").
        run_type: LangSmith run type: "chain", "tool", "llm", "retriever".
        metadata: Optional metadata dict to attach.
        tags: Optional tags for filtering in LangSmith.

    Usage:
        with trace_span("compute_indicators", tags=["ta", "engine"]):
            result = ta_engine.compute(bars)
    """
    start = time.perf_counter()
    extra = {"span_name": name, "run_type": run_type}

    if is_tracing_enabled():
        try:
            from langsmith import trace as ls_trace

            with ls_trace(
                name=name,
                run_type=run_type,
                metadata=metadata or {},
                tags=tags or [],
            ) as run:
                logger.debug("trace_span_start", **extra)
                try:
                    yield run
                finally:
                    elapsed = time.perf_counter() - start
                    logger.debug("trace_span_end", elapsed_ms=round(elapsed * 1000, 2), **extra)
        except ImportError:
            logger.debug("trace_span_no_langsmith", **extra)
            yield None
    else:
        logger.debug("trace_span_local", **extra)
        yield None

    elapsed = time.perf_counter() - start
    if elapsed > 5.0:
        logger.warning("trace_span_slow", elapsed_s=round(elapsed, 2), **extra)


def traced(
    name: Optional[str] = None,
    run_type: str = "chain",
    tags: Optional[list[str]] = None,
):
    """Decorator to trace a function as a LangSmith span.

    Usage:
        @traced("compute_greeks", run_type="tool", tags=["options"])
        def compute_greeks(...):
            ...
    """
    def decorator(func: Callable) -> Callable:
        span_name = name or f"{func.__module__}.{func.__qualname__}"

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            with trace_span(span_name, run_type=run_type, tags=tags):
                return func(*args, **kwargs)

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            with trace_span(span_name, run_type=run_type, tags=tags):
                return await func(*args, **kwargs)

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return wrapper

    return decorator


# ──────────────────────────────────────────────
# Feedback & Evaluation Helpers
# ──────────────────────────────────────────────

def log_feedback(
    run_id: str,
    key: str,
    score: float,
    comment: Optional[str] = None,
):
    """Log feedback to LangSmith for a traced run.

    Args:
        run_id: LangSmith run ID.
        key: Feedback key (e.g., "accuracy", "helpfulness").
        score: Score (0.0 to 1.0).
        comment: Optional comment.
    """
    if not is_tracing_enabled():
        logger.debug("feedback_skipped_no_tracing", run_id=run_id, key=key)
        return

    try:
        from langsmith import Client

        client = Client()
        client.create_feedback(
            run_id=run_id,
            key=key,
            score=score,
            comment=comment,
        )
        logger.info("feedback_logged", run_id=run_id, key=key, score=score)
    except ImportError:
        logger.warning("feedback_failed_no_langsmith")
    except Exception as e:
        logger.error("feedback_failed", error=str(e))


# ──────────────────────────────────────────────
# Agent Performance Metrics
# ──────────────────────────────────────────────

class AgentMetrics:
    """Track and report agent performance metrics for LangSmith dashboards."""

    def __init__(self):
        self._call_counts: dict[str, int] = {}
        self._total_latency: dict[str, float] = {}
        self._error_counts: dict[str, int] = {}

    def record_call(self, agent_name: str, latency_ms: float, success: bool = True):
        """Record a single agent call."""
        self._call_counts[agent_name] = self._call_counts.get(agent_name, 0) + 1
        self._total_latency[agent_name] = self._total_latency.get(agent_name, 0.0) + latency_ms
        if not success:
            self._error_counts[agent_name] = self._error_counts.get(agent_name, 0) + 1

    def get_stats(self) -> dict[str, dict]:
        """Get performance stats per agent."""
        stats = {}
        for agent in self._call_counts:
            calls = self._call_counts[agent]
            stats[agent] = {
                "total_calls": calls,
                "avg_latency_ms": round(self._total_latency.get(agent, 0) / max(calls, 1), 2),
                "error_count": self._error_counts.get(agent, 0),
                "error_rate": round(self._error_counts.get(agent, 0) / max(calls, 1), 4),
            }
        return stats

    def reset(self):
        """Reset all metrics."""
        self._call_counts.clear()
        self._total_latency.clear()
        self._error_counts.clear()


# Module-level shared instance
agent_metrics = AgentMetrics()
