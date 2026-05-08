# SPEC: Agent 生产化加固 P1 — 流式响应 + 并行工具调用

> **编号**: SPEC-agent-prod-hardening-p1
> **版本**: 1.0
> **作者**: 丁昂
> **日期**: 2026-05-08
> **状态**: Draft
> **前置**: SPEC-agent-prod-hardening（P0 已实现）
> **来源**: `sprints/backlog/tech-debt/agent-production-hardening.md` TD-04 ~ TD-05

---

## 1. 概述

| ID | 改进项 | 核心变更 |
|----|--------|---------|
| TD-05 | 并行工具调用 | `planner.py` `_react_loop` 中 tool_call 改 `asyncio.gather` |
| TD-04 | 流式响应 | `planner.py` 新增 `chat_stream()` + `server.py` SSE 端点 + 前端流式渲染 |

**原则**: 保留现有 `chat()` / `_react_loop()` 不变，新增流式路径，两条路径共存。

---

## 2. TD-05: 并行工具调用

### 2.1 现状

`planner.py:381-438` 中多个 tool_call 串行执行：

```python
for tool_call in message.tool_calls:
    ...
    tool_result = await self.tools.execute(fn_name, fn_args)
    ...
```

LLM 单次可返回 N 个 tool_call（OpenAI parallel function calling），串行执行浪费时间。

### 2.2 设计

将串行 `for` 循环改为分两阶段：
1. **解析阶段**: 遍历 tool_calls，解析参数，分为「可并行」和「需确认」两组
2. **执行阶段**: 可并行的用 `asyncio.gather` 并行执行；需确认的暂停返回

### 2.3 改动细节

**`planner.py` — `_react_loop` 中 Case A 部分重写**:

```python
# Case A: LLM 调用工具
if message.tool_calls:
    msg_dict = message.model_dump()
    # ... 参数修正（保持不变）...
    messages.append(msg_dict)

    # Phase 1: 解析所有 tool_calls
    parsed_calls: list[tuple] = []  # (tool_call, fn_name, fn_args)
    for tool_call in message.tool_calls:
        fn_name = tool_call.function.name
        try:
            fn_args = json.loads(tool_call.function.arguments)
        except json.JSONDecodeError:
            # JSON 错误处理（保持不变）
            ...
            continue
        parsed_calls.append((tool_call, fn_name, fn_args))

    # Phase 2: 并行执行
    async def _exec_one(tc, name, args):
        result = await self.tools.execute(name, args)
        return tc, name, args, result

    tasks = [_exec_one(tc, name, args) for tc, name, args in parsed_calls]
    outcomes = await asyncio.gather(*tasks, return_exceptions=True)

    # Phase 3: 处理结果
    confirmation_result = None
    for outcome in outcomes:
        if isinstance(outcome, Exception):
            # gather 捕获的异常
            ...
            continue
        tc, fn_name, fn_args, tool_result = outcome

        tool_calls_log.append(...)

        if tool_result.get("requires_confirmation"):
            confirmation_result = (tc, fn_name, fn_args, tool_result)
            messages.append(...)  # waiting_confirmation
            continue

        messages.append(...)  # 正常 tool_result

    # 如果有需要确认的工具，暂停返回
    if confirmation_result:
        tc, fn_name, fn_args, tool_result = confirmation_result
        result.success = True
        result.requires_confirmation = True
        result.pending_tool = {...}
        return result
```

### 2.4 确认拦截与并行的交互

| 场景 | 行为 |
|------|------|
| 3 个查询工具 | 全部并行执行 |
| 2 个查询 + 1 个写操作 | 全部并行提交；查询工具正常返回结果，写操作返回 `requires_confirmation`；将查询结果写入 messages，然后暂停等确认 |
| 2 个写操作 | 均返回 `requires_confirmation`；取第一个暂停等确认，第二个也记入 messages 等下一轮 |

**关键**: `asyncio.gather` 不会真正执行写操作——`ToolRegistry.execute()` 在 `confirmed=False` 时直接返回 `requires_confirmation` 而不调用 handler，所以并行提交是安全的。

---

## 3. TD-04: 流式响应

### 3.1 事件类型定义

```python
@dataclass
class AgentEvent:
    type: str       # thinking / tool_call / tool_result / text / confirmation / error / done
    data: dict
```

| 事件类型 | 触发时机 | data 内容 |
|---------|---------|----------|
| `thinking` | LLM 流式输出每个 chunk | `{"content": "部分文本", "delta": "增量"}` |
| `tool_call` | 开始执行工具 | `{"tool": "name", "args": {...}}` |
| `tool_result` | 工具返回 | `{"tool": "name", "result": {...}, "duration_ms": N}` |
| `text` | Agent 最终文本输出 | `{"content": "完整回复"}` |
| `confirmation` | 写操作需确认 | `{"tool": "name", "args": {...}, "tool_call_id": "..."}` |
| `error` | 出错 | `{"message": "错误描述"}` |
| `done` | 本轮结束 | `{"session_id": "...", "iterations": N}` |

### 3.2 planner.py 新增方法

**不改现有方法**。新增:

