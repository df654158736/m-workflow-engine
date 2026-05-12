# Flink SQL 语法速查

> 用于生成 Pipeline 节点的 sqlFragment。基于 Flink 1.18+ 语法。

## CREATE TABLE（SOURCE 节点对应）

```sql
CREATE TABLE df_order (
  id BIGINT,
  order_no VARCHAR,
  customer_id BIGINT,
  total_amount DECIMAL(18,2),
  status VARCHAR,
  created_at TIMESTAMP(3),
  PRIMARY KEY (id) NOT ENFORCED
) WITH (
  'connector' = 'jdbc',
  'url' = 'jdbc:postgresql://192.168.2.60:5432/demo',
  'table-name' = 'df_order',
  'username' = '...',
  'password' = '...'
)
```

## SELECT 基础

```sql
-- 列选择 + 重命名
SELECT order_no AS 订单编号, total_amount AS 金额 FROM input

-- 过滤
SELECT * FROM input WHERE status != 'CANCELED' AND total_amount > 0

-- CASE 表达式
SELECT *,
  CASE WHEN total_amount > 1000 THEN 'HIGH' ELSE 'LOW' END AS amount_level
FROM input

-- 类型转换
SELECT CAST(order_time AS TIMESTAMP) AS order_ts FROM input
```

## JOIN

```sql
-- LEFT JOIN
SELECT a.*, b.customer_name
FROM df_order a
LEFT JOIN df_customer b ON a.customer_id = b.id

-- INNER JOIN
SELECT a.order_no, b.product_name, a.quantity
FROM df_order_item a
INNER JOIN df_product b ON a.product_id = b.id
```

## 聚合

```sql
-- 分组聚合
SELECT customer_id,
  COUNT(*) AS order_count,
  SUM(total_amount) AS total
FROM input
GROUP BY customer_id
HAVING SUM(total_amount) > 1000

-- 窗口聚合（滚动窗口）
SELECT
  TUMBLE_START(order_time, INTERVAL '1' HOUR) AS window_start,
  TUMBLE_END(order_time, INTERVAL '1' HOUR) AS window_end,
  COUNT(*) AS cnt,
  SUM(total_amount) AS total
FROM input
GROUP BY TUMBLE(order_time, INTERVAL '1' HOUR)

-- 窗口聚合（滑动窗口）
SELECT
  HOP_START(order_time, INTERVAL '5' MINUTE, INTERVAL '1' HOUR) AS window_start,
  COUNT(*) AS cnt
FROM input
GROUP BY HOP(order_time, INTERVAL '5' MINUTE, INTERVAL '1' HOUR)
```

## 去重

```sql
-- ROW_NUMBER 去重（保留最新一条）
SELECT * FROM (
  SELECT *, ROW_NUMBER() OVER (
    PARTITION BY order_no
    ORDER BY updated_at DESC
  ) AS rn
  FROM input
) WHERE rn = 1
```

## UNION

```sql
-- 合并（保留重复）
SELECT * FROM input_a
UNION ALL
SELECT * FROM input_b

-- 合并（去重）
SELECT * FROM input_a
UNION
SELECT * FROM input_b
```

## INSERT INTO（SINK 节点对应）

```sql
INSERT INTO silver.order_cleaned
SELECT order_no, customer_id, total_amount, status
FROM input
WHERE status != 'CANCELED'
```

## 常用函数

| 分类 | 函数 | 示例 |
|------|------|------|
| 字符串 | `UPPER/LOWER/TRIM/CONCAT/SUBSTRING` | `UPPER(status)` |
| 数值 | `ABS/ROUND/FLOOR/CEIL/MOD` | `ROUND(amount, 2)` |
| 时间 | `CURRENT_TIMESTAMP/DATE_FORMAT/TIMESTAMPDIFF` | `DATE_FORMAT(ts, 'yyyy-MM-dd')` |
| 条件 | `CASE WHEN/COALESCE/NULLIF/IF` | `COALESCE(name, 'N/A')` |
| 聚合 | `COUNT/SUM/AVG/MIN/MAX/COUNT(DISTINCT)` | `COUNT(DISTINCT customer_id)` |
| 窗口 | `ROW_NUMBER/RANK/LAG/LEAD` | `LAG(amount, 1) OVER (ORDER BY ts)` |
| 类型 | `CAST/TRY_CAST` | `CAST(val AS DECIMAL(18,2))` |
