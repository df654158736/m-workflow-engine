"""Memory Tools — Agent 记忆读写工具。

save_to_memory: Agent 生成 DAG 后保存为成功案例
recall_memory: Agent 规划前搜索相似历史案例
"""

from backend.agent.tool_registry import tool
from backend.agent.memory_store import get_memory_store


@tool(
    name="save_to_memory",
    description="保存当前工作流为成功案例。规划完成且用户确认后调用，供未来类似需求参考。",
    parameters={
        "type": "object",
        "properties": {
            "user_input": {
                "type": "string",
                "description": "用户的原始需求描述",
            },
            "yaml_text": {
                "type": "string",
                "description": "生成的 YAML 工作流文本",
            },
            "tags": {
                "type": "string",
                "description": "标签（逗号分隔，如 'supplier,risk,approval'）",
            },
        },
        "required": ["user_input", "yaml_text"],
    },
)
async def save_to_memory(user_input: str, yaml_text: str, tags: str = "") -> dict:
    store = get_memory_store()
    metadata = {}
    if tags:
        metadata["tags"] = [t.strip() for t in tags.split(",") if t.strip()]

    entry = store.save(
        mem_type="success",
        user_input=user_input,
        yaml_text=yaml_text,
        metadata=metadata,
    )
    stats = store.stats()
    return {
        "saved": True,
        "memory_id": entry.id,
        "memory_stats": stats,
    }


@tool(
    name="recall_memory",
    description="搜索历史成功案例。规划开始前调用，查看是否有类似需求的工作流可作为参考。",
    parameters={
        "type": "object",
        "properties": {
            "keyword": {
                "type": "string",
                "description": "搜索关键词（如 '供应商'、'数据质量'）",
            },
            "max_results": {
                "type": "integer",
                "description": "最多返回几条（默认 2）",
            },
        },
        "required": ["keyword"],
    },
)
async def recall_memory(keyword: str, max_results: int = 2) -> dict:
    store = get_memory_store()
    entries = store.search(keyword, mem_type="success", max_results=max_results)

    if not entries:
        return {"found": 0, "results": [], "message": "没有找到相关历史案例"}

    results = []
    for e in entries:
        results.append({
            "memory_id": e.id,
            "user_input": e.user_input,
            "yaml_preview": e.yaml_text[:500] if e.yaml_text else "",
            "tags": e.metadata.get("tags", []),
        })

    return {"found": len(results), "results": results}
