# Tech Debt: Agent 生产化加固

> **Created**: 2026-05-08
> **Author**: dingang
> **Module**: `src/backend/agent/`
> **Origin**: Agent 架构全面 Review（与主流实践对标）

---

## 背景

当前 Agent 实现（ReAct Loop + Function Calling + Session）架构正确、代码整洁，但距离生产级部署有若干短板。本需求将这些短板按优先级分为 P0/P1/P2/P3 四档，逐步加固。

---

## P0 — 必须修复（阻碍生产部署）

### TD-01: Session 持久化

**现状**: `SessionStore` 是纯内存 dict，进程重启所有会话丢失。
**风险**: 用户多轮对话中途服务重启 → 对话上下文全丢 → 用户需从头开始。
**方案**: 用 SQLite 做持久化（零外部依赖），Session 序列化为 JSON 存储。
**改动范围**: `session.py`
**工作量**: 半天

### TD-02: 写操作代码层拦截

**现状**: `create_object_type`、`delete_object_type` 等写操作的"用户确认"只写在 prompt 里，没有代码层强制。
**风险**: LLM 可能无视 prompt 指令，直接执行破坏性操作（如删除 ObjectType）。
**方案**: 在 `ToolRegistry.execute()` 中加 middleware —— 标记为 `requires_confirmation` 的工具，返回确认请求而非直接执行；前端展示确认弹窗，用户确认后携带 `confirmed=true` 再次调用。
**改动范围**: `tool_registry.py` + `planner.py` + `server.py`（API 层透传确认态） + 前端
**工作量**: 2-3 小时

### TD-03: 工具执行超时

**现状**: `ToolRegistry.execute()` 无超时，下游 API hang 住 → 整个 ReAct loop 卡死。`api_client.py` 的 httpx timeout=30s 只管 HTTP 层，工具函数自身无保护。
**风险**: 单个工具卡住导致整个会话无响应。
**方案**: `ToolRegistry.execute()` 用 `asyncio.wait_for(handler(), timeout=60)` 包裹；`_react_loop` 整体加 2 分钟超时。
**改动范围**: `tool_registry.py` + `planner.py`
**工作量**: 1 小时

---

## P1 — 重要改进（显著提升体验/可靠性）

### TD-04: 流式响应（SSE）

**现状**: `_react_loop` 一次性返回，用户要等整个循环跑完才看到结果。
**收益**: 用户实时看到 Agent 思考过程、工具调用、中间结果 —— 体验质的飞跃。
**方案**: `_react_loop` 改为 `AsyncGenerator[AgentEvent, None]`，yield 每步事件；`/api/datafirst` 改为 SSE endpoint。
**改动范围**: `planner.py` + `server.py` + 前端 Chat UI
**工作量**: 1-1.5 天

### TD-05: 并行工具调用

**现状**: `planner.py:347-383` 中多个 tool_call 串行执行。
**收益**: LLM 一次返回多个 tool_call 时并行执行，提升速度。
**方案**: `asyncio.gather(*tasks, return_exceptions=True)`
**改动范围**: `planner.py`
**工作量**: 2 小时

---

## P2 — 锦上添花

### TD-06: Token 用量跟踪

**现状**: 没有统计每次对话消耗的 token 数。
**方案**: 从 LLM response 的 `usage` 字段累计，Session 级汇总，超限预警。
**改动范围**: `planner.py` + `session.py`
**工作量**: 半天

---

## P3 — 长期演进

### TD-07: 向量化记忆检索

**现状**: `MemoryStore.search()` 用纯字符串 `in` 匹配。
**方案**: TF-IDF + cosine similarity（短期）/ embedding + FAISS（长期）。
**改动范围**: `memory_store.py`
**工作量**: 1 天

### TD-08: OpenTelemetry 链路追踪

**现状**: 有 structlog 日志，但缺结构化 trace（parent-child span）。
**方案**: 引入 OpenTelemetry，每个 ReAct iteration 一个 span，tool_call 为子 span。
**改动范围**: `planner.py` + `tool_registry.py`
**工作量**: 1 天
