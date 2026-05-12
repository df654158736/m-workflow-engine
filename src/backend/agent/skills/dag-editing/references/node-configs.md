# 20 种 Pipeline 节点类型 config 字段详表

> 数据来源：`proto/plane_f/pipeline_engine.proto` StepType enum + `df-pipeline-dag.vue` `generateMockSql()` 第 192-228 行 + `pipeline.ts` STEP_TYPE_MAP

## P0 — 数据加工（11 种，优先支持）

### FILTER — 数据过滤

```json
{
  "conditions": [
    { "field": "status", "operator": "!=", "value": "CANCELED" },
    { "field": "total_amount", "operator": ">", "value": "0" }
  ]
}
```

sqlFragment 示例：
```sql
SELECT * FROM input
WHERE status != 'CANCELED'
  AND total_amount > 0
```

operator 可选值：`=`, `!=`, `>`, `>=`, `<`, `<=`, `LIKE`, `IN`, `IS NULL`, `IS NOT NULL`

---

### MAP — 字段映射/重命名

```json
{
  "mappings": [
    { "source": "order_no", "target": "订单编号" },
    { "source": "total_amount", "target": "订单金额" }
  ]
}
```

sqlFragment 示例：
```sql
SELECT
  order_no AS 订单编号,
  total_amount AS 订单金额
FROM input
```

---

### JOIN — 多表关联

```json
{
  "join_type": "LEFT",
  "left_table": "df_order",
  "right_table": "df_customer",
  "conditions": [
    { "left": "customer_id", "right": "id" }
  ]
}
```

sqlFragment 示例：
```sql
SELECT a.*, b.*
FROM df_order a
LEFT JOIN df_customer b
  ON a.customer_id = b.id
```

join_type 可选值：`INNER`, `LEFT`, `RIGHT`, `FULL`

---

### UNION — 合并数据集

```json
{
  "distinct": true
}
```

sqlFragment 示例：
```sql
SELECT * FROM input_1
UNION ALL
SELECT * FROM input_2
```

`distinct: true` 时用 `UNION`（去重），`false` 时用 `UNION ALL`

---

### DEDUPLICATE — 数据去重

```json
{
  "key_fields": ["order_no", "customer_id"],
  "order_by": "updated_at DESC"
}
```

sqlFragment 示例：
```sql
SELECT * FROM (
  SELECT *, ROW_NUMBER() OVER (
    PARTITION BY order_no, customer_id
    ORDER BY updated_at DESC
  ) AS rn
  FROM input
) WHERE rn = 1
```

---

### GROUP_AGGREGATION — 分组聚合

```json
{
  "group_by": ["customer_id", "status"],
  "aggregates": [
    { "function": "SUM", "field": "total_amount", "alias": "total" },
    { "function": "COUNT", "field": "*", "alias": "order_count" }
  ],
  "having": "SUM(total_amount) > 1000"
}
```

sqlFragment 示例：
```sql
SELECT customer_id, status,
  SUM(total_amount) AS total,
  COUNT(*) AS order_count
FROM input
GROUP BY customer_id, status
HAVING SUM(total_amount) > 1000
```

aggregate function 可选值：`SUM`, `COUNT`, `AVG`, `MIN`, `MAX`, `COUNT_DISTINCT`

---

### WINDOW_AGGREGATION — 窗口聚合

```json
{
  "time_column": "order_time",
  "window_type": "TUMBLE",
  "window_size": "1 HOUR",
  "aggregates": [
    { "function": "SUM", "field": "total_amount", "alias": "hourly_total" }
  ]
}
```

sqlFragment 示例：
```sql
SELECT
  TUMBLE_START(order_time, INTERVAL '1' HOUR) AS window_start,
  SUM(total_amount) AS hourly_total
FROM input
GROUP BY TUMBLE(order_time, INTERVAL '1' HOUR)
```

window_type 可选值：`TUMBLE`（滚动）、`HOP`（滑动）、`SESSION`（会话）

---

### SQL_TRANSFORM — SQL 自由转换

```json
{
  "sql": "SELECT *, CASE WHEN total_amount > 1000 THEN 'HIGH' ELSE 'LOW' END AS amount_level FROM input"
}
```

sqlFragment = config.sql（直接取值）

