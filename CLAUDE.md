# Project Rules — Workflow Engine Demo

基于 **Temporal + DAG + LLM** 的智能工作流引擎。用户用自然语言描述需求，LLM 自动规划为 DAG 工作流，Temporal 负责可靠执行与故障恢复。

---

## 必读文档（每次开始工作前）

1. `AGENTS.md` — 多 Agent / 多人协作规范（身份、分支、冲突避免）
2. `PROGRESS.md` — 项目进度追踪（当前谁在做什么）
3. `docs/design/00-overview.md` — 架构总览

---

## 自动进度更新（必须遵守）

每次完成开发任务（FEAT、Bug 修复、重构等）并提交代码后，**必须自动更新以下文件**，无需用户提醒：

1. **`PROGRESS.md`** — 在 "Recently Completed" 部分添加完成记录，更新模块进度百分比
2. **`sprints/active/{日期}/tasks-{gitid}.md`** — 将对应任务状态从 ⬜ 改为 ✅

> GitID 从 `git config user.name` 派生：去空格 → 全小写。
> 这是领导查看团队进度的主入口，遗漏更新 = 工作不可见。

---

## 文档同步（必须遵守）

> **核心原则**：代码实现、需求文档（PRD）、详设文档（SPEC）三者始终同步。任何变更有留痕，包括变更人。
> **文档格式**：正文只保留当前态，历史变更外置到 `.changelog.md`。
> 详见：`.claude/skills/doc-sync-after-dev/SKILL.md`

### 增量同步（自动触发，无需手动输入命令）

**Claude 完成一轮代码实现后，必须自查本轮变更是否偏离了需求文档或详设文档。如果偏离，在回复中主动告知用户偏离点，等用户确认功能 OK 后再执行 `/doc-sync` 同步文档。**

**流程**：
1. Claude 完成代码实现
2. 自查：本轮变更是否偏离需求文档或详设文档？
3. 如果偏离 → 在回复中告知用户偏离点，并询问："要现在同步文档，还是等本轮迭代结束后统一更新？"
4. 用户选择"现在更新" → 执行 `/doc-sync`
5. 用户选择"稍后统一" → Claude 记住待同步项，继续开发
6. **累积提醒**：如果用户选了"稍后"且已累积了待同步项，在用户说"功能做完了"/"可以了"/"没其他改的了"时，Claude 必须主动提醒："本轮有 N 处文档偏离待同步：{清单}，现在统一更新文档吗？"

### 全量同步（自动触发）

**以下任一条件成立时，Claude 必须自动执行 `/doc-sync-after-dev` skill**：

1. **feature 分支开发完成** — 用户说"准备合并"、"提 PR"、"合并到 main"
2. **用户主动调用** — `/doc-sync-after-dev`

---

## 技术红线（绝对禁止）

### 技术栈与编码

- ❌ 空的 except 块 `except: pass`
- ❌ 删除失败的测试来"通过"测试
- ❌ 在 API 层暴露内部实现细节
- ❌ 硬编码密钥、密码、Token（使用 config.local.yaml，模板用 config.yaml）
- ❌ 把 config.local.yaml 提交到 git（已在 .gitignore）
- ❌ 同步阻塞调用（项目全程使用 async/await）
- ❌ 绕过 Temporal Activity 直接执行副作用操作

### 流程与协作

- ❌ 修改他人负责的模块目录（未经协调）
- ❌ 直接 push 共享文件到 main（必须走 PR）

### 数据与持久化

- ❌ 直接修改 Temporal Workflow 的持久化状态
- ❌ 跳过 DSL 校验直接构造 DAG

---

## 开发边界规则

| 问题 | 答案 | 写在哪里 |
|------|------|---------|
| 新增/修改节点执行器？ | 是 | `src/backend/executors/` |
| Temporal Workflow/Activity 变更？ | 是 | `src/backend/temporal/` |
| Agent 规划能力（ReAct/Tool/Skill）？ | 是 | `src/backend/agent/planner.py` |
| 新增 DataFirst 工具？ | 是 | `src/backend/agent/tools/` + 注册到 `DATAFIRST_TOOLS` |
| Session/多轮对话机制？ | 是 | `src/backend/agent/session.py` |
| zhice-paas API 调用？ | 是 | `src/backend/agent/api_client.py` |
| API 路由变更？ | 是 | `src/backend/server.py` |
| DSL 格式/解析变更？ | 是 | `src/backend/dsl_parser.py` + `src/backend/models.py` |
| 前端 UI？ | 是 | `src/frontend/index.html` |
| 工作流定义文件？ | 是 | `workflows/*.yaml` |
| 配置变更？ | 是 | `config.yaml`（模板）+ `config.local.yaml`（真实值） |

