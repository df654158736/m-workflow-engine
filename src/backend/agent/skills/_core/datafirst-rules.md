---
name: datafirst-core
type: core
mode: datafirst
---

# 数据接入核心规则（始终生效）

## SQL → Ontology 类型映射

| 源列类型（scan_table_columns 返回） | create_object_type 应传的 type |
|--------------------------------------|-------------------------------|
| `bigint` | `String`（主键）/ `Long`（外键） |
| `character varying` / `text` | `String` |
| `integer` / `smallint` | `Integer` |
| `numeric` / `double precision` | `Double` |
| `boolean` | `Boolean` |
| `date` | `Date` |
| `timestamp without time zone` | `Timestamp` |
| `jsonb` / `json` | `Json` |

## 强制规则

1. **先查后建**：必须 list_datasources → list_tables → scan_table_columns → list_object_types，拿到真实数据后才设计
2. **确认后写**：create_object_type 前必须用 ask_user_choice 展示方案让用户确认
3. **source_column 必填**：传了 datasource_id 时每个属性必须有 source_column
4. **AI 类型必修正**：ai_infer_properties 返回的 suggested_type 大多是 STRING，必须对照源列类型和上表修正
5. **display_name 用中文**：不能照搬列名（"order_no" ❌ → "订单号" ✅）
6. **有且只有一个主键**：选业务编码优先（order_no > id）
7. **bigint 外键用 Long**：Integer 只有 32 位会溢出

## 决策树

```
用户需求 → 提到具体表名？
  ├── 是 → 直接 scan_table_columns
  └── 否 → list_tables 展示让用户选
→ 已有同名 ObjectType？
  ├── ACTIVE → 告知已存在
  ├── EDITING/DRAFT → 判断补全还是删除重建
  └── 不存在 → 新建
→ 多表批量？
  ├── 是 → 探查流程（create_fabric_task → trigger_ai_analysis → ...）
  └── 否 → 一步到位（create_object_type 自动建编织+Pipeline）
```

## 反模式

- ❌ 不查就建（datasource_id / 列结构 / 已有类型全未知）
- ❌ AI 推荐类型直接用不修正（birthday STRING → 应为 Date）
- ❌ 缺少 source_column（Pipeline 无法映射）
- ❌ display_name 用英文列名

## 需要更多细节时

调用 `get_skill_detail` 工具查询：
- `"ontology-design"` — 完整设计示例（df_order / df_customer 从列到属性）、AI 推荐修正指南
- `"exploration-flow"` — 多表探查完整 few-shot（6 步 + 交互卡片 + 候选决策规则）
- `"field-mapping"` — 字段映射规范、confirm_field_mappings 交互流程
