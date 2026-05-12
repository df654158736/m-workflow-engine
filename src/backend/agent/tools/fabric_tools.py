"""数据编织 Tools — 调用真实 web-app REST API。

T8:  create_fabric_task — 创建数据编织任务
T9:  trigger_ai_analysis — 触发 AI 语义分析 + 获取候选对象
T10: get_field_mappings — 获取/生成字段映射
T11: generate_pipeline — 生成 Pipeline DSL
"""

import asyncio
import logging

from pydantic import BaseModel, Field

from backend.agent.tool_registry import tool
from backend.agent.api_client import get_project_id, api_get, api_post, ApiError

logger = logging.getLogger(__name__)


class SelectedTable(BaseModel):
    datasourceId: str
    tableName: str


class CreateFabricTaskArgs(BaseModel):
    name: str = Field(..., min_length=1, description="任务名称")
    datasource_ids: list[str] = Field(..., min_length=1)
    selected_tables: list[SelectedTable] = Field(..., min_length=1)


class GeneratePipelineArgs(BaseModel):
    task_id: str = Field(..., min_length=1)


class SubmitPipelineArgs(BaseModel):
    task_id: str = Field(..., min_length=1)
    run: bool = Field(default=True, description="注册后是否立即运行")


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

    logger.info("[trigger_ai_analysis] 触发分析: task_id=%s, project_id=%s", task_id, project_id)
    try:
        await api_post(f"{base}/analyze")
    except ApiError as e:
        logger.error("[trigger_ai_analysis] 触发分析失败: %s", e)
        return {"error": f"触发分析失败: {e}"}

    logger.info("[trigger_ai_analysis] 分析已触发，开始轮询状态...")
    last_phase = ""
    last_progress = 0
    error_message = ""
    for i in range(60):
        await asyncio.sleep(3)
        try:
            status_data = await api_get(f"{base}/analyze/status")
        except ApiError:
            continue
        if not isinstance(status_data, dict):
            continue
        progress = status_data.get("progress", 0)
        phase = status_data.get("currentPhase", status_data.get("phase", ""))
        is_failed = status_data.get("failed", False)
        is_completed = status_data.get("completed", False)
        error_message = status_data.get("errorMessage", status_data.get("error_message", ""))
        if phase != last_phase or abs(progress - last_progress) > 5:
            logger.info("[trigger_ai_analysis] 轮询 #%d: phase=%s, progress=%s%%, failed=%s, error=%s",
                        i + 1, phase, progress, is_failed, error_message or "(none)")
            last_phase = phase
            last_progress = progress
        if is_failed or phase in ("FAILED", "ERROR"):
            logger.error("[trigger_ai_analysis] 分析失败: phase=%s, error=%s", phase, error_message)
            return {
                "error": f"AI 分析失败 (phase={phase}): {error_message or '未知错误，请检查 web-app 和 intelligence-plane 日志'}",
                "task_id": task_id,
                "phase": phase,
            }
        if is_completed or progress >= 100 or phase in ("COMPLETED", "DONE"):
            logger.info("[trigger_ai_analysis] 分析完成: phase=%s", phase)
            break

    try:
        task_data = await api_get(f"{base}")
    except ApiError:
        task_data = {}
    task_status = task_data.get("status", "") if isinstance(task_data, dict) else ""
    if task_status == "FAILED":
        logger.error("[trigger_ai_analysis] 任务状态 FAILED (轮询未检测到失败)")
        return {
            "error": f"AI 分析任务失败 (task.status=FAILED): {error_message or '请检查 web-app 日志中的 [Step2] Orchestrator 失败 错误'}",
            "task_id": task_id,
        }

    try:
        results = await api_get(f"{base}/compare-results")
    except ApiError as e:
        logger.error("[trigger_ai_analysis] 获取候选对象失败: %s", e)
        return {"error": f"获取候选对象失败: {e}"}

    candidates = results if isinstance(results, list) else results.get("items", results.get("results", []))
    logger.info("[trigger_ai_analysis] 获取到 %d 个候选对象", len(candidates))

    output = []
    for c in candidates:
        sources = c.get("sourceTables", c.get("source_tables", []))
        source_str = ", ".join(
            f"{s.get('datasourceName', '')}/{s.get('tableName', '')}" if isinstance(s, dict) else str(s)
            for s in (sources if isinstance(sources, list) else [])
        ) or "—"
        matched_name = c.get("matchedOntologyName", c.get("matched_ontology_name", ""))
        matched_id = c.get("matchedOntologyId", c.get("matched_ontology_id", ""))
        confidence = c.get("confidence", c.get("matchConfidence", 0))
        status = c.get("status", c.get("matchStatus", "NEW"))
        output.append({
            "id": c.get("id"),
            "candidate_name": c.get("candidateName", c.get("candidate_name", "")),
            "candidate_name_en": c.get("candidateNameEn", c.get("candidate_name_en", "")),
            "status": status,
            "confidence": confidence if isinstance(confidence, (int, float)) else 0,
            "matched_ontology": matched_name or "—",
            "matched_ontology_id": matched_id or "",
            "source_tables": source_str,
            "decision": c.get("decision", "UNSPECIFIED"),
        })

    if not output:
        logger.warning("[trigger_ai_analysis] 0 个候选对象，task_status=%s", task_status)

    return {"task_id": task_id, "candidates": output, "total": len(output)}


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
            "target_property": m.get("targetAttribute", m.get("targetPropertyName", m.get("target_property_name", ""))),
            "target_data_type": m.get("targetType", m.get("targetDataType", m.get("target_data_type", ""))),
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