---

## 必须遵守

- ✅ Python 3.10+，`pyproject.toml` 管理依赖
- ✅ Pydantic v2 做数据校验与模型定义
- ✅ 全程 async/await（FastAPI + Temporal 均为异步）
- ✅ 类型注解覆盖所有公开 API
- ✅ 新增节点类型必须实现 `NodeExecutor` SPI 接口
- ✅ 开工前跑 Checklist（见 AGENTS.md）
- ✅ 分支命名遵循 `feature/{module}-{task}` 格式

---

## 整体架构

```
┌─────────────── Web UI (:8686) ──────────────────┐
│  Tab 1: Agent 模式（自然语言 → DAG 工作流）      │
│  Tab 2: 预设场景（选择已有 workflow 执行）        │
│  Tab 3: 数据接入（多轮对话 → 本体 → Pipeline）   │
└──────────────────┬──────────────────────────────┘
                   │ REST API
                   ▼
┌─────────────── FastAPI Server ──────────────────┐
│  POST /api/plan      → PlanningAgent.plan()     │
│  POST /api/datafirst → PlanningAgent.chat()     │
│  POST /api/run       → Temporal Workflow        │
└──────────────────┬──────────────────────────────┘
           ┌───────┼───────┐
           ▼       ▼       ▼
     Planning   Session   Temporal
      Agent     Store     Workflow
    (ReAct)   (多轮持久)  (DAG 编排)
       │                     │
       ▼                     ▼ 多队列分发
   29 Tools ──→ zhice-paas   ┌──────────────────┐
   (真实API)    web-app      │ LLM / Tool /     │
   + Skills     :6682        │ FlinkSQL / etc.  │
   (三层架构)                └──────────────────┘
```

## 两种 Agent 模式

| 模式 | 入口 | 状态 | 用途 |
|------|------|------|------|
| **Workflow 模式** | `POST /api/plan` | 无状态（单次 ReAct） | 自然语言 → DAG YAML → Temporal 执行 |
| **DataFirst 模式** | `POST /api/datafirst` | **有状态（Session 持久化）** | 多轮对话 → 查数据源 → 建本体 → 生成 Pipeline |

### Session 架构（DataFirst 模式核心）

```
首次请求（无 session_id）:
  → 创建 Session，注入 system prompt
  → ReAct loop → Agent 输出文本 → 暂停返回 session_id
  → Session.messages = [system, user1, tool_call, tool_result, assistant1]

后续请求（带 session_id）:
  → 从 SessionStore 取回 Session
  → 追加 user2 到 Session.messages
  → ReAct loop 继续 → Agent 看到完整上下文（含之前的 tool 结果）
  → Session.messages = [...之前所有, user2, tool_call, tool_result, assistant2]
```

关键设计：
- **messages 永远追加，从不重建** — tool_call / tool_result 完整保留
- **tool_result 截断** — 单条结果超 2000 字时截断（头 1200 + 尾 600）
- **Session 自动压缩** — messages > 80 条时，压缩早期对话为摘要
- **Session 自动过期** — 30 分钟无活动自动清理
- **前端持有 session_id** — 不传 history 数组，只传一个 ID

## 模块划分

