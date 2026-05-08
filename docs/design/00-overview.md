# 架构总览 — Workflow Engine Demo

## 系统定位

基于 Temporal + DAG + LLM 的智能工作流引擎。核心能力：自然语言 → DAG 工作流自动规划 → 持久化可靠执行。

## 架构分层

```
┌─────────────────────────────────┐
│  Web UI (index.html)            │  DAG 可视化 + 执行时间线
├─────────────────────────────────┤
│  REST API (FastAPI server.py)   │  HTTP + WebSocket
├─────────────────────────────────┤
│  Planning Agent (ReAct Loop)    │  自然语言 → YAML DAG
├─────────────────────────────────┤
│  DSL Parser (dsl_parser.py)     │  YAML → 拓扑排序 → DAG
├─────────────────────────────────┤
│  Temporal Workflow Engine       │  持久化编排 + 故障恢复
├─────────────────────────────────┤
│  Executors (SPI)                │  LLM / Tool / FlinkSQL / Function / Condition / Approval
└─────────────────────────────────┘
```

## 多队列（Multi-Plane）架构

| Queue | 节点类型 | 职责 |
|-------|---------|------|
| plane-e-default | LLM, Condition, Approval | AI 决策 + 人工审批 |
| plane-b-action | Tool | 系统操作（API 调用、写库） |
| plane-c-pipeline | FlinkSQL | 数据查询 / ETL |
| plane-d-function | Function | 自定义函数逻辑 |

## 运行模式

- **standalone**: 无需外部依赖，所有节点模拟执行
- **full**: 连接真实 Temporal Server + LLM API

## 关键技术决策

- Temporal Signal 实现人机交互（Approval 节点暂停/恢复）
- SPI 接口 (`NodeExecutor`) 保证执行器可插拔
- ReAct Agent 模式实现 LLM 规划（Think → Act → Observe 循环）
- 配置优先级：环境变量 > config.yaml > 默认值
