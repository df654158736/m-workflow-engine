"""Planning Agent — ReAct Loop 核心。

流程：
1. 加载相关 Skills 注入 system prompt
2. 进入 ReAct Loop（最多 max_iterations 轮）
3. 每轮：LLM 输出 → 如果是 tool_call → 执行工具 → 结果回传 → 下一轮
4. 直到 LLM 输出最终 YAML（finish_reason=stop 且包含 nodes）
5. 最终自动调一次 validate_dag 确保质量
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from typing import Any

import structlog
from openai import AsyncOpenAI

from backend.agent.tool_registry import ToolRegistry, get_registry
from backend.agent.skill_loader import SkillLoader
from backend.agent.memory_store import MemoryStore, get_memory_store

logger = structlog.get_logger()

SYSTEM_PROMPT_TEMPLATE = """你是一个工作流规划 Agent。用户给你业务需求，你将其分解为一个 DAG 工作流。

## 可用节点类型

- **LLM**: 调用大语言模型做分析/推理/生成。config 需要 prompt 和 model(固定用 qwen-plus)。
- **Tool**: 执行系统操作（写入数据库/调用外部API/发通知等）。config 需要 tool_id 和 args。
- **FlinkSQL**: 执行数据查询/ETL。config 需要 sql 和 sink。
- **Function**: 调用自定义函数做数据处理。config 需要 function_id。
- **Condition**: 条件判断分支。config 需要 expression、true_branch、false_branch。
- **Approval**: 人工审批节点，工作流暂停等人决策。config 需要 title、description、approvers。
- **Sandbox**: 执行用户自定义代码（隔离沙箱）。config 需要 code 和 language。

## YAML 格式要求

```yaml
workflow_id: wf-xxx
name: "名称"

nodes:
  - id: node_id          # 唯一标识，snake_case
    type: LLM            # 节点类型
    config: {{...}}       # 节点配置
    inputs:              # 引用上游输出（可选）
      key: "${{upstream_node.outputs.field}}"
    when: "表达式"       # 条件执行（可选）
    on_error: FAIL       # FAIL | SKIP | RETRY（可选）

edges:
  - from: node_a
    to: node_b
```

## ⚠️ 核心工作流程（严格按此顺序）

**你必须先生成 YAML，再用工具校验。不要花超过 1 轮来查询工具信息。**

1. 分析用户需求 → 立即生成完整 YAML（基于你对节点类型的了解直接生成）
2. 调用 `validate_dag` 校验你生成的 YAML
3. 如果校验有错误，修正后重新输出 YAML
4. 只在不确定某个 tool_id 是否存在时，才调用 `list_available_tools`
5. 只在不确定节点输出字段时，才调用 `check_output_compatibility`

**禁止行为**：不要连续多轮只调用查询工具而不生成 YAML。你的首要任务是生成 DAG。

## 关键规则

- 每个 node 的 id 必须在 edges 的 from/to 中被正确引用
- edges 必须构成有向无环图（DAG），不能有循环
- inputs 中的 ${{node.outputs.field}} 引用的 node 必须是其上游节点
- Approval 节点后通常需要条件判断（审批通过/拒绝走不同分支）
- Tool 节点的 tool_id 如果不确定是否存在，用 list_available_tools 确认

## 输出格式

直接用 yaml 代码块输出你的 DAG：

```yaml
<你的完整 YAML 内容>
```

系统会自动校验，如果有错误会告诉你，你只需修正后重新输出即可。

