# PRD-001: Pipeline DAG AI 助手

> **Version**: 1.0
> **Author**: 丁昂
> **Date**: 2026-05-12
> **Status**: Draft

---

## 1. Overview

### 1.1 Problem Statement

智策平台的 Pipeline DAG 编辑器已具备完整的可视化编排能力（14 种节点类型、拖拽连线、沙箱测试、DSL 导出等），但页面右侧的 **AI 助手面板** 目前全部功能为 Mock 实现，无法提供真实的智能辅助。

用户痛点：
- **手动编排效率低**：构建一条完整的 ETL Pipeline 需要逐个拖拽节点、配置参数、写 SQL，对新手门槛高
- **SQL 编写困难**：Flink SQL 语法与标准 SQL 有差异，用户容易写错
- **流程设计依赖经验**：不知道应该加哪些清洗步骤、JOIN 顺序怎么排、数据质量检查放在哪里

当前 AI 助手的 8 个快捷命令（添加过滤、添加 JOIN、生成完整流程、优化 SQL 等）和自由对话均返回硬编码数据，无法根据实际数据源和业务场景给出合理建议。

### 1.2 Proposed Solution

基于现有 workflow-engine-demo Agent 架构（ReAct Planner + ToolRegistry + Session + SSE），新增 **DAG 编排 Skill** 和 **DAG 工具集**，让 AI 助手具备：

1. 读取当前画布状态，理解已有 DAG 结构
2. 根据自然语言描述，自动生成/修改/删除节点和连线
3. 为每种节点类型生成合法的 Flink SQL 和参数配置
4. 触发校验和沙箱测试，根据结果自动修复
5. 导出完整的 Flink SQL 脚本或 YAML DSL

**核心设计决策**：不新建子 Agent，而是在现有 Agent 中通过 Skill 切换上下文 + 新增工具集实现。理由：
- 复用已有的 Planner/Session/SSE/Memory 基础设施
- DAG 编排需要查数据源字段、查本体类型，这些工具已有
- Skill 机制天然支持 prompt 切换，不同场景加载不同提示词

### 1.3 Goals & Non-Goals

#### Goals
- G1: 覆盖页面 AI 助手的全部 8 个快捷命令
- G2: 支持自由对话模式下的 DAG 增删改查
- G3: 生成的节点配置和 SQL 可直接用于沙箱测试
- G4: 与现有 DataFirst 模式共存，通过 Skill 自动切换

#### Non-Goals
- 不改动 zhice-paas web-app 后端代码（仅改 workflow-engine-demo 和 web-ui 对接层）
- 不实现 DATA_QUALITY / ENTITY_RESOLUTION 节点（页面本身未实装）
- 不做 Pipeline 生命周期管理（执行/暂停/恢复属于外部页面功能）
- 不做实时协同编辑（多人同时编辑同一 DAG）

---

## 2. User Stories

### Story 1: 数据工程师快速构建 ETL 流程

**As a** 数据工程师,
**I want to** 用自然语言描述数据处理需求后自动生成 Pipeline DAG,
**So that** 不需要手动逐个拖拽节点和写 SQL，10 分钟内完成一条完整 Pipeline。

#### Acceptance Criteria

1. WHEN 用户在 AI 面板输入"从 orders 表过滤已取消订单，关联 customers 表，按月汇总销售额，写入 monthly_sales" THEN 系统 SHALL 自动生成包含 SOURCE → FILTER → JOIN → GROUP_AGGREGATION → SINK 的完整 DAG
2. WHEN 生成的 DAG 包含 SQL 节点 THEN 系统 SHALL 确保 SQL 语法为合法 Flink SQL
3. WHEN 用户点击"生成完整流程"快捷命令 THEN 系统 SHALL 基于已有 SOURCE 节点的表 Schema 自动推荐清洗和转换步骤

### Story 2: 数据工程师修改现有 Pipeline

**As a** 数据工程师,
**I want to** 用自然语言修改已有的 DAG 节点配置,
**So that** 不需要手动打开每个节点的配置面板去改 SQL。

#### Acceptance Criteria