适用于无法用结构化 config 表达的复杂转换。

---

### TRANSFORM — 通用转换

```json
{
  "sql": "SELECT *, CAST(order_time AS TIMESTAMP) AS order_ts FROM input WHERE order_no IS NOT NULL"
}
```

sqlFragment = config.sql

与 SQL_TRANSFORM 功能相同，前端两者共用同一渲染逻辑。历史原因保留两个 type。

---

### QUERY — 简单查询

```json
{
  "sql": "SELECT * FROM df_order WHERE created_at > '2026-01-01'"
}
```

sqlFragment = config.sql

通常用于 DAG 入口节点，从数据源表直接查询数据。

---

### ONTOLOGY_MAPPING — 本体映射

```json
{
  "target_object_type": "Order",
  "field_mappings": [
    { "source_field": "order_no", "target_property": "orderNumber", "transform": null },
    { "source_field": "total_amount", "target_property": "amount", "transform": "CAST(? AS DECIMAL(18,2))" }
  ]
}
```

sqlFragment 示例（伪码，实际由 Ontology SDK 执行）：
```sql
-- Ontology SDK
map_to_ontology(
  object_type="Order",
  mappings={...}
)
```

---

## P1 — 本体与智能（3 种）

### ONTOLOGY_LINK — 创建本体关系

```json
{
  "link_type": "OrderBelongsToCustomer",
  "source_object_type": "Order",
  "target_object_type": "Customer",
  "source_key": "customer_id",
  "target_key": "id"
}
```

---

### DATA_QUALITY — 数据质量校验

```json
{
  "rules": [
    { "field": "order_no", "check": "NOT_NULL", "threshold": 0.99 },
    { "field": "total_amount", "check": "RANGE", "min": 0, "max": 999999 },
    { "field": "email", "check": "REGEX", "pattern": "^[\\w.-]+@[\\w.-]+$" }
  ],
  "fail_action": "FILTER"
}
```

check 可选值：`NOT_NULL`, `UNIQUE`, `RANGE`, `REGEX`, `ENUM`, `LENGTH`
fail_action 可选值：`FILTER`（过滤不合格行）、`TAG`（标记但保留）、`FAIL`（中止）

---

### ENTITY_RESOLUTION — 实体消歧

```json
{
  "match_fields": ["name", "phone", "address"],
  "algorithm": "FUZZY",
  "threshold": 0.85,
  "merge_strategy": "KEEP_LATEST"
}
```

algorithm 可选值：`EXACT`, `FUZZY`, `ML`
merge_strategy 可选值：`KEEP_LATEST`, `KEEP_FIRST`, `MERGE_ALL`

---

## P2 — 智能节点（3 种）

### REASONING — 调用推理引擎

```json
{
  "model": "qwen-plus",
  "prompt": "分析以下订单数据，识别异常模式",
  "input_field": "data",
  "output_format": "JSON"
}
```

---

### DECISION — 调用决策引擎

```json
{
  "rule_set_id": "risk-assessment-v1",
  "input_mapping": { "amount": "total_amount", "customer_level": "level" },
  "output_field": "risk_score"
}
```

---

### ACTION — 调用 Plane E Action

```json
{
  "action_id": "send-notification",
  "args": { "channel": "email", "template": "order-alert" }
}
```

---

## P2 — 流程控制（3 种）

### BRANCH — 条件分支

```json
{
  "expression": "total_amount > 10000",
  "true_branch": "high_value",
  "false_branch": "normal"
}
```

---

### WAIT — 等待/定时

```json
{
  "wait_type": "DURATION",
  "duration": "30m"
}
```

wait_type 可选值：`DURATION`（固定时长）、`CRON`（定时）、`SIGNAL`（等待外部信号）

---

### SUB_PIPELINE — 调用子 Pipeline

```json
{
  "pipeline_id": "019e1623-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "input_mapping": { "data": "upstream_output" }
}
```

---

## WRITE — 写入操作

> 通常作为 SINK 节点使用，AI 一般不需要手动创建。

```json
{
  "target_table": "silver.order_cleaned",
  "write_mode": "APPEND"
}
```

write_mode 可选值：`APPEND`, `OVERWRITE`, `UPSERT`
