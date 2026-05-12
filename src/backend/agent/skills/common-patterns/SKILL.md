---
name: common-patterns
description: 5 种常见 DAG 模式的完整 YAML 示例和反模式
mode: workflow
catalog: 设计新工作流时查看 5 种常见模式和真实 YAML 示例
sections:
  - patterns: 5 种 DAG 模式的完整 YAML + 反模式清单
---

# 常见工作流模式

5 种模式概览：

| 模式 | 结构 | 适用场景 |
|------|------|---------|
| 1 数据→AI→分支 | `FlinkSQL → LLM → Condition → Tool/Approval` | 风险评估、异常检测 |
| 2 异常→根因→分流修复 | `FlinkSQL → LLM → Condition → Tool(auto) / Approval(manual)` | 数据质量、Pipeline 故障 |
| 3 多源汇聚→AI | `FlinkSQL ×N → LLM` | 报告生成、综合评估 |
| 4 串行多轮 AI | `LLM → LLM → LLM → Condition` | 复杂推理、分步思考 |
| 5 采集→函数→告警 | `FlinkSQL → Function → Condition → Tool` | 监控告警（无 LLM，成本最低） |

调用 `get_skill_detail("common-patterns", "patterns")` 查看完整 YAML 示例。
