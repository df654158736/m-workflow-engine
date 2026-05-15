"""DAG 编辑 Tools — Pipeline DAG AI 助手的核心工具集。

T2: read_dag_state — 读取 Pipeline DAG 当前状态
T3: add_dag_node — 新增 DAG 节点
T6: modify_dag_node / remove_dag_node — 修改/删除 DAG 节点
"""

from __future__ import annotations

import logging

from backend.agent.tool_registry import tool
from backend.agent.api_client import api_get, api_put, ApiError

logger = logging.getLogger(__name__)


def _strip_step_type_prefix(raw_type: str) -> str:
    """去掉 proto 前缀 STEP_TYPE_，返回 FILTER / JOIN 等。"""
    return raw_type.replace("STEP_TYPE_", "") if raw_type.startswith("STEP_TYPE_") else raw_type


def _rebuild_edges(sources: list, steps: list, sinks: list) -> list[dict]:
    """根据 inputs / input 字段重建 edges。"""
    edges = []
    for step in steps:
        step_id = step.get("step_id", step.get("stepId", step.get("id", "")))
        for inp in step.get("inputs", []):
            edges.append({"source": inp, "target": step_id})
    for sink in sinks:
        sink_inputs = sink.get("inputs", [])
        if sink_inputs:
            for inp in sink_inputs:
                edges.append({"source": inp, "target": sink["id"]})
        elif sink.get("input"):
            edges.append({"source": sink["input"], "target": sink["id"]})
    return edges


