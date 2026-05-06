"""list_available_tools — 查询系统中可用的 tool_id。

Agent 在需要创建 Tool 类型节点时，可以调用此工具查询有哪些 tool_id 可用。
"""

from backend.agent.tool_registry import tool

AVAILABLE_SYSTEM_TOOLS = [
    {
        "tool_id": "act-save-result",
        "description": "保存数据到本体存储",
        "args": {"target": "存储目标 (ontology|file|database)"},
    },
    {
        "tool_id": "act-send-notification",
        "description": "发送通知（支持钉钉/飞书/企微）",
        "args": {"channel": "通知渠道", "message": "通知内容"},
    },
    {
        "tool_id": "act-send-email",
        "description": "发送邮件",
        "args": {"recipients": "收件人列表", "subject": "邮件主题"},
    },
    {
        "tool_id": "act-execute-action",
        "description": "执行通用操作",
        "args": {"action": "操作名称"},
    },
    {
        "tool_id": "act-update-supplier-status",
        "description": "更新供应商状态（启用/禁用/拉黑）",
        "args": {"action": "blacklist|enable|disable|monitor"},
    },
    {
        "tool_id": "act-create-purchase-order",
        "description": "创建采购订单",
        "args": {"supplier_id": "供应商ID", "items": "采购明细"},
    },
    {
        "tool_id": "act-data-repair",
        "description": "数据修复操作",
        "args": {"mode": "auto|manual", "target_table": "目标表"},
    },
    {
        "tool_id": "act-archive-document",
        "description": "归档文档",
        "args": {"category": "文档类别"},
    },
    {
        "tool_id": "act-trigger-pipeline",
        "description": "触发数据 Pipeline",
        "args": {"pipeline_id": "Pipeline ID"},
    },
]


@tool(
    name="list_available_tools",
    description="查询系统中可用的 tool_id 列表及其参数说明。在创建 Tool 类型节点时调用此工具确认 tool_id 有效。",
    parameters={
        "type": "object",
        "properties": {
            "keyword": {
                "type": "string",
                "description": "可选：按关键词过滤（如 'notification'、'supplier'）",
            }
        },
        "required": [],
    },
)
async def list_available_tools(keyword: str = "") -> dict:
    if keyword:
        filtered = [
            t for t in AVAILABLE_SYSTEM_TOOLS
            if keyword.lower() in t["tool_id"].lower() or keyword.lower() in t["description"].lower()
        ]
    else:
        filtered = AVAILABLE_SYSTEM_TOOLS

    return {
        "tools": filtered,
        "total": len(AVAILABLE_SYSTEM_TOOLS),
        "filtered": len(filtered),
    }
