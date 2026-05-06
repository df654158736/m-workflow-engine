"""Web UI Server — 可视化工作流 DAG + 实时执行状态。

启动方式:
    python -m backend.server           # 按 config.yaml 配置启动
    STANDALONE=1 python -m backend.server  # 强制单机模式

浏览器打开: http://localhost:8686
"""

from __future__ import annotations

import asyncio
import os
import random
import time
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Any

import structlog
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.responses import StreamingResponse

from backend.dsl_parser import parse_file, topological_sort, validate
from backend.routing import ALL_QUEUES, get_queue_for_node

# --- Load Config ---
import yaml as _yaml

CONFIG_PATH = Path(__file__).parent.parent.parent / "config.yaml"


def _load_config() -> dict:
    """Load config from config.yaml, with env vars taking priority."""
    cfg = {}
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            cfg = _yaml.safe_load(f) or {}
    return cfg


_cfg = _load_config()
_cfg_temporal = _cfg.get("temporal", {})
_cfg_llm = _cfg.get("llm", {})
_cfg_server = _cfg.get("server", {})

# Env vars override config file
STANDALONE_MODE = (
    os.environ.get("STANDALONE", "").strip() in ("1", "true", "yes")
    or _cfg.get("mode") == "standalone"
)
# If env STANDALONE is explicitly "0"/"false"/"no", force full mode even if config says standalone
if os.environ.get("STANDALONE", "").strip() in ("0", "false", "no"):
    STANDALONE_MODE = False

QWEN_API_KEY = os.environ.get("QWEN_API_KEY") or _cfg_llm.get("api_key", "")
QWEN_BASE_URL = os.environ.get("QWEN_BASE_URL") or _cfg_llm.get("base_url", "https://dashscope.aliyuncs.com/compatible-mode/v1")
QWEN_MODEL = os.environ.get("QWEN_MODEL") or _cfg_llm.get("model", "qwen-plus")
TEMPORAL_ADDRESS = os.environ.get("TEMPORAL_ADDRESS") or _cfg_temporal.get("address", "192.168.2.60:7233")
SERVER_HOST = _cfg_server.get("host", "0.0.0.0")
SERVER_PORT = int(os.environ.get("PORT", _cfg_server.get("port", 8686)))

def _save_config():
    """Persist current runtime config back to config.yaml."""
    data = {
        "mode": "standalone" if STANDALONE_MODE else "full",
        "temporal": {"address": TEMPORAL_ADDRESS, "namespace": "default"},
        "llm": {"api_key": QWEN_API_KEY, "base_url": QWEN_BASE_URL, "model": QWEN_MODEL},
        "server": {"host": SERVER_HOST, "port": SERVER_PORT},
    }
    with open(CONFIG_PATH, "w") as f:
        _yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


# Always import — needed when switching from standalone to full at runtime
from temporalio.client import Client
from temporalio.worker import Worker
from openai import AsyncOpenAI
from backend.temporal.activities import execute_node
from backend.temporal.workflow import WorkflowEngineWorkflow

logger = structlog.get_logger()

WORKFLOWS_DIR = Path(__file__).parent.parent.parent / "workflows"

app = FastAPI(title="Workflow Engine Demo UI")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global state
_client: Any = None
_workers_started = False
_execution_logs: dict[str, list[dict]] = {}
_standalone_runs: dict[str, dict] = {}


async def get_client():
    global _client
    if STANDALONE_MODE:
        return None
    if _client is None:
        _client = await Client.connect(TEMPORAL_ADDRESS)
    return _client


async def ensure_workers():
    """Start workers in background (once). Skip in standalone mode."""
    global _workers_started
    if STANDALONE_MODE or _workers_started:
        return
    _workers_started = True

    client = await get_client()
    for queue in ALL_QUEUES:
        if queue == "plane-e-default":
            w = Worker(
                client,
                task_queue=queue,
                workflows=[WorkflowEngineWorkflow],
                activities=[execute_node],
            )
        else:
            w = Worker(
                client,
                task_queue=queue,
                activities=[execute_node],
            )
        asyncio.create_task(w.run())

    logger.info("Workers started for all queues", queues=ALL_QUEUES)


@app.on_event("startup")
async def startup():
    if STANDALONE_MODE:
        logger.info("Running in STANDALONE mode (no Temporal, no LLM)")
    else:
        await ensure_workers()


# --- API Routes ---

_llm_client: Any = None
if not STANDALONE_MODE:
    _llm_client = AsyncOpenAI(api_key=QWEN_API_KEY, base_url=QWEN_BASE_URL)