@tool(
    name="read_dag_state",
    description=(
        "读取 Pipeline DAG 当前状态。优先使用请求中的 dag_state（前端画布快照），"
        "无则通过 pipeline_id 调 web-app API 获取。返回节点列表、边列表和 SOURCE 表 schema。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "pipeline_id": {
                "type": "string",
                "description": "Pipeline ID（当 dag_state 未提供时使用）",
            },
            "dag_state": {
                "type": "object",
                "description": "前端传入的 DAG 画布快照 { nodes, edges, pipeline_id?, pipeline_name? }",
                "properties": {
                    "nodes": {"type": "array"},
                    "edges": {"type": "array"},
                    "pipeline_id": {"type": "string"},
                    "pipeline_name": {"type": "string"},
                },
            },
        },
        "required": [],
    },
)
async def read_dag_state(pipeline_id: str = "", dag_state: dict | None = None) -> dict:
    if dag_state and dag_state.get("nodes"):
        nodes = [
            n for n in dag_state["nodes"]
            if not n.get("config", {}).get("is_gold_mirror")
        ]
        edges = dag_state.get("edges", [])
        real_ids = {n["id"] for n in nodes}
        edges = [e for e in edges if e.get("source") in real_ids and e.get("target") in real_ids]

        return {
            "nodes": nodes,
            "edges": edges,
            "pipeline_id": dag_state.get("pipeline_id", pipeline_id),
            "pipeline_name": dag_state.get("pipeline_name", ""),
            "source": "dag_state",
        }

    if not pipeline_id:
        return {"error": "需要提供 pipeline_id 或 dag_state"}

    try:
        raw = await api_get(f"/api/v1/pipelines/{pipeline_id}")
    except ApiError as e:
        return {"error": f"获取 Pipeline 失败: {e}"}

    nested = raw
    for key in ("data", "data", "pipeline"):
        if isinstance(nested, dict) and key in nested:
            nested = nested[key]
    pipeline = nested

    sources_raw = pipeline.get("sources", [])
    steps_raw = pipeline.get("steps", [])
    sinks_raw = pipeline.get("sinks", [])

    nodes = []

    for src in sources_raw:
        nodes.append({
            "id": src.get("id", ""),
            "type": "SOURCE",
            "label": src.get("name", "") or src.get("table", "") or src.get("id", ""),
            "config": {
                "connection_id": src.get("connectionId", src.get("connection_id", "")),
                "table": src.get("table", ""),
                "source_type": src.get("type", ""),
            },
        })

    for step in steps_raw:
        step_id = step.get("step_id", step.get("stepId", step.get("id", "")))
        raw_type = step.get("type", "")
        config = step.get("genericConfig", step.get("generic_config", {}))
        if not config or not isinstance(config, dict):
            config = {}
        sql_fragment = ""
        for cfg_key in ("sql_transform_config", "sqlTransformConfig"):
            cfg_block = step.get(cfg_key, {})
            if isinstance(cfg_block, dict) and cfg_block.get("sql"):
                sql_fragment = cfg_block["sql"]
                config.update({k: v for k, v in cfg_block.items() if k != "sql"})
                break
        if not sql_fragment:
            sql_fragment = config.pop("sql", "") if isinstance(config, dict) else ""
        description = config.pop("description", "") if isinstance(config, dict) else ""
        label = config.pop("label", step.get("name", "")) if isinstance(config, dict) else step.get("name", "")

        nodes.append({
            "id": step_id,
            "type": _strip_step_type_prefix(raw_type),
            "label": label or step_id,
            "config": config if config else {"mode": "default"},
            "sqlFragment": sql_fragment,
            "description": description,
            "inputs": step.get("inputs", []),
        })

    for sink in sinks_raw:
        sink_inputs = sink.get("inputs", [])
        single_input = sink_inputs[0] if sink_inputs else sink.get("input", "")
        nodes.append({
            "id": sink.get("id", ""),
            "type": "SINK",
            "label": sink.get("name", "") or sink.get("id", ""),
            "config": {
                "connection_id": sink.get("connectionId", sink.get("connection_id", "")),
                "target_table": sink.get("targetTable", sink.get("target_table", "")),
                "write_mode": sink.get("writeMode", sink.get("write_mode", "")),
                "input": single_input,
            },
        })

    edges = _rebuild_edges(sources_raw, steps_raw, sinks_raw)

    source_schemas = {}
    for src in sources_raw:
        conn_id = src.get("connectionId", src.get("connection_id", ""))
        table = src.get("table", "")
        if conn_id and table:
            try:
                from backend.agent.api_client import get_project_id
                pid = get_project_id()
                cols_raw = await api_get(
                    f"/api/v1/projects/{pid}/datasources/{conn_id}/metadata/{table}/columns"
                )
                cols = cols_raw if isinstance(cols_raw, list) else cols_raw.get("data", [])
                source_schemas[src.get("id", "")] = {
                    "table": table,
                    "columns": [
                        {
                            "name": c.get("name"),
                            "type": c.get("type"),
                            "nullable": c.get("nullable", True),
                            "primary_key": c.get("primary_key", False),
                            "comment": c.get("comment", ""),
                        }
                        for c in cols
                    ],
                }
            except Exception:
                source_schemas[src.get("id", "")] = {"table": table, "columns": [], "error": "获取表结构失败"}

    return {
        "nodes": nodes,
        "edges": edges,
        "source_schemas": source_schemas,
        "pipeline_id": pipeline_id,
        "pipeline_name": pipeline.get("metadata", {}).get("name", ""),
        "pipeline_status": pipeline.get("metadata", {}).get("status", pipeline.get("status", "")),
        "source": "api",
    }


