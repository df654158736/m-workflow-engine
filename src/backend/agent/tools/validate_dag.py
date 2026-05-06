"""validate_dag — DAG 合法性校验工具。"""

from __future__ import annotations

import re
from collections import defaultdict, deque

import yaml

from backend.agent.tool_registry import tool
from backend.models import NodeType

VALID_TYPES = {e.value for e in NodeType}
REF_PATTERN = re.compile(r"\$\{(\w+)\.outputs\.(\w+)\}")


@tool(
    name="validate_dag",
    description="校验 YAML 工作流定义的 DAG 合法性。检查语法、结构、环、引用完整性。返回 {valid, errors, warnings, workflow_id}。",
    parameters={
        "type": "object",
        "properties": {
            "yaml_text": {
                "type": "string",
                "description": "要校验的 YAML 文本",
            }
        },
        "required": ["yaml_text"],
    },
)
async def validate_dag(yaml_text: str) -> dict:
    errors: list[str] = []
    warnings: list[str] = []

    # 1. YAML 语法
    try:
        data = yaml.safe_load(yaml_text)
    except yaml.YAMLError as e:
        return {"valid": False, "errors": [f"YAML 语法错误: {e}"], "warnings": [], "workflow_id": ""}

    if not isinstance(data, dict):
        return {"valid": False, "errors": ["YAML 顶层必须是字典"], "warnings": [], "workflow_id": ""}

    # 2. 必填字段
    workflow_id = data.get("workflow_id", "")
    if not workflow_id:
        errors.append("缺少 workflow_id 字段")

    nodes = data.get("nodes", [])
    if not nodes:
        errors.append("缺少 nodes 字段或为空")

    edges = data.get("edges", [])
    if not edges and len(nodes) > 1:
        warnings.append("有多个节点但没有 edges 定义，节点之间无依赖关系")

    if errors:
        return {"valid": False, "errors": errors, "warnings": warnings, "workflow_id": workflow_id}

    # 3. 节点 id 唯一性 & type 合法性
    node_ids: set[str] = set()
    for i, node in enumerate(nodes):
        if not isinstance(node, dict):
            errors.append(f"nodes[{i}] 不是字典")
            continue
        nid = node.get("id", "")
        if not nid:
            errors.append(f"nodes[{i}] 缺少 id")
            continue
        if nid in node_ids:
            errors.append(f"节点 id 重复: '{nid}'")
        node_ids.add(nid)

        ntype = node.get("type", "")
        if not ntype:
            errors.append(f"节点 '{nid}' 缺少 type")
        elif ntype not in VALID_TYPES:
            errors.append(f"节点 '{nid}' 的 type '{ntype}' 无效，可选: {sorted(VALID_TYPES)}")

        if not node.get("config"):
            warnings.append(f"节点 '{nid}' 没有 config 配置")

    # 4. Edges 引用存在性
    graph: dict[str, list[str]] = defaultdict(list)
    in_degree: dict[str, int] = {nid: 0 for nid in node_ids}
    referenced_in_edges: set[str] = set()

    for i, edge in enumerate(edges):
        if not isinstance(edge, dict):
            errors.append(f"edges[{i}] 不是字典")
            continue
        from_node = edge.get("from", edge.get("from_node", ""))
        to_node = edge.get("to", edge.get("to_node", ""))
        if not from_node:
            errors.append(f"edges[{i}] 缺少 from")
            continue
        if not to_node:
            errors.append(f"edges[{i}] 缺少 to")
            continue
        if from_node not in node_ids:
            errors.append(f"edges[{i}] 的 from '{from_node}' 不在 nodes 中")
        if to_node not in node_ids:
            errors.append(f"edges[{i}] 的 to '{to_node}' 不在 nodes 中")
        if from_node in node_ids and to_node in node_ids:
            graph[from_node].append(to_node)
            in_degree[to_node] = in_degree.get(to_node, 0) + 1
            referenced_in_edges.add(from_node)
            referenced_in_edges.add(to_node)

    # 5. 环检测（Kahn's algorithm）
    if not errors:
        queue = deque(n for n in node_ids if in_degree.get(n, 0) == 0)
        visited = 0
        temp_in = dict(in_degree)
        while queue:
            curr = queue.popleft()
            visited += 1
            for neighbor in graph.get(curr, []):
                temp_in[neighbor] -= 1
                if temp_in[neighbor] == 0:
                    queue.append(neighbor)
        if visited < len(node_ids):
            errors.append("DAG 中存在环（循环依赖），无法拓扑排序")

    # 6. 孤立节点检测
    for nid in node_ids:
        if nid not in referenced_in_edges and len(node_ids) > 1:
            warnings.append(f"节点 '{nid}' 是孤立的（没有入边也没有出边）")

    # 7. inputs 引用完整性
    upstream_map: dict[str, set[str]] = _build_upstream_map(node_ids, graph)
    for node in nodes:
        if not isinstance(node, dict):
            continue
        nid = node.get("id", "")
        inputs = node.get("inputs", {})
        if not isinstance(inputs, dict):
            continue
        for key, value in inputs.items():
            if not isinstance(value, str):
                continue
            match = REF_PATTERN.search(value)
            if match:
                ref_node = match.group(1)
                if ref_node not in node_ids:
                    errors.append(f"节点 '{nid}' 的 inputs.{key} 引用了不存在的节点 '{ref_node}'")
                elif ref_node not in upstream_map.get(nid, set()):
                    errors.append(
                        f"节点 '{nid}' 的 inputs.{key} 引用了 '{ref_node}'，"
                        f"但 '{ref_node}' 不是其上游节点（数据流方向错误）"
                    )

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "workflow_id": workflow_id,
        "node_count": len(node_ids),
        "edge_count": len(edges),
    }


def _build_upstream_map(node_ids: set[str], graph: dict[str, list[str]]) -> dict[str, set[str]]:
    """为每个节点构建其所有上游节点集合（传递闭包）。"""
    upstream: dict[str, set[str]] = {nid: set() for nid in node_ids}
    reverse_graph: dict[str, list[str]] = defaultdict(list)
    for src, dsts in graph.items():
        for dst in dsts:
            reverse_graph[dst].append(src)

    for nid in node_ids:
        visited = set()
        queue = deque(reverse_graph.get(nid, []))
        while queue:
            curr = queue.popleft()
            if curr in visited:
                continue
            visited.add(curr)
            upstream[nid].add(curr)
            queue.extend(reverse_graph.get(curr, []))
    return upstream