PLANNER_SYSTEM_PROMPT = """你是一个工作流规划 Agent。用户会给你一个业务需求，你需要将其分解为一个 DAG 工作流。

可用的节点类型：
- LLM: 调用大语言模型做分析/推理/生成。config 需要 prompt 和 model(固定用 qwen-plus)。
- Tool: 执行系统操作（写入数据库/调用外部API/发通知等）。config 需要 tool_id 和 args。
- FlinkSQL: 执行数据查询/ETL。config 需要 sql 和 sink。
- Function: 调用自定义函数做数据处理。config 需要 function_id。
- Condition: 条件判断分支。config 需要 expression、true_branch、false_branch。
- Approval: 人工审批节点，工作流会暂停等人决策。config 需要 title、description、approvers。

节点间数据传递用 ${node_id.outputs.field} 语法。
条件执行用 when 字段（Python 表达式）。

请输出严格的 YAML 格式，包含 workflow_id、name、nodes 和 edges。
每个 node 必须有 id、type、config。
edges 定义 from 和 to。

重要：只输出 YAML 内容，不要输出其他文字。不要用 markdown 代码块包裹。"""


STANDALONE_PLAN_TEMPLATES: dict[str, dict[str, str]] = {
    "supplier_risk": {
        "label": "评估供应商风险 → 高风险人工审批",
        "yaml": """workflow_id: wf-plan-supplier-risk-{uid}
name: "供应商风险评估与人工审批"

nodes:
  - id: fetch_supplier_data
    type: FlinkSQL
    config:
      sql: "SELECT * FROM supplier_profiles WHERE supplier_id = 'A'"
      sink: bronze.supplier_risk_input
      description: "拉取供应商历史数据"

  - id: ai_risk_assessment
    type: LLM
    config:
      prompt: "根据供应商的交付记录、财务状况和市场口碑，评估其综合风险等级（低/中/高）。给出评分和理由。"
      model: qwen-plus
      description: "AI 风险评估"
    inputs:
      data: "${{fetch_supplier_data.outputs.dataset_ref}}"

  - id: risk_level_check
    type: Condition
    config:
      expression: "True"
      true_branch: "high_risk"
      false_branch: "low_risk"
      description: "判断风险是否过高"
    inputs:
      assessment: "${{ai_risk_assessment.outputs.text}}"

  - id: human_review
    type: Approval
    config:
      title: "高风险供应商审批"
      description: "AI 评估该供应商为高风险，请决定是否拉黑"
      approvers: ["procurement_manager"]
    when: "risk_level_check.get('branch') == 'high_risk'"

  - id: execute_decision
    type: Tool
    config:
      tool_id: act-update-supplier-status
      args:
        action: "blacklist_or_monitor"
      description: "执行审批决策"
    inputs:
      decision: "${{human_review.outputs.decision}}"
    when: "risk_level_check.get('branch') == 'high_risk'"

edges:
  - from: fetch_supplier_data
    to: ai_risk_assessment
  - from: ai_risk_assessment
    to: risk_level_check
  - from: risk_level_check
    to: human_review
  - from: human_review
    to: execute_decision
""",
    },
    "data_anomaly": {
        "label": "数据异常检测 → AI 定位根因 → 自动修复",
        "yaml": """workflow_id: wf-plan-data-anomaly-{uid}
name: "数据异常检测与自动修复"

nodes:
  - id: detect_anomaly
    type: FlinkSQL
    config:
      sql: "SELECT * FROM metrics WHERE value > threshold ORDER BY ts DESC LIMIT 100"
      sink: bronze.anomaly_batch
      description: "检测异常数据点"

  - id: ai_root_cause
    type: LLM
    config:
      prompt: "分析以下异常数据的根因，判断是数据源问题、ETL 错误还是业务波动。给出修复建议。"
      model: qwen-plus
      description: "AI 根因分析"
    inputs:
      anomalies: "${{detect_anomaly.outputs.dataset_ref}}"

  - id: severity_check
    type: Condition
    config:
      expression: "True"
      true_branch: "auto_fixable"
      false_branch: "need_human"
      description: "判断是否可自动修复"
    inputs:
      analysis: "${{ai_root_cause.outputs.text}}"

  - id: auto_fix
    type: Tool
    config:
      tool_id: act-data-repair
      args:
        mode: "auto"
      description: "自动修复数据"
    inputs:
      plan: "${{ai_root_cause.outputs.text}}"
    when: "severity_check.get('branch') == 'auto_fixable'"

  - id: notify_team
    type: Tool
    config:
      tool_id: act-send-notification
      args:
        channel: "data-quality-alerts"
      description: "通知团队"
    inputs:
      summary: "${{ai_root_cause.outputs.text}}"

edges:
  - from: detect_anomaly
    to: ai_root_cause
  - from: ai_root_cause
    to: severity_check
  - from: severity_check
    to: auto_fix
  - from: severity_check
    to: notify_team
""",
    },
    "report_generation": {
        "label": "多源数据汇总 → AI 生成报告 → 邮件发送",
        "yaml": """workflow_id: wf-plan-report-{uid}
name: "智能报告生成与分发"

nodes:
  - id: gather_sales
    type: FlinkSQL
    config:
      sql: "SELECT region, SUM(amount) as total FROM sales GROUP BY region"
      sink: bronze.sales_summary
      description: "汇总销售数据"

  - id: gather_inventory
    type: FlinkSQL
    config:
      sql: "SELECT warehouse, COUNT(*) as stock FROM inventory GROUP BY warehouse"
      sink: bronze.inventory_summary
      description: "汇总库存数据"

  - id: ai_write_report
    type: LLM
    config:
      prompt: "根据销售和库存数据，撰写一份管理层周报，包含趋势分析和建议。"
      model: qwen-plus
      description: "AI 撰写报告"
    inputs:
      sales: "${{gather_sales.outputs.dataset_ref}}"
      inventory: "${{gather_inventory.outputs.dataset_ref}}"

  - id: send_email
    type: Tool
    config:
      tool_id: act-send-email
      args:
        recipients: ["management@company.com"]
        subject: "本周经营报告"
      description: "邮件发送报告"
    inputs:
      content: "${{ai_write_report.outputs.text}}"

edges:
  - from: gather_sales
    to: ai_write_report
  - from: gather_inventory
    to: ai_write_report
  - from: ai_write_report
    to: send_email
""",
    },
    "contract_review": {
        "label": "合同智能审查 → 风险条款标注 → 法务审批",
        "yaml": """workflow_id: wf-plan-contract-{uid}
name: "合同智能审查流程"

nodes:
  - id: extract_clauses
    type: Function
    config:
      function_id: fn-extract-contract-clauses
      description: "提取合同条款"

  - id: ai_review
    type: LLM
    config:
      prompt: "审查以下合同条款，标注风险点（违约金比例过高、排他条款、知识产权归属不清等）。输出风险等级。"
      model: qwen-plus
      description: "AI 审查风险条款"
    inputs:
      clauses: "${{extract_clauses.outputs.result}}"

  - id: has_risk
    type: Condition
    config:
      expression: "True"
      true_branch: "risky"
      false_branch: "safe"
      description: "是否有风险条款"
    inputs:
      review: "${{ai_review.outputs.text}}"

  - id: legal_approval
    type: Approval
    config:
      title: "合同风险条款审批"
      description: "AI 发现风险条款，请法务确认是否继续签署"
      approvers: ["legal_dept"]
    when: "has_risk.get('branch') == 'risky'"

  - id: archive_contract
    type: Tool
    config:
      tool_id: act-archive-document
      args:
        category: "contract"
      description: "归档合同"

edges:
  - from: extract_clauses
    to: ai_review
  - from: ai_review
    to: has_risk
  - from: has_risk
    to: legal_approval
  - from: legal_approval
    to: archive_contract
  - from: has_risk
    to: archive_contract
""",
    },
}