1. WHEN 用户输入"把过滤条件改成 status = 'ACTIVE'" THEN 系统 SHALL 找到 FILTER 节点并更新其 WHERE 条件
2. WHEN 用户输入"在 filter 和 sink 之间加一个去重步骤，按 order_id 去重" THEN 系统 SHALL 在正确位置插入 DEDUPLICATE 节点并自动连线
3. WHEN 用户输入"删掉聚合那个步骤" THEN 系统 SHALL 移除该节点并重新连接上下游

### Story 3: 数据工程师优化和调试 Pipeline

**As a** 数据工程师,
**I want to** 让 AI 分析现有 Pipeline 的问题并自动修复,
**So that** 不需要逐个检查每个 SQL 节点的语法和逻辑。

#### Acceptance Criteria

1. WHEN 用户点击"优化 SQL"快捷命令 THEN 系统 SHALL 分析所有 SQL 节点并给出性能优化建议（索引、窗口大小、JOIN 顺序等）
2. WHEN 用户输入"帮我校验一下" THEN 系统 SHALL 调用 DAG 校验工具，对发现的问题给出修复建议
3. WHEN 用户点击"解释当前流程"快捷命令 THEN 系统 SHALL 用自然语言逐节点解释整个 DAG 的数据处理逻辑

### Story 4: 数据工程师导出 Pipeline

**As a** 数据工程师,
**I want to** 将 DAG 导出为 Flink SQL 脚本,
**So that** 可以直接在 Flink 集群上执行或交给运维部署。

#### Acceptance Criteria

1. WHEN 用户点击"导出 Flink SQL"快捷命令 THEN 系统 SHALL 将整个 DAG 转换为可执行的 Flink SQL 脚本（包含 CREATE TABLE / INSERT INTO 语句）
2. WHEN DAG 包含多个 SOURCE 和 JOIN THEN 导出的 SQL SHALL 按拓扑顺序组织，注释标注每步对应的节点 ID

---

## 3. Requirements

### 3.1 Functional Requirements

| ID | Requirement | Priority | Notes |
|----|-------------|----------|-------|
| FR-001 | 读取当前画布状态（节点列表、边列表、每个节点的配置） | P0 | 所有操作的前置条件 |
| FR-002 | 添加节点：支持 14 种节点类型，自动生成节点 ID 和默认配置 | P0 | 返回 `{ steps, edges }` 格式供前端渲染 |
| FR-003 | 生成完整流程：基于已有 SOURCE 节点，自动推荐 Transform 链并生成 SINK | P0 | 核心差异化功能 |
| FR-004 | 修改节点配置：更新已有节点的 SQL / 条件 / 映射等参数 | P1 | 自由对话场景 |
| FR-005 | 删除节点：移除指定节点并自动重连上下游 | P1 | 自由对话场景 |
| FR-006 | 修改连线：调整节点间的连接关系 | P2 | 低频操作 |
| FR-007 | 优化 SQL：分析节点 SQL 并给出性能优化建议 | P1 | 快捷命令 |
| FR-008 | 解释流程：用自然语言描述整个 DAG 的数据处理逻辑 | P1 | 快捷命令，纯 LLM 推理 |
| FR-009 | 导出 Flink SQL：整个 DAG 转换为可执行 SQL 脚本 | P1 | 快捷命令 |
| FR-010 | 沙箱测试：触发单节点或全流程沙箱执行 | P2 | 调用已有 web-app API |
| FR-011 | DAG 校验：调用校验工具并根据错误自动修复 | P1 | 复用已有 validate_dag |
| FR-012 | SQL 导入：将 Flink SQL 脚本拆解为 DAG 节点 | P2 | 逆向操作 |

### 3.2 Non-Functional Requirements

| ID | Requirement | Metric | Target |
|----|-------------|--------|--------|
| NFR-001 | AI 响应延迟 | 首 token 时间 | < 2s |
| NFR-002 | 生成完整 DAG | 端到端时间 | < 15s |
| NFR-003 | 生成 SQL 正确率 | 校验通过率 | > 85% |
| NFR-004 | 会话上下文保持 | Session 多轮对话 | 支持至少 20 轮 |

---

## 4. Data & API

### 4.1 Agent ↔ 前端数据交换格式（dag_update SSE 事件）

> **前端代码验证基准**：`df-pipeline-dag.vue` 第 79-92 行 `DagNodeData` / `DagEdgeData` 接口

#### 4.1.1 dag_update 事件 payload

