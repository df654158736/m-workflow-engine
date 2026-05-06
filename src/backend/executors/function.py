"""Function Node Executor — simulates custom function (Plane D)."""

from __future__ import annotations

import asyncio
import random
from typing import Any

import structlog

from backend.models import Determinism, NodeResult, NodeType, Runtime, StepStatus
from backend.spi import NodeExecutor

logger = structlog.get_logger()


class FunctionExecutor(NodeExecutor):
    @property
    def node_type(self) -> NodeType:
        return NodeType.FUNCTION

    @property
    def runtime(self) -> Runtime:
        return Runtime.PLANE_D

    @property
    def determinism(self) -> Determinism:
        return Determinism.NONDETERMINISTIC_CACHEABLE

    async def execute(
        self, node_id: str, config: dict[str, Any], inputs: dict[str, Any]
    ) -> NodeResult:
        function_id = config.get("function_id", "unknown-fn")

        logger.info(
            "[Plane D] Function executing",
            node_id=node_id,
            function_id=function_id,
        )

        # Simulate function execution
        await asyncio.sleep(random.uniform(0.2, 0.8))

        return NodeResult(
            node_id=node_id,
            status=StepStatus.COMPLETED,
            outputs={
                "function_id": function_id,
                "result": {
                    "processed": True,
                    "score": round(random.uniform(0.5, 1.0), 3),
                    "anomaly_detected": random.choice([True, False]),
                },
            },
        )
