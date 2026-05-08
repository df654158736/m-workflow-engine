# Wave 2 — Agent 生产化加固 P1

> **创建时间**: 2026-05-08
> **来源**: `sprints/backlog/tech-debt/agent-production-hardening.md` TD-04 ~ TD-05
> **目标**: 流式响应提升用户体验 + 并行工具调用提升速度

## 范围

| ID | 改进项 | 工作量 |
|----|--------|--------|
| TD-04 | 流式响应（SSE） — planner 改 AsyncGenerator + server SSE + 前端流式渲染 | 1-1.5 天 |
| TD-05 | 并行工具调用 — LLM 返回多个 tool_call 时 asyncio.gather 并行执行 | 2 小时 |
