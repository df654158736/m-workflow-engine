# 违规→修复 Few-shot

## 示例 1：孤立节点 + 引用错误字段 + 空泛 prompt

**❌ 违规 YAML：**

```yaml
workflow_id: wf-risk
name: "风险评估"

nodes:
  - id: fetch_data
    type: FlinkSQL
    config:
      sql: "SELECT * FROM supplier_profiles"
      sink: bronze.supplier
  - id: ai_analyze
    type: LLM
    config:
      prompt: "分析风险"
      model: qwen-plus
    inputs:
      data: "${fetch_data.outputs.text}"
  - id: send_alert
    type: Tool
    config:
      tool_id: act-send-notification
      args: {}

edges:
  - from: fetch_data
    to: ai_analyze
```

**问题**：
- `fetch_data.outputs.text` 错误 — FlinkSQL 没有 `text` 输出，应为 `dataset_ref`
- `ai_analyze` 的 prompt "分析风险" 太空泛，没有引用数据
- `send_alert` 没有连入 edges（孤立节点）

**✅ 修复后：**

```yaml
workflow_id: wf-risk
name: "风险评估"

nodes:
  - id: fetch_data
    type: FlinkSQL
    config:
      sql: "SELECT * FROM supplier_profiles WHERE status = 'active'"
      sink: bronze.supplier
  - id: ai_analyze
    type: LLM
    config:
      prompt: "根据以下供应商数据进行风险评估，输出 JSON: {\"risk_level\": \"高|中|低\", \"reason\": \"...\"}。\n\n数据: ${fetch_data.outputs.dataset_ref}"
      model: qwen-plus
    inputs:
      data: "${fetch_data.outputs.dataset_ref}"
  - id: send_alert
    type: Tool
    config:
      tool_id: act-send-notification
      args:
        message: "风险评估完成: ${ai_analyze.outputs.text}"

edges:
  - from: fetch_data
    to: ai_analyze
  - from: ai_analyze
    to: send_alert
```

## 示例 2：缺少审批 + 命名违规

**❌ 违规 YAML：**

```yaml
workflow_id: wf-blacklist
nodes:
  - id: step1
    type: LLM
    config:
      prompt: "分析供应商"
      model: qwen-plus
  - id: step2
    type: Tool
    config:
      tool_id: act-update-supplier-status
      args:
        action: "blacklist"

edges:
  - from: step1
    to: step2
```

**问题**：
- `step1`/`step2` 违反命名规则（应语义命名）
- 拉黑是危险操作，LLM 直连 Tool，缺少 Approval
- prompt 空泛

**✅ 修复后：**

```yaml
workflow_id: wf-supplier-blacklist
name: "供应商拉黑审批"

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
  - id: approve_blacklist
    type: Approval
    config:
      title: "高风险供应商拉黑审批"
      description: "AI 分析结论: ${ai_risk_assessment.outputs.text}"
      approvers: ["procurement_manager"]
  - id: check_approval
    type: Condition
    config:
      expression: "${approve_blacklist.outputs.decision} == 'APPROVED'"
      true_branch: "approved"
      false_branch: "rejected"
  - id: blacklist_supplier
    type: Tool
    when: "${check_approval.outputs.branch} == 'approved'"
    config:
      tool_id: act-update-supplier-status
      args:
        action: "blacklist"

edges:
  - from: fetch_supplier_data
    to: ai_risk_assessment
  - from: ai_risk_assessment
    to: approve_blacklist
  - from: approve_blacklist
    to: check_approval
  - from: check_approval
    to: blacklist_supplier
```
