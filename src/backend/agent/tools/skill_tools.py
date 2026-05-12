"""get_skill_detail — Agent 按需查询领域知识的详细内容。

三层技能架构的 Layer 3 入口：Agent 通过 function calling 调用此工具，
按需获取完整的规则、示例和 few-shot，而不是一次性灌入所有内容。
"""

from __future__ import annotations

from backend.agent.tool_registry import tool
from backend.agent.skill_loader import SkillLoader

_skill_loader: SkillLoader | None = None


def set_skill_loader(loader: SkillLoader) -> None:
    global _skill_loader
    _skill_loader = loader


@tool(
    name="get_skill_detail",
    description=(
        "查询领域知识的详细内容。当你需要具体的规则、示例、few-shot 或参考表时调用。"
        "传入 skill_name 获取技能概要和可用 sections 列表；"
        "传入 skill_name + section 获取该 section 的完整详细内容。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "skill_name": {
                "type": "string",
                "description": "技能名称（如 'dag-quality', 'node-types', 'domain/supply-chain'）",
            },
            "section": {
                "type": "string",
                "description": "可选，指定查询的 section（如 'validate-errors', 'configs'）。不传则返回技能概要。",
            },
        },
        "required": ["skill_name"],
    },
)
async def get_skill_detail(skill_name: str, section: str | None = None) -> dict:
    if _skill_loader is None:
        return {"error": "SkillLoader 未初始化"}
    return _skill_loader.get_skill_detail(skill_name, section)
