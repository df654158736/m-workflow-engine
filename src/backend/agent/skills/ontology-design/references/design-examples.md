# ObjectType 属性设计示例

## ObjectType 命名规则

- **type_name**：PascalCase 英文 — `Customer`、`Order`、`OrderItem`
- **display_name**：中文 — `客户`、`订单`、`订单项`
- 名称反映业务实体，不要用表名（`DfCustomer` ❌ → `Customer` ✅）

## 主键设计

- 每个 ObjectType **必须有且只有一个主键**
- 主键属性设置 `"is_primary_key": true` 和 `"required": true`
- 选择优先级：**业务编码 > 唯一标识 > 自增 ID**

## 示例 1：df_order 表（13 列）

### 输入：列结构

```json
[
  {"name": "id",                 "type": "bigint",                       "primary_key": true,  "comment": ""},
  {"name": "order_no",           "type": "character varying",            "primary_key": false, "comment": "订单号（业务唯一键）"},
  {"name": "customer_id",        "type": "bigint",                       "primary_key": false, "comment": "下单客户 ID"},
  {"name": "total_amount",       "type": "numeric",                      "primary_key": false, "comment": "订单总金额"},
  {"name": "status",             "type": "character varying",            "primary_key": false, "comment": "PENDING/PAID/SHIPPED/DELIVERED/CANCELED"},
  {"name": "payment_method",     "type": "character varying",            "primary_key": false, "comment": "ALIPAY/WECHAT/CREDIT_CARD"},
  {"name": "shipping_region_id", "type": "bigint",                       "primary_key": false, "comment": "收货区域 ID"},
  {"name": "remark",             "type": "text",                         "primary_key": false, "comment": ""},
  {"name": "created_at",         "type": "timestamp without time zone",  "primary_key": false, "comment": ""},
  {"name": "paid_at",            "type": "timestamp without time zone",  "primary_key": false, "comment": ""},
  {"name": "shipped_at",         "type": "timestamp without time zone",  "primary_key": false, "comment": ""},
  {"name": "delivered_at",       "type": "timestamp without time zone",  "primary_key": false, "comment": ""},
  {"name": "canceled_at",        "type": "timestamp without time zone",  "primary_key": false, "comment": ""}
]
```

### 正确设计

```json
[
  {"property_name": "order_no",           "display_name": "订单号",     "type": "String",    "required": true,  "is_primary_key": true,  "source_column": "order_no"},
  {"property_name": "customer_id",        "display_name": "客户ID",     "type": "Long",      "required": true,  "is_primary_key": false, "source_column": "customer_id"},
  {"property_name": "total_amount",       "display_name": "订单总额",   "type": "Double",    "required": true,  "is_primary_key": false, "source_column": "total_amount"},
  {"property_name": "status",             "display_name": "订单状态",   "type": "String",    "required": true,  "is_primary_key": false, "source_column": "status"},
  {"property_name": "payment_method",     "display_name": "支付方式",   "type": "String",    "required": false, "is_primary_key": false, "source_column": "payment_method"},
  {"property_name": "shipping_region_id", "display_name": "收货区域ID", "type": "Long",      "required": false, "is_primary_key": false, "source_column": "shipping_region_id"},
  {"property_name": "remark",             "display_name": "备注",       "type": "String",    "required": false, "is_primary_key": false, "source_column": "remark"},
  {"property_name": "created_at",         "display_name": "创建时间",   "type": "Timestamp", "required": false, "is_primary_key": false, "source_column": "created_at"},
  {"property_name": "paid_at",            "display_name": "支付时间",   "type": "Timestamp", "required": false, "is_primary_key": false, "source_column": "paid_at"},
  {"property_name": "shipped_at",         "display_name": "发货时间",   "type": "Timestamp", "required": false, "is_primary_key": false, "source_column": "shipped_at"},
  {"property_name": "delivered_at",       "display_name": "签收时间",   "type": "Timestamp", "required": false, "is_primary_key": false, "source_column": "delivered_at"},
  {"property_name": "canceled_at",        "display_name": "取消时间",   "type": "Timestamp", "required": false, "is_primary_key": false, "source_column": "canceled_at"}
]
```