| 模块 | 目录 | 技术栈 | 职责 |
|------|------|--------|------|
| Server | `src/backend/server.py` | FastAPI + Uvicorn | REST API、WebSocket、静态文件服务 |
| DSL Parser | `src/backend/dsl_parser.py` | Pydantic + YAML | 工作流定义解析、拓扑排序、DAG 校验 |
| Models | `src/backend/models.py` | Pydantic v2 | 数据模型（WorkflowDefinition、NodeSpec 等） |
| Routing | `src/backend/routing.py` | Python | 节点类型 → Task Queue 路由映射 |
| SPI | `src/backend/spi.py` | ABC | NodeExecutor 抽象接口 |
| Executors | `src/backend/executors/` | Python | 6 种节点执行器（LLM/Tool/FlinkSQL/Function/Condition/Approval） |
| Temporal | `src/backend/temporal/` | temporalio | Workflow 编排、Activity 分发、Worker 管理 |
| Agent | `src/backend/agent/` | OpenAI SDK | Planning Agent（ReAct Loop + 29 Tools + 三层 Skills + Memory） |
| Session | `src/backend/agent/session.py` | Python dict | 服务端会话存储（messages 持久化 + 压缩 + 过期清理） |
| Frontend | `src/frontend/index.html` | Vanilla HTML/JS | DAG 可视化 + 执行时间线 + 数据接入 Chat UI |

---

## Python 开发规范

```
src/backend/
├── server.py              # FastAPI 入口（/api/plan, /api/datafirst, /api/run）
├── dsl_parser.py          # DSL 解析
├── models.py              # Pydantic 模型
├── routing.py             # 队列路由
├── spi.py                 # 执行器接口
├── executors/             # SPI 实现
│   ├── llm.py
│   ├── tool.py
│   ├── flink_sql.py
│   ├── function.py
│   ├── condition.py
│   └── approval.py
├── temporal/              # Temporal 编排
│   ├── workflow.py
│   ├── activities.py
│   └── worker.py
└── agent/                 # Planning Agent
    ├── planner.py         # ReAct Loop + Session 多轮对话
    ├── session.py         # Session 持久化（SQLite WAL）
    ├── api_client.py      # zhice-paas REST API 客户端
    ├── memory_store.py    # 经验记忆（JSON 文件）
    ├── skill_loader.py    # 三层技能加载器（Core / Catalog / Detail）
    ├── tool_registry.py   # Tool 注册 + Pydantic 校验 + 超时执行
    ├── tools/             # 可执行工具（29 个，@tool 装饰即注册）
    │   ├── validate_dag.py      # DAG 校验（Kahn 环检测）
    │   ├── datasource_tools.py  # 3 个数据源查询工具
    │   ├── ontology_tools.py    # 9 个本体操作工具
    │   ├── fabric_tools.py      # 5 个数据编织工具
    │   ├── interaction_tools.py # ask_user_choice（交互选择）
    │   ├── skill_tools.py       # get_skill_detail（三层技能 Layer 3 入口）
    │   ├── memory_tools.py      # save_to_memory, recall_memory
    │   └── ...                  # estimate_cost, search_workflows, list_tools 等
    └── skills/            # 三层领域知识体系
        ├── _core/               # Layer 1: 核心规则（始终注入 ~2K chars/mode）
        │   ├── workflow-rules.md
        │   └── datafirst-rules.md
        ├── {skill}/             # Layer 3: 按需查询（Agent 调用 get_skill_detail）
        │   ├── SKILL.md         # 摘要 + frontmatter（含 catalog 字段）
        │   └── references/      # 详细内容（section 粒度按需加载）
        └── domain/              # 领域子目录
            ├── supply-chain/
            └── data-quality/

src/frontend/
└── index.html             # 单文件 UI（3 Tab：Agent / 预设 / 数据接入 Chat）

config.yaml                # 模板配置（提交到 git，占位符值）
config.local.yaml          # 真实配置（.gitignore，含 API key / project_id）
```

### DataFirst 工具清单（19 个）

| 工具 | 类型 | 确认 | 说明 |
|------|------|------|------|
| `list_datasources` | 查询 | - | 列出已接入的数据源 |
| `list_tables` | 查询 | - | 列出数据源中的所有表 |
| `scan_table_columns` | 查询 | - | 扫描表的列元数据 |
| `list_object_types` | 查询 | - | 列出已有 ObjectType |
| `get_object_type_detail` | 查询 | - | ObjectType 详情 |
| `ai_infer_properties` | 查询 | - | AI 推断属性 |
| `create_object_type` | 写入 | ✅ | 创建 + 定稿 + 发布 |
| `update_object_type_properties` | 写入 | ✅ | 补充属性 |
| `finalize_and_publish` | 写入 | ✅ | 定稿发布 |
| `delete_object_type` | 写入 | ✅ | 删除（不可逆） |
| `submit_compare_decisions` | 写入 | ✅ | 提交探查决策 |
| `confirm_field_mappings` | 写入 | ✅ | 确认字段映射 |
| `create_fabric_task` | 写入 | ✅ | 创建数据编织任务 |
| `trigger_ai_analysis` | 写入 | - | 触发 AI 语义分析 |
| `get_field_mappings` | 查询 | - | 获取字段映射建议 |
| `generate_pipeline` | 写入 | ✅ | 生成 Pipeline DSL |
| `submit_pipeline` | 写入 | ✅ | 提交 Pipeline |
| `ask_user_choice` | 交互 | - | 向用户展示选项 |
| `get_skill_detail` | 查询 | - | 按需查询领域知识（三层技能 Layer 3） |