@tool(
    name="add_dag_node",
    description=(
        "向 DAG 添加新节点。传入新增的 steps 和改动后的完整边列表 edges。\n"
        "每个 step 必须包含 id/type/label/config/sqlFragment/description。config 不能为空。\n"
        "【重要】edges 是改动后 DAG 的全部边（包括原有保留的 + 新增的），前端会整体替换边数组。\n"
        "调用前必须先调 read_dag_state 获取当前 DAG，然后在当前边基础上增删得到新的完整边列表。\n"
        "示例：当前有 A→B，要在中间插入 C，则 edges=[{source:A,target:C},{source:C,target:B}]（去掉旧的 A→B，加上新的两条边）。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "steps": {
                "type": "array",
                "description": "要新增的节点列表",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "description": "节点 ID，格式 {type_lower}-{random6}"},
                        "type": {"type": "string", "description": "节点类型，如 FILTER/JOIN/MAP 等"},
                        "label": {"type": "string", "description": "节点显示名称（中文）"},
                        "config": {"type": "object", "description": "节点配置（不能为空 {}）"},
                        "sqlFragment": {"type": "string", "description": "Flink SQL 片段"},
                        "description": {"type": "string", "description": "中文加工逻辑描述"},
                    },
                    "required": ["id", "type", "label", "config"],
                },
            },
            "edges": {
                "type": "array",
                "description": "改动后的完整边列表（包含所有原有保留边 + 新增边，前端整体替换）",
                "items": {
                    "type": "object",
                    "properties": {
                        "source": {"type": "string"},
                        "target": {"type": "string"},
                    },
                    "required": ["source", "target"],
                },
            },
        },
        "required": ["steps", "edges"],
    },
)
async def add_dag_node(steps: list[dict], edges: list[dict]) -> dict:
    errors = []
    for i, step in enumerate(steps):
        if not step.get("id"):
            errors.append(f"steps[{i}]: 缺少 id")
        if not step.get("type"):
            errors.append(f"steps[{i}]: 缺少 type")
        if not step.get("config"):
            errors.append(f"steps[{i}]: config 不能为空")
        if step.get("type") in (
            "FILTER", "JOIN", "SQL_TRANSFORM", "TRANSFORM", "QUERY",
            "DEDUPLICATE", "GROUP_AGGREGATION", "WINDOW_AGGREGATION", "UNION", "MAP",
        ) and not step.get("sqlFragment"):
            errors.append(f"steps[{i}] ({step.get('type')}): SQL 类节点必须提供 sqlFragment")

    if errors:
        return {"error": "校验失败", "details": errors}

    return {
        "action": "add",
        "steps": steps,
        "edges": edges,
        "dag_update": True,
    }


@tool(
    name="modify_dag_node",
    description=(
        "修改已有 DAG 节点的配置。传入节点 ID 和要修改的字段，返回 action='modify' 的 dag_update 事件。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "node_id": {"type": "string", "description": "要修改的节点 ID"},
            "config": {"type": "object", "description": "新的 config（整体替换）"},
            "sqlFragment": {"type": "string", "description": "新的 SQL 片段"},
            "description": {"type": "string", "description": "新的描述"},
            "label": {"type": "string", "description": "新的显示名称"},
        },
        "required": ["node_id"],
    },
)
async def modify_dag_node(
    node_id: str,
    config: dict | None = None,
    sqlFragment: str | None = None,
    description: str | None = None,
    label: str | None = None,
) -> dict:
    step: dict = {"id": node_id}
    if config is not None:
        step["config"] = config
    if sqlFragment is not None:
        step["sqlFragment"] = sqlFragment
    if description is not None:
        step["description"] = description
    if label is not None:
        step["label"] = label

    if len(step) <= 1:
        return {"error": "至少需要修改一个字段（config/sqlFragment/description/label）"}

    return {
        "action": "modify",
        "steps": [step],
        "dag_update": True,
    }


@tool(
    name="remove_dag_node",
    description=(
        "删除 DAG 节点并自动重连上下游。禁止删除 SOURCE 节点和 is_gold_mirror 虚拟节点。"
        "只需要传入 node_id 和 pipeline_id，工具自动读取当前 DAG 状态来计算重连。"
        "返回 action='remove' 的 dag_update 事件，包含重连后的边。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "node_id": {"type": "string", "description": "要删除的节点 ID"},
            "pipeline_id": {"type": "string", "description": "Pipeline ID（用于读取当前 DAG 状态）"},
        },
        "required": ["node_id", "pipeline_id"],
    },
)
async def remove_dag_node(node_id: str, pipeline_id: str = "") -> dict:
    dag = await read_dag_state(pipeline_id=pipeline_id)
    if dag.get("error"):
        return {"error": f"读取 DAG 失败: {dag['error']}"}

    nodes = dag.get("nodes", [])
    edges = dag.get("edges", [])

    target_node = None
    for n in nodes:
        if n.get("id") == node_id:
            target_node = n
            break

    if not target_node:
        return {"error": f"节点 '{node_id}' 不存在"}
    if target_node.get("type") == "SOURCE":
        return {"error": "禁止删除 SOURCE 节点（数据锚点）"}
    if target_node.get("config", {}).get("is_gold_mirror"):
        return {"error": "禁止删除 gold_mirror 虚拟节点"}

    upstream_ids = [e["source"] for e in edges if e.get("target") == node_id]
    downstream_ids = [e["target"] for e in edges if e.get("source") == node_id]

    remaining_edges = [e for e in edges if e.get("source") != node_id and e.get("target") != node_id]
    new_edges = []
    for up in upstream_ids:
        for down in downstream_ids:
            new_edges.append({"source": up, "target": down})

    return {
        "action": "remove",
        "remove_node_ids": [node_id],
        "edges": remaining_edges + new_edges,
        "dag_update": True,
    }


