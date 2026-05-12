# 供应商风险评估工作流

## 完整真实工作流（wf-plan-supplier-risk-a0d4e7）

```yaml
workflow_id: wf-plan-supplier-risk-a0d4e7
name: "供应商风险评估与人工审批"

nodes:
  - id: fetch_supplier_data
    type: FlinkSQL
    config:
      sql: "SELECT * FROM supplier_profiles WHERE supplier_id = 'A'"
      sink: bronze.supplier_risk_input
  - id: ai_risk_assessment
    type: LLM
    config:
      prompt: "根据供应商的交付记录、财务状况和市场口碑，评估其综合风险等级（低/中/高）。给出评分和理由。"
      model: qwen-plus
    inputs:
      data: "${fetch_supplier_data.outputs.dataset_ref}"
  - id: risk_level_check
    type: Condition
    config:
      expression: "True"
      true_branch: "high_risk"
      false_branch: "low_risk"
    inputs:
      assessment: "${ai_risk_assessment.outputs.text}"
  - id: human_review
    type: Approval
    config:
      title: "高风险供应商审批"
      description: "AI 评估该供应商为高风险，请决定是否拉黑"
      approvers: ["procurement_manager"]
    when: "risk_level_check.get('branch') == 'high_risk'"
  - id: execute_decision
    type: Tool
    config:
      tool_id: act-update-supplier-status
      args:
        action: "blacklist_or_monitor"
    inputs:
      decision: "${human_review.outputs.decision}"
    when: "risk_level_check.get('branch') == 'high_risk'"

edges:
  - from: fetch_supplier_data
    to: ai_risk_assessment
  - from: ai_risk_assessment
    to: risk_level_check
  - from: risk_level_check
    to: human_review
  - from: human_review
    to: execute_decision
```

## 领域常用表

| 表名 | 说明 | 常用查询 |
|------|------|---------|
| `supplier_profiles` | 供应商档案 | 按 supplier_id / region / status 过滤 |
| `purchase_orders` | 采购订单 | 按 supplier_id 聚合金额 |
| `delivery_records` | 交付记录 | 按时间段统计交付率 |

## 领域常用 tool_id

| tool_id | 场景 |
|---------|------|
| `act-update-supplier-status` | 拉黑/启用/禁用/监控供应商 |
| `act-create-purchase-order` | 创建采购订单 |
| `act-send-notification` | 发送风险告警通知 |

## 领域常用 function_id

| function_id | 场景 |
|-------------|------|
| `fn-calculate-risk-score` | 综合风险评分 |
| `fn-aggregate-stats` | 采购金额/交付率统计 |
