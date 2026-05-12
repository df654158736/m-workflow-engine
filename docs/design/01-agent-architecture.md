# Agent 架构文档

> **模块**: `src/backend/agent/`
> **最后更新**: 2026-05-08
> **作者**: dingang

---

## 1. 系统定位

Agent 是整个工作流引擎的"大脑"——接收用户自然语言输入，通过 ReAct Loop（推理-行动循环）调用工具完成任务。支持两种运行模式：

| 模式 | 入口 | 状态 | 用途 |
|------|------|------|------|
| **Workflow** | `POST /api/plan` | 无状态 | 自然语言 → DAG YAML → Temporal 执行 |
| **DataFirst** | `POST /api/datafirst` | 有状态（Session） | 多轮对话 → 查数据源 → 建本体 → 生成 Pipeline |

---

## 2. 整体架构

```
┌─────────────────── Web UI ──────────────────────┐
│  Chat 输入 → SSE 流式响应 → 工具确认弹窗         │
│  左侧 Session 历史列表（永久保留 + 手动删除）     │
└──────────────────┬──────────────────────────────┘
                   │ REST API
                   ▼
┌─────────────── FastAPI Server ──────────────────┐
│  POST /api/plan          → plan()   (无状态)     │
│  POST /api/datafirst     → chat()   (有状态)     │
│  POST /api/datafirst/stream → chat_stream() SSE  │
│  GET  /api/datafirst/sessions                    │
│  GET  /api/datafirst/sessions/{id}/history       │
│  DELETE /api/datafirst/sessions/{id}             │
└──────────────────┬──────────────────────────────┘
                   ▼
         ┌─── PlanningAgent ───┐
         │                     │
    ┌────┴────┐          ┌─────┴─────┐
    │ ReAct   │          │ Session   │
    │  Loop   │          │  Store    │
    │(≤15轮)  │          │ (SQLite)  │
    └────┬────┘          └───────────┘
         │
    ┌────┼────────────┐
    ▼    ▼            ▼
  Skills Memory    ToolRegistry
  Loader  Store     (29 tools)
    │       │           │
    ▼       ▼           ▼
  .md     JSON     asyncio.gather
  files   files    (并行执行)
                       │
              ┌────────┼────────┐
              ▼        ▼        ▼
          zhice-paas  DAG校验   本地工具
          REST API   (validate) (估算/查询)
          :6682
```

---

## 3. 核心组件

### 3.1 PlanningAgent (`planner.py`)

Agent 的核心类，协调 LLM、工具、Session、记忆、技能。

```python
class PlanningAgent:
    llm: AsyncOpenAI          # 通义千问 qwen-plus
    tools: ToolRegistry       # 29 个注册工具
    skills: SkillLoader       # 三层技能架构（2 Core + 9 Skills + 26 .md）
    memory: MemoryStore       # 经验记忆（JSON 文件）
    sessions: SessionStore    # 会话持久化（SQLite）
    max_iterations: int = 15  # ReAct 最大轮次
```

**关键方法**：

| 方法 | 用途 |
|------|------|
| `plan(input, mode)` | 无状态规划，一次性输入 → YAML 输出 |
| `chat(input, session_id, confirmed_tool)` | 有状态多轮对话 |
| `chat_stream(...)` | chat 的 SSE 流式版本 |
| `_react_loop(messages, mode, log)` | 核心 ReAct 循环 |
| `_react_loop_stream(...)` | ReAct 循环的流式版本 |
| `_llm_call(messages, schemas, stream)` | LLM 调用（带重试） |
| `_build_system_messages(input, mode)` | 组装 system prompt |

### 3.2 ReAct Loop 流程

