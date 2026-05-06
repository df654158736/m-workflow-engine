"""SPI — NodeExecutor abstract interface.

All node executors must implement this interface. The engine discovers
executors via the registry and dispatches to them based on node_type.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from backend.models import Determinism, NodeResult, NodeType, Runtime


class NodeExecutor(ABC):
    """Abstract base for all node executors (SPI contract)."""

    @property
    @abstractmethod
    def node_type(self) -> NodeType:
        """Which node type this executor handles."""
        ...

    @property
    @abstractmethod
    def runtime(self) -> Runtime:
        """Which Plane this executor runs on."""
        ...

    @property
    def determinism(self) -> Determinism:
        return Determinism.DETERMINISTIC

    @abstractmethod
    async def execute(
        self,
        node_id: str,
        config: dict[str, Any],
        inputs: dict[str, Any],
    ) -> NodeResult:
        """Execute the node and return result."""
        ...


class ExecutorRegistry:
    """Registry of all available node executors (SPI discovery)."""

    def __init__(self) -> None:
        self._executors: dict[NodeType, NodeExecutor] = {}

    def register(self, executor: NodeExecutor) -> None:
        self._executors[executor.node_type] = executor

    def get(self, node_type: NodeType) -> NodeExecutor:
        if node_type not in self._executors:
            raise ValueError(
                f"No executor registered for {node_type}. "
                f"Available: {list(self._executors.keys())}"
            )
        return self._executors[node_type]

    def all_types(self) -> list[NodeType]:
        return list(self._executors.keys())
