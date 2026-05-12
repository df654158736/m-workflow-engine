# 字段映射规范

## 何时涉及字段映射

字段映射出现在**数据编织流程**中（create_fabric_task → trigger_ai_analysis → get_field_mappings → confirm_field_mappings）。
如果用 `create_object_type`（传了 datasource_id + table_name）的一步到位流程，字段映射是自动完成的。

## get_field_mappings 真实返回

```json
{
  "mappings": [
    {
      "id": "019e1621-37cd-76c7-97fa-c902d30d5345",
      "source_column": "order_no",
      "target_property": "order_no",
      "target_data_type": "String",
      "status": "USER_CONFIRMED"
    },
    {
      "id": "019e1621-37cd-76c7-97fb-177099d07c9a",
      "source_column": "customer_id",
      "target_property": "customer_id",
      "target_data_type": "Long",
      "status": "USER_CONFIRMED"
    }
  ],
  "total": 13
}
```

## confirm_field_mappings 交互流程

```
→ confirm_field_mappings(
    task_id="019e1620-...",
    compare_result_id="019e1621-01dd-...",
    decisions={
      "019e1621-37cd-...-5345": "CONFIRM",
      "019e1621-37cd-...-d07c9a": "CONFIRM"
    }
  )
← 弹出交互式卡片，用户逐个确认/跳过
← 用户提交后：{"success": true, "confirmed": 11, "skipped": 2}
```

## Pipeline 类型映射表

| sourceType（源列） | targetType（Pipeline） |
|--------------------|----------------------|
| `character varying` | `String` |
| `text` | `String` |
| `bigint` | `Long` |
| `integer` | `Integer` |
| `numeric` | `Double` |
| `boolean` | `Boolean` |
| `date` | `Date` |
| `timestamp without time zone` | `DateTime` |
| `jsonb` | `String`（序列化） |

**注意**：Pipeline 中 timestamp 映射为 `DateTime`，ObjectType 属性中是 `Timestamp`。两者同一概念不同命名。

## 映射状态流转

| 状态 | 含义 | Agent 动作 |
|------|------|-----------|
| `AI_SUGGESTED` | AI 自动生成 | 需调 confirm_field_mappings 让用户确认 |
| `USER_CONFIRMED` | 用户已确认 | 无需操作 |
| `REJECTED` | 用户跳过 | 该字段不进入 Pipeline |

## 反面示例

### ❌ 跳过确认直接提交 Pipeline

```
trigger_ai_analysis → get_field_mappings → submit_pipeline  ← 跳过了 confirm_field_mappings
```

### ❌ 不展示映射详情

```
Agent: "字段映射已生成，要提交吗？"  ← 没展示具体映射了哪些字段
```

正确做法：展示映射表让用户看到每个字段对应关系后再确认。
