# Workflow Engine Demo

基于 **Temporal + DAG + LLM** 的智能工作流引擎。用户用自然语言描述需求，LLM 自动规划为 DAG 工作流，Temporal 负责可靠执行与故障恢复。

---

## 快速开始

```bash
# 安装
python3 -m venv .venv && source .venv/bin/activate
pip install -e .

# 启动（按 config.yaml 配置运行）
python3 run.py
```

打开浏览器访问 **http://localhost:8686**

---

## 两种运行模式

| 模式 | 说明 | 适用场景 |
|------|------|---------|
| **standalone** | 无需外部依赖，所有节点模拟执行 | 快速体验、本地演示 |
| **full** | 连接真实 Temporal + LLM | 真实验证、集成测试 |

切换方式：
- **UI 切换**：右上角 ⚙ 配置按钮，填写连接信息后应用（自动持久化）
- **配置文件**：编辑 `config.yaml` 中的 `mode` 字段
- **环境变量**：`STANDALONE=1 python3 run.py`（优先级最高）

---

## 配置

所有配置集中在 `config.yaml`：

```yaml
mode: standalone              # standalone | full

temporal:
  address: "192.168.2.60:7233"
  namespace: "default"

llm:
  api_key: "sk-xxx"
  base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1"
  model: "qwen-plus"

server:
  host: "0.0.0.0"
  port: 8686
```

环境变量可覆盖任意配置项：`TEMPORAL_ADDRESS` / `QWEN_API_KEY` / `QWEN_BASE_URL` / `QWEN_MODEL` / `PORT`

---

## 核心流程

```
① 用户输入（自然语言 / 选择预设场景）
        ↓
② LLM 规划（Qwen-Plus 生成 YAML 工作流定义）
        ↓
③ DSL 解析（YAML → 拓扑排序 → DAG 图）
        ↓
④ Temporal 执行（多队列分发，每个节点按类型路由）
        ↓
⑤ 结果展示（实时时间线 + DAG 状态着色）
```

---

## 节点类型

| 类型 | 执行队列 | 能力 |
|------|---------|------|
| **LLM** | plane-e-default | 调用大模型做分析、推理、生成 |
| **Tool** | plane-b-action | 系统操作（写库、调 API、发通知） |
| **FlinkSQL** | plane-c-pipeline | 数据查询 / ETL |
| **Function** | plane-d-function | 自定义函数（计算、转换） |
| **Condition** | plane-e-default | 条件分支（纯逻辑，非 AI） |
| **Approval** | plane-e-default | 人工审批（暂停等待 Signal） |

---

## DSL 格式

```yaml
workflow_id: wf-example
name: "示例"

nodes:
  - id: query_data
    type: FlinkSQL
    config:
      sql: "SELECT * FROM orders WHERE date > '2026-01-01'"
      sink: bronze.orders

  - id: ai_analyze
    type: LLM
    config:
      prompt: "分析以下订单数据的异常模式"
      model: qwen-plus
    inputs:
      data: "${query_data.outputs.dataset_ref}"    # 引用上游输出

  - id: risk_check
    type: Condition
    config:
      expression: "score > 0.8"
      true_branch: "high_risk"
      false_branch: "normal"

  - id: manager_approve
    type: Approval
    config:
      title: "高风险订单审批"
      approvers: ["manager"]
    when: "risk_check.get('branch') == 'high_risk'"  # 条件执行

edges:
  - from: query_data
    to: ai_analyze
  - from: ai_analyze
    to: risk_check
  - from: risk_check
    to: manager_approve
```

**关键语法**：
- `inputs.field: "${node_id.outputs.key}"` — 节点间数据传递
- `when: "表达式"` — 条件执行（false 则跳过）
- `on_error: FAIL | SKIP | RETRY` — 错误处理策略

---

## 预设工作流

| 文件 | 场景 |
|------|------|
| `supplier_onboarding.yaml` | 供应商准入：采集 → AI 风险评估 → 条件分支 → 人工审批 |
| `intelligent_procurement.yaml` | 智能采购：需求解析 → 供应商匹配 → AI 比价 → 审批 → 下单 |
| `data_quality_alert.yaml` | 数据质量：异常检测 → AI 根因分析 → 自动修复 / 升级审批 |
| `approval_flow.yaml` | 审批交互演示 |
| `fault_recovery_demo.yaml` | 故障恢复演示（Worker 宕机 → 自动恢复） |
| `multi_branch.yaml` | 多分支条件路由 |
| `sample_pipeline.yaml` | 基础 Pipeline |
| `simple_agent.yaml` | 简单 Agent 流程 |

---

## API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/config` | 当前配置 |
| POST | `/api/config` | 切换模式（持久化到 config.yaml） |
| GET | `/api/workflows` | 工作流列表 |
| GET | `/api/workflows/{file}` | 工作流 DAG 详情 |
| POST | `/api/workflows/{file}/run` | 执行工作流 |
| GET | `/api/runs/{id}` | 执行状态与结果 |
| POST | `/api/runs/{id}/approve` | 提交审批决策 |
| POST | `/api/plan-workflow` | Agent 规划（LLM 生成 / 模板） |
| GET | `/api/plan-templates` | 预设模板列表（单机模式） |
| GET | `/api/fault-recovery-demo` | 故障恢复 SSE 流 |

---

## 项目结构

```
workflow-engine-demo/
├── run.py                      # 启动入口
├── config.yaml                 # 配置文件
├── pyproject.toml              # 依赖与构建
├── workflows/                  # YAML 工作流定义
└── src/
    ├── frontend/
    │   └── index.html          # Web UI（DAG 可视化 + 执行追踪）
    └── backend/
        ├── server.py           # FastAPI 服务
        ├── dsl_parser.py       # DSL 解析 + 拓扑排序
        ├── models.py           # 数据模型
        ├── routing.py          # 队列路由
        ├── spi.py              # 执行器接口
        ├── temporal/
        │   ├── workflow.py     # Temporal Workflow（DAG 编排）
        │   ├── activities.py   # Activity（节点执行分发）
        │   └── worker.py       # Worker 管理
        └── executors/
            ├── llm.py          # LLM（Qwen-Plus）
            ├── tool.py         # 工具调用
            ├── flink_sql.py    # 数据查询
            ├── function.py     # 自定义函数
            ├── condition.py    # 条件分支
            └── approval.py     # 人工审批
```

---

## 技术要点

- **Temporal Workflow** — 持久化执行状态，Worker 宕机后自动从断点恢复，无需业务代码处理故障
- **多队列分发** — 不同类型节点路由到不同 Task Queue，模拟多 Plane 架构
- **Signal 机制** — Approval 节点通过 Temporal Signal 实现人机交互，工作流暂停/恢复
- **DAG 拓扑排序** — 自动解析依赖关系，确定执行顺序
- **LLM Agent 规划** — 自然语言 → 结构化 YAML，实现"需求即工作流"