```json
{
  "action": "add",
  "steps": [
    {
      "id": "filter-cancelled",
      "type": "FILTER",
      "label": "过滤取消订单",
      "config": {
        "conditions": [{ "field": "status", "operator": "!=", "value": "CANCELLED" }]
      },
      "sqlFragment": "SELECT * FROM input\nWHERE status != 'CANCELLED'",
      "description": "过滤状态为 CANCELLED 的记录"
    }
  ],
  "edges": [
    { "source": "src-orders", "target": "filter-cancelled" }
  ]
}
```

#### 4.1.2 action 操作类型

| action | 含义 | 前端行为 |
|--------|------|---------|
| `add` | 新增节点和边 | `pushHistory()` → `dagNodes.push(...)` / `dagEdges.push(...)` |
| `modify` | 修改已有节点配置 | `pushHistory()` → 找到节点 → 合并 config/sqlFragment/description |
| `remove` | 删除节点（自动重连由 Agent 返回的 edges 覆盖） | `pushHistory()` → `dagNodes.filter(...)` / `dagEdges.filter(...)` → 追加新 edges |
| `replace_all` | 替换整个 DAG（"生成完整流程"场景） | `pushHistory()` → `dagNodes.value = [...]` / `dagEdges.value = [...]` |

> **关键**：所有操作前必须调 `pushHistory()`，让用户可以 Ctrl+Z 撤销 AI 操作。前端已有完整的 undo/redo 栈（`df-pipeline-dag.vue` 第 991-1028 行）。

#### 4.1.3 steps 字段结构（对齐 DagNodeData）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | string | ✅ | 节点 ID，格式 `{type_lower}-{random_6}` 如 `filter-a3b2c1` |
| `type` | string | ✅ | 节点类型，去 `STEP_TYPE_` 前缀，如 `FILTER` / `JOIN` / `SOURCE` / `SINK` |
| `label` | string | ✅ | 节点显示名（中文） |
| `config` | object | ✅ | 节点配置，key 因 type 而异（见附录 A） |
| `sqlFragment` | string | ⚡ | SQL 代码（SQL 类节点必填），保存时合并到 `genericConfig.sql` |
| `description` | string | ⚡ | 中文加工逻辑描述，保存时进 `genericConfig.description` |

> **不传 position**：前端 `buildFlowGraph()` 按拓扑深度自动分层布局（X=320, Y=130 间距），AI 传 position 会冲突。

#### 4.1.4 edges 字段结构（对齐 DagEdgeData）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `source` | string | ✅ | 源节点 ID |
| `target` | string | ✅ | 目标节点 ID |

> **注意**：前端用 `source/target`（非 `from/to`），边 ID 由前端生成：`e-${source}-${target}`

### 4.2 前端对接改动

| 当前 (Mock) | 改造后 (Agent) |
|------------|---------------|
| `pipelineApi.aiGenerateDag(prompt, existingNodeIds)` | Agent SSE `/api/dag-assist` |
| 返回固定 `{ steps, edges }` | Agent ReAct 调工具后 SSE 流式返回 |
| 无上下文 | Session 多轮对话 |

### 4.3 新增 Agent API

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/dag-assist` | DAG 编辑 AI 助手入口（SSE 流式） |
| POST | `/api/dag-assist/sessions` | 创建 DAG 编辑会话 |
| GET | `/api/dag-assist/sessions/{id}/history` | 获取会话历史 |

### 4.4 依赖的 web-app API（2026-05-12 实测验证通过）

> 认证: `Authorization: Bearer admin-mock-token`
> 配置: config.local.yaml → `web_app.base_url=http://127.0.0.1:6682`

#### Pipeline CRUD（路径不带 projectId）

| API | 方法 | 路径 | 响应解包 |
|-----|------|------|---------|
| 详情 | GET | `/api/v1/pipelines/{id}` | `data.data.pipeline` (双层嵌套) |
| 列表 | GET | `/api/v1/pipelines` | 需 `X-Project-Id` header |
| 创建 | POST | `/api/v1/pipelines` | body: `{ pipeline: { metadata, execution_config, sources, steps, sinks } }` |
| 更新 | PUT | `/api/v1/pipelines/{id}` | body 同创建 |
| 删除 | DELETE | `/api/v1/pipelines/{id}` | `{ success: true }` |

