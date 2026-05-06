# DAG 质量规则（强制）

## 结构规则

1. 每个 node 必须有唯一的 `id`（snake_case 命名）
2. 每个 node 必须有合法的 `type`
3. `edges` 必须引用已存在的 node id
4. DAG 不能有环（循环依赖）
5. 不能有孤立节点（至少有一条入边或出边）
6. 至少有一个起始节点（入度为 0）

## 数据流规则

7. `inputs` 中的 `${node.outputs.field}` 必须引用上游节点
8. 引用的 `field` 必须是该节点类型实际会输出的字段
9. LLM 节点输出 `text`, `model`, `tokens_used`
10. FlinkSQL 节点输出 `dataset_ref`, `rows_affected`
11. Condition 节点输出 `result`(bool), `branch`(string)
12. Approval 节点输出 `decision`, `approver`, `comment`

## 语义规则

13. Approval 节点后面通常接 Condition 判断审批结果，或带 `when` 条件执行
14. 涉及重要操作（删除、拉黑、支付）前必须有 Approval 节点
15. LLM 节点的 prompt 应包含对输入数据的引用，不能是空泛指令
16. Condition 的 expression 应引用上游节点的输出值
17. Tool 节点的 tool_id 必须是系统已注册的，不确定时调用 list_available_tools 确认

## 命名规则

18. workflow_id 格式：`wf-<描述>`
19. node id 格式：`<动作>_<对象>`，如 `fetch_data`、`ai_analyze`、`risk_check`
20. 不要使用 step1、step2 这类无意义命名