@app.get("/api/plan-templates")
async def list_plan_templates():
    """List available plan templates (for standalone mode dropdown)."""
    return [{"id": k, "label": v["label"]} for k, v in STANDALONE_PLAN_TEMPLATES.items()]


@app.post("/api/plan-workflow")
async def plan_workflow(payload: dict[str, Any]):
    """Use LLM to plan a workflow from natural language input."""
    user_input = payload.get("input", "")
    template_id = payload.get("template_id", "")

    # Standalone mode: use template
    if STANDALONE_MODE:
        if not template_id:
            raise HTTPException(400, "template_id is required in standalone mode")
        tpl = STANDALONE_PLAN_TEMPLATES.get(template_id)
        if not tpl:
            raise HTTPException(400, f"Unknown template: {template_id}")
        await asyncio.sleep(0.5)
        uid = uuid.uuid4().hex[:6]
        yaml_text = tpl["yaml"].format(uid=uid)
    else:
        if not user_input:
            raise HTTPException(400, "input is required")
        response = await _llm_client.chat.completions.create(
            model=QWEN_MODEL,
            messages=[
                {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
                {"role": "user", "content": user_input},
            ],
            temperature=0.3,
            max_tokens=2048,
        )
        yaml_text = response.choices[0].message.content or ""
    # Clean up: remove markdown code fences if present
    yaml_text = yaml_text.strip()
    if yaml_text.startswith("```"):
        lines = yaml_text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        yaml_text = "\n".join(lines)

    # Try to parse it
    tokens_used = 0
    if not STANDALONE_MODE and response.usage:
        tokens_used = response.usage.total_tokens

    import yaml as _yaml
    try:
        parsed = _yaml.safe_load(yaml_text)
    except Exception as e:
        return {
            "success": False,
            "error": f"YAML 解析失败: {str(e)}",
            "raw_yaml": yaml_text,
            "tokens_used": tokens_used,
        }

    if not parsed or "nodes" not in parsed:
        return {
            "success": False,
            "error": "LLM 返回的 YAML 缺少 nodes 定义",
            "raw_yaml": yaml_text,
            "tokens_used": tokens_used,
        }

    # Save to temp file and parse with our DSL parser
    import tempfile
    tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, dir=str(WORKFLOWS_DIR))
    tmp.write(yaml_text)
    tmp.close()

    try:
        defn = parse_file(tmp.name)
        errors = validate(defn)
        order = topological_sort(defn)

        nodes = []
        for i, node_id in enumerate(order):
            node = next(n for n in defn.nodes if n.id == node_id)
            queue = get_queue_for_node(node.type)
            nodes.append({
                "id": node.id,
                "type": node.type.value,
                "queue": queue,
                "order": i,
                "config": node.config,
                "inputs": node.inputs,
                "when": node.when,
            })
        edges = [{"from": e.from_node, "to": e.to_node} for e in defn.edges]

        # Keep the file for execution
        generated_filename = f"_generated_{uuid.uuid4().hex[:6]}.yaml"
        final_path = WORKFLOWS_DIR / generated_filename
        os.rename(tmp.name, str(final_path))

        return {
            "success": True,
            "raw_yaml": yaml_text,
            "filename": generated_filename,
            "workflow_id": defn.id,
            "name": defn.name,
            "nodes": nodes,
            "edges": edges,
            "execution_order": order,
            "errors": errors,
            "tokens_used": tokens_used,
        }
    except Exception as e:
        os.unlink(tmp.name)
        return {
            "success": False,
            "error": f"DSL 解析失败: {str(e)}",
            "raw_yaml": yaml_text,
            "tokens_used": tokens_used,
        }


