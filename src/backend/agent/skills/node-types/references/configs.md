# 7 种节点类型完整 config 示例

## LLM — 大模型分析/推理/生成

适用：分析数据、做判断、生成文本、提取信息

```yaml
- id: ai_risk_assessment
  type: LLM
  config:
    prompt: "根据供应商的交付记录、财务状况和市场口碑，评估其综合风险等级（低/中/高）。给出评分和理由。\n\n数据: ${fetch_supplier_data.outputs.dataset_ref}"
    model: qwen-plus
  inputs:
    data: "${fetch_supplier_data.outputs.dataset_ref}"
```

**outputs**: `text`, `model`, `tokens_used`, `duration_ms`

最佳实践：
- prompt 中**必须引用上游数据**，不能空泛
- **明确输出格式要求**（JSON/表格/分类）
- 一个 LLM 只做一件事

## Tool — 系统操作

适用：写数据库、调外部 API、发通知、触发 Pipeline

```yaml
- id: execute_decision
  type: Tool
  config:
    tool_id: act-update-supplier-status
    args:
      action: "blacklist"
  inputs:
    decision: "${human_review.outputs.decision}"
  when: "${check_approval.outputs.branch} == 'approved'"
```

**outputs**: `tool_id`, `result`, `execution_id`

最佳实践：
- 重要写操作前**必须加 Approval 节点**
- args 中用 `${上游.outputs.field}` 传递动态参数

## FlinkSQL — 数据查询/ETL

适用：从数据表查数据、聚合统计、数据清洗

```yaml
- id: fetch_supplier_data
  type: FlinkSQL
  config:
    sql: "SELECT * FROM supplier_profiles WHERE supplier_id = 'A'"
    sink: bronze.supplier_risk_input
    description: "拉取供应商历史数据"
  on_error: RETRY
```

**outputs**: `dataset_ref`, `rows_affected`

最佳实践：
- sql 带 WHERE 条件过滤，不要无条件全表扫
- sink 指定输出位置（如 `bronze.table_name`）

## Function — 自定义函数

适用：数据转换、阈值检查、格式化等轻量计算

```yaml
- id: check_threshold
  type: Function
  config:
    function_id: fn-threshold-check
    args:
      field: "risk_score"
      threshold: 0.9
      operator: "gt"
  inputs:
    value: "${fetch_metrics.outputs.dataset_ref}"
  on_error: FAIL
```

**outputs**: `function_id`, `result`

## Condition — 条件分支

适用：根据上游结果走不同路径

```yaml
- id: severity_check
  type: Condition
  config:
    expression: "'critical' in str(text).lower()"
    true_branch: "escalate"
    false_branch: "auto_fix"
  inputs:
    text: "${analyze_root_cause.outputs.text}"
```

**outputs**: `result`(bool), `branch`(string)

下游节点通过 `when` 判断分支：
```yaml
- id: auto_repair
  type: Tool
  when: "severity_check.get('branch') == 'auto_fix'"
```

最佳实践：
- expression **必须引用上游节点输出**，不能硬编码 `"True"`
- true_branch/false_branch 命名要有语义

## Approval — 人工审批

适用：需要人确认才能继续的操作

```yaml
- id: human_review
  type: Approval
  config:
    title: "高风险供应商审批"
    description: "AI 评估该供应商为高风险，请决定是否拉黑"
    approvers: ["procurement_manager"]
  when: "risk_level_check.get('branch') == 'high_risk'"
```

**outputs**: `decision`(APPROVED/REJECTED/TIMEOUT), `approver`, `comment`

最佳实践：
- description **包含上游分析结果**供审批人参考
- 审批后**必须接 Condition 或 when** 判断结果
- 以下操作前**强制**加 Approval：拉黑供应商、大额采购、数据批量修复、删除操作

## Sandbox — 沙箱代码执行

适用：运行用户自定义代码（隔离环境）

```yaml
- id: custom_calc
  type: Sandbox
  config:
    code: |
      import json
      data = json.loads("""${fetch_data.outputs.dataset_ref}""")
      result = sum(item['amount'] for item in data)
      return {"total": result, "count": len(data)}
    language: python
  on_error: SKIP
```

**outputs**: `stdout`, `stderr`, `exit_code`, `result`

最佳实践：
- 仅在无现成 Function 时使用
- `on_error` 建议 SKIP（用户代码出错不应阻塞主流程）