#### Pipeline 执行（路径带 projectId）

| API | 方法 | 路径 | 注意 |
|-----|------|------|------|
| 运行 | POST | `/api/v1/projects/{pid}/fabric/pipelines/{id}/run` | **必须 body** `{"mode":"FULL"}` |
| 执行历史 | GET | `/api/v1/projects/{pid}/fabric/pipelines/{id}/runs` | `data.runs[]` |

#### DAG 校验与沙箱

| API | 方法 | 路径 | Content-Type | body |
|-----|------|------|-------------|------|
| DSL 校验 | POST | `/api/v1/pipelines/validate` | `text/plain` | YAML 字符串 |
| DSL 生成 | POST | `/api/v1/pipelines/generate-dsl` | JSON | `{ pipeline_id, pipeline_name, steps, edges }` |
| 沙箱节点 | POST | `/api/v1/pipelines/{id}/execute-node` | JSON | `{ node_id, yaml_dsl, max_rows }` |
| 沙箱全流程 | POST | `/api/v1/pipelines/sandbox-run` | JSON | `{ yamlDsl, maxRows }` |

#### 数据源

| API | 方法 | 路径 |
|-----|------|------|
| 数据源列表 | GET | `/api/v1/projects/{pid}/datasources` |
| 表列表 | GET | `/api/v1/projects/{pid}/datasources/{dsId}/metadata` |
| 表字段 | GET | `/api/v1/projects/{pid}/datasources/{dsId}/metadata/{tableName}/columns` |

#### Proto 数据结构

```
pipeline.metadata:  { id, name, owner, description, version, labels{}, project_id }
pipeline.sources[]: { id, name, type(SOURCE_TYPE_*), connection_id, table }
pipeline.steps[]:   { step_id, name, type(STEP_TYPE_*), inputs[], generic_config{} }
pipeline.sinks[]:   { id, name, type(SINK_TYPE_*), connection_id, input, target_table, write_mode }
```

> `generic_config` 是 step 配置容器，前端编辑器把 mappings/condition/sql 等全部塞进这里。
> Proto type 前缀如 `STEP_TYPE_TRANSFORM`，前端去前缀为 `TRANSFORM`。

---

## 5. Technical Design

### 5.1 工具清单

#### 新增工具（dag_editing_tools.py）

| 工具名 | 职责 | 输入 | 输出 |
|--------|------|------|------|
| `read_dag_state` | 读取当前画布上的节点和边 | `pipeline_id` | `{ nodes, edges, schemas }` |
| `add_dag_node` | 添加一个或多个节点到 DAG | `nodes[], edges[]` | `{ steps, edges }` |
| `modify_dag_node` | 修改已有节点的配置 | `node_id, config` | `{ updated_node }` |
| `remove_dag_node` | 删除节点并自动重连 | `node_id` | `{ removed, reconnected_edges }` |
| `generate_full_dag` | 基于 Source 自动生成完整 ETL | `source_schemas` | `{ steps, edges, explanation }` |
| `rewire_dag_edge` | 修改连线关系 | `remove_edges[], add_edges[]` | `{ edges }` |

#### 新增工具（dag_export_tools.py）

| 工具名 | 职责 | 输入 | 输出 |
|--------|------|------|------|
| `export_flink_sql` | 整个 DAG 导出为 Flink SQL | `dag_state` | `{ sql_script }` |
| `optimize_sql` | 分析并优化节点 SQL | `dag_state` | `{ suggestions[] }` |
| `parse_sql_to_dag` | SQL 拆解为 DAG 节点 | `sql_text` | `{ steps, edges }` |

#### 新增工具（dag_execution_tools.py）

| 工具名 | 职责 | 输入 | 输出 |
|--------|------|------|------|
| `sandbox_run_node` | 单节点沙箱执行 | `pipeline_id, node_id` | `{ status, result_preview }` |
| `sandbox_run_all` | 全流程沙箱测试 | `pipeline_id` | `{ results[] }` |

#### 复用已有工具

| 工具名 | 来源 | 用途 |
|--------|------|------|
| `validate_dag` | validate_dag.py | DAG 拓扑校验 |
| `list_datasources` | datasource_tools.py | 查数据源列表 |
| `list_tables` | datasource_tools.py | 查表清单 |
| `get_table_columns` | datasource_tools.py | 查表字段 Schema |
| `query_schema` | query_schema.py | 查本体类型（ONTOLOGY_MAPPING 用） |

