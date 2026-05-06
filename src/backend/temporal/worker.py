"""Temporal Worker — starts workers for each Plane's task queue.

In production, each Plane runs its own worker process. For this demo,
we start all 4 workers in one process to show multi-queue dispatch.
"""

from __future__ import annotations

import asyncio
import sys

import structlog
from temporalio.client import Client
from temporalio.worker import Worker

from backend.routing import ALL_QUEUES
from backend.temporal.activities import execute_node
from backend.temporal.workflow import WorkflowEngineWorkflow

logger = structlog.get_logger()

TEMPORAL_ADDRESS = "192.168.2.60:7233"


async def start_workers(queues: list[str] | None = None) -> None:
    """Start Temporal workers for specified queues (default: all).

    Each worker listens on its own task queue, simulating separate
    Plane processes (B/C/D/E) in a single demo process.
    """
    target_queues = queues or ALL_QUEUES

    logger.info("Connecting to Temporal", address=TEMPORAL_ADDRESS)
    client = await Client.connect(TEMPORAL_ADDRESS)
    logger.info("Connected to Temporal")

    workers: list[Worker] = []
    for queue in target_queues:
        # Only the first queue (plane-e-default) registers the Workflow.
        # All queues register the execute_node activity.
        if queue == "plane-e-default":
            w = Worker(
                client,
                task_queue=queue,
                workflows=[WorkflowEngineWorkflow],
                activities=[execute_node],
            )
        else:
            w = Worker(
                client,
                task_queue=queue,
                activities=[execute_node],
            )
        workers.append(w)
        logger.info(f"Worker registered for queue: {queue}")

    logger.info(
        "All workers starting",
        queues=target_queues,
        total=len(workers),
    )

    # Run all workers concurrently
    await asyncio.gather(*[w.run() for w in workers])


def main():
    """CLI entry point: wf-worker [queue1 queue2 ...]"""
    queues = sys.argv[1:] if len(sys.argv) > 1 else None
    if queues:
        print(f"Starting workers for queues: {queues}")
    else:
        print(f"Starting workers for ALL queues: {ALL_QUEUES}")

    asyncio.run(start_workers(queues))


if __name__ == "__main__":
    main()
