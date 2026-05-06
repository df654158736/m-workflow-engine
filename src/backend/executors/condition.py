"""Condition Node Executor — evaluates expressions (Plane E)."""

from __future__ import annotations

from typing import Any

import structlog

from backend.models import Determinism, NodeResult, NodeType, Runtime, StepStatus
from backend.spi import NodeExecutor

logger = structlog.get_logger()


class ConditionExecutor(NodeExecutor):
    @property
    def node_type(self) -> NodeType:
        return NodeType.CONDITION

    @property
    def runtime(self) -> Runtime:
        return Runtime.PLANE_E

    @property
    def determinism(self) -> Determinism:
        return Determinism.DETERMINISTIC

    async def execute(
        self, node_id: str, config: dict[str, Any], inputs: dict[str, Any]
    ) -> NodeResult:
        expression = config.get("expression", "true")

        logger.info(
            "[Plane E] Condition evaluating",
            node_id=node_id,
            expression=expression,
        )

        # Simple expression evaluation against inputs
        try:
            result = eval(expression, {"__builtins__": {}}, inputs)
        except Exception as e:
            result = True
            logger.warning("Expression eval failed, defaulting to True", error=str(e))

        branch = config.get("true_branch", "yes") if result else config.get("false_branch", "no")

        logger.info(
            "[Plane E] Condition result",
            node_id=node_id,
            result=result,
            branch=branch,
        )

        return NodeResult(
            node_id=node_id,
            status=StepStatus.COMPLETED,
            outputs={"result": result, "branch": branch},
        )