### 5.2 Skill 设计

```
workflow-engine-demo/src/backend/agent/skills/dag_editing/
├── skill.yaml          # Skill 元数据
└── prompt.md           # DAG 编排专用 system prompt
```

`prompt.md` 核心内容：
- 14 种节点类型的完整参数结构（让 LLM 知道 FILTER 要填 condition、JOIN 要填 join_type + keys 等）
- Flink SQL 语法速查（CREATE TABLE、INSERT INTO、TUMBLE/HOP 窗口函数等）
- 输出格式强约束（`{ steps, edges }` JSON，不是 YAML）
- 增量 vs 全量规则（有 existingNodeIds 时只返回新节点，否则全量生成）

### 5.3 前端对接架构

> **代码基准**：`df-pipeline-dag.vue` `sendChat()` 第 1322-1338 行（当前 Mock 实现）

```
df-pipeline-dag.vue
  │
  ├── sendChat(text)                          ← 需重写为 SSE 消费
  │     ├── pushHistory()                     ← 操作前压 undo 栈（已有机制，第 999 行）
  │     ├── 收集 dag_state（过滤 is_gold_mirror 虚拟节点）
  │     │     → { nodes: [{id, type, label, config}], edges: [{source, target}] }
  │     ├── POST /api/dag-assist (SSE)
  │     │     body: { prompt: text, dag_state, session_id, pipeline_id }
  │     └── 消费 SSE 事件流
  │           ├── event: token      → 追加到 chatMsgs 聊天气泡
  │           ├── event: tool_call  → 显示"正在执行: xxx"灰色提示
  │           ├── event: dag_update → 按 action 分发：
  │           │     ├── add:         dagNodes.push(步骤) + dagEdges.push(边)
  │           │     ├── modify:      找到节点 → 合并 config / sqlFragment / description
  │           │     ├── remove:      dagNodes.filter + dagEdges.filter + 追加新边
  │           │     └── replace_all: dagNodes.value = [...] + dagEdges.value = [...]
  │           │     步骤字段含 config + sqlFragment + description（非空壳）
  │           │     → watch 自动触发 buildFlowGraph() 重绘（无需传 position）
  │           └── event: done       → chatSending=false, 记录 session_id
  │
  ├── 快捷命令按钮（8 个，第 117-126 行）
  │     → applyQuickCommand(cmd) → chatInput = cmd.prompt → sendChat()
  │
  └── 规则约束
        - AI 不操作 is_gold_mirror=true 的虚拟节点
        - AI 不删除 SOURCE 节点（数据锚点）
        - 所有操作前 pushHistory() → 用户可 Ctrl+Z 撤销
```

**关键设计**：
- 前端把当前 DAG 状态（过滤虚拟节点后）作为上下文传给 Agent
- Agent 工具返回 `{ action, steps, edges }` 指令，前端按 action 分发操作
- position 不传 — `buildFlowGraph()` 按拓扑深度自动布局
- 每个 step 必须携带 `config`（非空 `{}`）+ `sqlFragment`（SQL 类节点），前端直接渲染到节点配置面板

---

## 6. Dependencies

### 6.1 Internal Dependencies

| Dependency | Module | Status | Notes |
|------------|--------|--------|-------|
| Agent ReAct Planner | planner.py | ✅ 已有 | 复用 Session + SSE |
| ToolRegistry | tool_registry.py | ✅ 已有 | 注册新工具 |
| Skill Loader | skill_loader.py | ✅ 已有 | 加载 dag_editing skill |
| 数据源工具 | datasource_tools.py | ✅ 已有 | 查表/查字段 |
| DAG 校验工具 | validate_dag.py | ✅ 已有 | 拓扑校验 |
| web-app Pipeline API | FabricPipelineController | ✅ 已有 | 保存/校验/执行 |
| web-app 数据源 API | DatasourceController | ✅ 已有 | Schema 查询 |

### 6.2 External Dependencies

| Dependency | Provider | Status |
|------------|----------|--------|
| LLM API (qwen-plus) | 通义千问 | ✅ 已接入 |

---

