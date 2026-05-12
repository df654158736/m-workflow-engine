# 本体对象探查流程（多表批量分析）

## 用户："帮我分析这个数据源里的表，看看有哪些本体对象"

**Step 1: 查数据源 + 列表**

```
→ list_datasources()
← { "datasources": [{"id": "019dd21d-17f8-7967-a04f-3305c95af788", "name": "192.168.2.60", ...}] }

→ list_tables(datasource_id="019dd21d-17f8-7967-a04f-3305c95af788")
← { "tables": [
    {"name": "df_customer", "comment": "客户信息表（实体）"},
    {"name": "df_order", "comment": "订单事件"},
    {"name": "df_product", "comment": "产品信息表（实体）"},
    ...
  ], "total": 8 }
```

> Agent："数据源有 8 张表，我来创建编织任务进行 AI 分析。"

**Step 2: 创建编织任务**

```
→ create_fabric_task(
    name="CRM数据探查",
    datasource_ids=["019dd21d-17f8-7967-a04f-3305c95af788"],
    selected_tables=[
      {"datasourceId": "019dd21d-17f8-7967-a04f-3305c95af788", "tableName": "df_customer"},
      {"datasourceId": "019dd21d-17f8-7967-a04f-3305c95af788", "tableName": "df_order"},
      {"datasourceId": "019dd21d-17f8-7967-a04f-3305c95af788", "tableName": "df_product"}
    ]
  )
← {"success": true, "task_id": "019e1620-0fcb-7761-b262-7c4aa28f53e6", "status": "CREATED"}
```

**Step 3: 触发 AI 分析**

```
→ trigger_ai_analysis(task_id="019e1620-0fcb-7761-b262-7c4aa28f53e6")
← {
    "candidates": [
      {
        "id": "cr-001",
        "candidate_name": "客户",
        "candidate_name_en": "Customer",
        "status": "MATCHABLE",
        "confidence": 85,
        "matched_ontology": "客户主数据",
        "source_tables": "192.168.2.60/df_customer",
        "decision": "UNSPECIFIED"
      },
      {
        "id": "cr-002",
        "candidate_name": "订单",
        "status": "NEW",
        "confidence": 0,
        "matched_ontology": "—",
        "source_tables": "192.168.2.60/df_order",
        "decision": "UNSPECIFIED"
      },
      {
        "id": "cr-003",
        "candidate_name": "产品",
        "status": "MATCHABLE",
        "confidence": 72,
        "matched_ontology": "产品目录",
        "source_tables": "192.168.2.60/df_product",
        "decision": "UNSPECIFIED"
      }
    ],
    "total": 3
  }
```

**Step 4: 提交候选决策（自动弹交互卡片）**

> Agent 根据 status 构造建议决策：MATCHABLE → CONFIRM，NEW → CREATE

```
→ submit_compare_decisions(
    task_id="019e1620-...",
    decisions={
      "cr-001": "CONFIRM",
      "cr-002": "CREATE",
      "cr-003": "CONFIRM"
    }
  )
← 弹出交互式卡片（review_table 类型），用户逐行点击 ✅确认/➕新建/❌驳回
← 用户提交后：{"success": true, "submitted": 3, "confirmed_object_ids": ["cr-001", "cr-002", "cr-003"]}
```

**Step 5: 字段映射确认（对每个已确认对象）**

```
→ get_field_mappings(task_id="019e1620-...", compare_result_id="cr-001")
← {
    "mappings": [
      {"id": "fm-001", "source_column": "id", "target_property": "id", "target_data_type": "String", "status": "AI_SUGGESTED"},
      {"id": "fm-002", "source_column": "name", "target_property": "name", "target_data_type": "String", "status": "AI_SUGGESTED"},
      ...共 12 个
    ],
    "total": 12
  }

→ confirm_field_mappings(
    task_id="019e1620-...",
    compare_result_id="cr-001",
    decisions={
      "fm-001": "CONFIRM",
      "fm-002": "CONFIRM",
      ...所有 AI_SUGGESTED → CONFIRM
    }
  )
← 弹出交互式卡片，用户逐个确认/跳过字段映射
← 用户提交后：{"success": true, "confirmed": 11, "skipped": 1}
```

**Step 6: 提交 Pipeline**

```
→ submit_pipeline(task_id="019e1620-...", run=true)
← {
    "success": true,
    "pipelines": [
      {"object_name": "Customer", "pipeline_id": "pl-001", "run_status": "PENDING"},
      {"object_name": "Order", "pipeline_id": "pl-002", "run_status": "PENDING"},
      {"object_name": "Product", "pipeline_id": "pl-003", "run_status": "PENDING"}
    ]
  }
```

> Agent："探查完成！3 个本体对象已创建，Pipeline 已启动运行。"

## 探查流程决策规则

| 候选 status | 建议决策 | 含义 |
|------------|---------|------|
| `MATCHABLE` | `CONFIRM` | 已匹配到已有本体，确认关联 |
| `MAPPED` | `CONFIRM` | 已完全映射，确认 |
| `NEW` | `CREATE` | 未匹配，建议新建本体 |
| 其他 | 由用户在卡片中决定 | — |
