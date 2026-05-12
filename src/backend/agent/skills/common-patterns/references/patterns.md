# 5 种 DAG 模式完整 YAML

## 模式 1：数据采集 → AI 分析 → 条件分支

适用：风险评估、异常检测、数据质量分析

### 真实工作流示例（wf-plan-supplier-risk-a0d4e7）

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

## 模式 2：异常检测 → AI 根因 → 自动/人工修复分流

适用：数据质量修复、Pipeline 故障恢复

```yaml
workflow_id: wf-data-quality-alert
name: "数据质量异常诊断修复"

nodes:
  - id: detect_anomaly
    type: FlinkSQL
    config:
      sql: "SELECT table_name, column_name, null_ratio, duplicate_ratio, outlier_count FROM dq_monitor.latest_scan WHERE null_ratio > 0.1 OR duplicate_ratio > 0.05 ORDER BY severity DESC LIMIT 10"
      sink: bronze.dq_alerts
  - id: analyze_root_cause
    type: LLM
    config:
      prompt: "你是数据工程专家。分析以下数据质量异常：\n1. 最可能的根因？\n2. 严重程度：critical/warning/info\n3. 修复方案\n4. 是否可自动修复\n\n用JSON: {severity, root_cause, fix_plan, auto_fixable}"
      model: qwen-plus
    inputs:
      anomaly_data: "${detect_anomaly.outputs.dataset_ref}"
  - id: severity_check
    type: Condition
    config:
      expression: "'critical' in str(text).lower()"
      true_branch: "escalate"
      false_branch: "auto_fix"
    inputs:
      text: "${analyze_root_cause.outputs.text}"
  - id: auto_repair
    type: Tool
    config:
      tool_id: act-data-repair
      args:
        strategy: "fill_median_and_dedup"
    when: "severity_check.get('branch') == 'auto_fix'"
  - id: escalate_approval
    type: Approval
    config:
      title: "Critical 数据异常 — 需确认修复方案"
      approvers: ["data_owner", "data_engineer_lead"]
    when: "severity_check.get('branch') == 'escalate'"
  - id: manual_repair
    type: Tool
    config:
      tool_id: act-data-repair
      args:
        strategy: "human_confirmed_fix"
    when: "escalate_approval.get('decision') == 'APPROVED'"

edges:
  - from: detect_anomaly
    to: analyze_root_cause
  - from: analyze_root_cause
    to: severity_check
  - from: severity_check
    to: auto_repair
  - from: severity_check
    to: escalate_approval
  - from: escalate_approval
    to: manual_repair
```

## 模式 3：多源汇聚 → AI 综合

适用：报告生成、多维度对比、综合评估

```yaml
nodes:
  - id: fetch_suppliers
    type: FlinkSQL
    config:
      sql: "SELECT * FROM supplier_profiles WHERE region = 'east'"
      sink: bronze.east_suppliers
  - id: fetch_orders
    type: FlinkSQL
    config:
      sql: "SELECT supplier_id, SUM(amount) as total FROM purchase_orders GROUP BY supplier_id"
      sink: bronze.order_summary
  - id: ai_comprehensive
    type: LLM
    config:
      prompt: "综合以下供应商档案和采购数据，生成供应商评估报告。"
      model: qwen-plus
    inputs:
      suppliers: "${fetch_suppliers.outputs.dataset_ref}"
      orders: "${fetch_orders.outputs.dataset_ref}"

edges:
  - from: fetch_suppliers
    to: ai_comprehensive
  - from: fetch_orders
    to: ai_comprehensive
```

## 模式 4：串行多轮 AI

适用：复杂推理、分步思考、多角度分析

```
LLM(需求解析) → LLM(方案生成) → LLM(方案评估) → Condition → ...
```

**注意**：每个 LLM 消耗约 2000 tokens / ¥0.02，串行 3 个 LLM = ¥0.06 + 24s。

## 模式 5：采集 → 函数计算 → 告警

适用：监控告警、数据质量、SLA 检查（**无 LLM，成本最低**）

```yaml
nodes:
  - id: fetch_metrics
    type: FlinkSQL
    config:
      sql: "SELECT table_name, column_name, null_ratio, duplicate_ratio FROM dq_monitor.latest_scan WHERE null_ratio > 0.1 OR duplicate_ratio > 0.05"
      sink: bronze.recent_metrics
  - id: check_threshold
    type: Function
    config:
      function_id: fn-threshold-check
      args:
        field: "value"
        threshold: 0.9
        operator: "gt"
    inputs:
      value: "${fetch_metrics.outputs.dataset_ref}"
  - id: alert_check
    type: Condition
    config:
      expression: "${check_threshold.outputs.result}.get('triggered', False)"
      true_branch: "alert"
      false_branch: "normal"
  - id: send_alert
    type: Tool
    when: "alert_check.get('branch') == 'alert'"
    config:
      tool_id: act-send-notification
      args:
        channel: "ops-alerts"
        message: "指标超阈值: ${check_threshold.outputs.result}"

edges:
  - from: fetch_metrics
    to: check_threshold
  - from: check_threshold
    to: alert_check
  - from: alert_check
    to: send_alert
```

## 反模式（必须避免）

### ❌ LLM 直连 Tool 执行危险操作

```yaml
edges:
  - from: ai_analyze
    to: blacklist_supplier  # 缺 Approval
```

正确：`ai_analyze → approve(Approval) → check(Condition) → blacklist(Tool)`

### ❌ Condition 硬编码 "True"

```yaml
expression: "True"  # 永远走 true_branch，无意义
```

正确：`"'critical' in str(text).lower()"` 引用上游输出

### ❌ 孤立节点

节点定义了但没出现在 edges 中。

### ❌ 所有节点一条线无分支

需求包含"如果…则…否则…"时必须用 Condition 分支。