## 7. Risks & Mitigations

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| LLM 生成的 Flink SQL 语法错误 | High | Medium | 生成后自动调 validate_dag 校验，错误时自动修复重试 |
| 复杂 DAG（>10 节点）生成不准 | Medium | Medium | 分步生成：先骨架后细节；限制单次生成不超过 5 个节点 |
| 前端 DAG 状态与 Agent 不同步 | Low | High | 每次请求传完整 dag_state，不依赖 Agent 缓存 |
| Prompt 过长导致 LLM 超时 | Low | Medium | Skill prompt 控制在 2000 token 以内；节点类型按需加载 |

---

## 8. Success Metrics

| Metric | Current | Target | Measurement |
|--------|---------|--------|-------------|
| AI 生成 DAG 可用率 | 0%（Mock） | > 80% | 生成后校验通过 + 沙箱执行成功 |
| 构建 Pipeline 平均时间 | ~15min（手动） | < 5min（AI 辅助） | 从打开页面到沙箱测试通过 |
| 快捷命令覆盖率 | 0/8 | 8/8 | 全部 8 个快捷命令有真实 LLM 响应 |
| 用户满意度 | N/A | > 4.0/5 | 内部测试反馈 |

---

## 9. Timeline

| Milestone | Target Date | Status |
|-----------|-------------|--------|
| PRD Review | 2026-05-12 | ⬜ |
| Sprint 1: P0 核心工具 + Skill | 2026-05-13 ~ 2026-05-15 | ⬜ |
| Sprint 2: P1 扩展工具 + 前端对接 | 2026-05-16 ~ 2026-05-18 | ⬜ |
| Sprint 3: P2 高级功能 + 集成测试 | 2026-05-19 ~ 2026-05-20 | ⬜ |
| Release | 2026-05-21 | ⬜ |

---

## 10. Open Questions

- [ ] AI 生成的节点 position 如何计算？前端自动排布 or Agent 计算坐标？
- [ ] 是否需要支持"AI 自动修复校验错误"的闭环（校验失败 → 自动改 → 重新校验）？
- [ ] dag_state 传输量较大时（>20 节点），是否需要做压缩或只传增量？
- [ ] 沙箱测试是否需要 AI 自动解读结果并给出改进建议？

---

## Changelog

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-05-12 | 丁昂 | Initial version |

---

## Appendix

### A. 节点类型速查（proto StepType 完整枚举 + 前端 config 字段）

> **来源**：`proto/plane_f/pipeline_engine.proto` StepType enum + `df-pipeline-dag.vue` `generateMockSql()` 第 192-228 行 + 保存序列化第 914-923 行

#### 非 Step 节点（SOURCE / SINK）

| 类型 | 中文名 | config 字段（来自前端代码实测） | 保存路径 |
|------|--------|-------------------------------|---------|
| SOURCE | 数据源 | `connection_id`, `ds_type`, `ds_name`, `table` | proto `SourceDefinition` |
| SINK | 输出 | `sink_type`, `write_mode`, `target_object_type`, `target_table`, `connection_id`, `is_gold_mirror`, `is_bronze_disabled` | proto `SinkDefinition` |

#### Step 节点（保存到 `genericConfig`）

