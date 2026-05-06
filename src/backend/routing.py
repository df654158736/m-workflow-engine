"""Node type → task queue routing table."""

from __future__ import annotations

from dataclasses import dataclass

from backend.models import NodeType, Runtime

PLANE_E_QUEUE = "plane-e-default"
PLANE_B_QUEUE = "plane-b-action"
PLANE_C_QUEUE = "plane-c-pipeline"
PLANE_D_QUEUE = "plane-d-function"

ALL_QUEUES = [PLANE_E_QUEUE, PLANE_B_QUEUE, PLANE_C_QUEUE, PLANE_D_QUEUE]


@dataclass(frozen=True)
class NodeRoute:
    node_type: NodeType
    runtime: Runtime
    task_queue: str


NODE_ROUTING_TABLE: dict[NodeType, NodeRoute] = {
    NodeType.LLM: NodeRoute(NodeType.LLM, Runtime.PLANE_E, PLANE_E_QUEUE),
    NodeType.CONDITION: NodeRoute(NodeType.CONDITION, Runtime.PLANE_E, PLANE_E_QUEUE),
    NodeType.SANDBOX: NodeRoute(NodeType.SANDBOX, Runtime.PLANE_E, PLANE_E_QUEUE),
    NodeType.TOOL: NodeRoute(NodeType.TOOL, Runtime.PLANE_B, PLANE_B_QUEUE),
    NodeType.APPROVAL: NodeRoute(NodeType.APPROVAL, Runtime.PLANE_B, PLANE_B_QUEUE),
    NodeType.FLINK_SQL: NodeRoute(NodeType.FLINK_SQL, Runtime.PLANE_C, PLANE_C_QUEUE),
    NodeType.FUNCTION: NodeRoute(NodeType.FUNCTION, Runtime.PLANE_D, PLANE_D_QUEUE),
}


def get_route(node_type: NodeType) -> NodeRoute:
    if node_type not in NODE_ROUTING_TABLE:
        raise ValueError(f"Unknown node type: {node_type}")
    return NODE_ROUTING_TABLE[node_type]


def get_queue_for_node(node_type: NodeType) -> str:
    return get_route(node_type).task_queue
