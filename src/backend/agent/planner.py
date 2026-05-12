"""Planning Agent — ReAct Loop 核心。

流程：
1. 加载相关 Skills 注入 system prompt
2. 进入 ReAct Loop（最多 max_iterations 轮）
3. 每轮：LLM 输出 → 如果是 tool_call → 执行工具 → 结果回传 → 下一轮
4. 直到 LLM 输出最终 YAML（finish_reason=stop 且包含 nodes）
5. 最终自动调一次 validate_dag 确保质量

Session 模式（datafirst）：
- 首次请求创建 Session，后续请求通过 session_id 追加到同一个 messages
- tool_call / tool_result 完整保留在 Session 中
- Agent 输出文本时暂停返回，用户回复后从断点恢复
"""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from typing import Any

import structlog
from openai import AsyncOpenAI

from backend.agent.tool_registry import ToolRegistry, get_registry
from backend.agent.skill_loader import SkillLoader
from backend.agent.memory_store import MemoryStore, get_memory_store
from backend.agent.session import Session, SessionStore, get_session_store, truncate_tool_result

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

DATAFIRST_TOOLS = {
    "list_datasources",
    "list_tables",
    "scan_table_columns",
    "list_object_types",
    "create_object_type",
    "ai_infer_properties",
    "get_object_type_detail",
    "update_object_type_properties",
    "finalize_and_publish",
    "delete_object_type",
    "create_fabric_task",
    "trigger_ai_analysis",
    "get_field_mappings",
    "generate_pipeline",
    "submit_compare_decisions",
    "confirm_field_mappings",
    "submit_pipeline",
    "ask_user_choice",
    "get_skill_detail",
}

