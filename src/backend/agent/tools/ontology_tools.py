"""本体管理 Tools — 调用真实 web-app REST API。

T5:  list_object_types — 列出已有的 ObjectType
T6:  create_object_type — 创建 ObjectType + 属性
T7:  ai_infer_properties — AI 属性推断
T8:  get_object_type_detail — 查看 ObjectType 详情（状态、属性、映射）
T9:  update_object_type_properties — 补全/修改已有 ObjectType 的属性
T10: finalize_and_publish — 定稿并发布处于 EDITING/DRAFT 状态的 ObjectType
"""

from backend.agent.tool_registry import tool
from backend.agent.api_client import get_project_id, api_get, api_post, api_put, api_delete, ApiError


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
    description=(
        "创建一个新的 ObjectType（本体对象类型）及其属性，并自动定稿发布。这是写操作，调用前应让用户确认方案。"
        "如果从数据库表创建，必须提供 datasource_id 和 table_name，每个属性必须包含 source_column。"
    ),
    requires_confirmation=True,
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
            "datasource_id": {
                "type": "string",
                "description": "数据源 ID（从 list_datasources 获取）。提供后会自动创建数据映射关系。",
            },
            "table_name": {
                "type": "string",
                "description": "源表名（如 df_product）。与 datasource_id 配合使用。",
            },
            "properties_json": {
                "type": "string",
                "description": (
                    "属性列表 JSON 字符串。格式: "
                    '[{"property_name":"sku","display_name":"SKU编码","type":"String","required":true,"is_primary_key":false,"source_column":"sku"}]。'
                    "type 可选: String/Integer/Double/Boolean/Date/Timestamp/Json。"
                    "source_column 必填（对应源表列名），display_name 必填（中文显示名）。"
                ),
            },
        },
        "required": ["type_name", "display_name"],
    },
)
async def create_object_type(
    type_name: str,
    display_name: str,
    description: str = "",
    datasource_id: str = "",
    table_name: str = "",
    properties_json: str = "[]",
) -> dict:
    project_id = get_project_id()
    if not project_id:
        return {"error": "未配置 project_id"}

    import json as _json
    try:
        properties = _json.loads(properties_json) if properties_json else []
    except _json.JSONDecodeError:
        return {"error": "properties_json 格式错误，必须是合法 JSON 数组"}

    for prop in properties:
        if not prop.get("display_name"):
            prop["display_name"] = prop.get("property_name", "")
        if datasource_id and table_name:
            prop.setdefault("source_type", "DATABASE")
            prop.setdefault("source_table", table_name)
            if not prop.get("source_column"):
                prop["source_column"] = prop.get("property_name", "")
            prop.setdefault("source_field", prop.get("source_column", ""))

    body = {
        "type_name": type_name,
        "display_name": display_name,
        "description": description,
        "properties": properties,
    }
    if datasource_id:
        body["datasource_id"] = datasource_id
    if table_name:
        body["data_source"] = table_name

    try:
        data = await api_post(
            f"/api/v1/projects/{project_id}/ontology/object-types",
            json_data=body,
        )
    except ApiError as e:
        return {"error": str(e)}

    created_name = data.get("name", type_name)

    # Step 2: finalize (EDITING → DRAFT)
    try:
        await api_put(
            f"/api/v1/projects/{project_id}/ontology/object-types/{created_name}/finalize",
        )
    except ApiError as e:
        return {
            "success": True,
            "name": created_name,
            "display_name": data.get("display_name", display_name),
            "status": "EDITING",
            "warning": f"创建成功但定稿失败: {e}",
        }

    # Step 3: publish (DRAFT → ACTIVE)
    try:
        pub_data = await api_put(
            f"/api/v1/projects/{project_id}/ontology/object-types/{created_name}/publish",
        )
    except ApiError as e:
        return {
            "success": True,
            "name": created_name,
            "display_name": data.get("display_name", display_name),
            "status": "DRAFT",
            "warning": f"创建并定稿成功，但发布失败: {e}",
        }

    return {
        "success": True,
        "name": created_name,
        "display_name": pub_data.get("display_name", display_name),
        "version": pub_data.get("version", ""),
        "status": pub_data.get("status", "ACTIVE"),
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


@tool(
    name="get_object_type_detail",
    description=(
        "查看一个已有 ObjectType 的详情：状态（EDITING/DRAFT/ACTIVE）、已有属性列表、数据映射。"
        "用于判断半成品 ObjectType 卡在哪一步，决定后续补全策略。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "type_name": {
                "type": "string",
                "description": "ObjectType 名称（如 Supplier）",
            },
        },
        "required": ["type_name"],
    },
)
async def get_object_type_detail(type_name: str) -> dict:
    project_id = get_project_id()
    if not project_id:
        return {"error": "未配置 project_id"}

    try:
        data = await api_get(
            f"/api/v1/projects/{project_id}/ontology/object-types/{type_name}"
        )
    except ApiError as e:
        return {"error": str(e)}

    attributes = data.get("attributes", []) if isinstance(data, dict) else []
    return {
        "name": data.get("name", type_name),
        "display_name": data.get("displayName", data.get("display_name", "")),
        "status": data.get("status", ""),
        "kind": data.get("kind", "Entity"),
        "description": data.get("description", ""),
        "version": data.get("version", ""),
        "attributes": [
            {
                "property_name": a.get("name", a.get("property_name", "")),
                "display_name": a.get("displayName", a.get("display_name", "")),
                "type": a.get("type", ""),
                "required": a.get("required", False),
                "is_primary_key": a.get("isPrimaryKey", a.get("is_primary_key", False)),
                "source_column": a.get("sourceColumn", a.get("source_column", "")),
            }
            for a in attributes
        ],
        "attribute_count": len(attributes),
        "relations": data.get("relations", []),
    }