@tool(
    name="submit_pipeline",
    description="为数据编织任务中的每个已确认对象创建独立 Pipeline 并注册到系统。写操作，调用前应让用户确认。",
    requires_confirmation=True,
    args_model=SubmitPipelineArgs,
    parameters={
        "type": "object",
        "properties": {
            "task_id": {
                "type": "string",
                "description": "数据编织任务 ID（从 create_fabric_task 获取）",
            },
            "run": {
                "type": "boolean",
                "description": "注册后是否立即运行（默认 true）",
            },
        },
        "required": ["task_id"],
    },
)
async def submit_pipeline(task_id: str, run: bool = True) -> dict:
    project_id = get_project_id()
    if not project_id:
        return {"error": "未配置 project_id"}

    base = f"/api/v1/projects/{project_id}/data-fabric/tasks/{task_id}"

    # 获取 task 下所有 compare results
    try:
        results = await api_get(f"{base}/compare-results")
    except ApiError as e:
        return {"error": f"获取候选对象失败: {e}"}

    candidates = results if isinstance(results, list) else results.get("items", results.get("results", []))
    bindable = [c for c in candidates if c.get("decision") in ("CREATE", "CONFIRM")]
    if not bindable:
        return {"error": "没有 CREATE/CONFIRM 决策的候选对象，无法创建 Pipeline"}

    pipelines = []
    errors = []
    for obj in bindable:
        object_id = obj.get("id")
        object_name = obj.get("candidateNameEn", obj.get("candidateName", object_id))

        # Step 1: complete-attr — 推进到 PIPELINE_READY（生成 YAML + 写绑定准备）
        try:
            await api_post(f"{base}/objects/{object_id}/complete-attr")
            logger.info("[submit_pipeline] complete-attr OK: %s (%s)", object_name, object_id)
        except ApiError as e:
            err_str = str(e)
            if "PIPELINE_READY" in err_str or "PIPELINE_CREATED" in err_str:
                logger.info("[submit_pipeline] %s 已在 PIPELINE_READY+，跳过 complete-attr", object_name)
            else:
                errors.append(f"{object_name}: complete-attr 失败: {e}")
                continue

        # Step 2: create-pipeline (对象级) — 创建 Pipeline + 写 ontology_type_pipeline_binding
        try:
            data = await api_post(
                f"{base}/objects/{object_id}/pipeline/create",
                json_data={"name": f"fabric-{object_name}"},
            )
        except ApiError as e:
            errors.append(f"{object_name}: pipeline 创建失败: {e}")
            continue

        pipeline_id = data.get("pipelineId", "")
        pipelines.append({
            "object_id": object_id,
            "object_name": object_name,
            "pipeline_id": pipeline_id,
        })
        logger.info("[submit_pipeline] pipeline 创建成功: %s → %s", object_name, pipeline_id)

    result = {
        "success": len(pipelines) > 0,
        "pipelines": pipelines,
        "errors": errors,
        "message": f"成功创建 {len(pipelines)} 个 Pipeline" + (f"，{len(errors)} 个失败" if errors else ""),
    }

    # 可选：触发运行
    if run:
        for p in pipelines:
            pid = p["pipeline_id"]
            if not pid:
                continue
            try:
                run_data = await api_post(
                    f"/api/v1/projects/{project_id}/fabric/pipelines/{pid}/run",
                    json_data={"mode": "FULL"},
                )
                p["run_id"] = run_data.get("runId", run_data.get("id", ""))
                p["run_status"] = run_data.get("status", "PENDING")
            except ApiError as e:
                p["run_error"] = str(e)

    return result
