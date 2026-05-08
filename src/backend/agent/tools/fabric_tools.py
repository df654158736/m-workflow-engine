"""数据编织 Tools — 调用真实 web-app REST API。

T8:  create_fabric_task — 创建数据编织任务
T9:  trigger_ai_analysis — 触发 AI 语义分析 + 获取候选对象
T10: get_field_mappings — 获取/生成字段映射
T11: generate_pipeline — 生成 Pipeline DSL
"""

import asyncio

from pydantic import BaseModel, Field

from backend.agent.tool_registry import tool
from backend.agent.api_client import get_project_id, api_get, api_post, ApiError


class SelectedTable(BaseModel):
    datasourceId: str
    tableName: str


class CreateFabricTaskArgs(BaseModel):
    name: str = Field(..., min_length=1, description="任务名称")
    datasource_ids: list[str] = Field(..., min_length=1)
    selected_tables: list[SelectedTable] = Field(..., min_length=1)


class GeneratePipelineArgs(BaseModel):
    task_id: str = Field(..., min_length=1)


@tool(
    name="create_fabric_task",
    description="创建数据编织任务。将数据源的表选入任务，后续可做 AI 分析、字段映射、Pipeline 生成。写操作，调用前应让用户确认。",
    requires_confirmation=True,
    args_model=CreateFabricTaskArgs,
    parameters={
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "任务名称",
            },
            "datasource_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "数据源 ID 列表",
            },
            "selected_tables": {
                "type": "array",
                "description": "选中的表列表",
                "items": {
                    "type": "object",
                    "properties": {
                        "datasourceId": {"type": "string"},
                        "tableName": {"type": "string"},
                    },
                },
            },
        },
        "required": ["name", "datasource_ids", "selected_tables"],
    },
)
async def create_fabric_task(
    name: str,
    datasource_ids: list,
    selected_tables: list,
) -> dict:
    project_id = get_project_id()
    if not project_id:
        return {"error": "未配置 project_id"}

    body = {
        "name": name,
        "datasourceIds": datasource_ids,
        "selectedTables": selected_tables,
    }

    try:
        data = await api_post(
            f"/api/v1/projects/{project_id}/data-fabric/tasks",
            json_data=body,
        )
    except ApiError as e:
        return {"error": str(e)}

    task_id = data.get("id", data.get("taskId", ""))
    return {
        "success": True,
        "task_id": task_id,
        "name": data.get("name", name),
        "status": data.get("status", ""),
    }


@tool(
    name="trigger_ai_analysis",
    description="触发数据编织任务的 AI 语义分析。分析完成后返回候选对象列表（本体对象推荐）。这个过程可能需要几秒到几分钟。",
    parameters={
        "type": "object",
        "properties": {
            "task_id": {
                "type": "string",
                "description": "数据编织任务 ID（从 create_fabric_task 获取）",
            },
        },
        "required": ["task_id"],
    },
)
async def trigger_ai_analysis(task_id: str) -> dict:
    project_id = get_project_id()
    if not project_id:
        return {"error": "未配置 project_id"}

    base = f"/api/v1/projects/{project_id}/data-fabric/tasks/{task_id}"

    try:
        await api_post(f"{base}/analyze")
    except ApiError as e:
        return {"error": f"触发分析失败: {e}"}

    for _ in range(30):
        await asyncio.sleep(2)
        try:
            status_data = await api_get(f"{base}/analyze/status")
        except ApiError:
            continue
        progress = status_data.get("progress", 0) if isinstance(status_data, dict) else 0
        phase = status_data.get("phase", "") if isinstance(status_data, dict) else ""
        if progress >= 100 or phase in ("COMPLETED", "DONE"):
            break

    try:
        results = await api_get(f"{base}/compare-results")
    except ApiError as e:
        return {"error": f"获取候选对象失败: {e}"}

    candidates = results if isinstance(results, list) else results.get("items", results.get("results", []))
    output = []
    for c in candidates:
        output.append({
            "id": c.get("id"),
            "candidate_name": c.get("candidateName", c.get("candidate_name", "")),
            "candidate_name_en": c.get("candidateNameEn", c.get("candidate_name_en", "")),
            "source_tables": c.get("sourceTables", c.get("source_tables", [])),
            "decision": c.get("decision", "UNSPECIFIED"),
        })

    return {"candidates": output, "total": len(output)}


@tool(
    name="get_field_mappings",
    description="获取或生成某个候选对象的字段映射。先调 generate 生成建议，再返回映射列表。",
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
        },
        "required": ["task_id", "compare_result_id"],
    },
)
async def get_field_mappings(task_id: str, compare_result_id: str) -> dict:
    project_id = get_project_id()
    if not project_id:
        return {"error": "未配置 project_id"}

    base = f"/api/v1/projects/{project_id}/data-fabric/tasks/{task_id}/mappings/{compare_result_id}"

    try:
        await api_post(f"{base}/generate")
    except ApiError:
        pass

    try:
        data = await api_get(base)
    except ApiError as e:
        return {"error": str(e)}

    mappings = data if isinstance(data, list) else data.get("mappings", data.get("items", []))
    result = []
    for m in mappings:
        result.append({
            "id": m.get("id"),
            "source_column": m.get("sourceColumn", m.get("source_column", "")),
            "target_property": m.get("targetPropertyName", m.get("target_property_name", "")),
            "target_data_type": m.get("targetDataType", m.get("target_data_type", "")),
            "status": m.get("status", ""),
        })

    return {"mappings": result, "total": len(result)}


@tool(
    name="generate_pipeline",
    description="根据数据编织任务的字段映射生成 Pipeline DSL（YAML 格式）。写操作前应让用户确认。",
    requires_confirmation=True,
    args_model=GeneratePipelineArgs,
    parameters={
        "type": "object",
        "properties": {
            "task_id": {
                "type": "string",
                "description": "数据编织任务 ID",
            },
            "validate": {
                "type": "boolean",
                "description": "是否同时校验生成的 DSL（默认 true）",
            },
        },
        "required": ["task_id"],
    },
)
async def generate_pipeline(task_id: str, validate: bool = True) -> dict:
    project_id = get_project_id()
    if not project_id:
        return {"error": "未配置 project_id"}

    base = f"/api/v1/projects/{project_id}/data-fabric/tasks/{task_id}"

    try:
        data = await api_post(f"{base}/generate-pipeline")
    except ApiError as e:
        return {"error": str(e)}

    yaml_dsl = data.get("yamlContent", data.get("yaml_content", data.get("yamlDsl", "")))

    result = {
        "success": True,
        "yaml_dsl": yaml_dsl,
    }

    if validate and yaml_dsl:
        try:
            validation = await api_post(
                f"{base}/validate-pipeline",
                json_data={"yamlDsl": yaml_dsl},
            )
            result["validation"] = {
                "valid": validation.get("valid", False),
                "errors": validation.get("errors", []),
            }
        except ApiError as e:
            result["validation"] = {"valid": False, "errors": [str(e)]}

    return result