{skills_context}
"""


@dataclass
class PlanResult:
    success: bool
    yaml_text: str = ""
    workflow_id: str = ""
    errors: list[str] = field(default_factory=list)
    iterations: int = 0
    tool_calls_log: list[dict] = field(default_factory=list)
    thinking_log: list[str] = field(default_factory=list)


class PlanningAgent:
    """DAG Planning Agent with ReAct Loop."""

    def __init__(
        self,
        llm_client: AsyncOpenAI,
        model: str = "qwen-plus",
        tool_registry: ToolRegistry | None = None,
        skill_loader: SkillLoader | None = None,
        max_iterations: int = 8,
    ) -> None:
        self.llm = llm_client
        self.model = model
        self.tools = tool_registry or get_registry()
        self.skills = skill_loader or SkillLoader()
        self.memory = get_memory_store()
        self.max_iterations = max_iterations
        self._nudge_threshold = 3

    async def plan(self, user_input: str) -> PlanResult:
        """执行 ReAct 循环规划工作流。"""
        # 1. 加载相关 Skills
        skills_context = self.skills.load_relevant(user_input)
        system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
            skills_context=f"\n## 领域知识\n\n{skills_context}" if skills_context else ""
        )

        # 2. 召回历史经验
        memory_context = self._recall_similar(user_input)

        # 3. 初始化 messages
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
        ]
        if memory_context:
            messages.append({"role": "system", "content": memory_context})
        messages.append({"role": "user", "content": user_input})

        result = PlanResult(success=False)
        tool_schemas = self.tools.schemas() or None

        # 4. ReAct Loop
        for iteration in range(self.max_iterations):
            result.iterations = iteration + 1
            logger.info(f"Planning iteration {iteration + 1}/{self.max_iterations}")

            response = await self.llm.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=tool_schemas,
                temperature=0.2,
                max_tokens=4096,
            )

            choice = response.choices[0]
            message = choice.message

            # Case A: LLM 调用工具
            if message.tool_calls:
                messages.append(message.model_dump())
                for tool_call in message.tool_calls:
                    fn_name = tool_call.function.name
                    fn_args = json.loads(tool_call.function.arguments)

                    logger.info(f"Agent calling tool: {fn_name}", args=fn_args)
                    tool_result = await self.tools.execute(fn_name, fn_args)

                    result.tool_calls_log.append({
                        "iteration": iteration + 1,
                        "tool": fn_name,
                        "args": fn_args,
                        "result": tool_result,
                    })

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(tool_result, ensure_ascii=False),
                    })

                if iteration + 1 >= self._nudge_threshold:
                    messages.append({
                        "role": "user",
                        "content": "你已经用了多轮来查询信息。请立即根据已有信息生成完整的 YAML 工作流，用 ```yaml 代码块输出。",
                    })
                continue

            # Case B: LLM 输出文本
            content = message.content or ""
            messages.append({"role": "assistant", "content": content})
            result.thinking_log.append(content)

            yaml_text = self._extract_yaml(content)
            if not yaml_text and iteration + 1 >= self._nudge_threshold:
                messages.append({
                    "role": "user",
                    "content": "请直接输出 YAML 工作流，用 ```yaml 代码块包裹。不要再做额外分析。",
                })
                continue

            if yaml_text:
                # 最终校验
                final_check = await self.tools.execute("validate_dag", {"yaml_text": yaml_text})
                result.tool_calls_log.append({
                    "iteration": iteration + 1,
                    "tool": "validate_dag (final)",
                    "args": {"yaml_text": "..."},
                    "result": final_check,
                })

                if final_check.get("valid"):
                    result.success = True
                    result.yaml_text = yaml_text
                    result.workflow_id = final_check.get("workflow_id", "")
                    result.errors = []
                    self._auto_save_memory(user_input, yaml_text)
                    logger.info("Planning succeeded", iterations=iteration + 1)
                    return result
                else:
                    # 校验失败，让 Agent 修正
                    error_msg = json.dumps(final_check, ensure_ascii=False)
                    messages.append({
                        "role": "user",
                        "content": f"你输出的 YAML 校验未通过，请修正：\n{error_msg}\n\n请修正后重新输出完整 YAML。",
                    })
                    continue

        # 超过最大迭代次数
        result.errors = ["达到最大迭代次数，规划未完成"]
        logger.warning("Planning failed: max iterations reached")
        return result

    def _recall_similar(self, user_input: str) -> str:
        """从 Memory 中召回相似案例，拼接为参考 context。"""
        entries = self.memory.search(user_input, mem_type="success", max_results=2)
        if not entries:
            return ""

        parts = ["## 历史参考案例（以下是过去成功生成的类似工作流，仅供参考）\n"]
        for i, e in enumerate(entries, 1):
            preview = e.yaml_text[:600] if e.yaml_text else "(无)"
            parts.append(f"### 案例 {i}: {e.user_input}\n```yaml\n{preview}\n```\n")
        return "\n".join(parts)

    def _auto_save_memory(self, user_input: str, yaml_text: str) -> None:
        """规划成功后自动保存到记忆。"""
        try:
            self.memory.save(
                mem_type="success",
                user_input=user_input,
                yaml_text=yaml_text,
            )
            logger.info("Memory saved", user_input=user_input[:50])
        except Exception as e:
            logger.warning("Failed to save memory", error=str(e))

    def _extract_yaml(self, text: str) -> str:
        """从 LLM 输出中提取 YAML 代码块。"""
        # 尝试提取 ```yaml ... ``` 代码块
        if "```yaml" in text:
            parts = text.split("```yaml")
            if len(parts) >= 2:
                yaml_part = parts[-1].split("```")[0]
                return yaml_part.strip()

        # 尝试提取 ``` ... ``` 代码块（无语言标记）
        if "```" in text:
            parts = text.split("```")
            for i in range(1, len(parts), 2):
                candidate = parts[i].strip()
                if "workflow_id:" in candidate and "nodes:" in candidate:
                    return candidate

        # 如果整段文本看起来就是 YAML
        stripped = text.strip()
        if stripped.startswith("workflow_id:") and "nodes:" in stripped:
            return stripped

        return ""