@tool(
    name="update_object_type_properties",
    description=(
        "向已有 ObjectType 添加缺失的属性。用于补全半成品（如 EDITING/DRAFT 状态下属性不全的 ObjectType）。"
        "每次调用添加一个属性。如需添加多个，请多次调用。"
    ),
    requires_confirmation=True,
    parameters={
        "type": "object",
        "properties": {
            "type_name": {
                "type": "string",
                "description": "ObjectType 名称",
            },
            "property_name": {
                "type": "string",
                "description": "属性名（snake_case 英文，如 sku_code）",
            },
            "display_name": {
                "type": "string",
                "description": "中文显示名（如 SKU编码）",
            },
            "property_type": {
                "type": "string",
                "description": "属性类型：String/Integer/Double/Boolean/Date/Timestamp/Json",
            },
            "required": {
                "type": "boolean",
                "description": "是否必填（默认 false）",
            },
            "is_primary_key": {
                "type": "boolean",
                "description": "是否主键（默认 false）",
            },
            "source_column": {
                "type": "string",
                "description": "源表列名（数据映射用）",
            },
        },
        "required": ["type_name", "property_name", "display_name", "property_type"],
    },
)
async def update_object_type_properties(
    type_name: str,
    property_name: str,
    display_name: str,
    property_type: str = "String",
    required: bool = False,
    is_primary_key: bool = False,
    source_column: str = "",
) -> dict:
    project_id = get_project_id()
    if not project_id:
        return {"error": "未配置 project_id"}

    body: dict = {
        "property_name": property_name,
        "display_name": display_name,
        "type": property_type,
        "required": required,
        "is_primary_key": is_primary_key,
    }
    if source_column:
        body["source_type"] = "DATABASE"
        body["source_column"] = source_column

    try:
        data = await api_post(
            f"/api/v1/projects/{project_id}/ontology/object-types/{type_name}/properties",
            json_data=body,
        )
    except ApiError as e:
        return {"error": str(e)}

    return {
        "success": True,
        "type_name": type_name,
        "added_property": property_name,
        "status": data.get("status", ""),
    }


@tool(
    name="finalize_and_publish",
    description=(
        "将处于 EDITING 或 DRAFT 状态的 ObjectType 定稿并发布为 ACTIVE。"
        "EDITING → finalize → DRAFT → publish → ACTIVE。如已是 DRAFT 则跳过 finalize 直接 publish。"
    ),
    requires_confirmation=True,
    parameters={
        "type": "object",
        "properties": {
            "type_name": {
                "type": "string",
                "description": "ObjectType 名称",
            },
        },
        "required": ["type_name"],
    },
)
async def finalize_and_publish(type_name: str) -> dict:
    project_id = get_project_id()
    if not project_id:
        return {"error": "未配置 project_id"}

    try:
        detail = await api_get(
            f"/api/v1/projects/{project_id}/ontology/object-types/{type_name}"
        )
    except ApiError as e:
        return {"error": f"查询失败: {e}"}

    status = detail.get("status", "")

    if status == "ACTIVE":
        return {"success": True, "type_name": type_name, "status": "ACTIVE", "message": "已是 ACTIVE 状态，无需操作"}

    if status == "EDITING":
        try:
            await api_put(
                f"/api/v1/projects/{project_id}/ontology/object-types/{type_name}/finalize",
            )
            status = "DRAFT"
        except ApiError as e:
            return {"error": f"定稿失败: {e}", "current_status": "EDITING"}

    if status == "DRAFT":
        try:
            pub_data = await api_put(
                f"/api/v1/projects/{project_id}/ontology/object-types/{type_name}/publish",
            )
        except ApiError as e:
            return {"error": f"发布失败: {e}", "current_status": "DRAFT"}

        return {
            "success": True,
            "type_name": type_name,
            "status": pub_data.get("status", "ACTIVE"),
            "version": pub_data.get("version", ""),
        }

    return {"error": f"未知状态: {status}", "type_name": type_name}


@tool(
    name="delete_object_type",
    description=(
        "删除一个 ObjectType 及其所有关联资源（属性、数据映射、Pipeline、编织任务）。"
        "⚠️ 这是不可逆的写操作，调用前必须向用户确认。cascade=true 时会同时删除关联的关系类型。"
    ),
    requires_confirmation=True,
    parameters={
        "type": "object",
        "properties": {
            "type_name": {
                "type": "string",
                "description": "要删除的 ObjectType 名称",
            },
            "cascade": {
                "type": "boolean",
                "description": "是否级联删除关联的关系类型（默认 true）",
            },
        },
        "required": ["type_name"],
    },
)
async def delete_object_type(type_name: str, cascade: bool = True) -> dict:
    project_id = get_project_id()
    if not project_id:
        return {"error": "未配置 project_id"}

    try:
        await api_delete(
            f"/api/v1/projects/{project_id}/ontology/object-types/{type_name}?cascade={str(cascade).lower()}"
        )
    except ApiError as e:
        return {"error": str(e)}

    return {
        "success": True,
        "type_name": type_name,
        "cascade": cascade,
        "message": f"ObjectType '{type_name}' 及其所有关联资源已删除",
    }
