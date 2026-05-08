# Tasks — 丁昂 — 2026-05-08 Wave4

> **Sprint**: 2026-05-08
> **模块**: Backend / Agent
> **分支**: `feature/agent-production-hardening`（继续）
> **设计依据**: 无独立 SPEC（各 TD 设计内聚在任务描述中）
> **预估工时**: 2.5 人日
> **分配人**: 丁昂
>
> **关联需求点**:
>   - TD-06 LLM 调用重试
>   - TD-07 Token 用量跟踪
>   - TD-08 Graceful shutdown
>   - TD-11 Plan-then-Execute
>   - TD-15 Guard Rails（Pydantic 参数校验）

---

## 开工前必读（现状核对）

- [ ] Wave3 已提交（Session 历史恢复 + gather 异常 bug 修复）
- [ ] 读过 `planner.py` 确认 `_react_loop` / `_react_loop_stream` 双路径现状
- [ ] 读过 `tool_registry.py` 确认 `execute()` 当前无参数校验
- [ ] 读过 PROGRESS.md 确认无冲突工作

---

## Tasks

### T1: LLM 调用重试 (TD-06)

**目标**: LLM API 调用失败时自动重试，指数退避，避免偶发 5xx/超时直接返错。

**交付物**:
- `src/backend/agent/planner.py` — LLM 调用处加重试逻辑

**设计**:
```python
_LLM_MAX_RETRIES = 3
_LLM_RETRY_BASE_DELAY = 1.0  # seconds

async def _llm_call_with_retry(self, messages, tool_schemas, stream=False):
    for attempt in range(_LLM_MAX_RETRIES):
        try:
            return await self.llm.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=tool_schemas,
                temperature=0.2,
                max_tokens=4096,
                stream=stream,
            )
        except Exception as e:
            if attempt == _LLM_MAX_RETRIES - 1:
                raise
            delay = _LLM_RETRY_BASE_DELAY * (2 ** attempt)
            logger.warning(f"LLM call failed (attempt {attempt+1}), retrying in {delay}s: {e}")
            await asyncio.sleep(delay)
```

**验收**:
- [x] `_react_loop` 和 `_react_loop_stream` 的 LLM 调用都走重试
- [x] 最多重试 3 次，指数退避（1s, 2s, 4s）
- [x] 最终失败才返回 error
- [x] 重试日志可观测（logger.warning）

---

### T2: Token 用量跟踪 (TD-07)

**目标**: 记录每轮 LLM 调用的 token 消耗，累计到 session，前端可见。

**交付物**:
- `src/backend/agent/planner.py` — 从 `response.usage` 提取并累计
- `src/backend/agent/session.py` — Session 增加 `total_tokens` 字段
- 前端 `done` 事件展示 token 消耗（可选）

**设计**:
```python
# Session 增加字段
@dataclass
class Session:
    ...
    total_tokens: int = 0

# _react_loop 中：
if response.usage:
    session_tokens += response.usage.total_tokens

# _react_loop_stream 中（流式需要在最后一个 chunk 拿 usage）：
# OpenAI stream_options={"include_usage": True} 可让最后一个 chunk 包含 usage
```

**验收**:
- [x] 非流式路径：每轮 `response.usage.total_tokens` 累计
- [x] 流式路径：启用 `stream_options={"include_usage": True}`，从最后 chunk 取 usage
- [x] `done` 事件 data 中包含 `total_tokens`
- [x] Session 中持久化 `total_tokens`（SQLite 表加列）

---

### T3: Graceful shutdown (TD-08)

**目标**: 进程退出时正确关闭 SQLite 连接，防丢数据。

**交付物**:
- `src/backend/server.py` — FastAPI shutdown 事件中调 `SessionStore.close()`

**设计**:
```python
@app.on_event("shutdown")
async def shutdown():
    store = get_session_store()
    await store.close()
```

**验收**:
- [x] FastAPI shutdown 事件注册
- [x] `SessionStore.close()` 被调用
- [x] Ctrl+C 退出后 sessions.db 数据完整

---

### T4: Guard Rails — Pydantic 工具参数校验 (TD-15)

**目标**: LLM 输出的工具参数在执行前用 Pydantic 校验，不合法直接返回结构化错误给 LLM 自行修正，避免无效 API 调用。

**交付物**:
- `src/backend/agent/tool_registry.py` — `@tool` 支持传入 Pydantic Model，`execute()` 前自动校验
- `src/backend/agent/tools/*.py` — 关键写操作工具补充 Pydantic Model

**设计**:

```python
# tool_registry.py
from pydantic import BaseModel, ValidationError

@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[..., Awaitable[dict]]
    requires_confirmation: bool = False
    args_model: type[BaseModel] | None = None  # 新增

class ToolRegistry:
    async def execute(self, name, arguments, confirmed=False):
        defn = self._tools.get(name)
        ...
        # Pydantic 校验
        if defn.args_model:
            try:
                validated = defn.args_model.model_validate(arguments)
                arguments = validated.model_dump()
            except ValidationError as e:
                return {
                    "error": f"参数校验失败: {e.errors()}",
                    "hint": "请检查参数格式后重新调用。",
                }
        ...

# 装饰器增加 args_model 参数
def tool(name, description, parameters=None, requires_confirmation=False, args_model=None):
    ...
```

```python
# tools/ontology_tools.py 示例
from pydantic import BaseModel, Field

class CreateObjectTypeArgs(BaseModel):
    object_type_name: str = Field(..., min_length=1, max_length=100)
    display_name: str = Field(..., min_length=1)
    properties: list[dict] = Field(..., min_length=1)
    datasource_id: str = Field(default="")
    table_name: str = Field(default="")

@tool(
    name="create_object_type",
    description="...",
    requires_confirmation=True,
    args_model=CreateObjectTypeArgs,
)
async def create_object_type(...):
    ...
```

**验收**:
- [x] `ToolDefinition` 新增 `args_model` 可选字段
- [x] `execute()` 在调 handler 前做 Pydantic 校验
- [x] 校验失败返回结构化 error（含字段级错误详情），不调 handler
- [x] `@tool` 装饰器支持 `args_model=XxxModel` 参数
- [x] `create_object_type` 补充 Model（properties 非空、name 非空等）
- [x] `generate_pipeline` 补充 Model
- [x] 其他写操作工具视情况补充（6 个写操作工具全部覆盖）
- [x] 无 Model 的工具行为不变（向后兼容）

---

### T5: Plan-then-Execute (TD-11)

**目标**: 复杂任务（如"同时接入 3 张表"）先生成执行计划，用户确认后逐步执行，防遗漏。

**交付物**:
- `src/backend/agent/planner.py` — DATAFIRST_PROMPT_TEMPLATE 增加计划生成指令
- `src/backend/agent/tools/planning_tools.py` — 新增 `create_plan` / `update_plan_step` 工具（可选）

**设计**:

方案 A（Prompt 驱动，轻量）:
在 DATAFIRST_PROMPT_TEMPLATE 中增加规则：
```
## 复杂任务处理
当用户需求涉及多个对象（多张表、多个本体、多步操作）时：
1. 先输出执行计划（编号步骤列表），每步说明要做什么
2. 等用户确认计划后，按步骤逐个执行
3. 每完成一步，汇报进度："✅ 步骤 1/N 完成，开始步骤 2..."
4. 某步失败时，告知用户并询问是否跳过或重试
```

方案 B（工具驱动，强约束）:
新增 `create_plan` 工具，Agent 必须先调工具创建 plan，系统强制按 plan 步骤推进。

**推荐方案 A**：用 Prompt 引导即可，无需额外工具。复杂度低，效果可验证后再考虑 B。

**验收**:
- [x] DATAFIRST_PROMPT_TEMPLATE 增加复杂任务规则
- [ ] 测试：输入"帮我同时接入 A 和 B 两张表"，Agent 先列计划再逐步执行
- [ ] 单步失败时 Agent 给出恢复建议（而非整体失败）

---

## 技术红线自查（对齐 CLAUDE.md）

- [ ] 无硬编码密钥/密码/Token
- [ ] 无空 `except: pass` 块
- [ ] 全程 async/await，无同步阻塞
- [ ] 配置项走 config.yaml，不硬编码
- [ ] 不修改他人模块目录

---

## 合并前 Checklist（DoD）

- [ ] 所有 task checkbox 完成
- [ ] `ruff check src/` 通过
- [ ] `black --check src/ && isort --check src/` 通过
- [ ] `pytest` 全绿
- [ ] PROGRESS.md 已更新
- [ ] `/doc-sync-after-dev` 已执行
- [ ] PR 已创建

---

## 风险 / 遗留

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| 流式路径取 usage 需要 `stream_options`，部分 LLM provider 不支持 | token 统计缺失 | 流式路径 usage 取不到时降级为 0，不报错 |
| Pydantic 校验过严可能阻止 LLM 的合理参数变体 | Agent 循环重试同一工具 | Model 字段用宽松类型 + 合理 default，只校验关键约束 |
| Plan-then-Execute 纯 Prompt 方案，LLM 可能不遵守 | 复杂任务仍一步到位 | 观察效果，不佳再升级为工具驱动方案 B |
