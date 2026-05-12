# AI 推断属性修正指南

## ai_infer_properties 真实响应示例

```json
{
  "table_name": "df_customer",
  "inferred_properties": [
    {"column_name": "id",         "suggested_cn_name": "客户编号",  "suggested_type": "STRING",  "is_primary_key": true,  "confidence": 0.75},
    {"column_name": "name",       "suggested_cn_name": "客户姓名",  "suggested_type": "STRING",  "is_primary_key": false, "confidence": 0.65},
    {"column_name": "birthday",   "suggested_cn_name": "出生日期",  "suggested_type": "STRING",  "is_primary_key": false, "confidence": 0.65},
    {"column_name": "vip_level",  "suggested_cn_name": "会员等级",  "suggested_type": "ENUM",    "is_primary_key": false, "confidence": 0.80},
    {"column_name": "is_active",  "suggested_cn_name": "启用状态",  "suggested_type": "STRING",  "is_primary_key": false, "confidence": 0.65},
    {"column_name": "tags",       "suggested_cn_name": "客户标签",  "suggested_type": "STRING",  "is_primary_key": false, "confidence": 0.65},
    {"column_name": "created_at", "suggested_cn_name": "创建时间",  "suggested_type": "STRING",  "is_primary_key": false, "confidence": 0.65}
  ],
  "total": 12
}
```

## ⚠️ AI 推断类型大多是 STRING，必须修正

| AI suggested_type | 源列 type | 应修正为 | 原因 |
|-------------------|-----------|---------|------|
| STRING | `date` | **Date** | AI 不识别日期类型 |
| STRING | `boolean` | **Boolean** | AI 不识别布尔类型 |
| STRING | `timestamp without time zone` | **Timestamp** | AI 不识别时间戳 |
| STRING | `jsonb` | **Json** | AI 不识别 JSON |
| STRING | `bigint`（主键） | **String** | 正确，无需修正 |
| STRING | `character varying` | **String** | 正确，无需修正 |
| ENUM | `integer` | **Integer** | 虽然语义是枚举，但存储类型是整数 |

**AI 推荐的 `suggested_cn_name` 质量较好，可以直接用作 `display_name`。**

## 反面示例

### ❌ 照搬 AI 推荐类型

```json
{"property_name": "birthday",  "type": "STRING"}
{"property_name": "is_active", "type": "STRING"}
{"property_name": "tags",      "type": "STRING"}
```

应为 `Date` / `Boolean` / `Json`。

### ❌ bigint 外键用 Integer

```json
{"property_name": "customer_id", "type": "Integer"}
```

`customer_id` 源类型 bigint，Integer 32 位会溢出，应用 `Long`。

### ❌ display_name 用英文

```json
{"property_name": "order_no", "display_name": "order_no"}
```

display_name 应中文（"订单号"），不是列名重复。