- 依赖管理：`pyproject.toml`
- 测试：`pytest` + `pytest-asyncio`
- 格式：`black + isort + ruff`
- 类型检查：`mypy`
- 所有公开 API 必须有类型注解

---

## 配置管理

```yaml
# config.yaml（模板，提交到 git）      # config.local.yaml（真实值，.gitignore）
llm:                                    llm:
  api_key: your-api-key-here              api_key: sk-xxxx（通义千问 API Key）
web_app:                                web_app:
  base_url: http://127.0.0.1:6682        base_url: http://127.0.0.1:6682
  project_id: your-project-id            project_id: 019dd21a-xxxx（实际项目 ID）
  world_id: your-world-id                world_id: 019dd21a-xxxx（实际 World ID）
  auth_token: admin-mock-token            auth_token: dev-mock-token
```

- Server 启动时优先读 `config.local.yaml`，不存在才 fallback 到 `config.yaml`
- 环境变量 `QWEN_API_KEY` 可覆盖配置文件中的 api_key
- 脱敏提交：只改 `config.yaml`，`config.local.yaml` 始终保持真实值

## 常用命令

```bash
# 启动服务（需要先 pip install -e .）
cd /home/zxxy/repository/workflow-engine-demo
python -m backend.server               # 按 config(.local).yaml 启动
STANDALONE=1 python -m backend.server   # 单机模式（无 Temporal / LLM）

# 依赖
pip install -e .

# 浏览器访问
http://localhost:8686
```

## 端口依赖

| 服务 | 端口 | 必须运行 |
|------|------|---------|
| workflow-engine-demo | 8686 | 本项目 |
| zhice-paas web-app | 6682 | DataFirst 工具需要 |
| zhice-paas control-plane | 6666/6667 | web-app 后端依赖 |
| Temporal | 7233 | Workflow 执行需要 |

---

## 质量门（提交前必须通过）

| 检查项 | 命令 |
|--------|------|
| Python lint | `ruff check src/` |
| Python format | `black --check src/ && isort --check src/` |
| Python typecheck | `mypy src/` |
| Python test | `pytest` |

---

## Commit Message 规范（GitLab pre-receive hook 强制）

允许的前缀：`更新:` `修复:` `增加:` `删除:` `临时:` `测试:` `恢复:` `合并:`

---

## Sprint 管理（Wave 模式）

- Sprint 目录：`sprints/active/YYYY-MM-DD/`
- 每波需求一个 Wave 目录：`wave{N}-{timestamp}/`
- 每人独立任务文件：`tasks-{gitid}.md`（只编辑自己的）
- 跨人协调：日期级 `coordination.md`（append-only）

详见：`.claude/skills/sprint-management/SKILL.md`

---

## 项目自定义 Skills（`/` 命令）

| 命令 | 用途 |
|------|------|
| `/sprint-management` | Sprint/Wave 创建与任务管理 |
| `/need-to-code` | 需求 ↔ 文档 ↔ 代码 全链路定位 |
| `/spec-prelaunch-review` | 详设开工前全链路代码核验 |
| `/prd-status` | PRD 发布版本追踪与 AC 进度聚合 |
| `/git-workflow` | Git 分支与协作工作流 |
| `/git-team-collaboration` | 多人/多 Session 协作规则 |
| `/scenario-testing` | 场景化测试方法论 |
| `/gitlab-auto-commit` | GitLab 自动提交配置 |
| `/doc-sync` | 增量文档同步 |
| `/doc-sync-after-dev` | 全量文档同步（合并前） |
| `/code-review` | 开发完成后多维度 Review |
| `/commenting-standards` | 注释规范检查 |
