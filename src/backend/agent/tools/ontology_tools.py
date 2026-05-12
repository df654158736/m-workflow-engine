"""本体管理 Tools — 调用真实 web-app REST API。

T5:  list_object_types — 列出已有的 ObjectType
T6:  create_object_type — 创建 ObjectType + 属性
T7:  ai_infer_properties — AI 属性推断
T8:  get_object_type_detail — 查看 ObjectType 详情（状态、属性、映射）
T9:  update_object_type_properties — 补全/修改已有 ObjectType 的属性
T10: finalize_and_publish — 定稿并发布处于 EDITING/DRAFT 状态的 ObjectType
"""

from pydantic import BaseModel, Field

from backend.agent.tool_registry import tool
from backend.agent.api_client import get_project_id, api_get, api_post, api_put, api_delete, ApiError


class CreateObjectTypeArgs(BaseModel):
    type_name: str = Field(..., min_length=1, description="PascalCase 英文名")
    display_name: str = Field(..., min_length=1, description="中文显示名")
    description: str = ""
    datasource_id: str = ""
    table_name: str = ""
    properties_json: str = "[]"


class UpdateObjectTypePropertiesArgs(BaseModel):
    type_name: str = Field(..., min_length=1)
    properties: list[dict] = Field(..., min_length=1, description="属性列表")
    decisions: dict[str, str] = Field(default_factory=dict, description="用户决策 { propertyName: ADD|SKIP }")


class FinalizeAndPublishArgs(BaseModel):
    type_name: str = Field(..., min_length=1)


class DeleteObjectTypeArgs(BaseModel):
    type_name: str = Field(..., min_length=1)
    cascade: bool = True


class SubmitCompareDecisionsArgs(BaseModel):
    task_id: str = Field(..., min_length=1)
    decisions: dict[str, str] = Field(..., description="{ compareResultId: CONFIRM|CREATE|REJECT }")


