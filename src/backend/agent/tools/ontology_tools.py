"""本体管理 Tools — 调用真实 web-app REST API。

T5: list_object_types — 列出已有的 ObjectType
T6: create_object_type — 创建 ObjectType + 属性
T7: ai_infer_properties — AI 属性推断
"""

from backend.agent.tool_registry import tool
from backend.agent.api_client import get_project_id, api_get, api_post, ApiError


@tool(
    name="list_object_types",
    description="列出当前项目已有的 ObjectType（本体对象类型）。返回名称、显示名、状态、版本。Agent 用来避免重复创建。",
    parameters={
        "type": "object",
        "properties": {
            "keyword": {
                "type": "string",
                "description": "可选：按名称关键词过滤",
            },
        },
        "required": [],
    },
)
async def list_object_types(keyword: str = "") -> dict:
    project_id = get_project_id()
    if not project_id:
        return {"error": "未配置 project_id"}

    try:
        data = await api_get(f"/api/v1/projects/{project_id}/ontology")
    except ApiError as e:
        return {"error": str(e)}

    schemas = data.get("schemas", []) if isinstance(data, dict) else data
    result = []
    for s in schemas:
        name = s.get("name", "")
        display = s.get("display_name", s.get("displayName", ""))
        if keyword and keyword.lower() not in name.lower() and keyword.lower() not in display.lower():
            continue
        result.append({
            "name": name,
            "display_name": display,
            "status": s.get("status", ""),
            "version": s.get("version", ""),
            "kind": s.get("kind", "Entity"),
            "description": s.get("description", ""),
        })

    return {"object_types": result, "total": len(result)}


@tool(
    name="create_object_type",
    description="创建一个新的 ObjectType（本体对象类型）及其属性。这是写操作，调用前应让用户确认方案。",
    parameters={
        "type": "object",
        "properties": {
            "type_name": {
                "type": "string",
                "description": "类型名称（PascalCase，英文，如 Supplier）",
            },
            "display_name": {
                "type": "string",
                "description": "中文显示名（如 供应商）",
            },
            "description": {
                "type": "string",
                "description": "类型描述",
            },
            "properties_json": {
                "type": "string",
                "description": "属性列表的 JSON 字符串，格式: [{\"property_name\":\"name\",\"type\":\"String\",\"required\":true,\"is_primary_key\":false}]。type 可选: String/Integer/Double/Boolean/Date/Timestamp",
            },
        },
        "required": ["type_name", "display_name"],
    },
)
async def create_object_type(
    type_name: str,
    display_name: str,
    description: str = "",
    properties_json: str = "[]",
) -> dict:
    project_id = get_project_id()
    if not project_id:
        return {"error": "未配置 project_id"}

    import json as _json
    try:
        properties = _json.loads(properties_json) if properties_json else []
    except _json.JSONDecodeError:
        return {"error": f"properties_json 格式错误，必须是合法 JSON 数组"}

    body = {
        "type_name": type_name,
        "display_name": display_name,
        "description": description,
        "properties": properties,
    }

    try:
        data = await api_post(
            f"/api/v1/projects/{project_id}/ontology/object-types",
            json_data=body,
        )
    except ApiError as e:
        return {"error": str(e)}

    return {
        "success": True,
        "name": data.get("name", type_name),
        "display_name": data.get("display_name", display_name),
        "version": data.get("version", ""),
        "status": data.get("status", ""),
    }


@tool(
    name="ai_infer_properties",
    description="AI 属性推断：根据数据源的表，由 AI 推荐 ObjectType 应有的属性。只需提供数据源 ID 和表名，系统会自动获取列信息。",
    parameters={
        "type": "object",
        "properties": {
            "datasource_id": {
                "type": "string",
                "description": "数据源 ID",
            },
            "table_name": {
                "type": "string",
                "description": "表名",
            },
        },
        "required": ["datasource_id", "table_name"],
    },
)
async def ai_infer_properties(
    datasource_id: str,
    table_name: str,
) -> dict:
    project_id = get_project_id()
    if not project_id:
        return {"error": "未配置 project_id"}

    try:
        col_data = await api_get(
            f"/api/v1/projects/{project_id}/datasources/{datasource_id}/metadata/{table_name}/columns"
        )
        raw_cols = col_data if isinstance(col_data, list) else col_data.get("data", col_data.get("columns", []))
        columns = [{"name": c.get("name"), "type": c.get("type")} for c in raw_cols]
    except ApiError:
        columns = []

    body = {
        "datasourceId": datasource_id,
        "tableName": table_name,
        "columns": columns,
    }

    try:
        data = await api_post(
            f"/api/v1/projects/{project_id}/ontology/ai/infer-properties",
            json_data=body,
        )
    except ApiError as e:
        return {"error": str(e), "hint": "AI 推断服务可能未启动，可手动指定属性"}

    properties = data.get("properties", []) if isinstance(data, dict) else data
    return {
        "table_name": table_name,
        "inferred_properties": properties,
        "total": len(properties),
    }