```
    ┌──────────────────────────────────┐
    │ 1. LLM 调用（带 tool schemas）    │
    │    ↓                             │
    │ 2. 解析响应                       │
    │    ├─ tool_calls → 3             │
    │    └─ text → 6                   │
    │                                  │
    │ 3. Pydantic 参数校验              │
    │    ├─ 失败 → 返回错误让 LLM 修正  │
    │    └─ 通过 → 4                   │
    │                                  │
    │ 4. 检查 requires_confirmation     │
    │    ├─ 需确认 → 暂停,返回前端      │
    │    └─ 不需要 → 5                 │
    │                                  │
    │ 5. 并行执行工具                   │
    │    asyncio.gather(tool1, tool2…)  │
    │    ├─ 成功 → 追加 tool_result     │
    │    └─ 异常 → 生成 error result    │
    │    ↓                             │
    │    回到 1（下一轮迭代）            │
    │                                  │
    │ 6. 输出处理                       │
    │    ├─ Workflow: 提取 YAML → 校验  │
    │    └─ DataFirst: 返回文本给用户   │
    └──────────────────────────────────┘
```

### 3.3 SessionStore (`session.py`)

SQLite 持久化的多轮对话管理器。

```python
@dataclass
class Session:
    session_id: str                    # UUID[:8]
    mode: str                          # "workflow" | "datafirst"
    messages: list[dict]               # 完整 messages 数组
    tool_calls_log: list[dict]         # 工具调用记录
    total_tokens: int = 0              # 累计 Token 消耗
```

**上下文管理策略**：

| 策略 | 触发条件 | 行为 |
|------|---------|------|
| tool_result 截断 | 单条 > 2000 字 | 保留头 1200 + 尾 600 |
| Session 自动压缩 | messages > 80 条 | 早期对话压缩为摘要，保留最近 40 条 |
| 永不过期 | TTL = 0 | 用户手动删除 |

**数据流**：

```
首次请求（无 session_id）:
  → 创建 Session，注入 system prompt
  → ReAct loop → Agent 输出 → 返回 session_id
  → messages = [system, user₁, tool_call, tool_result, assistant₁]

后续请求（带 session_id）:
  → 从 SQLite 恢复 Session
  → 追加 user₂ → ReAct loop 继续
  → messages = [...之前所有, user₂, …, assistant₂]

刷新页面:
  → localStorage 读取 session_id
  → GET /sessions/{id}/history 回填聊天记录
  → 下次发消息带 session_id，无缝继续
```

### 3.4 ToolRegistry (`tool_registry.py`)

工具注册、发现与安全执行。

```python
@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters: dict              # JSON Schema（OpenAI function calling 格式）
    handler: Callable[..., Awaitable[dict]]
    requires_confirmation: bool   # 写操作需用户确认
    args_model: type[BaseModel]   # Pydantic 校验模型（可选）
```

**执行管线**：

```
execute(name, arguments, confirmed)
  │
  ├─ 1. 查找工具定义
  │
  ├─ 2. Pydantic 参数校验（如有 args_model）
  │     └─ 失败 → 返回结构化错误 + hint
  │
  ├─ 3. 确认检查（requires_confirmation && !confirmed）
  │     └─ 未确认 → 返回 {requires_confirmation: true}
  │
  ├─ 4. asyncio.wait_for(handler(), timeout=60s)
  │     ├─ 超时 → 返回超时错误
  │     └─ 异常 → 返回异常错误
  │
  └─ 5. 返回工具结果 dict
```

### 3.5 SkillLoader (`skill_loader.py`) — 三层技能架构

领域知识注入系统，仿照 Claude Code 的 Skill 机制设计为三层按需加载架构，大幅减少 system prompt 体积（85-91% 减少）。

**三层架构**：

| 层 | 注入方式 | 内容 | 体积 |
|----|---------|------|------|
| **Layer 1: Core Rules** | 始终注入 system prompt | 硬规则（类型映射表 + 强制规则 + 反模式） | ~2K chars/mode |
| **Layer 2: Skill Catalog** | 始终注入 system prompt | 技能索引表（名称 + 一句话描述 + sections 列表） | ~500 chars/mode |
| **Layer 3: Skill Detail** | Agent 通过 `get_skill_detail` 工具按需加载 | 完整规则、few-shot、配置表、示例 | 按需 1-4K/section |