DATAFIRST_PROMPT_TEMPLATE = """你是一个数据接入助手 Agent。用户用自然语言描述数据接入需求，你通过调用工具完成全流程。

## ⚠️ 多轮对话

这是一个持续的多轮对话。你的 messages 中包含之前所有轮次的完整内容，包括你调用过的工具和返回结果。

**你必须基于已有上下文继续工作，而不是重新开始。**

常见的延续场景：
- 用户回复 "确认"/"好的"/"创建"/"提交"/"继续" → 执行你上一轮提出的方案
- 用户回复 "修改" + 具体内容 → 按修改意见调整方案
- 用户提出新需求 → 才从标准流程第 1 步开始

**禁止行为**：
- ❌ 用户说"确认"时，不要重新查询数据源/表/本体，直接执行上一轮提出的操作
- ❌ 忽略已经获取的信息（数据源ID、表结构、已设计的属性等）
- ❌ 让用户重复提供已经提供过的信息

## 你的能力

你可以调用以下工具完成数据接入的完整流程：

### 查询类工具
- `list_datasources` — 列出已有数据源（ID、名称、类型、状态）
- `list_tables` — 列出某个数据源的所有表（表名、schema、行数、备注）
- `scan_table_columns` — 扫描某张表的列元数据（列名、类型、主键）
- `list_object_types` — 列出已有 ObjectType（避免重复创建）

### 本体操作工具
- `ai_infer_properties` — AI 根据表列推荐 ObjectType 属性
- `create_object_type` — 创建 ObjectType 并自动定稿发布（⚠️ 写操作，需用户确认）
  - **必须传 datasource_id 和 table_name**（从之前工具获取的值）
  - 每个属性**必须包含 display_name（中文名）和 source_column（源表列名）**
  - 示例属性: `{{"property_name":"sku","display_name":"SKU编码","type":"String","required":true,"is_primary_key":false,"source_column":"sku"}}`

### 本体补全工具（处理半成品 ObjectType）
- `get_object_type_detail` — 查看 ObjectType 详情：当前状态（EDITING/DRAFT/ACTIVE）、已有属性、数据映射
- `update_object_type_properties` — 向已有 ObjectType 批量添加属性（⚠️ 交互式卡片，一次传所有缺失属性，用户勾选后提交）
- `finalize_and_publish` — 将 EDITING/DRAFT 状态的 ObjectType 定稿发布为 ACTIVE
- `delete_object_type` — 删除 ObjectType 及所有关联资源（⚠️ 不可逆，必须用户确认）

### 数据编织工具
- `create_fabric_task` — 创建数据编织任务
- `trigger_ai_analysis` — 触发 AI 语义分析，返回候选对象列表
- `get_field_mappings` — 获取/生成字段映射建议
- `generate_pipeline` — 生成 Pipeline DSL
- `submit_pipeline` — 将 Pipeline 注册到系统并可选立即运行（⚠️ 写操作，需用户确认）
- `submit_compare_decisions` — 对候选对象批量提交确认/驳回/新建决策（⚠️ 交互式卡片，需用户点击确认）
- `confirm_field_mappings` — 对字段映射进行交互式确认/跳过（⚠️ 交互式卡片，需用户点击确认）

### 交互工具
- `ask_user_choice` — 向用户弹出选择按钮（⚠️ 交互式卡片）
  - **必须用此工具代替文字提问**。需要用户做决策时（是否继续、选方案、确认/取消），调此工具弹出按钮，不要让用户打字回答。
  - 参数: question（问题文字）、options（选项列表，每项含 value/label/color 字段）
  - 用户点击后 choice 字段会自动填入用户的选择

## 标准流程（仅在新需求时从头开始）

1. **查数据源** → `list_datasources` 找到目标数据源
2. **列出表** → `list_tables` 查看数据源中有哪些表
3. **扫描表结构** → `scan_table_columns` 获取指定表的列信息
4. **检查已有本体** → `list_object_types` 避免重复
5. **设计本体** → 可选用 `ai_infer_properties`，或根据表列自行设计
6. **向用户展示方案** → 列出推荐的 ObjectType 名称和属性，等待用户确认
7. **创建 ObjectType** → 用户确认后调用 `create_object_type`（传 datasource_id + table_name，会自动创建编织任务、字段映射和 Pipeline）
8. **完成** → 告知用户实体和 Pipeline 已创建成功

> 注意：`create_object_type` 传了 datasource_id 后，会自动完成编织任务创建、字段映射、Pipeline 生成。
> 不需要再手动调 `create_fabric_task` / `get_field_mappings` / `generate_pipeline`。

## 半成品补全流程（用户要求补全已有但未完成的 ObjectType）

当 `list_object_types` 发现状态为 EDITING 或 DRAFT 的 ObjectType 时，说明创建未完成。按以下步骤处理：

1. **查详情** → `get_object_type_detail` 查看当前已有哪些属性、缺什么
2. **对比表结构** → 如有 datasource_id，用 `scan_table_columns` 获取表列，与已有属性对比找出缺失项
3. **向用户展示** → 告知"该 ObjectType 已存在，状态为 X，已有 N 个属性，缺少以下属性：…"
4. **补全属性** → 用户确认后，用 `update_object_type_properties` 一次性传入所有缺失属性（批量添加，只弹一次确认）
5. **定稿发布** → 属性补全后，调 `finalize_and_publish` 将其推进到 ACTIVE 状态

**判断逻辑**：
- 状态 EDITING + 属性不全 → 补属性 → finalize → publish
- 状态 EDITING + 属性已全 → 直接 finalize → publish
- 状态 DRAFT → 直接 publish
- 状态 ACTIVE → 已完成，告知用户无需操作

## 关键规则

1. **写操作必须确认** — 创建 ObjectType 前，必须向用户展示方案并等待确认
2. **渐进式推进** — 每步完成后汇报结果，等用户确认再继续下一步
3. **错误恢复** — API 报错时，向用户说明原因并给出替代方案
4. **已有资源复用** — 操作前先查询已有资源，避免重复创建
5. **禁止文字提问** — 需要用户做选择/决策/确认时，必须调 `ask_user_choice` 弹出按钮，不要用文字提问让用户打字回答。每次展示方案或汇报结果后，立即调 ask_user_choice 让用户点按钮决定下一步。

## 复杂任务规划（Plan-then-Execute）

当用户的需求涉及多步骤操作时（如"帮我接入这3张表"、"批量创建本体"），你必须：

1. **先规划再执行** — 列出完整的执行计划（要操作哪些表/本体、每步做什么），让用户确认后再逐步执行
2. **计划格式** — 用编号列表展示，标注每步涉及的工具和预期结果：
   ```
   执行计划：
   1. 扫描表 A 的列结构 → scan_table_columns
   2. 扫描表 B 的列结构 → scan_table_columns
   3. 设计 ObjectType X（基于表 A）→ 展示方案
   4. 设计 ObjectType Y（基于表 B）→ 展示方案
   5. 用户确认后依次创建
   ```
3. **分批确认** — 查询类工具可以批量执行无需逐一确认；写操作在展示完整方案后一次确认
4. **进度播报** — 每完成一个主要步骤，简要汇报进度（如"已完成 2/5：表 A 结构已扫描"）

对于简单的单步需求（如"查一下有哪些数据源"），直接执行即可，不需要规划。

## 本体对象探查流程（多表批量分析）

当用户要求"探查"、"分析这些表"、"批量发现本体对象"时，使用探查流程（而非一步到位的 create_object_type）：

1. **创建编织任务** → `create_fabric_task`
2. **触发 AI 分析** → `trigger_ai_analysis`，获取候选对象列表（每个候选有 id、名称、匹配状态、置信度、来源表）
3. **提交建议决策** → `submit_compare_decisions`，传入 task_id 和每个候选的建议决策
   - 系统会自动弹出交互式卡片，用户在卡片中逐个点击确认/驳回/新建
   - 用户提交后，你会收到最终的决策结果（用户可能修改你的建议）
4. **生成字段映射** → 对每个已确认的对象，先调 `get_field_mappings` 获取映射列表，再调 `confirm_field_mappings` 弹出交互卡片让用户确认
   - `confirm_field_mappings` 会自动弹出交互式卡片，用户在卡片中逐个确认/跳过每个字段映射
   - decisions 的 key 是 get_field_mappings 返回的映射 id，value 是 CONFIRM 或 SKIP
   - AI_SUGGESTED 状态的映射建议设为 CONFIRM
5. **生成 Pipeline** → 调 `generate_pipeline`
6. **提交并运行** → 调 `submit_pipeline` 将 Pipeline 注册到系统并触发运行

> 注意：`submit_compare_decisions` 会自动从后端查询候选对象并构造交互卡片，你只需传 task_id 和 decisions。
> decisions 中的 key 是 `trigger_ai_analysis` 返回的候选 id，value 是你的建议（MAPPED/MATCHABLE → CONFIRM，NEW → CREATE）。

## 回复风格

- 简洁明了，不要长篇大论
- 展示工具调用的关键结果，不要原样输出 JSON
- 方案展示用表格格式（属性名、类型、说明）
- 每步完成后，告诉用户下一步是什么
- **绝对禁止用文字向用户提问或列选项让用户打字回答**。任何需要用户做选择的地方（"请选择"、"你倾向哪种"、"是否继续"），必须立即调 `ask_user_choice` 弹出按钮。违反此规则 = 任务失败。

{skills_context}
"""