@app.get("/api/workflows")
async def list_workflows():
    """List available workflow YAML files."""
    files = sorted(WORKFLOWS_DIR.glob("*.yaml"))
    result = []
    for f in files:
        defn = parse_file(str(f))
        result.append({
            "file": f.name,
            "id": defn.id,
            "name": defn.name,
            "node_count": len(defn.nodes),
        })
    return result


@app.get("/api/workflows/{filename}")
async def get_workflow(filename: str):
    """Get workflow definition with DAG info."""
    path = WORKFLOWS_DIR / filename
    if not path.exists():
        raise HTTPException(404, f"Workflow not found: {filename}")

    defn = parse_file(str(path))
    errors = validate(defn)
    order = topological_sort(defn)

    nodes = []
    for i, node_id in enumerate(order):
        node = next(n for n in defn.nodes if n.id == node_id)
        queue = get_queue_for_node(node.type)
        nodes.append({
            "id": node.id,
            "type": node.type.value,
            "queue": queue,
            "order": i,
            "config": node.config,
            "inputs": node.inputs,
            "when": node.when,
        })

    edges = [{"from": e.from_node, "to": e.to_node, "condition": e.condition} for e in defn.edges]

    return {
        "id": defn.id,
        "name": defn.name,
        "nodes": nodes,
        "edges": edges,
        "errors": errors,
        "execution_order": order,
    }


@app.post("/api/workflows/{filename}/run")
async def run_workflow(filename: str):
    """Execute a workflow and return run ID."""
    path = WORKFLOWS_DIR / filename
    if not path.exists():
        raise HTTPException(404, f"Workflow not found: {filename}")

    defn = parse_file(str(path))
    errors = validate(defn)
    if errors:
        raise HTTPException(400, f"Validation errors: {errors}")

    run_id = f"run-{uuid.uuid4().hex[:8]}"

    if STANDALONE_MODE:
        # Execute locally without Temporal
        asyncio.create_task(_standalone_execute(run_id, defn))
        return {"run_id": run_id, "temporal_workflow_id": run_id}

    client = await get_client()

    definition_dict = {
        "id": defn.id,
        "name": defn.name,
        "nodes": [
            {
                "id": n.id,
                "type": n.type.value,
                "config": n.config,
                "inputs": n.inputs,
                "when": n.when,
                "on_error": n.on_error.value,
            }
            for n in defn.nodes
        ],
        "edges": [
            {"from_node": e.from_node, "to_node": e.to_node, "condition": e.condition}
            for e in defn.edges
        ],
    }

    handle = await client.start_workflow(
        WorkflowEngineWorkflow.run,
        definition_dict,
        id=run_id,
        task_queue="plane-e-default",
    )

    return {"run_id": run_id, "temporal_workflow_id": handle.id}