@tool(
    name="generate_full_dag",
    description=(
        "根据 SOURCE 节点的表 schema 和用户需求，生成完整的 DAG 清洗流程。"
        "由 LLM 推理，返回 action='replace_all' 的完整 steps + edges。"
        "注意：此工具仅构造返回结构，实际推理由 LLM 在 ReAct 循环中完成。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "steps": {
                "type": "array",
                "description": "LLM 生成的完整节点列表（含 SOURCE 之后的所有加工步骤）",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "type": {"type": "string"},
                        "label": {"type": "string"},
                        "config": {"type": "object"},
                        "sqlFragment": {"type": "string"},
                        "description": {"type": "string"},
                    },
                    "required": ["id", "type", "label", "config"],
                },
            },
            "edges": {
                "type": "array",
                "description": "完整的边列表",
                "items": {
                    "type": "object",
                    "properties": {
                        "source": {"type": "string"},
                        "target": {"type": "string"},
                    },
                    "required": ["source", "target"],
                },
            },
            "explanation": {
                "type": "string",
                "description": "对生成的 DAG 的整体说明",
            },
        },
        "required": ["steps", "edges"],
    },
)
async def generate_full_dag(steps: list[dict], edges: list[dict], explanation: str = "") -> dict:
    errors = []
    for i, step in enumerate(steps):
        if not step.get("config"):
            errors.append(f"steps[{i}] ({step.get('type', '?')}): config 不能为空")

    if errors:
        return {"error": "校验失败", "details": errors}

    return {
        "action": "replace_all",
        "steps": steps,
        "edges": edges,
        "explanation": explanation,
        "dag_update": True,
    }


def _node_type_to_step_type(t: str) -> str:
    """FILTER → STEP_TYPE_FILTER"""
    if t.startswith("STEP_TYPE_"):
        return t
    return f"STEP_TYPE_{t}"


def _conditions_to_expression(conditions: list[dict]) -> str:
    """将 [{field, operator, value}] 转为 SQL WHERE 表达式字符串。"""
    parts = []
    for c in conditions:
        field = c.get("field", "")
        op = c.get("operator", "=")
        val = c.get("value", "")
        if field:
            if isinstance(val, str) and not val.isdigit():
                parts.append(f"{field} {op} '{val}'")
            else:
                parts.append(f"{field} {op} {val}")
    return " AND ".join(parts) if parts else ""


def _build_step_proto(node: dict, inputs: list[str]) -> dict:
    """将前端节点格式转换为 web-app PUT API 期望的 step 格式（camelCase，与 zhice 前端一致）。

    web-app normalizeStepForUpdate 要求：
    - FILTER: genericConfig.condition (string) → FilterConfig.expression
    - SQL_TRANSFORM/TRANSFORM: genericConfig.sql (string) → SqlTransformConfig.sql
    - JOIN: genericConfig.join_type/left_key/right_key → JoinConfig
    嵌套数组（如 conditions[]）不能直接放 genericConfig，否则 protobuf Struct 序列化可能失败。
    """
    step: dict = {
        "stepId": node["id"],
        "name": node.get("label", ""),
        "type": _node_type_to_step_type(node.get("type", "TRANSFORM")),
        "inputs": inputs,
    }
    config = node.get("config", {})
    sql = node.get("sqlFragment", "")
    node_type = node.get("type", "")

    if sql or config:
        merged: dict = {}
        if sql:
            merged["sql"] = sql
        label = node.get("label", "")
        if label:
            merged["label"] = label

        if node_type == "FILTER":
            conditions = config.get("conditions", [])
            if conditions:
                merged["condition"] = _conditions_to_expression(conditions)
            elif config.get("condition"):
                merged["condition"] = config["condition"]
            elif sql:
                where_idx = sql.upper().find("WHERE")
                if where_idx >= 0:
                    merged["condition"] = sql[where_idx + 5:].strip()
        elif node_type == "JOIN":
            for k in ("join_type", "left_key", "right_key", "left_table", "right_table"):
                if config.get(k):
                    merged[k] = config[k]
            join_conds = config.get("conditions", [])
            if join_conds and not merged.get("left_key"):
                merged["left_key"] = join_conds[0].get("left", "")
                merged["right_key"] = join_conds[0].get("right", "")
        else:
            for k, v in config.items():
                if k not in merged and isinstance(v, (str, int, float, bool)):
                    merged[k] = v

        step["genericConfig"] = merged
    return step