| 类型 | 中文名 | config 关键字段（代码实证） | sqlFragment 模式 |
|------|--------|---------------------------|-----------------|
| FILTER | 过滤 | `conditions: [{field, operator, value}]` | `SELECT * FROM input WHERE {conditions}` |
| MAP | 映射 | `mappings: [{source, target}]` | `SELECT source AS target, ... FROM input` |
| JOIN | 关联 | `join_type`, `left_table`, `right_table`, `conditions: [{left, right}]` | `{type} JOIN ... ON a.left = b.right` |
| UNION | 合并 | `distinct: boolean` | `UNION [ALL]` |
| DEDUPLICATE | 去重 | `key_fields: string[]`, `order_by: string` | `ROW_NUMBER() OVER (PARTITION BY ... ORDER BY ...)` |
| GROUP_AGGREGATION | 分组聚合 | `group_by: string`, `aggregates: string`, `having?: string` | `GROUP BY ... HAVING ...` |
| WINDOW_AGGREGATION | 窗口聚合 | `time_column`, `window_type`, `window_size` | `TUMBLE/HOP/SESSION(...)` |
| SQL_TRANSFORM | SQL 转换 | `sql: string`（自由编写） | 用户自定义 SQL |
| TRANSFORM | 通用转换 | `sql: string`, `objectType?`, `mappings?` | 自由 SQL 或本体映射混合 |
| ONTOLOGY_MAPPING | 本体映射 | `target_object_type`, `field_mappings[]` | Ontology SDK 调用 |
| ONTOLOGY_LINK | 本体关系 | `link_type`, `source_object_type`, `target_object_type` | Ontology SDK 调用 |
| QUERY | 查询 | `sql: string` | `SELECT ... FROM ...` |
| WRITE | 写入 | `target_table`, `write_mode` | `INSERT INTO ...` |
| REASONING | 推理 | `model`, `prompt` | 调用 Plane D 推理引擎 |
| DECISION | 决策 | `rule_set`, `conditions` | 调用 Plane D 决策引擎 |
| ACTION | Action | `action_type`, `params` | 调用 Plane E Action |
| SUB_PIPELINE | 子 Pipeline | `pipeline_id` | 调用另一个 Pipeline |
| BRANCH | 分支 | `expression`, `true_branch`, `false_branch` | 条件路由 |
| WAIT | 等待 | `duration`, `cron` | 定时/等待 |
| ENTITY_RESOLUTION | 实体消歧 | `match_fields`, `threshold` | 跨源实体匹配 |

> **前端旧别名**：`MAP`（= 新的 TRANSFORM 子集）、`AGGREGATE`（= GROUP_AGGREGATION 别名），代码中保留向后兼容（`pipeline.ts` 第 37 行）
>
> **AI 生成优先级**：P0 阶段优先支持前 11 种（FILTER ~ ONTOLOGY_MAPPING），它们覆盖 95% 的 ETL 场景。REASONING / DECISION / ACTION / SUB_PIPELINE / BRANCH / WAIT 属于 P2 高级节点。
>
> **config → genericConfig 序列化规则**（代码实证 `df-pipeline-dag.vue` 第 914-923 行）：
> - `sqlFragment` 合并为 `genericConfig.sql`
> - `description` 合并为 `genericConfig.description`
> - `label` 合并为 `genericConfig.label`
> - 其余 config 字段原样展开到 `genericConfig`

### B. 现有 Agent 工具清单（可复用）

| 工具 | 文件 | DAG 场景用途 |
|------|------|-------------|
| `list_datasources` | datasource_tools.py | 查可用数据源 |
| `list_tables` | datasource_tools.py | 查数据源下的表 |
| `scan_table_columns` | datasource_tools.py | 查表 Schema（决定 JOIN key、FILTER 字段） |
| `validate_dag` | validate_dag.py | DAG 拓扑校验 |
| `list_object_types` | ontology_tools.py | 查本体类型（ONTOLOGY_MAPPING 节点配置） |
| `get_skill_detail` | skill_tools.py | 按需加载 DAG 编排领域知识 |
| `recall_memory` | memory_tools.py | 搜索历史成功案例 |

### C. 前端已有的 DAG 操作能力（可直接复用）

> 来源：`df-pipeline-dag.vue` 代码实测

| 能力 | 函数 / 机制 | 行号 | 说明 |
|------|-------------|------|------|
| 自动布局 | `buildFlowGraph()` | 510-560 | 按拓扑深度分层，X=320 Y=130 间距，AI 不需传 position |
| 删除节点 | `deleteSelectedNode()` | 1649-1663 | 删节点 + 清关联边，AI 可复用此逻辑 |
| Undo/Redo | `pushHistory()` / `undoDag()` / `redoDag()` | 991-1028 | AI 操作前 pushHistory()，用户可 Ctrl+Z 撤销 |
| DAG 快照 | `snapshotDag()` / `restoreDagSnapshot()` | 970-985 | JSON 序列化整个 DAG 状态 |
| SQL 生成 | `generateMockSql(step)` | 192-228 | 按 type+config 生成 SQL 片段，可作为 AI 生成参考 |
| DAG Dirty 检测 | `dagSnapshot` / `dagDirty` | 502-506 | 比对基线快照判断是否有未保存修改 |
| 金层镜像过滤 | `n.config.is_gold_mirror` | 278 | 虚拟节点，AI 不应操作 |
