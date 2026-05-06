# 数据治理工作流规范

## 数据质量检测流程

典型模式：`FlinkSQL(检测指标) → Function(阈值检查) → Condition(是否告警) → Tool(通知) + Approval(升级处理)`

关键要求：
- 查询 `data_quality_metrics` 表获取质量指标
- 四大维度：completeness（完整性）、accuracy（准确性）、timeliness（时效性）、consistency（一致性）
- 指标低于阈值触发告警
- 严重问题（critical）需要人工审批决定是否暂停 Pipeline

## 数据修复流程

典型模式：`FlinkSQL(定位问题数据) → LLM(分析修复方案) → Approval(确认修复) → Tool(执行修复) → Tool(通知)`

关键要求：
- 修复操作必须经过人工审批
- 使用 `act-data-repair` 工具执行修复
- 修复前后需要记录审计日志
- 修复后重新跑一次质量检测确认效果

## 数据 Pipeline 告警

典型模式：`FlinkSQL(监控 Pipeline) → Condition(状态异常?) → LLM(分析原因) → Tool(告警) + Tool(触发修复Pipeline)`

关键要求：
- 使用 `act-trigger-pipeline` 触发修复任务
- 告警通知包含：问题表、异常指标、影响范围
- 连续告警需要升级到人工处理

## 常用函数

| function_id | 用途 |
|-------------|------|
| fn-threshold-check | 阈值检测 |
| fn-aggregate-stats | 聚合统计 |
| fn-data-transform | 格式转换 |
| fn-dedup-merge | 去重合并 |

## 常用表

| 表名 | 用途 |
|------|------|
| data_quality_metrics | 质量指标（维度/值/阈值/状态） |
