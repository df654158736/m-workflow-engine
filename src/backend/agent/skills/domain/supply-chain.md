# 供应链领域工作流规范

## 供应商评估流程

典型模式：`FlinkSQL(查供应商档案) → LLM(风险分析) → Condition(风险等级) → Approval/Tool`

关键要求：
- 查询 `supplier_profiles` 表获取供应商数据
- LLM 分析时输出结构化 JSON：`{"risk_level": "高|中|低", "score": 0.0-1.0, "reason": "..."}`
- 风险等级"高"必须经过人工审批（Approval 节点）
- 供应商状态变更使用 `act-update-supplier-status` 工具

## 采购流程

典型模式：`FlinkSQL(查库存) → Condition(是否低于安全库存) → LLM(推荐供应商) → Approval(采购审批) → Tool(创建订单)`

关键要求：
- 金额超过 10 万的采购必须双人审批（两个串联 Approval）
- 创建采购订单使用 `act-create-purchase-order` 工具
- 采购结果通知使用 `act-send-notification`

## 质检流程

典型模式：`FlinkSQL(查质检记录) → Function(合格率计算) → Condition(是否达标) → Tool(通知)/Approval(处置)`

关键要求：
- 合格率低于 90% 触发告警
- 连续 3 次不合格需要人工审批是否拉黑供应商
- 查询 `quality_inspections` 表

## 常用表

| 表名 | 用途 |
|------|------|
| supplier_profiles | 供应商主档（ID/名称/状态/风险分/地区） |
| purchase_orders | 采购订单（订单ID/供应商/金额/状态） |
| quality_inspections | 质检记录（合格率/缺陷数/结论） |
| inventory | 库存（SKU/数量/安全库存/仓库） |

## 可用工具

| tool_id | 用途 |
|---------|------|
| act-update-supplier-status | 更新供应商状态 |
| act-create-purchase-order | 创建采购订单 |
| act-send-notification | 发送通知 |
| act-send-email | 发送邮件 |