_REACT_LOOP_TIMEOUT_SECONDS = 120
_LLM_MAX_RETRIES = 3
_LLM_RETRY_BASE_DELAY = 1.0


@dataclass
class PlanResult:
    success: bool
    yaml_text: str = ""
    workflow_id: str = ""
    session_id: str = ""
    errors: list[str] = field(default_factory=list)
    iterations: int = 0
    tool_calls_log: list[dict] = field(default_factory=list)
    thinking_log: list[str] = field(default_factory=list)
    requires_confirmation: bool = False
    pending_tool: dict | None = None
    tokens_used: int = 0


@dataclass
class AgentEvent:
    type: str   # thinking / tool_call / tool_result / text / confirmation / error / done
    data: dict = field(default_factory=dict)


class PlanningAgent:
    """DAG Planning Agent with ReAct Loop."""

    def __init__(
        self,
        llm_client: AsyncOpenAI,
        model: str = "qwen-plus",
        tool_registry: ToolRegistry | None = None,
        skill_loader: SkillLoader | None = None,
        max_iterations: int = 15,
    ) -> None:
        self.llm = llm_client
        self.model = model
        self.tools = tool_registry or get_registry()
        self.skills = skill_loader or SkillLoader()
        from backend.agent.tools.skill_tools import set_skill_loader
        set_skill_loader(self.skills)
        self.memory = get_memory_store()
        self.sessions = get_session_store()
        self.max_iterations = max_iterations
        self._nudge_threshold = 3

    async def _llm_call(self, messages, tool_schemas, stream=False):
        """LLM 调用，带指数退避重试。"""
        last_exc = None
        for attempt in range(_LLM_MAX_RETRIES):
            try:
                kwargs = dict(
                    model=self.model,
                    messages=messages,
                    tools=tool_schemas,
                    temperature=0.2,
                    max_tokens=4096,
                    stream=stream,
                )
                if stream:
                    kwargs["stream_options"] = {"include_usage": True}
                return await self.llm.chat.completions.create(**kwargs)
            except Exception as e:
                last_exc = e
                if attempt < _LLM_MAX_RETRIES - 1:
                    delay = _LLM_RETRY_BASE_DELAY * (2 ** attempt)
                    logger.warning(f"LLM call failed (attempt {attempt + 1}/{_LLM_MAX_RETRIES}), retrying in {delay}s: {e}")
                    await asyncio.sleep(delay)
        raise last_exc

    def _build_system_messages(self, user_input: str, mode: str) -> list[dict[str, Any]]:
        """构建 system prompt messages。"""
        skills_context = self.skills.load_relevant(user_input, mode=mode)
        template = DATAFIRST_PROMPT_TEMPLATE if mode == "datafirst" else SYSTEM_PROMPT_TEMPLATE
        system_prompt = template.format(
            skills_context=f"\n## 领域知识\n\n{skills_context}" if skills_context else ""
        )

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
        ]

        memory_context = self._recall_similar(user_input)
        if memory_context:
            messages.append({"role": "system", "content": memory_context})

        return messages

    async def plan(self, user_input: str, mode: str = "workflow") -> PlanResult:
        """无状态规划（workflow 模式使用）。"""
        system_msgs = self._build_system_messages(user_input, mode)
        messages = system_msgs + [{"role": "user", "content": user_input}]
        return await self._react_loop(messages, mode, tool_calls_log=[])

    async def chat(
        self,
        user_input: str,
        session_id: str | None = None,
        confirmed_tool: dict | None = None,
    ) -> PlanResult:
        """有状态对话（datafirst 模式使用）。

        session_id 为空时创建新 Session；
        有值时追加用户消息到已有 Session 继续。
        confirmed_tool: 用户确认执行的工具 {"tool": "xxx", "args": {...}}
        """
        mode = "datafirst"

        if session_id:
            session = await self.sessions.get(session_id)
            if not session:
                return PlanResult(
                    success=False,
                    errors=["会话已过期或不存在，请重新开始对话"],
                )
        else:
            system_msgs = self._build_system_messages(user_input, mode)
            session = await self.sessions.create(mode, system_msgs)

        if confirmed_tool:
            tool_result = await self.tools.execute(
                confirmed_tool["tool"],
                confirmed_tool["args"],
                confirmed=True,
            )
            session.messages.append({
                "role": "tool",
                "tool_call_id": confirmed_tool.get("tool_call_id", "confirmed"),
                "content": json.dumps(tool_result, ensure_ascii=False),
            })
        else:
            session.messages.append({"role": "user", "content": user_input})

        if session.needs_compact():
            session.compact()

        turn_tool_calls: list[dict] = []
        try:
            result = await asyncio.wait_for(
                self._react_loop(
                    session.messages,
                    mode,
                    tool_calls_log=turn_tool_calls,
                ),
                timeout=_REACT_LOOP_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            result = PlanResult(
                success=False,
                errors=["对话处理超时，请重试。可能是下游服务响应过慢。"],
            )
        session.tool_calls_log.extend(turn_tool_calls)
        session.total_tokens += result.tokens_used
        await self.sessions.save(session)
        result.tool_calls_log = turn_tool_calls
        result.session_id = session.session_id
        result.tokens_used = session.total_tokens
        return result

    async def _react_loop(
        self,
        messages: list[dict[str, Any]],
        mode: str,
        tool_calls_log: list[dict],
    ) -> PlanResult:
        """核心 ReAct 循环。messages 是引用传递，会被原地修改。"""
        result = PlanResult(success=False)
        result.tool_calls_log = tool_calls_log

        if mode == "datafirst":
            tool_schemas = self.tools.schemas(only=DATAFIRST_TOOLS) or None
        else:
            tool_schemas = self.tools.schemas() or None

        for iteration in range(self.max_iterations):
            result.iterations = iteration + 1
            logger.info(f"Planning iteration {iteration + 1}/{self.max_iterations}")

            try:
                response = await self._llm_call(messages, tool_schemas, stream=False)
            except Exception as e:
                logger.warning(f"LLM call failed after {_LLM_MAX_RETRIES} retries: {e}")
                result.errors = [f"LLM 调用失败: {str(e)}"]
                return result

            if response.usage:
                result.tokens_used += response.usage.total_tokens

            choice = response.choices[0]
            message = choice.message

            # Case A: LLM 调用工具
            if message.tool_calls:
                msg_dict = message.model_dump()
                for tc in msg_dict.get("tool_calls", []):
                    args_str = tc.get("function", {}).get("arguments", "")
                    try:
                        json.loads(args_str)
                    except (json.JSONDecodeError, TypeError):
                        tc["function"]["arguments"] = "{}"
                messages.append(msg_dict)

                # Phase 1: 解析所有 tool_calls
                parsed_calls = []
                for tool_call in message.tool_calls:
                    fn_name = tool_call.function.name
                    try:
                        fn_args = json.loads(tool_call.function.arguments)
                    except json.JSONDecodeError:
                        logger.warning(f"Invalid JSON in tool_call args for {fn_name}")
                        err = {"error": f"参数 JSON 格式错误，请重新调用 {fn_name}，确保参数是合法 JSON"}
                        tool_calls_log.append({
                            "iteration": iteration + 1,
                            "tool": fn_name,
                            "args": {"_raw": tool_call.function.arguments[:200]},
                            "result": err,
                        })
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": json.dumps(err, ensure_ascii=False),
                        })
                        continue
                    parsed_calls.append((tool_call, fn_name, fn_args))

                # Phase 2: 并行执行所有工具
                if parsed_calls:
                    async def _exec_one(tc, name, args):
                        logger.info(f"Agent calling tool: {name}", args=args)
                        res = await self.tools.execute(name, args)
                        return tc, name, args, res

                    tasks = [_exec_one(tc, n, a) for tc, n, a in parsed_calls]
                    outcomes = await asyncio.gather(*tasks, return_exceptions=True)

                    # Phase 3: 处理结果
                    pending_confirmation = None
                    for i, outcome in enumerate(outcomes):
                        if isinstance(outcome, Exception):
                            orig_tc, orig_name, orig_args = parsed_calls[i]
                            logger.warning(f"Tool execution exception: {orig_name}: {outcome}")
                            err_result = {"error": f"工具 '{orig_name}' 执行异常: {outcome}"}
                            tool_calls_log.append({
                                "iteration": iteration + 1,
                                "tool": orig_name,
                                "args": orig_args,
                                "result": err_result,
                            })
                            messages.append({
                                "role": "tool",
                                "tool_call_id": orig_tc.id,
                                "content": json.dumps(err_result, ensure_ascii=False),
                            })
                            continue
                        tc, fn_name, fn_args, tool_result = outcome

                        tool_calls_log.append({
                            "iteration": iteration + 1,
                            "tool": fn_name,
                            "args": fn_args,
                            "result": tool_result,
                        })

                        if tool_result.get("requires_confirmation"):
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tc.id,
                                "content": json.dumps({
                                    "status": "waiting_confirmation",
                                    "tool": fn_name,
                                    "args": fn_args,
                                    "message": tool_result["message"],
                                }, ensure_ascii=False),
                            })
                            if not pending_confirmation:
                                pending_confirmation = (tc, fn_name, fn_args, tool_result)
                            continue

                        result_str = json.dumps(tool_result, ensure_ascii=False)
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": truncate_tool_result(result_str),
                        })

                    if pending_confirmation:
                        tc, fn_name, fn_args, conf_result = pending_confirmation
                        result.success = True
                        result.requires_confirmation = True
                        conf_type = conf_result.get("confirmation_type")
                        if conf_type == "interactive_card" and conf_result.get("card_data"):
                            result.yaml_text = f"操作 '{fn_name}' 需要用户通过交互卡片确认。"
                            result.pending_tool = {
                                "tool": fn_name,
                                "args": fn_args,
                                "tool_call_id": tc.id,
                                "confirmation_type": conf_type,
                                "card_data": conf_result["card_data"],
                            }
                        else:
                            result.yaml_text = f"操作 '{fn_name}' 需要您确认后才能执行。"
                            result.pending_tool = {
                                "tool": fn_name,
                                "args": fn_args,
                                "tool_call_id": tc.id,
                            }
                        result.iterations = iteration + 1
                        return result

                if mode != "datafirst" and iteration + 1 >= self._nudge_threshold:
                    messages.append({
                        "role": "user",
                        "content": "你已经用了多轮来查询信息。请立即根据已有信息生成完整的 YAML 工作流，用 ```yaml 代码块输出。",
                    })
                continue

            # Case B: LLM 输出文本
            content = message.content or ""
            messages.append({"role": "assistant", "content": content})
            result.thinking_log.append(content)

            # datafirst 模式：Agent 输出文本即为最终回复（暂停等用户）
            if mode == "datafirst":
                if choice.finish_reason == "stop":
                    result.success = True
                    result.yaml_text = content
                    logger.info("Datafirst response complete", iterations=iteration + 1)
                    return result
                continue

            yaml_text = self._extract_yaml(content)
            if not yaml_text and iteration + 1 >= self._nudge_threshold:
                messages.append({
                    "role": "user",
                    "content": "请直接输出 YAML 工作流，用 ```yaml 代码块包裹。不要再做额外分析。",
                })
                continue

            if yaml_text:
                final_check = await self.tools.execute("validate_dag", {"yaml_text": yaml_text})
                tool_calls_log.append({
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
                    self._auto_save_memory(
                        self._find_user_input(messages),
                        yaml_text,
                    )
                    logger.info("Planning succeeded", iterations=iteration + 1)
                    return result
                else:
                    error_msg = json.dumps(final_check, ensure_ascii=False)
                    messages.append({
                        "role": "user",
                        "content": f"你输出的 YAML 校验未通过，请修正：\n{error_msg}\n\n请修正后重新输出完整 YAML。",
                    })
                    continue

        result.errors = ["达到最大迭代次数，规划未完成"]
        logger.warning("Planning failed: max iterations reached")
        return result

    def _find_user_input(self, messages: list[dict[str, Any]]) -> str:
        """从 messages 中找到第一条 user 消息。"""
        for m in messages:
            if m.get("role") == "user":
                return m.get("content", "")
        return ""

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
        if "```yaml" in text:
            parts = text.split("```yaml")
            if len(parts) >= 2:
                yaml_part = parts[-1].split("```")[0]
                return yaml_part.strip()

        if "```" in text:
            parts = text.split("```")
            for i in range(1, len(parts), 2):
                candidate = parts[i].strip()
                if "workflow_id:" in candidate and "nodes:" in candidate:
                    return candidate

        stripped = text.strip()
        if stripped.startswith("workflow_id:") and "nodes:" in stripped:
            return stripped

        return ""

    # ── 流式路径 ──────────────────────────────────────────────

    async def chat_stream(
        self,
        user_input: str,
        session_id: str | None = None,
        confirmed_tool: dict | None = None,
    ) -> AsyncGenerator[AgentEvent, None]:
        """有状态对话 — 流式版本。"""
        mode = "datafirst"

        if session_id:
            session = await self.sessions.get(session_id)
            if not session:
                yield AgentEvent(type="error", data={"message": "会话已过期或不存在，请重新开始对话"})
                return
        else:
            system_msgs = self._build_system_messages(user_input, mode)
            session = await self.sessions.create(mode, system_msgs)

        if confirmed_tool:
            tool_result = await self.tools.execute(
                confirmed_tool["tool"],
                confirmed_tool["args"],
                confirmed=True,
            )
            session.messages.append({
                "role": "tool",
                "tool_call_id": confirmed_tool.get("tool_call_id", "confirmed"),
                "content": json.dumps(tool_result, ensure_ascii=False),
            })
        else:
            session.messages.append({"role": "user", "content": user_input})

        if session.needs_compact():
            session.compact()

        tool_calls_log: list[dict] = []
        token_counter = [0]
        try:
            async for event in self._react_loop_stream(
                session.messages, mode, tool_calls_log, token_counter,
            ):
                yield event
        except asyncio.TimeoutError:
            yield AgentEvent(type="error", data={"message": "对话处理超时，请重试。"})

        session.tool_calls_log.extend(tool_calls_log)
        session.total_tokens += token_counter[0]
        await self.sessions.save(session)
        yield AgentEvent(type="done", data={
            "session_id": session.session_id,
            "iterations": len(tool_calls_log),
            "total_tokens": session.total_tokens,
        })

    async def _react_loop_stream(
        self,
        messages: list[dict[str, Any]],
        mode: str,
        tool_calls_log: list[dict],
        token_counter: list[int] | None = None,
    ) -> AsyncGenerator[AgentEvent, None]:
        """核心 ReAct 循环 — 流式版本（仅 datafirst 模式）。"""
        if mode == "datafirst":
            tool_schemas = self.tools.schemas(only=DATAFIRST_TOOLS) or None
        else:
            tool_schemas = self.tools.schemas() or None

        for iteration in range(self.max_iterations):
            logger.info(f"Stream iteration {iteration + 1}/{self.max_iterations}")

            try:
                response_stream = await self._llm_call(messages, tool_schemas, stream=True)
            except Exception as e:
                yield AgentEvent(type="error", data={"message": f"LLM 调用失败（重试 {_LLM_MAX_RETRIES} 次后）: {e}"})
                return

            collected_content = ""
            tool_call_chunks: dict[int, dict] = {}
            finish_reason = None

            async for chunk in response_stream:
                if hasattr(chunk, "usage") and chunk.usage:
                    if token_counter is not None:
                        token_counter[0] += chunk.usage.total_tokens
                choice = chunk.choices[0] if chunk.choices else None
                if not choice:
                    continue

                finish_reason = choice.finish_reason
                delta = choice.delta

                if delta.content:
                    collected_content += delta.content
                    yield AgentEvent(type="thinking", data={
                        "delta": delta.content,
                        "content": collected_content,
                    })

                if delta.tool_calls:
                    for tc_delta in delta.tool_calls:
                        idx = tc_delta.index
                        if idx not in tool_call_chunks:
                            tool_call_chunks[idx] = {"id": "", "name": "", "arguments": ""}
                        if tc_delta.id:
                            tool_call_chunks[idx]["id"] = tc_delta.id
                        if tc_delta.function:
                            if tc_delta.function.name:
                                tool_call_chunks[idx]["name"] = tc_delta.function.name
                            if tc_delta.function.arguments:
                                tool_call_chunks[idx]["arguments"] += tc_delta.function.arguments

            # 处理收集到的 tool_calls
            if tool_call_chunks:
                assembled = []
                for idx in sorted(tool_call_chunks.keys()):
                    tc_info = tool_call_chunks[idx]
                    try:
                        fn_args = json.loads(tc_info["arguments"])
                    except json.JSONDecodeError:
                        fn_args = {}
                    assembled.append((tc_info["id"], tc_info["name"], fn_args))

                assistant_msg: dict[str, Any] = {"role": "assistant", "content": None, "tool_calls": []}
                for tc_id, tc_name, tc_args in assembled:
                    assistant_msg["tool_calls"].append({
                        "id": tc_id,
                        "type": "function",
                        "function": {"name": tc_name, "arguments": json.dumps(tc_args, ensure_ascii=False)},
                    })
                    yield AgentEvent(type="tool_call", data={"tool": tc_name, "args": tc_args})
                messages.append(assistant_msg)

                # 并行执行工具
                async def _exec(tc_id, name, args):
                    res = await self.tools.execute(name, args)
                    return tc_id, name, args, res

                tasks = [_exec(tc_id, n, a) for tc_id, n, a in assembled]
                outcomes = await asyncio.gather(*tasks, return_exceptions=True)

                pending_confirmation = None
                for i, outcome in enumerate(outcomes):
                    if isinstance(outcome, Exception):
                        orig_id, orig_name, orig_args = assembled[i]
                        logger.warning(f"Stream tool exception: {orig_name}: {outcome}")
                        err_result = {"error": f"工具 '{orig_name}' 执行异常: {outcome}"}
                        tool_calls_log.append({
                            "iteration": iteration + 1,
                            "tool": orig_name,
                            "args": orig_args,
                            "result": err_result,
                        })
                        messages.append({
                            "role": "tool",
                            "tool_call_id": orig_id,
                            "content": json.dumps(err_result, ensure_ascii=False),
                        })
                        yield AgentEvent(type="tool_result", data={
                            "tool": orig_name,
                            "result": err_result,
                        })
                        continue
                    tc_id, fn_name, fn_args, tool_result = outcome

                    tool_calls_log.append({
                        "iteration": iteration + 1,
                        "tool": fn_name,
                        "args": fn_args,
                        "result": tool_result,
                    })

                    if tool_result.get("requires_confirmation"):
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc_id,
                            "content": json.dumps({
                                "status": "waiting_confirmation",
                                "tool": fn_name,
                                "args": fn_args,
                                "message": tool_result["message"],
                            }, ensure_ascii=False),
                        })
                        if not pending_confirmation:
                            pending_confirmation = (tc_id, fn_name, fn_args, tool_result)
                        continue

                    result_str = json.dumps(tool_result, ensure_ascii=False)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc_id,
                        "content": truncate_tool_result(result_str),
                    })
                    yield AgentEvent(type="tool_result", data={
                        "tool": fn_name,
                        "result": tool_result,
                    })

                if pending_confirmation:
                    tc_id, fn_name, fn_args, conf_result = pending_confirmation
                    conf_type = conf_result.get("confirmation_type")
                    logger.info("Pending confirmation: tool=%s, conf_type=%s, has_card_data=%s, result_keys=%s",
                                fn_name, conf_type, "card_data" in conf_result, list(conf_result.keys()))
                    if conf_type == "interactive_card" and conf_result.get("card_data"):
                        logger.info("Sending SSE interactive_card event for tool=%s", fn_name)
                        yield AgentEvent(type="interactive_card", data={
                            "tool": fn_name,
                            "args": fn_args,
                            "tool_call_id": tc_id,
                            "card_data": conf_result["card_data"],
                        })
                    else:
                        yield AgentEvent(type="confirmation", data={
                            "tool": fn_name,
                            "args": fn_args,
                            "tool_call_id": tc_id,
                        })
                    return
                continue

            # 文本输出
            if collected_content:
                messages.append({"role": "assistant", "content": collected_content})
                yield AgentEvent(type="text", data={"content": collected_content})
                if mode == "datafirst" and finish_reason == "stop":
                    return
                continue

        yield AgentEvent(type="error", data={"message": "达到最大迭代次数，规划未完成"})
