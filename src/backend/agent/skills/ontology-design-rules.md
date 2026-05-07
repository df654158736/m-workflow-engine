# 本体设计规范

## ObjectType 命名规则

- **类型名**（type_name）：PascalCase 英文，如 `Supplier`、`PurchaseOrder`、`QualityInspection`
- **显示名**（display_name）：中文，如 `供应商`、`采购订单`、`质量检测`
- 命名要反映业务实体的本质，不要使用技术性名称

## 属性类型选择

| 数据类型 | 适用场景 | 示例 |
|---------|---------|------|
| String | 文本、编码、名称 | name, code, description |
| Integer | 整数计数 | quantity, count, age |
| Double | 金额、比率、度量 | price, rate, weight |
| Boolean | 开关状态 | is_active, is_verified |
| Date | 日期（无时间） | birth_date, due_date |
| Timestamp | 精确时间 | created_at, updated_at |

## 主键设计

- 每个 ObjectType 必须有一个主键属性
- 优先使用业务主键（如 supplier_code），而非自增 ID
- 主键属性设置 `is_primary_key: true` 和 `required: true`

## 属性命名

- 使用 snake_case：`supplier_name`，不要 `supplierName`
- 名称要具有业务含义：`unit_price`，不要 `col3`
- 避免冗余前缀：属性名不需要包含类型名（`name` 而非 `supplier_name`，因为已在 Supplier 类型下）

## 常见实体模式

### 供应链
- Supplier: code(PK), name, contact, phone, email, status, rating
- PurchaseOrder: order_no(PK), supplier_code, total_amount, status, order_date
- Material: material_code(PK), name, category, unit, spec

### 数据治理
- DataQualityRule: rule_id(PK), name, target_table, check_type, threshold
- DataAsset: asset_id(PK), name, owner, classification, update_frequency
