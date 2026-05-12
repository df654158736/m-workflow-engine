# 数据传递规范

## 引用语法

节点间通过 `${node_id.outputs.field}` 传递数据。

```yaml
inputs:
  data: "${fetch_supplier_data.outputs.dataset_ref}"
  analysis: "${ai_risk_assessment.outputs.text}"
```

## 各节点类型最常引用的字段

| 节点类型 | 最常引用的字段 |
|---------|-------------|
| FlinkSQL | `dataset_ref` — 给 LLM 做分析 |
| LLM | `text` — 给 Condition 做判断、给 Approval 做展示 |
| Condition | `branch` — 给下游 `when` 做分流 |
| Approval | `decision` — APPROVED / REJECTED / TIMEOUT |
| Tool | `result` — 工具执行结果 |
| Function | `result` — 函数返回值 |
| Sandbox | `result` — 代码返回值 |

## 引用规则

1. **只能引用上游节点** — 引用非上游报错：`"数据流方向错误"`
2. **字段必须存在** — FlinkSQL 没有 `text`，LLM 没有 `dataset_ref`
3. **节点必须存在** — `${nonexistent.outputs.text}` 报错

## 条件执行（when 字段）

### 基于 Condition 分支

```yaml
- id: auto_repair
  type: Tool
  when: "severity_check.get('branch') == 'auto_fix'"

- id: escalate_approval
  type: Approval
  when: "severity_check.get('branch') == 'escalate'"
```

### 基于 Approval 决策

```yaml
- id: manual_repair
  type: Tool
  when: "escalate_approval.get('decision') == 'APPROVED'"
```

## Few-shot：真实工作流数据流

### 供应商风险评估（5 节点）

```
fetch_supplier_data (FlinkSQL)
  ↓ outputs.dataset_ref
ai_risk_assessment (LLM)
  ↓ outputs.text
risk_level_check (Condition)
  ↓ outputs.branch == "high_risk"
human_review (Approval)    [when: branch == high_risk]
  ↓ outputs.decision
execute_decision (Tool)    [when: branch == high_risk]
```

## 常见错误

| 错误写法 | 修复 |
|---------|------|
| `${flink_node.outputs.text}` | FlinkSQL 没有 `text`，应为 `dataset_ref` |
| `${llm_node.outputs.dataset_ref}` | LLM 没有 `dataset_ref`，应为 `text` |
| `${downstream.outputs.text}` | 只能引用上游 |
| 漏掉 `${}` 包裹 | 不报错但变成普通字符串 |
