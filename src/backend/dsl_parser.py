"""DSL Parser — YAML workflow definition → WorkflowDefinition model."""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Any

import yaml

from backend.models import EdgeSpec, NodeSpec, NodeType, OnError, WorkflowDefinition


def parse_yaml(yaml_content: str) -> WorkflowDefinition:
    """Parse YAML DSL into WorkflowDefinition."""
    data = yaml.safe_load(yaml_content)
    return _build_definition(data)


def parse_file(path: str) -> WorkflowDefinition:
    """Parse YAML file into WorkflowDefinition."""
    with open(path) as f:
        return parse_yaml(f.read())


def _build_definition(data: dict[str, Any]) -> WorkflowDefinition:
    nodes = [_parse_node(n) for n in data.get("nodes", [])]
    edges = [_parse_edge(e) for e in data.get("edges", [])]
    return WorkflowDefinition(
        id=data["workflow_id"],
        name=data.get("name", ""),
        nodes=nodes,
        edges=edges,
    )


def _parse_node(data: dict[str, Any]) -> NodeSpec:
    return NodeSpec(
        id=data["id"],
        type=NodeType(data["type"]),
        config=data.get("config", {}),
        inputs=data.get("inputs", {}),
        when=data.get("when"),
        on_error=OnError(data.get("on_error", "FAIL")),
    )


def _parse_edge(data: dict[str, Any]) -> EdgeSpec:
    return EdgeSpec(
        from_node=data["from"],
        to_node=data["to"],
        condition=data.get("condition"),
    )


def topological_sort(definition: WorkflowDefinition) -> list[str]:
    """Topological sort of nodes based on edges. Returns ordered node IDs."""
    in_degree: dict[str, int] = {n.id: 0 for n in definition.nodes}
    adjacency: dict[str, list[str]] = defaultdict(list)

    for edge in definition.edges:
        adjacency[edge.from_node].append(edge.to_node)
        in_degree[edge.to_node] = in_degree.get(edge.to_node, 0) + 1

    queue = deque(nid for nid, deg in in_degree.items() if deg == 0)
    result: list[str] = []

    while queue:
        node_id = queue.popleft()
        result.append(node_id)
        for neighbor in adjacency[node_id]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if len(result) != len(definition.nodes):
        raise ValueError("Cycle detected in workflow DAG")

    return result


def validate(definition: WorkflowDefinition) -> list[str]:
    """Validate a workflow definition. Returns list of errors (empty = valid)."""
    errors: list[str] = []

    if not definition.nodes:
        errors.append("Workflow has no nodes")

    node_ids = {n.id for n in definition.nodes}
    for edge in definition.edges:
        if edge.from_node not in node_ids:
            errors.append(f"Edge references unknown node: {edge.from_node}")
        if edge.to_node not in node_ids:
            errors.append(f"Edge references unknown node: {edge.to_node}")

    try:
        topological_sort(definition)
    except ValueError as e:
        errors.append(str(e))

    return errors