**目录结构**：

```
src/backend/agent/skills/
├── _core/                       # Layer 1: 核心规则（始终注入）
│   ├── workflow-rules.md        #   workflow 模式硬规则
│   └── datafirst-rules.md       #   datafirst 模式硬规则
├── dag-quality/                 # Layer 3: DAG 质量规则
│   ├── SKILL.md                 #   摘要 + frontmatter
│   └── references/
│       ├── validate-errors.md   #   17 errors + 3 warnings
│       └── fix-examples.md      #   2 个修正 few-shot
├── node-types/                  # Layer 3: 节点类型配置
│   ├── SKILL.md
│   └── references/
│       ├── configs.md           #   7 种节点类型完整配置
│       ├── registries.md        #   tool_id + function_id 注册表
│       └── cost-table.md        #   成本估算表
├── common-patterns/             # Layer 3: 常见 DAG 模式
├── data-flow/                   # Layer 3: 数据传递 + 错误处理
├── ontology-design/             # Layer 3: 本体设计规范
├── exploration-flow/            # Layer 3: 对象探查流程
├── field-mapping/               # Layer 3: 字段映射规则
└── domain/
    ├── supply-chain/            # Layer 3: 供应链领域
    └── data-quality/            # Layer 3: 数据质量领域
```

**Frontmatter 协议**（SKILL.md）：
```yaml
---
name: dag-quality
description: DAG 质量校验规则和修正示例
mode: workflow          # workflow | datafirst | all
catalog: DAG 结构校验规则（sections: "validate-errors", "fix-examples"）
sections:
  - validate-errors: 17 个校验错误码及其含义
  - fix-examples: 2 个修正前后对比
---
```

**加载流程**：
```
PlanningAgent.__init__()
  → SkillLoader(skills_dir)
  → _load_core_rules() — 扫描 _core/*.md，按 mode 过滤
  → _load_skills() — rglob("SKILL.md")，解析 frontmatter + references/

_build_system_messages(mode)
  → skills.load_core(mode) — Layer 1 注入
  → skills.load_catalog(mode) — Layer 2 注入

Agent ReAct Loop
  → LLM 看到 catalog 中的技能列表
  → 决定需要详情 → 调用 get_skill_detail(skill_name, section)
  → 获取 Layer 3 完整内容 → 继续推理
```

### 3.6 MemoryStore (`memory_store.py`)

基于 JSON 文件的经验记忆系统。

| 记忆类型 | 写入时机 | 用途 |
|---------|---------|------|
| success | DAG 校验通过后自动保存 | Few-shot 示例 |
| correction | DAG 校验失败后保存 | 避免重复错误 |
| preference | 用户明确要求时 | 个性化偏好 |

每类最多 50 条（FIFO），检索用关键词评分匹配，注入 system prompt。

### 3.7 API Client (`api_client.py`)

异步 HTTP 客户端，封装 zhice-paas web-app 的 REST API 调用。

```python
api_get(path, params)     # GET 请求
api_post(path, json_data) # POST 请求
api_put(path, json_data)  # PUT 请求
api_delete(path)          # DELETE 请求
```

自动处理 `{code, data}` 包装格式、认证头（Bearer token）、项目/世界上下文注入。

---

## 4. 工具清单

### Workflow 模式工具（全部 29 个）

Workflow 模式不限制工具集，Agent 可调用所有注册工具（含 DataFirst 工具）。常用：

| 工具 | 类型 | 说明 |
|------|------|------|
| `validate_dag` | 校验 | YAML DAG 语法/结构/环检测 |
| `list_available_tools` | 查询 | 可用的 Tool 节点 tool_id |
| `list_available_functions` | 查询 | 可用的 Function 节点 function_id |
| `check_output_compatibility` | 查询 | 节点输出字段 schema |
| `search_similar_workflows` | 查询 | 搜索相似 YAML 参考 |
| `query_table_schema` | 查询 | 数据库表结构 |
| `estimate_cost` | 查询 | 工作流执行成本估算 |
| `recall_memory` | 查询 | 搜索历史记忆 |
| `get_skill_detail` | 查询 | 按需查询领域知识（三层技能 Layer 3） |