class ConfirmFieldMappingsArgs(BaseModel):
    task_id: str = Field(..., min_length=1)
    compare_result_id: str = Field(..., min_length=1)
    decisions: dict[str, str] = Field(..., description="{ mappingId: CONFIRM|SKIP }")


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
    args_model=CreateObjectTypeArgs,
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
        "向已有 ObjectType 批量添加属性（⚠️ 交互式卡片）。"
        "传入所有待添加的属性列表，系统会弹出交互卡片让用户逐个勾选添加或跳过，提交后批量执行。"
    ),
    args_model=UpdateObjectTypePropertiesArgs,
    parameters={
        "type": "object",
        "properties": {
            "type_name": {
                "type": "string",
                "description": "ObjectType 名称",
            },
            "properties": {
                "type": "array",
                "description": "要添加/更新的属性列表",
                "items": {
                    "type": "object",
                    "properties": {
                        "property_name": {"type": "string", "description": "属性名（camelCase，如 paymentMethod）"},
                        "display_name": {"type": "string", "description": "中文显示名"},
                        "type": {"type": "string", "description": "String/Integer/Long/Double/Boolean/Date/Timestamp/Json"},
                        "required": {"type": "boolean", "description": "是否必填（默认 false）"},
                        "is_primary_key": {"type": "boolean", "description": "是否主键（默认 false）"},
                        "source_column": {"type": "string", "description": "源表列名（数据映射用）"},
                    },
                    "required": ["property_name", "display_name", "type"],
                },
            },
            "decisions": {
                "type": "object",
                "description": "用户决策（不要填，系统自动回传）: { propertyName: ADD|SKIP }",
            },
        },
        "required": ["type_name", "properties"],
    },
)
async def update_object_type_properties(
    type_name: str,
    properties: list,
    decisions: dict | None = None,
    _confirmed: bool = False,
) -> dict:
    import logging
    _log = logging.getLogger(__name__)

    project_id = get_project_id()
    if not project_id:
        return {"error": "未配置 project_id"}

    if not _confirmed:
        rows = []
        for prop in properties:
            pname = prop.get("property_name", "")
            if not pname:
                continue
            rows.append({
                "id": pname,
                "property_name": pname,
                "display_name": prop.get("display_name", ""),
                "type": prop.get("type", "String"),
                "source_column": prop.get("source_column", "") or "—",
                "required": "✓" if prop.get("required") else "",
                "suggestion": "ADD",
            })

        if not rows:
            return {"error": "属性列表为空"}

        card_data = {
            "card_type": "review_table",
            "title": f"属性补全 — {type_name}",
            "description": f"共 {len(rows)} 个属性待添加，请逐个确认或跳过",
            "columns": [
                {"key": "property_name", "label": "属性名"},
                {"key": "display_name", "label": "中文名"},
                {"key": "type", "label": "类型", "type": "badge"},
                {"key": "source_column", "label": "源列"},
                {"key": "required", "label": "必填"},
                {"key": "suggestion", "label": "建议", "type": "badge"},
            ],
            "rows": rows,
            "actions": [
                {"value": "ADD", "label": "✅ 添加", "color": "green"},
                {"value": "SKIP", "label": "⏭️ 跳过", "color": "gray"},
            ],
            "submit_label": "提交属性变更",
            "result_key": "decisions",
        }

        return {
            "requires_confirmation": True,
            "confirmation_type": "interactive_card",
            "card_data": card_data,
            "tool": "update_object_type_properties",
            "args": {"type_name": type_name, "properties": properties, "decisions": {}},
            "message": f"共 {len(rows)} 个属性待添加，请在卡片中确认。",
        }

    decisions = decisions or {}
    props_to_add = [p for p in properties if decisions.get(p.get("property_name", ""), "ADD") == "ADD"]

    _log.info("[update_object_type_properties] adding %d/%d properties to %s",
              len(props_to_add), len(properties), type_name)

    results = []
    errors = []
    for prop in props_to_add:
        body: dict = {
            "property_name": prop.get("property_name", ""),
            "display_name": prop.get("display_name", ""),
            "type": prop.get("type", "String"),
            "required": prop.get("required", False),
            "is_primary_key": prop.get("is_primary_key", False),
        }
        source_col = prop.get("source_column", "")
        if source_col:
            body["source_type"] = "DATABASE"
            body["source_column"] = source_col

        try:
            await api_post(
                f"/api/v1/projects/{project_id}/ontology/object-types/{type_name}/properties",
                json_data=body,
            )
            results.append({"property": prop.get("property_name"), "status": "ok"})
        except ApiError as e:
            errors.append({"property": prop.get("property_name"), "error": str(e)})

    skipped = len(properties) - len(props_to_add)
    return {
        "success": len(errors) == 0,
        "type_name": type_name,
        "added": len(results),
        "skipped": skipped,
        "failed": len(errors),
        "errors": errors,
        "message": f"已添加 {len(results)} 个属性" +
                   (f"，跳过 {skipped} 个" if skipped else "") +
                   (f"，{len(errors)} 个失败" if errors else ""),
    }