async def _standalone_execute(run_id: str, defn):
    """Execute workflow locally (standalone mode) — simulates all node types."""
    from backend.models import NodeType
    order = topological_sort(defn)
    node_map = {n.id: n for n in defn.nodes}
    results: dict[str, dict] = {}

    _standalone_runs[run_id] = {"status": "RUNNING", "result": None}

    for node_id in order:
        node = node_map[node_id]

        # Evaluate when clause
        if node.when:
            ctx = {nid: r.get("outputs", {}) for nid, r in results.items()}
            try:
                if not eval(node.when, {"__builtins__": {}}, ctx):
                    results[node_id] = {"node_id": node_id, "status": "SKIPPED", "outputs": {}, "duration_ms": 0, "error": ""}
                    continue
            except Exception:
                pass

        # Simulate execution per type
        start = time.time()
        await asyncio.sleep(random.uniform(0.3, 1.0))

        if node.type == NodeType.LLM:
            prompt = node.config.get("prompt", "")
            results[node_id] = {
                "node_id": node_id, "status": "COMPLETED",
                "duration_ms": int((time.time() - start) * 1000),
                "error": "",
                "outputs": {
                    "text": f"[模拟LLM] 针对「{prompt[:30]}」的分析结果：建议执行后续操作，风险等级中等。",
                    "model": "standalone-mock",
                    "tokens_used": random.randint(80, 200),
                    "prompt": prompt,
                    "duration_ms": int((time.time() - start) * 1000),
                },
            }
        elif node.type == NodeType.APPROVAL:
            # Auto-approve in standalone
            results[node_id] = {
                "node_id": node_id, "status": "COMPLETED",
                "duration_ms": 0, "error": "",
                "outputs": {"decision": "APPROVED", "approver": "standalone_auto", "comment": "单机模式自动通过"},
            }
        elif node.type == NodeType.CONDITION:
            expr = node.config.get("expression", "True")
            try:
                ctx = {}
                for nid, r in results.items():
                    ctx.update(r.get("outputs", {}))
                result_val = eval(expr, {"__builtins__": {}, "str": str}, ctx)
            except Exception:
                result_val = True
            branch = node.config.get("true_branch", "yes") if result_val else node.config.get("false_branch", "no")
            results[node_id] = {
                "node_id": node_id, "status": "COMPLETED",
                "duration_ms": int((time.time() - start) * 1000),
                "error": "",
                "outputs": {"result": result_val, "branch": branch},
            }
        elif node.type == NodeType.TOOL:
            results[node_id] = {
                "node_id": node_id, "status": "COMPLETED",
                "duration_ms": int((time.time() - start) * 1000),
                "error": "",
                "outputs": {
                    "tool_id": node.config.get("tool_id", "unknown"),
                    "result": {"status": "success", "affected_objects": random.randint(1, 5)},
                    "execution_id": f"exec-{random.randint(1000,9999)}",
                },
            }
        elif node.type == NodeType.FLINK_SQL:
            results[node_id] = {
                "node_id": node_id, "status": "COMPLETED",
                "duration_ms": int((time.time() - start) * 1000),
                "error": "",
                "outputs": {
                    "dataset_ref": f"ds-{uuid.uuid4().hex[:6]}",
                    "rows_affected": random.randint(10, 500),
                },
            }
        else:  # Function
            results[node_id] = {
                "node_id": node_id, "status": "COMPLETED",
                "duration_ms": int((time.time() - start) * 1000),
                "error": "",
                "outputs": {
                    "function_id": node.config.get("function_id", "unknown"),
                    "result": {"processed": True, "score": round(random.uniform(0.5, 0.99), 3)},
                },
            }

    _standalone_runs[run_id] = {"status": "COMPLETED", "result": results}


@app.get("/api/runs/{run_id}")
async def get_run_status(run_id: str):
    """Get workflow run status and results."""
    # Standalone mode: check local store
    if STANDALONE_MODE:
        run = _standalone_runs.get(run_id)
        if not run:
            raise HTTPException(404, f"Run not found: {run_id}")
        return {
            "run_id": run_id,
            "status": run["status"],
            "start_time": None,
            "close_time": None,
            "result": run["result"],
        }

    client = await get_client()
    try:
        handle = client.get_workflow_handle(run_id)
        desc = await handle.describe()

        status = str(desc.status.name) if desc.status else "UNKNOWN"
        result = None

        if status == "COMPLETED":
            result = await handle.result()

        return {
            "run_id": run_id,
            "status": status,
            "start_time": str(desc.start_time) if desc.start_time else None,
            "close_time": str(desc.close_time) if desc.close_time else None,
            "result": result,
        }
    except Exception as e:
        raise HTTPException(404, f"Run not found: {e}")


