"""Core data models for the workflow engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Runtime(str, Enum):
    PLANE_B = "plane-b"
    PLANE_C = "plane-c"
    PLANE_D = "plane-d"
    PLANE_E = "plane-e"


class NodeType(str, Enum):
    LLM = "LLM"
    TOOL = "Tool"
    APPROVAL = "Approval"
    CONDITION = "Condition"
    SANDBOX = "Sandbox"
    FLINK_SQL = "FlinkSQL"
    FUNCTION = "Function"


class Determinism(str, Enum):
    DETERMINISTIC = "DETERMINISTIC"
    NONDETERMINISTIC_CACHEABLE = "NONDETERMINISTIC_CACHEABLE"
    SIDE_EFFECT = "SIDE_EFFECT"


class OnError(str, Enum):
    RETRY = "RETRY"
    SKIP = "SKIP"
    FAIL = "FAIL"


class StepStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


@dataclass
class NodeSpec:
    id: str
    type: NodeType
    config: dict[str, Any] = field(default_factory=dict)
    inputs: dict[str, str] = field(default_factory=dict)
    when: str | None = None
    on_error: OnError = OnError.FAIL


@dataclass
class EdgeSpec:
    from_node: str
    to_node: str
    condition: str | None = None


@dataclass
class WorkflowDefinition:
    id: str
    name: str = ""
    nodes: list[NodeSpec] = field(default_factory=list)
    edges: list[EdgeSpec] = field(default_factory=list)


@dataclass
class NodeResult:
    node_id: str
    status: StepStatus = StepStatus.COMPLETED
    outputs: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    duration_ms: int = 0