### DataFirst 模式工具（19 个，白名单过滤）

| 工具 | 类型 | 确认 | 说明 |
|------|------|------|------|
| `list_datasources` | 查询 | - | 列出数据源 |
| `list_tables` | 查询 | - | 列出表 |
| `scan_table_columns` | 查询 | - | 扫描列元数据 |
| `list_object_types` | 查询 | - | 列出已有 ObjectType |
| `get_object_type_detail` | 查询 | - | ObjectType 详情 |
| `ai_infer_properties` | 查询 | - | AI 推断属性 |
| `get_field_mappings` | 查询 | - | 字段映射建议 |
| `create_object_type` | 写入 | ✅ | 创建 + 定稿 + 发布 |
| `update_object_type_properties` | 写入 | ✅ | 补充属性 |
| `finalize_and_publish` | 写入 | ✅ | 定稿发布 |
| `delete_object_type` | 写入 | ✅ | 删除（不可逆） |
| `submit_compare_decisions` | 写入 | ✅ | 提交对象探查决策 |
| `confirm_field_mappings` | 写入 | ✅ | 确认字段映射 |
| `create_fabric_task` | 写入 | ✅ | 创建编织任务 |
| `trigger_ai_analysis` | 写入 | - | 触发 AI 分析 |
| `generate_pipeline` | 写入 | ✅ | 生成 Pipeline |
| `submit_pipeline` | 写入 | ✅ | 提交 Pipeline |
| `ask_user_choice` | 交互 | - | 向用户展示选项 |
| `get_skill_detail` | 查询 | - | 按需查询领域知识（三层技能 Layer 3） |

---

## 5. 生产化加固措施

### 5.1 LLM 调用可靠性

```
失败 → 等 1s → 重试 → 等 2s → 重试 → 等 4s → 放弃
```

指数退避重试（最多 3 次），避免偶发 5xx/超时直接报错。

### 5.2 工具执行安全

```
LLM 参数
  → Pydantic 校验（类型/必填/格式）
    → 确认检查（写操作暂停等用户确认）
      → 超时保护（60s）
        → 异常捕获（不崩溃，返回结构化错误）
```

四层防护，每层失败都返回 LLM 可理解的错误信息，让 Agent 自行修正。

### 5.3 Token 用量跟踪

- 非流式：从 `response.usage.total_tokens` 累计
- 流式：启用 `stream_options={"include_usage": True}`，从最后一个 chunk 取
- Session 级持久化，前端 `done` 事件中返回

### 5.4 Graceful Shutdown

FastAPI shutdown 事件中关闭 SQLite 连接，确保数据完整写入。

### 5.5 Plan-then-Execute

复杂多步任务（如"接入 3 张表"）时，Agent 先输出执行计划，用户确认后逐步执行，每步播报进度。Prompt 驱动，无额外工具开销。

---

## 6. 关键常量

| 常量 | 值 | 位置 | 含义 |
|------|---|------|------|
| `_LLM_MAX_RETRIES` | 3 | planner.py | LLM 最大重试次数 |
| `_LLM_RETRY_BASE_DELAY` | 1.0s | planner.py | 重试基础延迟 |
| `_REACT_LOOP_TIMEOUT_SECONDS` | 120s | planner.py | ReAct 循环整体超时 |
| `max_iterations` | 15 | planner.py | ReAct 最大轮次 |
| `_TOOL_TIMEOUT_SECONDS` | 60s | tool_registry.py | 单个工具执行超时 |
| `_TOOL_RESULT_MAX_CHARS` | 2000 | session.py | tool_result 截断阈值 |
| `_COMPACT_TRIGGER` | 80 | session.py | Session 压缩触发阈值 |
| `_SESSION_TTL_SECONDS` | 0 | session.py | Session 过期时间（0=永不） |

