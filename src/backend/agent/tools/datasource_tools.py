"""数据源 Tools — 调用真实 web-app REST API。

T3: list_datasources — 列出已接入的数据源
T3.5: list_tables — 列出数据源中的所有表
T4: scan_table_columns — 扫描表的列元数据
"""

from backend.agent.tool_registry import tool
from backend.agent.api_client import get_project_id, api_get, ApiError


@tool(
    name="list_datasources",
    description="列出当前项目已接入的数据源。返回每个数据源的 ID、名称、类型、状态、表数量。可按类型或关键词过滤。",
    parameters={
        "type": "object",
        "properties": {
            "keyword": {
                "type": "string",
                "description": "可选：按名称关键词过滤",
            },
            "ds_type": {
                "type": "string",
                "description": "可选：按类型过滤（MYSQL/POSTGRESQL/ORACLE/HIVE/ICEBERG_REST/MAXCOMPUTE/HOLOGRES）",
            },
        },
        "required": [],
    },
)
async def list_datasources(keyword: str = "", ds_type: str = "") -> dict:
    project_id = get_project_id()
    if not project_id:
        return {"error": "未配置 project_id，请在 config.yaml 的 web_app 段配置"}

    params = {}
    if keyword:
        params["keyword"] = keyword
    if ds_type:
        params["type"] = ds_type

    try:
        data = await api_get(f"/api/v1/projects/{project_id}/datasources", params=params)
    except ApiError as e:
        return {"error": str(e)}

    sources = data if isinstance(data, list) else data.get("data", data.get("datasources", data.get("items", [])))
    result = []
    for ds in sources:
        result.append({
            "id": ds.get("id"),
            "name": ds.get("name"),
            "type": ds.get("type"),
            "status": ds.get("status"),
            "table_count": ds.get("tableCount", ds.get("table_count", 0)),
            "host": ds.get("host", ""),
            "database": ds.get("database", ""),
        })

    return {"datasources": result, "total": len(result)}


@tool(
    name="list_tables",
    description="列出指定数据源中的所有表。返回每张表的名称、schema、类型、行数、大小、备注。Agent 用此工具回答'有哪些表'的问题。",
    parameters={
        "type": "object",
        "properties": {
            "datasource_id": {
                "type": "string",
                "description": "数据源 ID（从 list_datasources 获取）",
            },
        },
        "required": ["datasource_id"],
    },
)
async def list_tables(datasource_id: str) -> dict:
    project_id = get_project_id()
    if not project_id:
        return {"error": "未配置 project_id"}

    try:
        data = await api_get(
            f"/api/v1/projects/{project_id}/datasources/{datasource_id}/metadata"
        )
    except ApiError as e:
        return {"error": str(e)}

    tables_raw = data if isinstance(data, list) else data.get("data", data.get("tables", []))
    result = []
    for t in tables_raw:
        result.append({
            "name": t.get("name"),
            "schema": t.get("schema", ""),
            "type": t.get("type", "TABLE"),
            "row_count": t.get("row_count", 0),
            "comment": t.get("comment", ""),
        })

    return {
        "datasource_id": datasource_id,
        "tables": result,
        "total": len(result),
    }


@tool(
    name="scan_table_columns",
    description="扫描指定数据源中某张表的列元数据。返回每列的名称、类型、是否可空、是否主键、备注。Agent 用这些信息来推荐 ObjectType 属性。",
    parameters={
        "type": "object",
        "properties": {
            "datasource_id": {
                "type": "string",
                "description": "数据源 ID（从 list_datasources 获取）",
            },
            "table_name": {
                "type": "string",
                "description": "表名",
            },
        },
        "required": ["datasource_id", "table_name"],
    },
)
async def scan_table_columns(datasource_id: str, table_name: str) -> dict:
    project_id = get_project_id()
    if not project_id:
        return {"error": "未配置 project_id"}

    try:
        data = await api_get(
            f"/api/v1/projects/{project_id}/datasources/{datasource_id}/metadata/{table_name}/columns"
        )
    except ApiError as e:
        return {"error": str(e)}

    columns = data if isinstance(data, list) else data.get("data", data.get("columns", []))
    result = []
    for col in columns:
        result.append({
            "name": col.get("name"),
            "type": col.get("type"),
            "nullable": col.get("nullable", True),
            "primary_key": col.get("pk", False),
            "comment": col.get("comment", ""),
        })

    return {
        "datasource_id": datasource_id,
        "table_name": table_name,
        "columns": result,
        "total": len(result),
    }
