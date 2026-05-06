"""FlinkSQL Node Executor — simulates data pipeline execution (Plane C)."""

from __future__ import annotations

import asyncio
import random
from typing import Any

import structlog

from backend.models import Determinism, NodeResult, NodeType, Runtime, StepStatus
from backend.spi import NodeExecutor

logger = structlog.get_logger()


class FlinkSQLExecutor(NodeExecutor):
    @property
    def node_type(self) -> NodeType:
        return NodeType.FLINK_SQL

    @property
    def runtime(self) -> Runtime:
        return Runtime.PLANE_C

    @property
    def determinism(self) -> Determinism:
        return Determinism.SIDE_EFFECT

    async def execute(
        self, node_id: str, config: dict[str, Any], inputs: dict[str, Any]
    ) -> NodeResult:
        sql = config.get("sql", "SELECT 1")

        logger.info(
            "[Plane C] FlinkSQL executing",
            node_id=node_id,
            sql_preview=sql[:80],
        )

        # Simulate SQL execution latency
        await asyncio.sleep(random.uniform(1.0, 3.0))

        rows_affected = random.randint(10, 1000)
        dataset_ref = f"dataset/{node_id}/{random.randint(100, 999)}"

        logger.info(
            "[Plane C] FlinkSQL completed",
            node_id=node_id,
            rows_affected=rows_affected,
            dataset_ref=dataset_ref,
        )

        return NodeResult(
            node_id=node_id,
            status=StepStatus.COMPLETED,
            outputs={
                "job_id": f"flink-job-{random.randint(1000, 9999)}",
                "rows_affected": rows_affected,
                "dataset_ref": dataset_ref,
            },
        )
