---
name: workflow-core
type: core
mode: workflow
---

# DAG 核心规则（始终生效）

## 节点输出字段速查

| 节点类型 | 可引用的输出字段 |
|---------|---------------|
| LLM | `text`, `model`, `tokens_used`, `duration_ms` |
| FlinkSQL | `dataset_ref`, `rows_affected` |
| Condition | `result`(bool), `branch`(string) |
| Approval | `decision`(APPROVED/REJECTED/TIMEOUT), `approver`, `comment` |
| Tool | `tool_id`, `result`, `execution_id` |
| Function | `function_id`, `result` |
| Sandbox | `stdout`, `stderr`, `exit_code`, `result` |

## 强制规则

1. **引用方向**：`${node.outputs.field}` 只能引用上游节点
2. **字段匹配**：引用的 field 必须在上表中存在（如 FlinkSQL 没有 `text`）
3. **Condition expression**：必须引用上游输出，禁止硬编码 `"True"`
4. **Approval 后接 Condition**：审批后必须判断 APPROVED/REJECTED
5. **危险操作前加 Approval**：拉黑、删除、大额采购等写操作前强制审批
6. **LLM prompt 引用数据**：prompt 中必须有 `${upstream.outputs.field}`，不能空泛
7. **when 语法**：标准写法 `node_id.get('branch') == 'value'`

## 反模式（必须避免）

- ❌ LLM 直连 Tool 执行危险操作（中间缺 Approval）
- ❌ Condition expression 硬编码 `"True"`（分支无意义）
- ❌ 孤立节点（不在 edges 中）
- ❌ node id 用 step1/step2（必须 snake_case 语义命名）

## 需要更多细节时

调用 `get_skill_detail` 工具查询：
- `"dag-quality"` — validate_dag 完整报错对照表 + 违规修复示例
- `"node-types"` — 7 种节点的完整 config 示例、tool_id/function_id 列表、成本表
- `"common-patterns"` — 5 种常见 DAG 模式的完整 YAML 示例
- `"data-flow"` — 数据传递语法、when 条件执行、引用校验规则
- `"error-handling"` — on_error 策略选择决策树、成本影响分析
- `"domain/supply-chain"` — 供应商风险评估完整工作流
- `"domain/data-quality"` — 数据质量异常检测修复完整工作流