```python
async def chat_stream(
    self,
    user_input: str,
    session_id: str | None = None,
    confirmed_tool: dict | None = None,
) -> AsyncGenerator[AgentEvent, None]:
    """有状态对话 — 流式版本。"""
    # Session 获取/创建逻辑同 chat()
    ...
    async for event in self._react_loop_stream(session.messages, mode, tool_calls_log):
        yield event
    await self.sessions.save(session)
    yield AgentEvent(type="done", data={"session_id": session.session_id, ...})


async def _react_loop_stream(
    self, messages, mode, tool_calls_log,
) -> AsyncGenerator[AgentEvent, None]:
    """核心 ReAct 循环 — 流式版本。"""
    for iteration in range(self.max_iterations):
        # LLM 调用改 stream=True
        response_stream = await self.llm.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=tool_schemas,
            temperature=0.2,
            max_tokens=4096,
            stream=True,
        )

        # 收集完整 message 同时 yield thinking chunks
        collected_content = ""
        collected_tool_calls = []
        async for chunk in response_stream:
            delta = chunk.choices[0].delta
            if delta.content:
                collected_content += delta.content
                yield AgentEvent(type="thinking", data={
                    "delta": delta.content,
                    "content": collected_content,
                })
            if delta.tool_calls:
                # 增量收集 tool_calls（OpenAI 流式 tool_call 分多个 chunk）
                ...

        # tool_calls 处理（并行执行 + yield tool_call/tool_result 事件）
        if collected_tool_calls:
            for tc_info in collected_tool_calls:
                yield AgentEvent(type="tool_call", data={"tool": ..., "args": ...})

            # 并行执行
            outcomes = await asyncio.gather(...)

            for outcome in outcomes:
                if tool_result.get("requires_confirmation"):
                    yield AgentEvent(type="confirmation", data={...})
                    return
                yield AgentEvent(type="tool_result", data={...})
            continue

        # 文本输出
        if collected_content:
            yield AgentEvent(type="text", data={"content": collected_content})
            if mode == "datafirst":
                return
```

### 3.3 server.py 新增 SSE 端点

```python
@app.post("/api/datafirst/stream")
async def datafirst_agent_stream(payload: dict[str, Any]):
    user_input = payload.get("input", "")
    session_id = payload.get("session_id")
    confirmed_tool = payload.get("confirmed_tool")

    async def event_generator():
        async for event in _planning_agent.chat_stream(
            user_input or "", session_id=session_id, confirmed_tool=confirmed_tool,
        ):
            yield f"event: {event.type}\ndata: {json.dumps(event.data, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

**注意**: 使用 `POST` + `StreamingResponse`，而非 `EventSource`（后者仅支持 GET）。前端用 `fetch` + `ReadableStream` 消费。

### 3.4 前端改动

**`sendDatafirst()` 改为双模式**:

```javascript
async function sendDatafirst() {
  // ... 同上 ...
  try {
    const body = { input: msg };
    if (_dfSessionId) body.session_id = _dfSessionId;

    const resp = await fetch('/api/datafirst/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });

    if (!resp.ok) {
      // fallback 到非流式
      return await sendDatafirstLegacy(msg);
    }

    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    // 创建 Agent 消息容器
    const agentMsgDiv = dfCreateAgentMsg();

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      // 解析 SSE 事件
      const events = parseSSE(buffer);
      buffer = events.remaining;

      for (const evt of events.parsed) {
        switch (evt.type) {
          case 'thinking':
            agentMsgDiv.updateText(evt.data.content);
            break;
          case 'tool_call':
            agentMsgDiv.addToolCard(evt.data.tool, evt.data.args, 'running');
            break;
          case 'tool_result':
            agentMsgDiv.updateToolCard(evt.data.tool, evt.data.result, 'done');
            break;
          case 'text':
            agentMsgDiv.finalizeText(evt.data.content);
            break;
          case 'confirmation':
            dfShowConfirmation(evt.data);
            break;
          case 'done':
            _dfSessionId = evt.data.session_id;
            break;
          case 'error':
            agentMsgDiv.showError(evt.data.message);
            break;
        }
      }
    }
  } catch (e) {
    // fallback
    ...
  }
}
```

**UI 展示**:

- `thinking` 事件 → 实时追加文本（打字机效果）
- `tool_call` 事件 → 显示工具卡片，状态 "调用中..."（带旋转动画）
- `tool_result` 事件 → 更新卡片为"完成"（绿色勾）或"失败"（红色叉），结果折叠展示
- `confirmation` 事件 → 弹出确认弹窗（复用 Wave1 的 `dfShowConfirmation`）
- `text` 事件 → 最终文本替换 thinking 中间态
- `error` 事件 → 红色错误提示

### 3.5 流式 tool_call 增量收集

OpenAI 流式 API 中 tool_call 分多个 chunk 到达，需要增量拼接：

```python
# 收集 tool_calls（增量拼接）
tool_call_chunks: dict[int, dict] = {}  # index → {id, name, arguments}
async for chunk in response_stream:
    delta = chunk.choices[0].delta
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
```

---

## 4. 影响面汇总

| 文件 | TD-05 | TD-04 | 改动性质 |
|------|-------|-------|---------|
| `planner.py` | 重写 Case A 并行逻辑 | 新增 `AgentEvent` + `chat_stream()` + `_react_loop_stream()` | 核心改动 |
| `server.py` | - | 新增 `POST /api/datafirst/stream` | 新增端点 |
| `index.html` | - | `sendDatafirst()` 改 fetch + ReadableStream | 重写发送逻辑 |

**不改动的文件**: `session.py`, `tool_registry.py`, `api_client.py`, 所有 tools/*.py

---

## 5. 兼容性策略

| 路径 | 用途 |
|------|------|
| `POST /api/datafirst` | 保留不变，非流式，作为 fallback |
| `POST /api/datafirst/stream` | 新增，流式 SSE |
| `chat()` | 保留不变 |
| `chat_stream()` | 新增 |
| `_react_loop()` | 保留不变（TD-05 并行改动在此方法中） |
| `_react_loop_stream()` | 新增 |

前端优先尝试 `/stream`，失败时 fallback 到非流式端点。

---

## 6. 不在本次范围

- LLM 调用重试（exponential backoff）—— 后续 P2
- Token 用量跟踪 —— 后续 P2
- 向量化记忆、OpenTelemetry —— 后续 P3
