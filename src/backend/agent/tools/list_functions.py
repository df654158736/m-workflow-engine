"""list_available_functions — 查询可用的 function_id。

Agent 在需要创建 Function 类型节点时，调用此工具确认 function_id 有效。
"""

from backend.agent.tool_registry import tool

AVAILABLE_FUNCTIONS = [
    {
        "function_id": "fn-calculate-risk-score",
        "description": "综合风险评分计算（输入多维度指标，输出 0-1 评分）",
        "args": {"weights": "各维度权重 (可选)"},
        "returns": {"score": "float", "details": "dict"},
    },
    {
        "function_id": "fn-data-transform",
        "description": "通用数据格式转换（JSON/CSV/XML 互转）",
        "args": {"format": "目标格式 (json|csv|xml)", "mapping": "字段映射 (可选)"},
        "returns": {"result": "transformed data"},
    },
    {
        "function_id": "fn-dedup-merge",
        "description": "数据去重与合并（基于主键或相似度）",
        "args": {"key_fields": "主键字段列表", "strategy": "dedup|merge|both"},
        "returns": {"result": "dict", "removed_count": "int"},
    },
    {
        "function_id": "fn-threshold-check",
        "description": "阈值检测（超阈值返回告警明细）",
        "args": {"field": "检测字段", "threshold": "阈值", "operator": "gt|lt|eq|gte|lte"},
        "returns": {"triggered": "bool", "violations": "list"},
    },
    {
        "function_id": "fn-text-extract",
        "description": "从非结构化文本中提取结构化字段（正则 + 模板）",
        "args": {"pattern": "提取模式", "fields": "目标字段列表"},
        "returns": {"extracted": "dict"},
    },
    {
        "function_id": "fn-aggregate-stats",
        "description": "数据聚合统计（count/sum/avg/min/max/percentile）",
        "args": {"group_by": "分组字段 (可选)", "metrics": "统计指标列表"},
        "returns": {"stats": "dict"},
    },
    {
        "function_id": "fn-date-calc",
        "description": "日期计算（工作日加减、区间天数、周期判断）",
        "args": {"operation": "add|diff|is_workday", "params": "计算参数"},
        "returns": {"result": "date or int"},
    },
]


@tool(
    name="list_available_functions",
    description="查询可用的 function_id 列表及参数签名。创建 Function 类型节点时调用此工具确认 function_id 有效。",
    parameters={
        "type": "object",
        "properties": {
            "keyword": {
                "type": "string",
                "description": "可选：按关键词过滤（如 'risk'、'转换'）",
            }
        },
        "required": [],
    },
)
async def list_available_functions(keyword: str = "") -> dict:
    if keyword:
        kw = keyword.lower()
        filtered = [
            f for f in AVAILABLE_FUNCTIONS
            if kw in f["function_id"].lower() or kw in f["description"].lower()
        ]
    else:
        filtered = AVAILABLE_FUNCTIONS

    return {
        "functions": filtered,
        "total": len(AVAILABLE_FUNCTIONS),
        "filtered": len(filtered),
    }
