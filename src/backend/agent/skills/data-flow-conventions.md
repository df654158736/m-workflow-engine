# 数据传递规范

## 引用语法

节点间通过 `${node_id.outputs.field}` 传递数据。

```yaml
inputs:
  data: "${fetch_data.outputs.dataset_ref}"
  analysis: "${ai_analyze.outputs.text}"
```

## 各节点类型的输出字段

| 节点类型 | 输出字段 | 说明 |
|---------|---------|------|
| **LLM** | `text` | 模型回答文本 |
| | `model` | 使用的模型名 |
| | `tokens_used` | 消耗的 token 数 |
| | `duration_ms` | 耗时毫秒 |
| **FlinkSQL** | `dataset_ref` | 结果数据集引用 |
| | `rows_affected` | 影响的行数 |
| **Tool** | `tool_id` | 执行的工具 ID |
| | `result` | 工具返回结果 |
| | `execution_id` | 执行追踪 ID |
| **Function** | `function_id` | 执行的函数 ID |
| | `result` | 函数返回值 |
| **Condition** | `result` | 布尔值（true/false）|
| | `branch` | 分支名称 |
| **Approval** | `decision` | 审批结论（APPROVED/REJECTED/TIMEOUT）|
| | `approver` | 审批人 |
| | `comment` | 审批意见 |
| **Sandbox** | `stdout` | 标准输出 |
| | `stderr` | 错误输出 |
| | `exit_code` | 退出码 |
| | `result` | 返回值 |

## 引用规则

1. **只能引用上游节点** — 被引用的节点必须在 edges 中是当前节点的直接或间接上游
2. **字段必须存在** — 引用的 field 必须是该节点类型实际输出的字段（见上表）
3. **类型自动推断** — 数据在传递时是字符串形式，接收方自行解析

## 条件执行（when 字段）

```yaml
- id: notify_high_risk
  type: Tool
  when: "${risk_check.outputs.branch} == 'high_risk'"
  config:
    tool_id: act-send-notification
```

`when` 是布尔表达式，引用上游 Condition 的 `branch` 输出判断当前节点是否执行。

## 常见错误

- ❌ `${unknown_node.outputs.text}` — 引用了不存在的节点
- ❌ `${llm_node.outputs.dataset_ref}` — LLM 节点没有 dataset_ref 输出
- ❌ 引用下游节点（数据流方向错误）
- ❌ 漏掉 `${}` 包裹（变成普通字符串）
