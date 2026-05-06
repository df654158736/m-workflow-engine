"""check_output_compatibility — 校验节点间数据流兼容性。

检查 inputs 引用的上游 outputs 是否符合预期类型。
"""

from backend.agent.tool_registry import tool

# 各节点类型的标准 outputs
NODE_OUTPUT_SCHEMAS = {
    "LLM": {
        "text": "string - LLM 生成的文本",
        "model": "string - 使用的模型名",
        "tokens_used": "integer - 消耗的 token 数",
        "duration_ms": "integer - 耗时毫秒",
    },
    "FlinkSQL": {
        "dataset_ref": "string - 数据集引用 ID",
        "rows_affected": "integer - 影响的行数",
    },
    "Tool": {
        "tool_id": "string - 执行的工具 ID",
        "result": "object - 工具返回结果",
        "execution_id": "string - 执行追踪 ID",
    },
    "Function": {
        "function_id": "string - 执行的函数 ID",
        "result": "object - 函数返回值",
    },
    "Condition": {
        "result": "boolean - 条件评估结果",
        "branch": "string - 选择的分支名",
    },
    "Approval": {
        "decision": "string - APPROVED | REJECTED | TIMEOUT",
        "approver": "string - 审批人",
        "comment": "string - 审批意见",
    },
    "Sandbox": {
        "stdout": "string - 标准输出",
        "stderr": "string - 错误输出",
        "exit_code": "integer - 退出码",
        "result": "object - 程序返回值",
    },
}


@tool(
    name="check_output_compatibility",
    description="查询指定节点类型的 outputs 字段列表，确认 ${node.outputs.field} 引用是否正确。",
    parameters={
        "type": "object",
        "properties": {
            "node_type": {
                "type": "string",
                "description": "节点类型（LLM, Tool, FlinkSQL, Function, Condition, Approval, Sandbox）",
            },
        },
        "required": ["node_type"],
    },
)
async def check_output_compatibility(node_type: str) -> dict:
    schema = NODE_OUTPUT_SCHEMAS.get(node_type)
    if not schema:
        return {
            "found": False,
            "error": f"未知节点类型: {node_type}",
            "valid_types": list(NODE_OUTPUT_SCHEMAS.keys()),
        }
    return {
        "found": True,
        "node_type": node_type,
        "outputs": schema,
        "usage": f"引用方式: ${{node_id.outputs.<field>}}，可用 field: {list(schema.keys())}",
    }
