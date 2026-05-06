"""estimate_cost — 估算工作流执行成本。

对齐 zhice-paas 的 Cost/TokenCost/CostBudget 模型。
按节点类型分别估算 token 消耗、执行时间、费用。
"""

import yaml

from backend.agent.tool_registry import tool

NODE_COST_PROFILES: dict[str, dict] = {
    "LLM": {
        "avg_tokens": 2000,
        "avg_duration_sec": 8,
        "cost_per_call_yuan": 0.02,
        "description": "大模型推理（token 消耗最高）",
    },
    "Tool": {
        "avg_tokens": 0,
        "avg_duration_sec": 2,
        "cost_per_call_yuan": 0.001,
        "description": "系统操作（无 token 消耗）",
    },
    "FlinkSQL": {
        "avg_tokens": 0,
        "avg_duration_sec": 5,
        "cost_per_call_yuan": 0.005,
        "description": "数据查询/ETL（按数据量计费）",
    },
    "Function": {
        "avg_tokens": 0,
        "avg_duration_sec": 1,
        "cost_per_call_yuan": 0.0005,
        "description": "自定义函数（轻量计算）",
    },
    "Condition": {
        "avg_tokens": 0,
        "avg_duration_sec": 0.1,
        "cost_per_call_yuan": 0.0,
        "description": "条件判断（零成本）",
    },
    "Approval": {
        "avg_tokens": 0,
        "avg_duration_sec": 0,
        "cost_per_call_yuan": 0.0,
        "description": "人工审批（等待时间不计入）",
    },
    "Sandbox": {
        "avg_tokens": 0,
        "avg_duration_sec": 3,
        "cost_per_call_yuan": 0.002,
        "description": "沙箱代码执行（隔离环境）",
    },
}


@tool(
    name="estimate_cost",
    description="估算工作流的执行成本（token、时间、费用）。在 DAG 规划完成后调用，帮助判断工作流是否在预算内。",
    parameters={
        "type": "object",
        "properties": {
            "yaml_text": {
                "type": "string",
                "description": "要估算的 YAML 工作流文本",
            }
        },
        "required": ["yaml_text"],
    },
)
async def estimate_cost(yaml_text: str) -> dict:
    try:
        data = yaml.safe_load(yaml_text)
    except yaml.YAMLError as e:
        return {"error": f"YAML 解析失败: {e}"}

    if not isinstance(data, dict) or "nodes" not in data:
        return {"error": "YAML 缺少 nodes 定义"}

    nodes = data["nodes"]
    total_tokens = 0
    total_duration = 0.0
    total_cost = 0.0
    node_estimates = []

    for node in nodes:
        if not isinstance(node, dict):
            continue
        nid = node.get("id", "unknown")
        ntype = node.get("type", "Unknown")
        profile = NODE_COST_PROFILES.get(ntype)

        if not profile:
            node_estimates.append({"node_id": nid, "type": ntype, "error": "未知节点类型"})
            continue

        node_estimates.append({
            "node_id": nid,
            "type": ntype,
            "est_tokens": profile["avg_tokens"],
            "est_duration_sec": profile["avg_duration_sec"],
            "est_cost_yuan": profile["cost_per_call_yuan"],
        })
        total_tokens += profile["avg_tokens"]
        total_duration += profile["avg_duration_sec"]
        total_cost += profile["cost_per_call_yuan"]

    return {
        "summary": {
            "total_nodes": len(nodes),
            "est_total_tokens": total_tokens,
            "est_total_duration_sec": round(total_duration, 1),
            "est_total_cost_yuan": round(total_cost, 4),
        },
        "per_node": node_estimates,
        "budget_note": "实际成本取决于 LLM prompt 长度和数据量，以上为平均估算",
    }