@app.get("/api/runs/{run_id}/approvals")
async def get_pending_approvals(run_id: str):
    """Get pending approval tasks for a running workflow."""
    if STANDALONE_MODE:
        return {"run_id": run_id, "pending_approvals": {}, "decisions": {}}

    client = await get_client()
    try:
        handle = client.get_workflow_handle(run_id)
        state = await handle.query("get_state")
        return {
            "run_id": run_id,
            "pending_approvals": state.get("pending_approvals", {}),
            "decisions": state.get("decisions", {}),
        }
    except Exception as e:
        return {"run_id": run_id, "pending_approvals": {}, "error": str(e)}


@app.get("/api/config")
async def get_config():
    """Return current server mode configuration."""
    masked_key = ""
    if QWEN_API_KEY:
        masked_key = QWEN_API_KEY[:6] + "****" + QWEN_API_KEY[-4:]
    return {
        "standalone": STANDALONE_MODE,
        "temporal": not STANDALONE_MODE,
        "llm": not STANDALONE_MODE,
        "temporal_address": TEMPORAL_ADDRESS,
        "llm_model": QWEN_MODEL,
        "qwen_base_url": QWEN_BASE_URL,
        "qwen_api_key_masked": masked_key,
    }


@app.post("/api/config")
async def update_config(payload: dict[str, Any]):
    """Switch between standalone and full mode at runtime."""
    global STANDALONE_MODE, TEMPORAL_ADDRESS, QWEN_API_KEY, QWEN_BASE_URL, QWEN_MODEL
    global _client, _llm_client, _workers_started

    mode = payload.get("mode")  # "standalone" or "full"
    if mode not in ("standalone", "full"):
        raise HTTPException(400, "mode must be 'standalone' or 'full'")

    if mode == "standalone":
        STANDALONE_MODE = True
        _save_config()
        logger.info("Switched to STANDALONE mode")
        return {"success": True, "standalone": True}

    # --- Switch to full mode: validate connections ---
    temporal_addr = payload.get("temporal_address", "").strip()
    api_key = payload.get("qwen_api_key", "").strip()
    base_url = payload.get("qwen_base_url", "").strip()
    model = payload.get("qwen_model", "").strip()

    errors = []

    # Test Temporal connection
    if temporal_addr:
        try:
            test_client = await Client.connect(temporal_addr)
            _client = test_client
            TEMPORAL_ADDRESS = temporal_addr
        except Exception as e:
            errors.append(f"Temporal 连接失败 ({temporal_addr}): {e}")
    else:
        errors.append("请填写 Temporal 地址")

    # Test LLM connection (use existing key if not provided)
    effective_key = api_key or QWEN_API_KEY
    effective_url = base_url or QWEN_BASE_URL
    effective_model = model or QWEN_MODEL
    if effective_key:
        test_llm = AsyncOpenAI(api_key=effective_key, base_url=effective_url)
        try:
            await test_llm.chat.completions.create(
                model=effective_model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=5,
            )
            _llm_client = test_llm
            QWEN_API_KEY = effective_key
            QWEN_BASE_URL = effective_url
            QWEN_MODEL = effective_model
        except Exception as e:
            errors.append(f"LLM 连接失败: {e}")
    else:
        errors.append("请填写 LLM API Key")

    if errors:
        return {"success": False, "errors": errors}

    STANDALONE_MODE = False
    _workers_started = False
    await ensure_workers()
    _save_config()
    logger.info("Switched to FULL mode", temporal=TEMPORAL_ADDRESS, model=QWEN_MODEL)
    return {"success": True, "standalone": False}


@app.post("/api/runs/{run_id}/approve")
async def submit_approval(run_id: str, payload: dict[str, Any]):
    """Submit approval/rejection decision for a pending approval node."""
    if STANDALONE_MODE:
        return {"run_id": run_id, "node_id": payload.get("node_id"), "decision": payload.get("decision"), "status": "standalone_auto"}

    client = await get_client()
    try:
        handle = client.get_workflow_handle(run_id)
        await handle.signal("approval_signal", payload)
        return {
            "run_id": run_id,
            "node_id": payload.get("node_id"),
            "decision": payload.get("decision"),
            "status": "signal_sent",
        }
    except Exception as e:
        raise HTTPException(400, f"Failed to send approval signal: {e}")


# --- Fault Recovery Demo (SSE) ---

