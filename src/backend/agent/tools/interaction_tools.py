"""交互工具 — 用按钮代替打字，让用户通过点击做选择。"""

import logging

from pydantic import BaseModel, Field

from backend.agent.tool_registry import tool

logger = logging.getLogger(__name__)


class AskUserChoiceArgs(BaseModel):
    question: str = Field(..., min_length=1, description="向用户展示的问题")
    options: list[dict] = Field(..., min_length=2, description="选项列表")
    choice: str = Field(default="", description="用户的选择（由系统填入）")


@tool(
    name="ask_user_choice",
    description=(
        "向用户展示一个选择题，用按钮代替打字。"
        "当你需要用户做决策（如：是否继续、选择方案 A 还是 B、确认/取消等）时调用此工具。"
        "不要用文字提问让用户打字回复，必须用此工具弹出按钮。"
        "⚠️ 交互式卡片：调用后会弹出选择按钮，等用户点击后返回结果。"
    ),
    args_model=AskUserChoiceArgs,
    parameters={
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "向用户展示的问题文字",
            },
            "options": {
                "type": "array",
                "description": "选项列表，每个选项包含 value, label, color(可选: green/blue/red/gray)",
                "items": {
                    "type": "object",
                    "properties": {
                        "value": {"type": "string", "description": "回传的值"},
                        "label": {"type": "string", "description": "按钮上显示的文字"},
                        "color": {"type": "string", "description": "按钮颜色: green/blue/red/gray"},
                    },
                    "required": ["value", "label"],
                },
            },
            "choice": {
                "type": "string",
                "description": "用户选择的值（不要填，系统自动回传）",
            },
        },
        "required": ["question", "options"],
    },
)
async def ask_user_choice(
    question: str,
    options: list,
    choice: str = "",
    _confirmed: bool = False,
) -> dict:
    if _confirmed and choice:
        logger.info("[ask_user_choice] user chose: %s", choice)
        return {"choice": choice}

    card_data = {
        "card_type": "choice",
        "title": question,
        "options": [
            {
                "value": opt.get("value", opt.get("label", "")),
                "label": opt.get("label", opt.get("value", "")),
                "color": opt.get("color", "blue"),
            }
            for opt in options
        ],
        "result_key": "choice",
    }

    return {
        "requires_confirmation": True,
        "confirmation_type": "interactive_card",
        "card_data": card_data,
        "tool": "ask_user_choice",
        "args": {"question": question, "options": options, "choice": ""},
        "message": question,
    }
