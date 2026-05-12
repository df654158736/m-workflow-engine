# 系统已注册的 tool_id 和 function_id

## 9 个 tool_id（真实数据）

| tool_id | 用途 | 必填 args |
|---------|------|----------|
| `act-save-result` | 保存数据到本体存储 | `target`: ontology\|file\|database |
| `act-send-notification` | 发送通知（钉钉/飞书/企微） | `channel`, `message` |
| `act-send-email` | 发送邮件 | `recipients`, `subject` |
| `act-execute-action` | 执行通用操作 | `action` |
| `act-update-supplier-status` | 更新供应商状态 | `action`: blacklist\|enable\|disable\|monitor |
| `act-create-purchase-order` | 创建采购订单 | `supplier_id`, `items` |
| `act-data-repair` | 数据修复操作 | `mode`: auto\|manual, `target_table` |
| `act-archive-document` | 归档文档 | `category` |
| `act-trigger-pipeline` | 触发数据 Pipeline | `pipeline_id` |

不确定时调 `list_available_tools` 确认。

## 7 个 function_id（真实数据）

| function_id | 用途 | args | returns |
|-------------|------|------|---------|
| `fn-calculate-risk-score` | 综合风险评分（多维度→0-1） | `weights`(可选) | `score`(float), `details`(dict) |
| `fn-data-transform` | 格式转换（JSON/CSV/XML 互转） | `format`, `mapping`(可选) | `result`(transformed data) |
| `fn-dedup-merge` | 去重合并（主键或相似度） | `key_fields`, `strategy`: dedup\|merge\|both | `result`(dict), `removed_count`(int) |
| `fn-threshold-check` | 阈值检测（超阈值返回告警） | `field`, `threshold`, `operator`: gt\|lt\|eq\|gte\|lte | `triggered`(bool), `violations`(list) |
| `fn-text-extract` | 非结构化文本→结构化字段 | `pattern`, `fields` | `extracted`(dict) |
| `fn-aggregate-stats` | 聚合统计（count/sum/avg/min/max/percentile） | `group_by`(可选), `metrics` | `stats`(dict) |
| `fn-date-calc` | 日期计算（工作日/区间/周期） | `operation`: add\|diff\|is_workday, `params` | `result`(date or int) |

不确定时调 `list_available_functions` 确认。