# Use a dedicated queue for fault demo to avoid conflicts with main workers
FAULT_DEMO_QUEUE = "fault-demo-queue"


@app.get("/api/fault-recovery-demo")
async def fault_recovery_demo():
    """Run fault recovery demo with real-time SSE events."""

    if STANDALONE_MODE:
        return await _standalone_fault_demo()

    async def event_stream():
        import json as _json

        def sse(event: str, data: dict):
            return f"event: {event}\ndata: {_json.dumps(data, ensure_ascii=False)}\n\n"

        client = await get_client()

        # Step 1: Start a dedicated worker on isolated queue
        yield sse("step", {"phase": "start_workers", "msg": "启动 Worker（故障演示专用队列）..."})
        demo_worker = Worker(
            client, task_queue=FAULT_DEMO_QUEUE,
            workflows=[WorkflowEngineWorkflow], activities=[execute_node],
        )
        demo_task = asyncio.create_task(demo_worker.run())
        await asyncio.sleep(1)
        yield sse("step", {"phase": "workers_ready", "msg": "✓ Worker 就绪，队列: fault-demo-queue"})

        # Step 2: Start workflow on the demo queue
        defn = parse_file(str(WORKFLOWS_DIR / "fault_recovery_demo.yaml"))
        definition_dict = {
            "id": defn.id, "name": defn.name,
            "override_queue": FAULT_DEMO_QUEUE,
            "nodes": [{"id": n.id, "type": n.type.value, "config": n.config,
                       "inputs": n.inputs, "when": n.when, "on_error": "RETRY"} for n in defn.nodes],
            "edges": [{"from_node": e.from_node, "to_node": e.to_node, "condition": e.condition} for e in defn.edges],
        }
        run_id = f"run-fault-{uuid.uuid4().hex[:6]}"

        # We override the workflow to use our demo queue for all activities
        handle = await client.start_workflow(
            WorkflowEngineWorkflow.run, definition_dict,
            id=run_id, task_queue=FAULT_DEMO_QUEUE,
        )
        yield sse("step", {"phase": "workflow_started", "msg": f"✓ Workflow 已提交: {run_id}", "run_id": run_id})

        # Step 3: Wait for step1 + step2 to start
        yield sse("step", {"phase": "executing", "msg": "step1_prepare 执行中...", "node": "step1_prepare"})
        await asyncio.sleep(3)
        yield sse("step", {"phase": "step1_done", "msg": "✓ step1_prepare 完成，step2_slow_llm 开始调用 LLM...", "node": "step2_slow_llm"})
        await asyncio.sleep(2)

        # Step 4: Kill the worker!
        yield sse("step", {"phase": "crash", "msg": "💥 模拟故障：杀掉 Worker！（LLM 请求被中断）"})
        demo_task.cancel()
        try:
            await demo_task
        except (asyncio.CancelledError, Exception):
            pass
        yield sse("step", {"phase": "workers_dead", "msg": "✓ Worker 已停止。进程宕机。\n  但 Temporal Server 仍保持 workflow 状态（RUNNING）。"})

        # Step 5: Downtime
        yield sse("step", {"phase": "downtime_start", "msg": "⏳ 宕机中...Temporal Server 在等待 Worker 重连"})
        for i in range(6, 0, -1):
            await asyncio.sleep(1)
            yield sse("countdown", {"remaining": i, "msg": f"宕机中... {i}s"})

        # Step 6: Restart worker
        yield sse("step", {"phase": "restart", "msg": "🔄 重新启动 Worker！"})
        demo_worker2 = Worker(
            client, task_queue=FAULT_DEMO_QUEUE,
            workflows=[WorkflowEngineWorkflow], activities=[execute_node],
        )
        demo_task2 = asyncio.create_task(demo_worker2.run())
        await asyncio.sleep(1)
        yield sse("step", {"phase": "workers_restarted", "msg": "✓ Worker 重新上线。Temporal 自动将未完成任务重新派发..."})
        yield sse("step", {"phase": "recovering", "msg": "Temporal 重试 step2_slow_llm（自动调度第2次尝试）...", "node": "step2_slow_llm"})

        # Wait for workflow to complete
        try:
            result = await asyncio.wait_for(handle.result(), timeout=60)
            yield sse("step", {"phase": "step2_done", "msg": "✓ step2_slow_llm 重试成功！LLM 返回结果", "node": "step2_slow_llm"})
            yield sse("step", {"phase": "step3_done", "msg": "✓ step3_save 执行完成", "node": "step3_save"})
            yield sse("complete", {"msg": "✅ Workflow 完成！故障恢复成功！", "result": result, "run_id": run_id})
        except asyncio.TimeoutError:
            yield sse("error", {"msg": "超时：workflow 未在60s内完成"})
        except Exception as e:
            yield sse("error", {"msg": f"错误: {str(e)}"})

        # Cleanup
        demo_task2.cancel()
        try:
            await demo_task2
        except (asyncio.CancelledError, Exception):
            pass

    return StreamingResponse(event_stream(), media_type="text/event-stream")


