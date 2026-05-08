# Wave 4 — Agent 生产化加固 P2 + 架构增强

> **创建时间**: 2026-05-08
> **来源**: Agent 架构全面评估后的优化 backlog
> **目标**: LLM 调用鲁棒性 + 成本可观测 + 工具参数校验 + 复杂任务规划能力

## 范围

| ID | 改进项 | 工作量 |
|----|--------|--------|
| TD-06 | LLM 调用重试（exponential backoff） | 2h |
| TD-07 | Token 用量跟踪 | 2h |
| TD-08 | Graceful shutdown | 0.5h |
| TD-11 | Plan-then-Execute（复杂任务分步规划） | 1d |
| TD-15 | Guard Rails — Pydantic 工具参数校验 | 1d |
