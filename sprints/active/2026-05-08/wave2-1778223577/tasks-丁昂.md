# Tasks — 丁昂 — 2026-05-08 Wave2

> **Sprint**: 2026-05-08
> **模块**: Backend / Frontend / Agent
> **分支**: `feature/agent-production-hardening`（继续 Wave1 分支）
> **设计依据**: SPEC-agent-prod-hardening-p1（待编写）
> **预估工时**: 1.5 人日
> **分配人**: 丁昂
>
> **关联需求点**:
>   - TD-04 流式响应（SSE）
>   - TD-05 并行工具调用
>
> **关联详设**: docs/specs/SPEC-agent-prod-hardening-p1.md

---

## 开工前必读（现状核对）

> 接手前必须确认以下代码现状，防止踩坑：

- [ ] 读过关联 SPEC，确认与代码一致
- [ ] Wave1 的 P0 改动已合入当前分支（Session async 化、tool_registry 超时/确认）
- [ ] 读过 PROGRESS.md 确认无冲突工作
- [ ] 当前在 `feature/agent-production-hardening` 分支

---

## Tasks

### T1: 并行工具调用 (TD-05)

**目标**: LLM 一次返回多个 tool_call 时并行执行，缩短多工具场景耗时。

**交付物**:
- `src/backend/agent/planner.py` — `_react_loop` 中 tool_call 执行改为 `asyncio.gather`

**验收**:
- [x] 多个 tool_call 并行执行（非串行）
- [x] 单个工具失败不影响其他工具执行（`return_exceptions=True`）
- [x] `requires_confirmation` 拦截在并行场景下仍正确（有确认工具时暂停，非确认工具先执行）
- [x] tool_calls_log 顺序与原始 tool_calls 一致
- [x] 单个工具超时不阻塞其他工具

---

### T2: 后端流式响应 — planner 改 AsyncGenerator (TD-04a)

**目标**: `_react_loop` 从一次性返回 `PlanResult` 改为 `yield AgentEvent`，每步实时产出事件。

**交付物**:
- `src/backend/agent/planner.py` — 新增 `AgentEvent` 数据类 + `_react_loop_stream()` 方法
- `src/backend/agent/planner.py` — `chat_stream()` 新方法，返回 `AsyncGenerator[AgentEvent, None]`

**验收**:
- [x] 定义 `AgentEvent` 类型：`thinking` / `tool_call` / `tool_result` / `text` / `confirmation` / `error` / `done`
- [x] LLM 流式输出时逐 token yield `thinking` 事件
- [x] 工具调用前 yield `tool_call` 事件（工具名 + 参数）
- [x] 工具返回后 yield `tool_result` 事件（结果摘要）
- [x] Agent 最终文本 yield `text` 事件
- [x] 写操作确认 yield `confirmation` 事件
- [x] 原有 `chat()` 方法保留不变（兼容非流式场景）

---

### T3: 后端 SSE 端点 (TD-04b)

**目标**: 新增 `/api/datafirst/stream` SSE 端点，将 `AgentEvent` 流式推送给前端。

**交付物**:
- `src/backend/server.py` — 新增 `POST /api/datafirst/stream` SSE 端点

**验收**:
- [x] SSE 事件格式: `event: {type}\ndata: {json}\n\n`
- [x] 支持 `session_id` 和 `confirmed_tool` 透传
- [x] 连接断开时不泄漏资源
- [x] 超时保护（复用 `_REACT_LOOP_TIMEOUT_SECONDS`）

---

### T4: 前端流式渲染 (TD-04c)

**目标**: Chat UI 从"等完整响应"改为 EventSource 逐步渲染 Agent 输出。

**交付物**:
- `src/frontend/index.html` — `sendDatafirst()` 改用 `fetch` + `ReadableStream` 或 `EventSource`

**验收**:
- [x] Agent 思考过程实时显示（逐字/逐句渲染）
- [x] 工具调用显示为带状态的卡片（调用中 → 完成/失败）
- [x] 工具结果折叠展示（点击展开详情）
- [x] 确认弹窗在流式模式下正确触发
- [x] 网络中断时友好提示，不卡死
- [x] 原有非流式 `sendDatafirst()` 保留为 fallback

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
| 流式改动涉及 planner 核心循环 | 可能引入回归 | 保留原有 `chat()` 不改，新增 `chat_stream()` 并行 |
| 前端 SSE 兼容性 | 部分浏览器对 POST SSE 不友好 | 用 `fetch` + `ReadableStream` 替代 `EventSource`（后者仅支持 GET） |
| 并行工具 + 确认拦截交叉 | 多工具中有一个需确认，其他已执行 | 非确认工具先并行执行，确认工具单独返回等用户确认 |
