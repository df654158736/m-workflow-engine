"""Temporal Activities — actual node execution logic.

Each activity runs on a specific task queue (Plane). The worker for that
queue picks it up and delegates to the corresponding NodeExecutor via SPI.
"""

from __future__ import annotations

import time
from dataclasses import asdict
from typing import Any

import structlog
from temporalio import activity

from backend.executors import build_default_registry
from backend.models import NodeResult, NodeType, StepStatus

logger = structlog.get_logger()

_registry = build_default_registry()


@activity.defn(name="execute_node")
async def execute_node(payload: dict[str, Any]) -> dict[str, Any]:
    """Generic activity that dispatches to the correct NodeExecutor.

    This single activity definition is registered on ALL task queues.
    The routing (which queue picks it up) is determined by the Workflow
    when it schedules the activity.
    """
    node_id = payload["node_id"]
    node_type = NodeType(payload["node_type"])
    config = payload.get("config", {})
    inputs = payload.get("inputs", {})
    task_queue = payload.get("task_queue", "unknown")

    logger.info(
        "Activity started",
        node_id=node_id,
        node_type=node_type.value,
        task_queue=task_queue,
    )

    start = time.monotonic()

    try:
        executor = _registry.get(node_type)
        result = await executor.execute(node_id, config, inputs)
        result.duration_ms = int((time.monotonic() - start) * 1000)
    except Exception as e:
        logger.error("Activity execution failed", node_id=node_id, error=str(e))
        result = NodeResult(
            node_id=node_id,
            status=StepStatus.FAILED,
            error=str(e),
            duration_ms=int((time.monotonic() - start) * 1000),
        )

    logger.info(
        "Activity completed",
        node_id=node_id,
        status=result.status.value,
        duration_ms=result.duration_ms,
    )

    return asdict(result)
