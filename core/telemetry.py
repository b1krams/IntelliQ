"""Zero-Cost CloudWatch Embedded Metric Format (EMF) Logger ($0 PutMetricData API calls)."""
import json
import logging
import os
import random
import sys
import time
from typing import Any

from core.config import get_settings

logger = logging.getLogger("intelliq.telemetry")


def log_debug(message: str, **kwargs: Any) -> None:
    """Sample debug logs at 10% in production to keep log volume well under 5GB Free Tier."""
    settings = get_settings()
    if settings.stage == "production" and random.random() > 0.10:
        return
    logger.debug(message, extra=kwargs)


def emit_emf_metrics(
    metric_name: str,
    value: float,
    unit: str = "Count",
    dimensions: dict[str, str] | None = None,
    extra_properties: dict[str, Any] | None = None,
) -> None:
    """
    Emit metrics strictly via CloudWatch Embedded Metric Format (EMF) JSON to stdout.
    This bypasses AWS CloudWatch PutMetricData API costs completely ($0.00).
    """
    settings = get_settings()
    timestamp_ms = int(time.time() * 1000)

    dims = {"Stage": settings.stage, "Application": settings.app_name}
    if dimensions:
        dims.update(dimensions)

    dimension_keys = list(dims.keys())

    emf_payload: dict[str, Any] = {
        "_aws": {
            "Timestamp": timestamp_ms,
            "CloudWatchMetrics": [
                {
                    "Namespace": f"{settings.app_name}/Engine",
                    "Dimensions": [dimension_keys],
                    "Metrics": [{"Name": metric_name, "Unit": unit}],
                }
            ],
        },
        metric_name: value,
    }

    # Add dimensions as root properties (required by EMF specification)
    for k, v in dims.items():
        emf_payload[k] = v

    if extra_properties:
        for k, v in extra_properties.items():
            if k not in emf_payload:
                emf_payload[k] = v

    # Print directly to stdout as a single JSON line for CloudWatch Logs agent
    sys.stdout.write(json.dumps(emf_payload) + "\n")
    sys.stdout.flush()


def emit_llm_execution_metrics(
    provider: str,
    model: str,
    stage: str,
    latency_ms: float,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    is_error: bool = False,
) -> None:
    """Flush standard LLM execution telemetry via EMF in the async generator finally block."""
    dims = {"Provider": provider, "Model": model, "Stage": stage}
    emit_emf_metrics("Invocations", 1, "Count", dimensions=dims)
    emit_emf_metrics("Latency", latency_ms, "Milliseconds", dimensions=dims)
    if prompt_tokens:
        emit_emf_metrics("TokensPrompt", prompt_tokens, "Count", dimensions=dims)
    if completion_tokens:
        emit_emf_metrics("TokensCompletion", completion_tokens, "Count", dimensions=dims)
    if is_error:
        emit_emf_metrics("Errors", 1, "Count", dimensions=dims)