@tool(
    name="finalize_and_publish",
    description=(
        "将处于 EDITING 或 DRAFT 状态的 ObjectType 定稿并发布为 ACTIVE。"
        "EDITING → finalize → DRAFT → publish → ACTIVE。如已是 DRAFT 则跳过 finalize 直接 publish。"
    ),
    requires_confirmation=True,
    args_model=FinalizeAndPublishArgs,
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
    args_model=DeleteObjectTypeArgs,
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


@tool(
    name="submit_compare_decisions",
    description=(
        "对 AI 探查到的候选对象批量提交确认/驳回/新建决策。"
        "调用前必须先用 trigger_ai_analysis 获取候选列表。"
        "此工具会自动弹出交互式卡片让用户逐个点击确认/驳回/新建，用户提交后才真正执行写入。"
        "decisions 中的 key 是 trigger_ai_analysis 返回的候选对象 id，value 是你的建议决策。"
    ),
    args_model=SubmitCompareDecisionsArgs,
    parameters={
        "type": "object",
        "properties": {
            "task_id": {
                "type": "string",
                "description": "数据编织任务 ID（从 create_fabric_task 或 trigger_ai_analysis 获取）",
            },
            "decisions": {
                "type": "object",
                "description": (
                    "每个候选对象的建议决策，格式: { compareResultId: 'CONFIRM'|'CREATE'|'REJECT' }。"
                    "key 是 trigger_ai_analysis 返回的候选 id，value 是建议决策。"
                    "MAPPED/MATCHABLE 状态建议 CONFIRM，NEW 状态建议 CREATE。"
                ),
            },
        },
        "required": ["task_id", "decisions"],
    },
)
async def submit_compare_decisions(
    task_id: str,
    decisions: dict[str, str],
    _confirmed: bool = False,
) -> dict:
    import logging
    _log = logging.getLogger(__name__)

    project_id = get_project_id()
    if not project_id:
        return {"error": "未配置 project_id"}

    _log.info("[submit_compare_decisions] task_id=%s, decisions=%s, _confirmed=%s", task_id, decisions, _confirmed)

    if not _confirmed:
        card_data = await _build_card_data_from_api(project_id, task_id, decisions)
        if card_data and card_data.get("rows"):
            _log.info("[submit_compare_decisions] built card_data with %d rows, returning for confirmation", len(card_data["rows"]))
            return {
                "requires_confirmation": True,
                "confirmation_type": "interactive_card",
                "card_data": card_data,
                "tool": "submit_compare_decisions",
                "args": {"task_id": task_id, "decisions": decisions},
                "message": f"AI 探查到 {len(card_data['rows'])} 个候选对象，请在卡片中确认决策。",
            }

    _log.info("[submit_compare_decisions] executing decisions for %d candidates", len(decisions))
    results = []
    errors = []
    for result_id, decision in decisions.items():
        try:
            await api_put(
                f"/api/v1/projects/{project_id}/data-fabric/tasks/{task_id}"
                f"/compare-results/{result_id}/decision",
                {"decision": decision},
            )
            results.append({"id": result_id, "decision": decision, "status": "ok"})
        except ApiError as e:
            errors.append({"id": result_id, "decision": decision, "error": str(e)})

    confirmed_ids = [r["id"] for r in results if r["decision"] in ("CONFIRM", "CREATE")]
    return {
        "success": len(errors) == 0,
        "submitted": len(results),
        "errors": errors,
        "confirmed_object_ids": confirmed_ids,
        "message": f"已提交 {len(results)} 个决策" + (f"，{len(errors)} 个失败" if errors else ""),
    }


async def _build_card_data_from_api(project_id: str, task_id: str, decisions: dict[str, str]) -> dict:
    """从 web-app API 查询 compare-results，自动构造交互卡片数据。"""
    try:
        results = await api_get(
            f"/api/v1/projects/{project_id}/data-fabric/tasks/{task_id}/compare-results"
        )
    except ApiError:
        return {}

    candidates = results if isinstance(results, list) else results.get("items", results.get("results", []))
    rows = []
    for c in candidates:
        cid = c.get("id", "")
        if not cid:
            continue
        sources = c.get("sourceTables", c.get("source_tables", []))
        source_str = ", ".join(
            f"{s.get('datasourceName', '')}/{s.get('tableName', '')}" if isinstance(s, dict) else str(s)
            for s in (sources if isinstance(sources, list) else [])
        ) or "—"
        status = c.get("status", c.get("matchStatus", "NEW"))
        confidence = c.get("confidence", c.get("matchConfidence", 0))
        if not isinstance(confidence, (int, float)):
            confidence = 0
        matched = c.get("matchedOntologyName", c.get("matched_ontology_name", "")) or "—"
        name_cn = c.get("candidateName", c.get("candidate_name", ""))
        name_en = c.get("candidateNameEn", c.get("candidate_name_en", ""))
        display_name = f"{name_cn} ({name_en})" if name_en else name_cn

        suggestion = decisions.get(cid, "CONFIRM" if status in ("MAPPED", "MATCHABLE") else "CREATE")
        rows.append({
            "id": cid,
            "name": display_name,
            "status": status,
            "confidence": int(confidence) if confidence else 0,
            "matched": matched,
            "sources": source_str,
            "suggestion": suggestion,
        })

    return {
        "card_type": "review_table",
        "title": f"AI 探查到 {len(rows)} 个候选对象",
        "description": "请对每个候选对象做出决策后提交",
        "columns": [
            {"key": "name", "label": "名称"},
            {"key": "status", "label": "匹配状态", "type": "badge"},
            {"key": "confidence", "label": "置信度", "type": "percent"},
            {"key": "matched", "label": "匹配本体"},
            {"key": "sources", "label": "来源表"},
            {"key": "suggestion", "label": "AI 建议", "type": "badge"},
        ],
        "rows": rows,
        "actions": [
            {"value": "CONFIRM", "label": "✅ 确认", "color": "green"},
            {"value": "CREATE", "label": "➕ 新建", "color": "blue"},
            {"value": "REJECT", "label": "❌ 驳回", "color": "red"},
        ],
        "submit_label": "提交全部决策",
        "result_key": "decisions",
    }


@tool(
    name="confirm_field_mappings",
    description=(
        "对某个候选对象的字段映射进行交互式确认。"
        "调用前必须先用 get_field_mappings 获取映射列表。"
        "此工具会自动弹出交互式卡片让用户逐个确认/跳过每个字段映射，用户提交后才真正执行写入。"
        "decisions 中的 key 是字段映射 id，value 是 CONFIRM 或 SKIP。"
    ),
    args_model=ConfirmFieldMappingsArgs,
    parameters={
        "type": "object",
        "properties": {
            "task_id": {
                "type": "string",
                "description": "数据编织任务 ID",
            },
            "compare_result_id": {
                "type": "string",
                "description": "候选对象 ID（从 trigger_ai_analysis 获取）",
            },
            "decisions": {
                "type": "object",
                "description": (
                    "每个字段映射的建议决策: { mappingId: 'CONFIRM'|'SKIP' }。"
                    "key 是 get_field_mappings 返回的映射 id，value 是建议决策。"
                    "AI_SUGGESTED 状态建议 CONFIRM，不需要的字段建议 SKIP。"
                ),
            },
        },
        "required": ["task_id", "compare_result_id", "decisions"],
    },
)
async def confirm_field_mappings(
    task_id: str,
    compare_result_id: str,
    decisions: dict[str, str],
    _confirmed: bool = False,
) -> dict:
    import logging
    _log = logging.getLogger(__name__)

    project_id = get_project_id()
    if not project_id:
        return {"error": "未配置 project_id"}

    _log.info("[confirm_field_mappings] task_id=%s, compare_result_id=%s, _confirmed=%s",
              task_id, compare_result_id, _confirmed)

    if not _confirmed:
        card_data = await _build_field_mapping_card(project_id, task_id, compare_result_id, decisions)
        if card_data and card_data.get("rows"):
            _log.info("[confirm_field_mappings] built card_data with %d rows", len(card_data["rows"]))
            return {
                "requires_confirmation": True,
                "confirmation_type": "interactive_card",
                "card_data": card_data,
                "tool": "confirm_field_mappings",
                "args": {
                    "task_id": task_id,
                    "compare_result_id": compare_result_id,
                    "decisions": decisions,
                },
                "message": f"共 {len(card_data['rows'])} 个字段映射，请在卡片中确认。",
            }
        _log.warning("[confirm_field_mappings] card_data empty, mappings not ready yet")
        return {
            "error": "字段映射尚未生成完成，请先调用 get_field_mappings 确认映射列表不为空后再试。",
            "hint": "可能需要等待几秒让映射生成完成。",
        }

    _log.info("[confirm_field_mappings] executing decisions for %d mappings", len(decisions))
    results = []
    errors = []
    base = f"/api/v1/projects/{project_id}/data-fabric/tasks/{task_id}/mappings/{compare_result_id}"
    for mapping_id, decision in decisions.items():
        status = "USER_CONFIRMED" if decision == "CONFIRM" else "REJECTED"
        try:
            await api_put(
                f"{base}/{mapping_id}",
                {"status": status},
            )
            results.append({"id": mapping_id, "decision": decision, "status": "ok"})
        except ApiError as e:
            errors.append({"id": mapping_id, "decision": decision, "error": str(e)})

    return {
        "success": len(errors) == 0,
        "confirmed": sum(1 for r in results if r["decision"] == "CONFIRM"),
        "skipped": sum(1 for r in results if r["decision"] == "SKIP"),
        "errors": errors,
        "message": f"已处理 {len(results)} 个字段映射" + (f"，{len(errors)} 个失败" if errors else ""),
    }


async def _build_field_mapping_card(
    project_id: str, task_id: str, compare_result_id: str, decisions: dict[str, str],
) -> dict:
    """从 web-app API 查询字段映射，构造交互卡片数据。若映射尚未生成则先触发生成。"""
    base = f"/api/v1/projects/{project_id}/data-fabric/tasks/{task_id}/mappings/{compare_result_id}"
    try:
        data = await api_get(base)
    except ApiError:
        data = []
    mappings_list = data if isinstance(data, list) else data.get("mappings", data.get("items", []))
    if not mappings_list:
        try:
            await api_post(f"{base}/generate")
            data = await api_get(base)
        except ApiError:
            return {}

    mappings = data if isinstance(data, list) else data.get("mappings", data.get("items", []))
    rows = []
    for m in mappings:
        mid = m.get("id", "")
        if not mid:
            continue
        source_col = m.get("sourceColumn", m.get("source_column", ""))
        target_prop = m.get("targetAttribute", m.get("targetPropertyName", m.get("target_property_name", "")))
        data_type = m.get("targetType", m.get("targetDataType", m.get("target_data_type", "")))
        status = m.get("status", "AI_SUGGESTED")
        suggestion = decisions.get(mid, "CONFIRM" if status in ("AI_SUGGESTED", "CONFIRMED") else "SKIP")
        rows.append({
            "id": mid,
            "source_column": source_col,
            "target_property": target_prop,
            "data_type": data_type,
            "status": status,
            "suggestion": suggestion,
        })

    # 尝试获取候选对象名称
    obj_name = ""
    try:
        results = await api_get(
            f"/api/v1/projects/{project_id}/data-fabric/tasks/{task_id}/compare-results"
        )
        candidates = results if isinstance(results, list) else results.get("items", [])
        for c in candidates:
            if c.get("id") == compare_result_id:
                obj_name = c.get("candidateName", c.get("candidate_name", ""))
                break
    except ApiError:
        pass

    title = f"字段映射确认" + (f" — {obj_name}" if obj_name else "")

    return {
        "card_type": "review_table",
        "title": title,
        "description": f"共 {len(rows)} 个字段映射，请逐个确认或跳过",
        "columns": [
            {"key": "source_column", "label": "源列名"},
            {"key": "target_property", "label": "目标属性"},
            {"key": "data_type", "label": "数据类型", "type": "badge"},
            {"key": "status", "label": "状态", "type": "badge"},
            {"key": "suggestion", "label": "AI 建议", "type": "badge"},
        ],
        "rows": rows,
        "actions": [
            {"value": "CONFIRM", "label": "✅ 确认", "color": "green"},
            {"value": "SKIP", "label": "⏭️ 跳过", "color": "gray"},
        ],
        "submit_label": "提交字段映射",
        "result_key": "decisions",
    }
