"""Approval Node Executor — human-in-the-loop approval (Plane B).

Uses Temporal Signals to pause workflow until human approves/rejects.
The executor returns immediately with a "WAITING" status; the actual
approval resolution happens via signal in the Workflow.
"""

from __future__ import annotations

from typing import Any

import structlog

from backend.models import Determinism, NodeResult, NodeType, Runtime, StepStatus
from backend.spi import NodeExecutor

logger = structlog.get_logger()


class ApprovalExecutor(NodeExecutor):
    @property
    def node_type(self) -> NodeType:
        return NodeType.APPROVAL

    @property
    def runtime(self) -> Runtime:
        return Runtime.PLANE_B

    @property
    def determinism(self) -> Determinism:
        return Determinism.SIDE_EFFECT

    async def execute(
        self, node_id: str, config: dict[str, Any], inputs: dict[str, Any]
    ) -> NodeResult:
        # This executor is NOT actually called for approval nodes.
        # Approval is handled directly in the Workflow via Signal.
        # This is a placeholder for the SPI registry.
        logger.info(
            "[Plane B] Approval task created",
            node_id=node_id,
            approvers=config.get("approvers", []),
            title=config.get("title", ""),
        )

        return NodeResult(
            node_id=node_id,
            status=StepStatus.COMPLETED,
            outputs={
                "decision": "PENDING",
                "message": "Waiting for human approval via Signal",
            },
        )
