"""Tool Node Executor — simulates ActionType execution (Plane B)."""

from __future__ import annotations

import asyncio
import random
from typing import Any

import structlog

from backend.models import Determinism, NodeResult, NodeType, Runtime, StepStatus
from backend.spi import NodeExecutor

logger = structlog.get_logger()


class ToolExecutor(NodeExecutor):
    @property
    def node_type(self) -> NodeType:
        return NodeType.TOOL

    @property
    def runtime(self) -> Runtime:
        return Runtime.PLANE_B

    @property
    def determinism(self) -> Determinism:
        return Determinism.SIDE_EFFECT

    async def execute(
        self, node_id: str, config: dict[str, Any], inputs: dict[str, Any]
    ) -> NodeResult:
        tool_id = config.get("tool_id", "unknown-tool")
        args = config.get("args", {})

        logger.info(
            "[Plane B] Tool executing",
            node_id=node_id,
            tool_id=tool_id,
            args=args,
        )

        # Simulate action execution
        await asyncio.sleep(random.uniform(0.3, 1.0))

        return NodeResult(
            node_id=node_id,
            status=StepStatus.COMPLETED,
            outputs={
                "tool_id": tool_id,
                "execution_id": f"exec-{random.randint(1000, 9999)}",
                "result": {"status": "success", "affected_objects": random.randint(1, 5)},
            },
        )