@tool(
    name="save_dag",
    description=(
        "将当前编辑后的 DAG 保存到 zhice-paas（调用 PUT /api/v1/pipelines/{id}/draft）。"
        "需要传入完整的 dag_state（包含 nodes 和 edges）。保存前会读取原始 pipeline 的 metadata/execution_config/sources/sinks，"
        "只替换 steps 部分。注意：PUBLISHED 状态的 Pipeline 不可编辑，需先调用 unpublish。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "pipeline_id": {
                "type": "string",
                "description": "Pipeline ID",
            },
            "dag_state": {
                "type": "object",
                "description": "当前 DAG 状态（前端传入的完整画布数据）",
                "properties": {
                    "nodes": {"type": "array"},
                    "edges": {"type": "array"},
                },
            },
        },
        "required": ["pipeline_id", "dag_state"],
    },
)
async def save_dag(pipeline_id: str, dag_state: dict) -> dict:
    nodes = dag_state.get("nodes", [])
    edges = dag_state.get("edges", [])

    if not nodes:
        return {"error": "dag_state 为空，没有可保存的内容"}

    try:
        raw = await api_get(f"/api/v1/pipelines/{pipeline_id}")
    except ApiError:
        all_ids = [p.get("metadata", {}).get("id", "") for p in
                   (await api_get("/api/v1/pipelines")).get("data", {}).get("pipelines", [])]
        if not all_ids:
            return {"error": f"Pipeline {pipeline_id} 不存在且无可用 pipeline"}
        pipeline_id = all_ids[0]
        try:
            raw = await api_get(f"/api/v1/pipelines/{pipeline_id}")
        except ApiError as e2:
            return {"error": f"读取 Pipeline 失败: {e2}"}

    # PUBLISHED 状态的 Pipeline 不可编辑
    nested_check = raw
    for key in ("data", "data", "pipeline"):
        if isinstance(nested_check, dict) and key in nested_check:
            nested_check = nested_check[key]
    status = nested_check.get("metadata", {}).get("status", nested_check.get("status", ""))
    if status == "PUBLISHED":
        return {"error": "Pipeline 已发布，不可编辑。如需修改请先调用 unpublish 接口下线。"}

    nested = raw
    for key in ("data", "data", "pipeline"):
        if isinstance(nested, dict) and key in nested:
            nested = nested[key]
    original = nested

    target_map: dict[str, list[str]] = {}
    for e in edges:
        t = e.get("target", "")
        s = e.get("source", "")
        if t and s:
            target_map.setdefault(t, []).append(s)

    new_steps = []
    for node in nodes:
        if node.get("type") in ("SOURCE", "SINK"):
            continue
        inputs = target_map.get(node["id"], [])
        new_steps.append(_build_step_proto(node, inputs))

    new_sinks = []
    for node in nodes:
        if node.get("type") != "SINK":
            continue
        sink_inputs = target_map.get(node["id"], [])
        sink_config = node.get("config", {})
        new_sinks.append({
            "id": node["id"],
            "name": node.get("label", ""),
            "type": sink_config.get("sink_type", original.get("sinks", [{}])[0].get("type", "SINK_TYPE_ICEBERG")),
            "connectionId": sink_config.get("connection_id", ""),
            "inputs": sink_inputs,
            "targetTable": sink_config.get("target_table", ""),
            "writeMode": sink_config.get("write_mode", "OVERWRITE"),
            "primary_keys": [],
            "partition_by": [],
            "options": {},
        })

    if not new_sinks:
        new_sinks = original.get("sinks", [])
        for sink in new_sinks:
            sink_id = sink.get("id", "")
            if sink_id in target_map:
                sink["inputs"] = target_map[sink_id]

    metadata = original.get("metadata", {})
    metadata["id"] = pipeline_id

    pipeline_def = {
        "metadata": metadata,
        "execution_config": original.get("execution_config", original.get("executionConfig", {})),
        "sources": original.get("sources", []),
        "steps": new_steps,
        "sinks": new_sinks,
    }

    import json as _json
    logger.info(f"[save_dag] target_map={_json.dumps(target_map, ensure_ascii=False)}")
    for s in new_steps:
        logger.info(f"[save_dag] step={s.get('stepId')} inputs={s.get('inputs')}")
    for s in new_sinks:
        logger.info(f"[save_dag] sink={s.get('id')} inputs={s.get('inputs')}")

    try:
        await api_put(
            f"/api/v1/pipelines/{pipeline_id}/draft",
            json_data={"pipeline": pipeline_def},
        )
        return {
            "success": True,
            "message": f"Pipeline 已保存到 zhice-paas（{len(new_steps)} 个 step）",
            "pipeline_id": pipeline_id,
        }
    except ApiError as e:
        return {"error": f"保存失败: {e}"}
    except Exception as e:
        return {"error": f"保存异常: {e}"}


