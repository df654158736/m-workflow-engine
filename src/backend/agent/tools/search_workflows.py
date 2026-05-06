"""search_similar_workflows — 搜索历史工作流。

扫描 workflows/ 目录下已有 YAML 文件，按关键词匹配返回摘要。
Agent 可将匹配结果作为 few-shot 参考来生成更好的 DAG。
"""

from __future__ import annotations

from pathlib import Path

import yaml

from backend.agent.tool_registry import tool

WORKFLOWS_DIR = Path(__file__).parent.parent.parent.parent / "workflows"


def _scan_workflows() -> list[dict]:
    """扫描 workflows/ 目录，解析每个 YAML 文件的摘要。"""
    results = []
    if not WORKFLOWS_DIR.exists():
        return results

    for f in sorted(WORKFLOWS_DIR.glob("*.yaml")):
        try:
            data = yaml.safe_load(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(data, dict) or "nodes" not in data:
            continue

        nodes = data.get("nodes", [])
        node_types = []
        node_ids = []
        for n in nodes:
            if isinstance(n, dict):
                node_types.append(n.get("type", ""))
                node_ids.append(n.get("id", ""))

        results.append({
            "file": f.name,
            "workflow_id": data.get("workflow_id", ""),
            "name": data.get("name", f.stem),
            "node_count": len(nodes),
            "edge_count": len(data.get("edges", [])),
            "node_types": list(set(node_types)),
            "node_ids": node_ids,
            "searchable_text": f"{data.get('name', '')} {' '.join(node_ids)} {' '.join(node_types)}".lower(),
        })

    return results


@tool(
    name="search_similar_workflows",
    description="搜索 workflows/ 目录中的历史工作流。按关键词匹配，返回相似工作流的结构摘要，可作为 DAG 设计参考。",
    parameters={
        "type": "object",
        "properties": {
            "keyword": {
                "type": "string",
                "description": "搜索关键词（如 'supplier'、'数据质量'、'approval'）",
            },
            "max_results": {
                "type": "integer",
                "description": "最多返回几个结果（默认 3）",
            },
        },
        "required": ["keyword"],
    },
)
async def search_similar_workflows(keyword: str, max_results: int = 3) -> dict:
    all_workflows = _scan_workflows()
    if not all_workflows:
        return {"results": [], "total_available": 0, "message": "workflows/ 目录为空或不存在"}

    kw = keyword.lower()
    scored = []
    for wf in all_workflows:
        text = wf["searchable_text"]
        score = text.count(kw)
        if kw in wf.get("workflow_id", "").lower():
            score += 2
        if kw in wf.get("name", "").lower():
            score += 2
        if score > 0:
            scored.append((score, wf))

    scored.sort(key=lambda x: -x[0])
    top = scored[:max_results]

    results = []
    for _, wf in top:
        results.append({
            "workflow_id": wf["workflow_id"],
            "name": wf["name"],
            "file": wf["file"],
            "node_count": wf["node_count"],
            "edge_count": wf["edge_count"],
            "node_types": wf["node_types"],
            "node_ids": wf["node_ids"],
        })

    return {
        "results": results,
        "matched": len(results),
        "total_available": len(all_workflows),
    }
