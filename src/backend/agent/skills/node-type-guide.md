# 节点类型使用指南

## LLM — 大模型分析/推理/生成

适用：分析数据、做判断、生成文本、提取信息
config 必填：prompt, model (固定 qwen-plus)
outputs: text, model, tokens_used, duration_ms

最佳实践：
- prompt 中引用上游数据：`根据以下数据分析...${upstream.outputs.text}`
- 明确输出格式要求：`输出 JSON 格式: {"risk_level": "高|中|低", "reason": "..."}`
- 一个 LLM 节点只做一件事，复杂任务拆成多个 LLM

## Tool — 系统操作

适用：写数据库、调外部 API、发通知、触发 Pipeline
config 必填：tool_id, args
outputs: tool_id, result, execution_id

最佳实践：
- 操作前先确认 tool_id 存在（调用 list_available_tools）
- 重要操作前加 Approval 节点
- args 中引用上游输出传递动态参数

## FlinkSQL — 数据查询/ETL

适用：从数据表查数据、聚合统计、数据清洗
config 必填：sql, sink
outputs: dataset_ref, rows_affected

最佳实践：
- sql 写完整的查询语句
- sink 指定输出位置（如 bronze.table_name）
- 大数据量操作设 on_error: RETRY

## Function — 自定义函数

适用：数据转换、计算、格式化等轻量操作
config 必填：function_id
outputs: function_id, result

## Condition — 条件分支

适用：根据上游结果走不同路径
config 必填：expression, true_branch, false_branch
outputs: result(bool), branch(string)

最佳实践：
- expression 引用上游节点输出
- true_branch/false_branch 命名要有语义（如 "high_risk" / "low_risk"）
- 下游节点通过 `when` 字段判断走哪个分支

## Approval — 人工审批

适用：需要人确认才能继续的操作
config 必填：title, description, approvers
outputs: decision(APPROVED/REJECTED/TIMEOUT), approver, comment

最佳实践：
- title 简明扼要
- description 包含上游分析结果供审批人参考
- approvers 指定角色或人名
- 审批后通常接 Condition 或 when 判断结果

## Sandbox — 沙箱代码执行

适用：运行用户自定义代码（隔离环境）
config 必填：code, language (python/javascript/sql)
outputs: stdout, stderr, exit_code, result

最佳实践：
- 仅在需要自定义逻辑且无现成 Function 时使用
- 代码应有明确的 return 值
- 设置合理的 on_error 策略
