# 字段映射规范

## SQL 类型 → Ontology 类型映射

| SQL 类型 | Ontology 类型 | 备注 |
|---------|--------------|------|
| VARCHAR / CHAR / TEXT | String | 默认映射 |
| INT / INTEGER / SMALLINT / BIGINT | Integer | |
| DECIMAL / NUMERIC / FLOAT / DOUBLE | Double | |
| BOOLEAN / BOOL / BIT | Boolean | |
| DATE | Date | |
| TIMESTAMP / DATETIME | Timestamp | |
| JSON / JSONB | String | 序列化为字符串 |

## 列名 → 属性名转换

1. 全部转 snake_case（`SupplierName` → `supplier_name`）
2. 去掉表名前缀（`t_supplier.sup_name` → `name`）
3. 去掉冗余后缀（`_flag` → 用 Boolean 类型代替）
4. 缩写展开（`qty` → `quantity`，`amt` → `amount`，`dt` → `date`）

## 常见映射模式

| 列名模式 | 推荐属性名 | 类型 |
|---------|-----------|------|
| `id` / `*_id` | 保持原名，设为主键 | String |
| `*_name` / `name` | 保持原名 | String |
| `*_code` / `code` | 保持原名 | String |
| `*_date` / `*_dt` | 展开为 `*_date` | Date |
| `*_time` / `*_at` | 保持原名 | Timestamp |
| `*_amount` / `*_amt` | 展开为 `*_amount` | Double |
| `*_count` / `*_qty` | 展开为 `*_quantity` | Integer |
| `is_*` / `has_*` | 保持原名 | Boolean |
| `status` / `state` | 保持原名 | String |
| `created_at` / `updated_at` | 保持原名 | Timestamp |
| `remark` / `memo` / `note` | 统一为 `remark` | String |

## 映射质量检查

- ✅ 主键列必须映射到主键属性
- ✅ NOT NULL 列应映射为 required 属性
- ✅ 所有源列都应有对应映射（无遗漏）
- ❌ 避免将多列映射到同一属性
- ❌ 避免跳过业务关键列（如金额、状态）
