"""query_table_schema — 查询数据表结构。

Agent 在生成 FlinkSQL 节点时，调用此工具获取表的列名和类型，确保 SQL 正确。
"""

from backend.agent.tool_registry import tool

TABLE_SCHEMAS: dict[str, dict] = {
    "supplier_profiles": {
        "description": "供应商主档",
        "columns": [
            {"name": "supplier_id", "type": "VARCHAR", "description": "供应商 ID（主键）"},
            {"name": "supplier_name", "type": "VARCHAR", "description": "供应商名称"},
            {"name": "status", "type": "VARCHAR", "description": "状态 (active|inactive|blacklisted)"},
            {"name": "risk_score", "type": "DOUBLE", "description": "风险评分 (0-1)"},
            {"name": "category", "type": "VARCHAR", "description": "供应商类别"},
            {"name": "region", "type": "VARCHAR", "description": "所在地区"},
            {"name": "contract_amount", "type": "DECIMAL(18,2)", "description": "合同总金额"},
            {"name": "last_audit_date", "type": "DATE", "description": "最近审计日期"},
            {"name": "created_at", "type": "TIMESTAMP", "description": "创建时间"},
            {"name": "updated_at", "type": "TIMESTAMP", "description": "更新时间"},
        ],
    },
    "purchase_orders": {
        "description": "采购订单表",
        "columns": [
            {"name": "order_id", "type": "VARCHAR", "description": "订单 ID（主键）"},
            {"name": "supplier_id", "type": "VARCHAR", "description": "供应商 ID（外键）"},
            {"name": "order_date", "type": "DATE", "description": "下单日期"},
            {"name": "total_amount", "type": "DECIMAL(18,2)", "description": "订单总额"},
            {"name": "status", "type": "VARCHAR", "description": "订单状态 (pending|approved|delivered|cancelled)"},
            {"name": "items_count", "type": "INT", "description": "明细行数"},
            {"name": "delivery_date", "type": "DATE", "description": "预计交付日期"},
            {"name": "created_at", "type": "TIMESTAMP", "description": "创建时间"},
        ],
    },
    "quality_inspections": {
        "description": "质检记录表",
        "columns": [
            {"name": "inspection_id", "type": "VARCHAR", "description": "质检 ID（主键）"},
            {"name": "order_id", "type": "VARCHAR", "description": "关联订单 ID"},
            {"name": "supplier_id", "type": "VARCHAR", "description": "供应商 ID"},
            {"name": "inspection_date", "type": "DATE", "description": "质检日期"},
            {"name": "pass_rate", "type": "DOUBLE", "description": "合格率 (0-1)"},
            {"name": "defect_count", "type": "INT", "description": "缺陷数"},
            {"name": "result", "type": "VARCHAR", "description": "质检结论 (pass|fail|conditional)"},
            {"name": "inspector", "type": "VARCHAR", "description": "质检员"},
        ],
    },
    "data_quality_metrics": {
        "description": "数据质量指标表",
        "columns": [
            {"name": "metric_id", "type": "VARCHAR", "description": "指标 ID（主键）"},
            {"name": "table_name", "type": "VARCHAR", "description": "监控的表名"},
            {"name": "metric_type", "type": "VARCHAR", "description": "指标类型 (completeness|accuracy|timeliness|consistency)"},
            {"name": "value", "type": "DOUBLE", "description": "指标值 (0-1)"},
            {"name": "threshold", "type": "DOUBLE", "description": "告警阈值"},
            {"name": "check_time", "type": "TIMESTAMP", "description": "检测时间"},
            {"name": "status", "type": "VARCHAR", "description": "状态 (normal|warning|critical)"},
        ],
    },
    "inventory": {
        "description": "库存表",
        "columns": [
            {"name": "sku_id", "type": "VARCHAR", "description": "SKU 编号（主键）"},
            {"name": "product_name", "type": "VARCHAR", "description": "产品名称"},
            {"name": "quantity", "type": "INT", "description": "库存数量"},
            {"name": "warehouse", "type": "VARCHAR", "description": "仓库编号"},
            {"name": "min_stock", "type": "INT", "description": "最低库存"},
            {"name": "unit_price", "type": "DECIMAL(10,2)", "description": "单价"},
            {"name": "last_restock_date", "type": "DATE", "description": "最近补货日期"},
        ],
    },
}


@tool(
    name="query_table_schema",
    description="查询数据表的列结构（列名、类型、说明）。生成 FlinkSQL 节点前调用此工具确认表结构和可用字段。",
    parameters={
        "type": "object",
        "properties": {
            "table_name": {
                "type": "string",
                "description": "表名。留空返回所有可用表的列表。",
            }
        },
        "required": [],
    },
)
async def query_table_schema(table_name: str = "") -> dict:
    if not table_name:
        return {
            "tables": [
                {"name": name, "description": schema["description"], "column_count": len(schema["columns"])}
                for name, schema in TABLE_SCHEMAS.items()
            ],
            "total": len(TABLE_SCHEMAS),
        }

    schema = TABLE_SCHEMAS.get(table_name)
    if not schema:
        return {
            "error": f"表 '{table_name}' 不存在",
            "available_tables": list(TABLE_SCHEMAS.keys()),
        }

    return {
        "table_name": table_name,
        "description": schema["description"],
        "columns": schema["columns"],
        "column_count": len(schema["columns"]),
    }
