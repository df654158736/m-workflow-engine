# 半成品属性补全（update_object_type_properties）

## 用户："Order 的属性不全，帮我补上"

```
→ get_object_type_detail(type_name="Order")
← { "name": "Order", "status": "EDITING", "attributes": [
    {"property_name": "order_no", "display_name": "order_no", "type": "string", ...},
    ...共 5 个，但表有 13 列
  ]}

→ scan_table_columns(datasource_id="019dd21d-...", table_name="df_order")
← { "columns": [...共 13 列] }
```

> Agent 对比发现缺 8 个属性，构造补全列表：

```
→ update_object_type_properties(
    type_name="Order",
    properties=[
      {"property_name": "payment_method", "display_name": "支付方式", "type": "String", "required": false, "is_primary_key": false, "source_column": "payment_method"},
      {"property_name": "shipping_region_id", "display_name": "收货区域ID", "type": "Long", "required": false, "is_primary_key": false, "source_column": "shipping_region_id"},
      {"property_name": "remark", "display_name": "备注", "type": "String", "required": false, "is_primary_key": false, "source_column": "remark"},
      {"property_name": "created_at", "display_name": "创建时间", "type": "Timestamp", "required": false, "is_primary_key": false, "source_column": "created_at"},
      {"property_name": "paid_at", "display_name": "支付时间", "type": "Timestamp", "required": false, "is_primary_key": false, "source_column": "paid_at"},
      {"property_name": "shipped_at", "display_name": "发货时间", "type": "Timestamp", "required": false, "is_primary_key": false, "source_column": "shipped_at"},
      {"property_name": "delivered_at", "display_name": "签收时间", "type": "Timestamp", "required": false, "is_primary_key": false, "source_column": "delivered_at"},
      {"property_name": "canceled_at", "display_name": "取消时间", "type": "Timestamp", "required": false, "is_primary_key": false, "source_column": "canceled_at"}
    ]
  )
← 弹出交互式卡片（review_table 类型），用户逐个勾选 ✅添加 / ⏭️跳过
← 用户提交后：{"success": true, "added": 7, "skipped": 1}

→ finalize_and_publish(type_name="Order")
← {"success": true, "status": "ACTIVE"}
```

> Agent："Order 已补全 7 个属性并发布为 ACTIVE 状态。"

## update_object_type_properties 参数说明

每个属性对象的必填字段：

```json
{
  "property_name": "payment_method",
  "display_name": "支付方式",
  "type": "String",
  "required": false,
  "is_primary_key": false,
  "source_column": "payment_method"
}
```

- `type` 可选值：String / Integer / Long / Double / Boolean / Date / Timestamp / Json
- `source_column` 必须与源表列名一致（从 scan_table_columns 获取）
- `decisions` 字段**不要填**，系统会通过交互卡片自动回传用户选择