async def _standalone_fault_demo():
    """Standalone version of fault recovery demo — simulates the flow without Temporal."""
    import json as _json

    async def event_stream():
        def sse(event: str, data: dict):
            return f"event: {event}\ndata: {_json.dumps(data, ensure_ascii=False)}\n\n"

        yield sse("step", {"phase": "start_workers", "msg": "启动 Worker（模拟模式）..."})
        await asyncio.sleep(1)
        yield sse("step", {"phase": "workers_ready", "msg": "✓ Worker 就绪（单机模拟）"})

        run_id = f"run-fault-mock-{uuid.uuid4().hex[:4]}"
        yield sse("step", {"phase": "workflow_started", "msg": f"✓ Workflow 已提交: {run_id}", "run_id": run_id})

        yield sse("step", {"phase": "executing", "msg": "step1_prepare 执行中...", "node": "step1_prepare"})
        await asyncio.sleep(2)
        yield sse("step", {"phase": "step1_done", "msg": "✓ step1_prepare 完成，step2_slow_llm 开始...", "node": "step2_slow_llm"})
        await asyncio.sleep(1)

        yield sse("step", {"phase": "crash", "msg": "💥 模拟故障：Worker 宕机！"})
        await asyncio.sleep(0.5)
        yield sse("step", {"phase": "workers_dead", "msg": "✓ Worker 已停止。\n  （真实环境中 Temporal Server 保持 workflow 状态）"})

        yield sse("step", {"phase": "downtime_start", "msg": "⏳ 宕机中..."})
        for i in range(4, 0, -1):
            await asyncio.sleep(1)
            yield sse("countdown", {"remaining": i, "msg": f"宕机中... {i}s"})

        yield sse("step", {"phase": "restart", "msg": "🔄 重新启动 Worker！"})
        await asyncio.sleep(1)
        yield sse("step", {"phase": "workers_restarted", "msg": "✓ Worker 重新上线，自动恢复执行..."})
        yield sse("step", {"phase": "recovering", "msg": "重试 step2_slow_llm...", "node": "step2_slow_llm"})
        await asyncio.sleep(2)
        yield sse("step", {"phase": "step2_done", "msg": "✓ step2_slow_llm 完成", "node": "step2_slow_llm"})
        await asyncio.sleep(0.5)
        yield sse("step", {"phase": "step3_done", "msg": "✓ step3_save 完成", "node": "step3_save"})

        yield sse("complete", {
            "msg": "✅ Workflow 完成！故障恢复成功！（单机模拟）",
            "run_id": run_id,
            "result": {
                "step1_prepare": {"status": "COMPLETED", "duration_ms": 450, "outputs": {"function_id": "fn-prepare-data", "result": {"processed": True}}, "node_id": "step1_prepare", "error": ""},
                "step2_slow_llm": {"status": "COMPLETED", "duration_ms": 2000, "outputs": {"text": "[模拟] 供应链韧性分析：企业需要建立多源采购体系...", "model": "standalone-mock", "tokens_used": 150, "prompt": "故障恢复测试", "duration_ms": 2000}, "node_id": "step2_slow_llm", "error": ""},
                "step3_save": {"status": "COMPLETED", "duration_ms": 500, "outputs": {"tool_id": "act-save-result", "result": {"status": "success", "affected_objects": 3}}, "node_id": "step3_save", "error": ""},
            }
        })

    return StreamingResponse(event_stream(), media_type="text/event-stream")


# --- Static UI ---


@app.get("/", response_class=HTMLResponse)
async def index():
    html_path = Path(__file__).parent.parent / "frontend" / "index.html"
    return HTMLResponse(html_path.read_text())


def main():
    import uvicorn
    mode_str = "STANDALONE" if STANDALONE_MODE else "FULL"
    print(f"\n  Workflow Engine Demo UI")
    print(f"  http://localhost:{SERVER_PORT}")
    print(f"  Mode: {mode_str}")
    print(f"  Config: {CONFIG_PATH}")
    print(f"  Temporal: {TEMPORAL_ADDRESS}")
    print(f"  LLM: {QWEN_MODEL} @ {QWEN_BASE_URL}\n")
    uvicorn.run(app, host=SERVER_HOST, port=SERVER_PORT)


if __name__ == "__main__":
    main()