@tool(
    name="publish_pipeline",
    description=(
        "发布 Pipeline（DRAFT → PUBLISHED）。只有 DRAFT 状态才能发布。"
        "发布后 Pipeline 变为只读，可运行、可 Fork，但不可编辑 DAG。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "pipeline_id": {
                "type": "string",
                "description": "Pipeline ID",
            },
        },
        "required": ["pipeline_id"],
    },
)
async def publish_pipeline(pipeline_id: str) -> dict:
    try:
        data = await api_post(f"/api/v1/pipelines/{pipeline_id}/publish")
        return {
            "success": True,
            "message": f"Pipeline {pipeline_id} 已发布",
            "data": data,
        }
    except ApiError as e:
        return {"error": f"发布失败: {e}"}


@tool(
    name="unpublish_pipeline",
    description=(
        "撤回发布（PUBLISHED → DRAFT）。撤回后 Pipeline 恢复可编辑状态，但不可运行。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "pipeline_id": {
                "type": "string",
                "description": "Pipeline ID",
            },
        },
        "required": ["pipeline_id"],
    },
)
async def unpublish_pipeline(pipeline_id: str) -> dict:
    try:
        data = await api_post(f"/api/v1/pipelines/{pipeline_id}/unpublish")
        return {
            "success": True,
            "message": f"Pipeline {pipeline_id} 已撤回为草稿",
            "data": data,
        }
    except ApiError as e:
        return {"error": f"撤回失败: {e}"}


@tool(
    name="fork_pipeline",
    description=(
        "Fork 一个 Pipeline 的副本。创建一个独立的 DRAFT 副本，包含完整的 DAG 定义和绑定记录。"
        "Fork 后的副本可独立编辑和发布，不影响原 Pipeline。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "pipeline_id": {
                "type": "string",
                "description": "要 Fork 的源 Pipeline ID",
            },
            "new_name": {
                "type": "string",
                "description": "副本名称（同项目内不可重名）",
            },
        },
        "required": ["pipeline_id", "new_name"],
    },
)
async def fork_pipeline(pipeline_id: str, new_name: str) -> dict:
    try:
        data = await api_post(
            f"/api/v1/pipelines/{pipeline_id}/fork",
            json_data={"name": new_name},
        )
        return {
            "success": True,
            "message": f"Fork 成功: {new_name}",
            "data": data,
        }
    except ApiError as e:
        return {"error": f"Fork 失败: {e}"}
