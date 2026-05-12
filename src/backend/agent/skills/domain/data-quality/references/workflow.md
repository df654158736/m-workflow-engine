# 数据质量异常检测修复工作流

## 完整真实工作流 1（wf-data-quality-alert）

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
      prompt: "你是数据工程专家。分析以下数据质量异常：\n1. 最可能的根因？（数据源/ETL错误/上游变更/人工录入）\n2. 严重程度：critical/warning/info\n3. 修复方案\n4. 是否可自动修复\n\n用JSON: {severity, root_cause, fix_plan, auto_fixable}"
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

## 完整真实工作流 2（wf-plan-data-anomaly-52c464）

```yaml
workflow_id: wf-plan-data-anomaly-52c464
name: "数据异常监控与告警"

nodes:
  - id: monitor_data
    type: FlinkSQL
    config:
      sql: "SELECT table_name, column_name, null_ratio, duplicate_ratio FROM dq_monitor.latest_scan WHERE null_ratio > 0.1 OR duplicate_ratio > 0.05"
      sink: bronze.data_anomaly_input
  - id: ai_analysis
    type: LLM
    config:
      prompt: "分析以下数据质量指标，识别异常模式和潜在问题。\n\n数据: ${monitor_data.outputs.dataset_ref}\n\n输出 JSON: {\"anomalies\": [{\"table\": \"...\", \"issue\": \"...\", \"severity\": \"high|medium|low\"}], \"summary\": \"...\"}"
      model: qwen-plus
    inputs:
      data: "${monitor_data.outputs.dataset_ref}"
  - id: severity_check
    type: Condition
    config:
      expression: "'high' in str(text).lower()"
      true_branch: "alert"
      false_branch: "log_only"
    inputs:
      text: "${ai_analysis.outputs.text}"
  - id: send_alert
    type: Tool
    config:
      tool_id: act-send-notification
      args:
        channel: "data-quality-alerts"
        message: "发现数据质量异常"
    when: "severity_check.get('branch') == 'alert'"

edges:
  - from: monitor_data
    to: ai_analysis
  - from: ai_analysis
    to: severity_check
  - from: severity_check
    to: send_alert
```

## 领域常用表

| 表名 | 说明 |
|------|------|
| `dq_monitor.latest_scan` | 数据质量最新扫描结果（null_ratio, duplicate_ratio, outlier_count） |

## 领域常用 tool_id

| tool_id | 场景 |
|---------|------|
| `act-data-repair` | 数据修复（strategy: fill_median_and_dedup / human_confirmed_fix） |
| `act-send-notification` | 发送异常告警通知 |

## 领域常用 function_id

| function_id | 场景 |
|-------------|------|
| `fn-threshold-check` | 阈值检测 |
| `fn-aggregate-stats` | 聚合统计 |