**设计要点**：
1. 跳过自增 `id`（bigint PK），选 `order_no`（业务唯一键）作主键
2. `customer_id` / `shipping_region_id` 是外键 bigint → 用 `Long`（不是 Integer）
3. `total_amount` 是 numeric → 用 `Double`
4. 所有 `timestamp without time zone` → 用 `Timestamp`
5. comment 为空的列，根据列名推断中文名
6. 每个属性都有 source_column

## 示例 2：df_customer 表（12 列）

### 输入：列结构

```json
[
  {"name": "id",         "type": "bigint",                       "primary_key": true,  "comment": "客户 ID"},
  {"name": "name",       "type": "character varying",            "primary_key": false, "comment": "姓名"},
  {"name": "email",      "type": "character varying",            "primary_key": false, "comment": "邮箱"},
  {"name": "phone",      "type": "character varying",            "primary_key": false, "comment": "电话"},
  {"name": "gender",     "type": "character varying",            "primary_key": false, "comment": "性别 M/F/OTHER"},
  {"name": "birthday",   "type": "date",                        "primary_key": false, "comment": "生日"},
  {"name": "region_id",  "type": "bigint",                      "primary_key": false, "comment": "所属区域 ID"},
  {"name": "vip_level",  "type": "integer",                     "primary_key": false, "comment": "VIP 等级 0-5"},
  {"name": "is_active",  "type": "boolean",                     "primary_key": false, "comment": "账号是否激活"},
  {"name": "tags",       "type": "jsonb",                       "primary_key": false, "comment": "标签"},
  {"name": "created_at", "type": "timestamp without time zone", "primary_key": false, "comment": ""},
  {"name": "updated_at", "type": "timestamp without time zone", "primary_key": false, "comment": ""}
]
```

### 正确设计

```json
[
  {"property_name": "id",         "display_name": "客户ID",   "type": "String",    "required": true,  "is_primary_key": true,  "source_column": "id"},
  {"property_name": "name",       "display_name": "客户姓名", "type": "String",    "required": true,  "is_primary_key": false, "source_column": "name"},
  {"property_name": "email",      "display_name": "邮箱",     "type": "String",    "required": false, "is_primary_key": false, "source_column": "email"},
  {"property_name": "phone",      "display_name": "电话",     "type": "String",    "required": false, "is_primary_key": false, "source_column": "phone"},
  {"property_name": "gender",     "display_name": "性别",     "type": "String",    "required": false, "is_primary_key": false, "source_column": "gender"},
  {"property_name": "birthday",   "display_name": "生日",     "type": "Date",      "required": false, "is_primary_key": false, "source_column": "birthday"},
  {"property_name": "region_id",  "display_name": "所属区域", "type": "Long",      "required": false, "is_primary_key": false, "source_column": "region_id"},
  {"property_name": "vip_level",  "display_name": "VIP等级",  "type": "Integer",   "required": false, "is_primary_key": false, "source_column": "vip_level"},
  {"property_name": "is_active",  "display_name": "是否激活", "type": "Boolean",   "required": false, "is_primary_key": false, "source_column": "is_active"},
  {"property_name": "tags",       "display_name": "客户标签", "type": "Json",      "required": false, "is_primary_key": false, "source_column": "tags"},
  {"property_name": "created_at", "display_name": "创建时间", "type": "Timestamp", "required": false, "is_primary_key": false, "source_column": "created_at"},
  {"property_name": "updated_at", "display_name": "更新时间", "type": "Timestamp", "required": false, "is_primary_key": false, "source_column": "updated_at"}
]
```

**设计要点**：
1. df_customer 没有业务编码列，`id` 直接用作主键，类型选 `String`
2. `birthday`（date）→ `Date`
3. `is_active`（boolean）→ `Boolean`
4. `tags`（jsonb）→ `Json`
5. `vip_level`（integer）→ `Integer`（不是 Long，因为是 integer 不是 bigint）
6. `region_id`（bigint 外键）→ `Long`