---

## 7. 文件结构

```
src/backend/agent/
├── planner.py              # ReAct Loop 核心 + 两种模式入口
├── session.py              # Session 持久化（SQLite WAL）
├── tool_registry.py        # 工具注册 + Pydantic 校验 + 超时执行
├── api_client.py           # zhice-paas HTTP 客户端
├── memory_store.py         # 经验记忆（JSON 文件）
├── skill_loader.py         # 三层技能加载器（Core / Catalog / Detail）
├── __init__.py             # 自动触发 @tool 注册
├── tools/                  # 29 个工具（@tool 装饰即注册）
│   ├── __init__.py
│   ├── validate_dag.py     # DAG 校验（Kahn 环检测）
│   ├── datasource_tools.py # 3 个数据源查询工具
│   ├── ontology_tools.py   # 9 个本体操作工具
│   ├── fabric_tools.py     # 5 个数据编织工具
│   ├── interaction_tools.py # ask_user_choice
│   ├── skill_tools.py      # get_skill_detail（三层技能 Layer 3 入口）
│   ├── memory_tools.py     # save_to_memory, recall_memory
│   ├── estimate_cost.py    # 成本估算
│   ├── check_compatibility.py  # 输出兼容性检查
│   ├── search_workflows.py # 工作流搜索
│   ├── list_tools.py       # 系统工具列表
│   ├── list_functions.py   # 可用函数列表
│   └── query_schema.py     # 表结构查询
└── skills/                 # 三层领域知识体系（26 .md 文件）
    ├── _core/              # Layer 1: 核心规则（始终注入）
    │   ├── workflow-rules.md
    │   └── datafirst-rules.md
    ├── dag-quality/        # Layer 3: 按需查询
    │   ├── SKILL.md
    │   └── references/
    │       ├── validate-errors.md
    │       └── fix-examples.md
    ├── node-types/
    ├── common-patterns/
    ├── data-flow/
    ├── ontology-design/
    ├── exploration-flow/
    ├── field-mapping/
    └── domain/
        ├── supply-chain/
        └── data-quality/
```

---

## 8. 典型请求流程（DataFirst 多轮对话）

```
Turn 1: "我想接入供应商表"
  ├─ 创建 Session
  ├─ LLM → 调 list_datasources → 调 list_tables
  ├─ Agent: "找到以下数据源…请确认使用哪个?"
  └─ 返回 {session_id: "abc123"}

Turn 2: "使用 ds-001 的 supplier_profiles"
  ├─ 恢复 Session，追加消息
  ├─ LLM → 调 scan_table_columns → 调 ai_infer_properties
  ├─ Agent: "推荐创建 ObjectType: Supplier，属性如下…"
  └─ 返回 {requires_confirmation: true, pending_tool: {create_object_type, ...}}

Turn 3: "确认创建"
  ├─ 恢复 Session，执行 confirmed_tool
  ├─ create_object_type → finalize → publish
  ├─ Agent: "Supplier 已创建并发布为 ACTIVE!"
  └─ 完成

刷新页面:
  ├─ localStorage → session_id
  ├─ GET /sessions → 左侧列表
  ├─ GET /sessions/{id}/history → 回填聊天
  └─ 下次发消息继续对话
```

---

## 9. 扩展方式

| 扩展点 | 做法 |
|--------|------|
| 新增工具 | `tools/` 下新建文件，用 `@tool` 装饰即可自动注册 |
| 新增领域知识 | `skills/{name}/` 下新建 `SKILL.md` + `references/`，SkillLoader 自动扫描 |
| 新增节点类型 | `executors/` 下实现 `NodeExecutor` SPI 接口 |
| 加强参数校验 | 给 `@tool` 添加 `args_model=PydanticModel` |
| 新增运行模式 | planner.py 中新增 PROMPT_TEMPLATE + 工具集 |
