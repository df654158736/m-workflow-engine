# Tasks — 丁昂 (2026-05-12 Wave 1)

> **PRD**: [PRD-001-pipeline-dag-ai-assistant](../../../docs/prd/PRD-001-pipeline-dag-ai-assistant.md)
> **分支**: feature/530-dingang
> **目标**: Pipeline DAG AI 助手 — 从 Mock 到真实 LLM 驱动

---

## API 实测备忘（2026-05-12 验证通过）

> 所有请求需 `Authorization: Bearer admin-mock-token`。
> config.local.yaml 已配置：base_url=`http://127.0.0.1:6682`，project_id=`019dd21a-2337-7226-ac60-1d4ea9fd8ae7`。

### Pipeline CRUD（路径不带 projectId）

| API | 方法 | 路径 | 注意事项 |
|-----|------|------|---------|
| 详情 | GET | `/api/v1/pipelines/{id}` | 响应双层嵌套：`data.data.pipeline`；pipeline 内含 `metadata/sources/steps/sinks` |
| 列表 | GET | `/api/v1/pipelines` | 需 `X-Project-Id` header 才能返回数据 |
| 创建 | POST | `/api/v1/pipelines` | body: `{ pipeline: { metadata, execution_config, sources, steps, sinks } }` |
| 更新 | PUT | `/api/v1/pipelines/{id}` | body 同创建；可原样 GET→PUT 实现 round-trip |
| 删除 | DELETE | `/api/v1/pipelines/{id}` | 返回 `{ success: true }` |

### Pipeline 执行（路径带 projectId）

| API | 方法 | 路径 | 注意事项 |
|-----|------|------|---------|
| 运行 | POST | `/api/v1/projects/{pid}/fabric/pipelines/{id}/run` | **必须带 body** `{"mode":"FULL"}`，否则 400 |
| 取消 | POST | `/api/v1/projects/{pid}/fabric/pipelines/{id}/cancel` | — |
| 执行历史 | GET | `/api/v1/projects/{pid}/fabric/pipelines/{id}/runs` | 返回 `data.runs[]`，每条含 `status/startedAt` |

### DAG 校验与生成

| API | 方法 | 路径 | Content-Type | 注意事项 |
|-----|------|------|-------------|---------|
| DSL 校验 | POST | `/api/v1/pipelines/validate` | `text/plain` | body 为 YAML 字符串；返回 `{ valid, items[] }` |
| DSL 生成 | POST | `/api/v1/pipelines/generate-dsl` | `application/json` | body: `{ pipeline_id, pipeline_name, steps, edges }`；返回 `{ yaml_dsl }` |
| 沙箱执行节点 | POST | `/api/v1/pipelines/{id}/execute-node` | `application/json` | body: `{ node_id, yaml_dsl, max_rows }`；返回 `{ status, data, error }` |
| 沙箱全流程 | POST | `/api/v1/pipelines/sandbox-run` | `application/json` | body: `{ yamlDsl, maxRows }`；返回 `{ stepResults[] }` |

### 数据源

| API | 方法 | 路径 | 注意事项 |
|-----|------|------|---------|
| 数据源列表 | GET | `/api/v1/projects/{pid}/datasources` | 返回 `data.data[]`，含 `id/name/type/schema_name/table_count` |
| 表列表 | GET | `/api/v1/projects/{pid}/datasources/{dsId}/metadata` | 返回 `data.data[]`，每项 `{ name }` |
| 表字段 | GET | `/api/v1/projects/{pid}/datasources/{dsId}/metadata/{tableName}/columns` | 返回 `data.data[]`，每列 `{ name, type, nullable, primary_key, comment }` |

### Pipeline 数据结构（proto 映射）

```
pipeline.metadata:  { id, name, owner, description, version, labels, project_id }
pipeline.sources[]: { id, name, type(SOURCE_TYPE_*), connection_id, table }
pipeline.steps[]:   { step_id, name, type(STEP_TYPE_*), inputs[], generic_config{} }
pipeline.sinks[]:   { id, name, type(SINK_TYPE_*), connection_id, input, target_table, write_mode }
```

- `generic_config` 是 step 的核心配置容器，前端编辑器把 mappings/condition/sql 等全部塞进这里
- type 前缀：proto 用 `STEP_TYPE_TRANSFORM`，前端去前缀变 `TRANSFORM`
- `step_id` 在 proto 中叫 `step_id`，前端映射为 `id`

### 现有测试 Pipeline 参考

```
Pipeline: 019e1623-2873-7a8d-abaa-309a9c343618 (fabric-Order)
  SOURCE: src-df_order → type=POSTGRESQL, table=df_order, conn=019dd21d-17f8-7967-a04f-3305c95af788
  STEP:   transform-df_order → type=TRANSFORM, inputs=[src-df_order], config_keys=[objectType, mappings]
  SINK:   sink-Order → type=ICEBERG, target=proj_*_bronze.order_raw

数据源: 019dd21d-17f8-7967-a04f-3305c95af788 (192.168.2.60, schema=demo_fabric_e2e)
  表: df_customer, df_order, df_order_item, df_product, df_product_category, df_region, df_daily_sales_metric
  df_order 字段: id(bigint PK), order_no(varchar), customer_id(bigint), total_amount(numeric),
                  status(varchar: PENDING/PAID/SHIPPED/DELIVERED/CANCELED), payment_method(varchar), ...
```

---

## Sprint 1: P0 核心工具 + Skill（5/13 ~ 5/15）

### T1: DAG 编排 Skill 定义
- ⬜ 创建 `skills/dag-editing/SKILL.md` — 三层架构 Layer 3，frontmatter 含 `mode: dag`
- ⬜ 创建 `skills/dag-editing/references/node-configs.md` — **20 种节点类型的 config 字段详表**
  - 数据来源：`proto/plane_f/pipeline_engine.proto` StepType enum + `df-pipeline-dag.vue` `generateMockSql()` 第 192-228 行
  - P0 优先覆盖前 11 种（FILTER ~ ONTOLOGY_MAPPING），P2 覆盖 REASONING / DECISION / ACTION 等
  - 每种节点的 config 字段必须基于前端代码实证（见 PRD 附录 A），不可凭猜测
- ⬜ 创建 `skills/dag-editing/references/flink-sql.md` — Flink SQL 语法速查（CREATE TABLE / INSERT INTO / 窗口函数）
- ⬜ 编写 SKILL.md 核心内容：
  - 输出格式约束：`{ action, steps: [{id,type,label,config,sqlFragment,description}], edges: [{source,target}] }`
  - **action 类型**：`add | modify | remove | replace_all`（见 PRD §4.1.2）
  - **不传 position**：前端 `buildFlowGraph()` 自动布局
  - **不操作 `is_gold_mirror=true` 虚拟节点**
  - **不删除 SOURCE 节点**
- ⬜ 在 `planner.py` 中注册 DAG 模式入口（`/api/dag-assist`），Skill 自动加载
  - `_core/dag-rules.md` 新增 Layer 1 核心规则（始终注入）
  - `DAG_TOOLS` 白名单集合
- ⬜ 验证：发送消息能触发 dag_editing Skill，system prompt 正确注入

### T2: read_dag_state 工具
- ⬜ 新建 `tools/dag_editing_tools.py`
- ⬜ 实现 `read_dag_state(pipeline_id)`:
  - 调 `GET /api/v1/pipelines/{id}`（需 auth token）
  - **解包路径**: `resp.data.data.pipeline`（双层嵌套，PRD §4.4 已实测）
  - 遍历 `sources[]` 提取 `{ id, type, connection_id, table }`
  - 遍历 `steps[]` 提取 `{ step_id→id, type(去STEP_TYPE_前缀), inputs, generic_config→config }`
  - 遍历 `sinks[]` 提取 `{ id, type, connection_id, target_table, input }`
  - 根据 `inputs` 和 `input` 字段重建 edges 列表
- ⬜ 返回结构化数据：`{ nodes: [{id, type, label, config}], edges: [{source, target}], source_schemas: {...} }`
  - **注意**：不传 position（前端自动布局）；edges 用 `source/target`（非 `from/to`）
- ⬜ 支持前端直传 dag_state 模式（优先用请求 body 中的 dag_state，无则走 API）
  - dag_state 来源：`df-pipeline-dag.vue` 第 1164-1170 行的 dagNodes/dagEdges 序列化
  - 需过滤 `is_gold_mirror=true` 的虚拟节点
- ⬜ 对每个 SOURCE 节点自动调 `GET .../datasources/{dsId}/metadata/{table}/columns` 填充 schema
  - 列字段：`{ name, type, nullable, primary_key, comment }`（已实测）

### T3: add_dag_node 工具
- ⬜ 实现 `add_dag_node(nodes[], edges[])` — 接受 LLM 生成的节点定义，校验后返回
- ⬜ 支持 P0 的 11 种 Step 类型（config 字段基于代码实证，见 PRD 附录 A）：
  - FILTER: `conditions: [{field, operator, value}]`
  - MAP: `mappings: [{source, target}]`
  - JOIN: `join_type, left_table, right_table, conditions: [{left, right}]`
  - UNION: `distinct: boolean`
  - DEDUPLICATE: `key_fields: string[], order_by: string`
  - GROUP_AGGREGATION: `group_by, aggregates, having?`
  - WINDOW_AGGREGATION: `time_column, window_type, window_size`
  - SQL_TRANSFORM / TRANSFORM: `sql: string`
  - ONTOLOGY_MAPPING: `target_object_type, field_mappings[]`
  - QUERY: `sql: string`
- ⬜ 自动生成节点 ID（格式 `{type_lower}-{random_6chars}`，如 `filter-a3b2c1`）
- ⬜ **不计算 position**（前端 `buildFlowGraph()` 自动按拓扑分层布局）
- ⬜ 返回 `{ action: "add", steps, edges }` 格式
  - steps 每项: `{ id, type, label, config, sqlFragment, description }`
  - edges 每项: `{ source, target }`
  - **config 必须非空** — 带具体字段值，不是 `{}`
  - **sqlFragment** — SQL 类节点必须生成对应的 Flink SQL 片段

### T4: generate_full_dag 工具
- ⬜ 实现 `generate_full_dag(source_schemas)` — 核心差异化工具
- ⬜ 输入：已有 SOURCE 节点的表 Schema
  - 可通过 `read_dag_state` 获取 SOURCE 节点的 `connection_id` + `table`
  - 再调 `GET .../datasources/{dsId}/metadata/{table}/columns` 获取每列 `{ name, type, nullable, primary_key, comment }`
- ⬜ LLM 推理：根据表结构推荐清洗步骤（NULL 过滤 / 类型转换 / 去重 / 聚合）
- ⬜ 自动生成 Transform 链 + SINK 节点 + 完整连线
- ⬜ 返回 `{ action: "replace_all", steps, edges, explanation }`
  - 每个 step 含完整 `config` + `sqlFragment` + `description`

### T5: server.py 路由注册 + dag_update SSE 协议
- ⬜ 新增 `POST /api/dag-assist` 路由（SSE 流式）
- ⬜ 请求 body 接受 `{ prompt, dag_state, session_id, pipeline_id }` 四个字段
  - `dag_state`: `{ nodes[], edges[], pipeline_id?, pipeline_name? }` — 前端当前画布快照
  - 需过滤 `is_gold_mirror=true` 的虚拟节点后传入
  - 如果 `dag_state` 非空，注入到 Planner 的工具上下文中，`read_dag_state` 优先从中读取
- ⬜ SSE 事件类型:
  - `token` — 流式文字
  - `tool_call` — 工具调用提示（`{ name, arguments }`）
  - `dag_update` — **含 action 字段**的 DAG 操作指令（见 PRD §4.1.2）
    ```json
    { "action": "add|modify|remove|replace_all", "steps": [...], "edges": [...] }
    ```
    - `add`: 新增节点和边
    - `modify`: steps 中只含被修改的节点（id + 变化的字段）
    - `remove`: `remove_node_ids: ["xxx"]` + 重连后的新 edges
    - `replace_all`: 替换整个 DAG（"生成完整流程"场景）
  - `done` — 完成（含 `session_id` + `total_tokens`）
- ⬜ 复用已有 Session 机制 — DAG 模式的 session 也走 `SessionStore`

---

## Sprint 2: P1 扩展工具 + 前端对接（5/16 ~ 5/18）

### T6: modify_dag_node + remove_dag_node
- ⬜ `modify_dag_node(node_id, config, sqlFragment?, description?)` — 修改已有节点的 SQL / 条件 / 映射
  - 从 dag_state 中找到目标节点，合并 config + sqlFragment + description
  - 返回 `{ action: "modify", steps: [{ id, config, sqlFragment?, description? }] }`
  - **config 字段格式必须与该节点 type 的规范一致**（见 PRD 附录 A），不能返回不存在的字段
- ⬜ `remove_dag_node(node_id)` — 删除节点，自动将其上游连到下游
  - 找到该节点的所有入边 sources 和出边 targets
  - 删除节点和关联边，为每个 (source, target) 对创建新边
  - 返回 `{ action: "remove", remove_node_ids: ["xxx"], edges: [{source, target}] }`
  - **禁止删除 SOURCE 节点**（数据锚点，删后下游悬空无法恢复）
  - **禁止删除 `is_gold_mirror=true` 虚拟节点**（前端自动生成的金层镜像）
- ⬜ 两个工具均需在 dag_state 中操作，不直接调后端 API（画布修改由前端负责持久化）

### T7: export_flink_sql 工具
- ⬜ `export_flink_sql(dag_state)` — 整个 DAG 转 Flink SQL 脚本
- ⬜ 拓扑排序遍历节点，每个节点生成对应 SQL 片段:
  - SOURCE → `CREATE TABLE {table} (...) WITH ('connector' = 'jdbc', 'url' = '...', 'table-name' = '{table}')`
  - FILTER → `CREATE VIEW {id} AS SELECT * FROM {input} WHERE {condition}`
  - JOIN → `CREATE VIEW {id} AS SELECT ... FROM {left} {join_type} JOIN {right} ON {condition}`
  - GROUP_AGGREGATION → `CREATE VIEW {id} AS SELECT {group_by}, {aggregates} FROM {input} GROUP BY {group_by}`
  - SINK → `INSERT INTO {target_table} SELECT * FROM {input}`
- ⬜ 生成完整可执行脚本，注释标注每步对应的节点 ID
- ⬜ 也可走 LLM 辅助生成（把 dag_state + 模板一起交给 LLM）

### T8: optimize_sql 工具
- ⬜ `optimize_sql(dag_state)` — 分析每个 SQL 节点
- ⬜ 检查常见性能问题：SELECT *、缺少分区裁剪、窗口过大、JOIN 无等值条件
- ⬜ 返回 `{ suggestions: [{ node_id, issue, recommendation, optimized_sql }] }`
- ⬜ 纯 LLM 推理（把所有节点的 config.sql / config.condition 拼接后发给 LLM 分析）

### T9: 前端 AI 面板对接 Agent SSE

> **改动基准**：`df-pipeline-dag.vue` `sendChat()` 第 1322-1338 行（当前 await Mock 实现）

#### T9.1: sendChat() 重写为 SSE 消费
- ⬜ 当前 Mock 调用: `await pipelineApi.aiGenerateDag(prompt, existingNodeIds)` → 固定返回空
- ⬜ 改为 `fetch + ReadableStream`（不用 EventSource，因为需要 POST body）:
  ```js
  const resp = await fetch('/api/dag-assist', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ prompt: text, dag_state: dagState, session_id: sessionId.value, pipeline_id: pipelineId.value }),
  })
  const reader = resp.body.getReader()
  // 逐行解析 SSE：data: {...}\n\n
  ```

#### T9.2: dag_state 收集（过滤虚拟节点）
- ⬜ 发送前收集当前 DAG 状态:
  ```js
  // 基于实际代码结构：dagNodes = ref<DagNodeData[]>，dagEdges = ref<DagEdgeData[]>
  const realNodes = dagNodes.value.filter(n => !n.config.is_gold_mirror)  // 过滤金层镜像虚拟节点
  const realIds = new Set(realNodes.map(n => n.id))
  const dagState = {
    pipeline_id: pipelineId.value,
    pipeline_name: pipelineName.value,
    nodes: realNodes.map(n => ({ id: n.id, type: n.type, label: n.label, config: n.config, sqlFragment: n.sqlFragment, description: n.description })),
    edges: dagEdges.value.filter(e => realIds.has(e.source) && realIds.has(e.target)).map(e => ({ source: e.source, target: e.target })),
  }
  ```

#### T9.3: SSE 事件消费 — 按 action 分发
- ⬜ `token` → 追加到 chatMsgs 聊天气泡（流式打字效果）
- ⬜ `tool_call` → 显示"正在执行: xxx"灰色提示
- ⬜ `dag_update` → **先 pushHistory() 再按 action 分发**:
  ```js
  pushHistory()  // 压 undo 栈，用户可 Ctrl+Z 撤销 AI 操作
  switch (data.action) {
    case 'add':
      data.steps.forEach(n => dagNodes.value.push({
        id: n.id, type: n.type, label: n.label,
        config: n.config || {},           // AI 返回的真实 config（非空 {}）
        description: n.description || '',
        sqlFragment: n.sqlFragment || '',  // AI 生成的 SQL
        status: 'configured',
        outputSchema: [],
        stepIndex: ..., engine: ...
      }))
      data.edges.forEach(e => dagEdges.value.push({ id: `e-${e.source}-${e.target}`, source: e.source, target: e.target }))
      break
    case 'modify':
      data.steps.forEach(upd => {
        const node = dagNodes.value.find(n => n.id === upd.id)
        if (node) {
          if (upd.config) Object.assign(node.config, upd.config)
          if (upd.sqlFragment) node.sqlFragment = upd.sqlFragment
          if (upd.description) node.description = upd.description
        }
      })
      break
    case 'remove':
      const removeIds = new Set(data.remove_node_ids || [])
      dagNodes.value = dagNodes.value.filter(n => !removeIds.has(n.id))
      dagEdges.value = dagEdges.value.filter(e => !removeIds.has(e.source) && !removeIds.has(e.target))
      data.edges?.forEach(e => dagEdges.value.push({ id: `e-${e.source}-${e.target}`, ...e }))
      break
    case 'replace_all':
      dagNodes.value = data.steps.map(n => ({ ...defaultNode, ...n }))
      dagEdges.value = data.edges.map(e => ({ id: `e-${e.source}-${e.target}`, ...e }))
      break
  }
  // watch 自动触发 buildFlowGraph() 重绘
  ```
- ⬜ `done` → `chatSending = false`，保存 `session_id` 到 ref
- ⬜ SSE 错误处理：连接断开时显示错误提示，不 crash

#### T9.4: Session 管理
- ⬜ `sessionId` ref：首次返回的 `done` 事件中包含 `session_id`，后续请求带上
- ⬜ 刷新页面：session_id 存 localStorage，恢复时自动带上

#### T9.5: 快捷命令（无需改动 — 已有 8 个，文案准确）
- ⬜ 验证：8 个快捷命令按钮（第 117-126 行）通过 `applyQuickCommand` → `sendChat()` 调用，无需改文案
  - 实际文案（代码实证）：
    1. "在当前 Pipeline 中添加一个过滤节点，过滤掉 status 为 CANCELLED 的记录"
    2. "在最后一个节点前添加一个去重节点，按主键去重"
    3. "添加一个 LEFT JOIN 节点，关联 customers 表和 orders 表"
    4. "根据当前数据源自动生成完整的 ETL 流程：过滤→清洗→去重→映射→写入"
    5. "分析当前 Pipeline 的 SQL 性能，给出优化建议"
    6. "在写入前添加数据质量检查节点，校验必填字段和数据类型"
    7. "用中文解释当前 Pipeline 每个节点的作用和数据流向"
    8. "将当前 Pipeline 导出为完整的 Flink SQL 语句"

#### T9.6: vite proxy 配置
- ⬜ vite.config.ts 添加 proxy: `/api/dag-assist` → Agent 后端 `http://127.0.0.1:8686`
  - 保留原有 proxy 配置不变（`/api/v1` → web-app:6682）

---

## Sprint 3: P2 高级功能 + 集成测试（5/19 ~ 5/20）

### T10: sandbox_run 工具
- ⬜ `sandbox_run_node(pipeline_id, node_id)`:
  - 先调 `POST /api/v1/pipelines/generate-dsl` 生成完整 YAML（需要 pipeline_id + steps + edges）
  - 再调 `POST /api/v1/pipelines/{id}/execute-node`，body: `{ node_id, yaml_dsl, max_rows: 50 }`
  - 返回 `{ status, row_count, output_schema[], data[][], error }`
- ⬜ `sandbox_run_all(pipeline_id)`:
  - 调 `POST /api/v1/pipelines/sandbox-run`，body: `{ yamlDsl, maxRows: 30 }`
  - 返回 `{ status, totalDurationMs, stepResults: [{ stepId, status, outputRows, sampleData }] }`
- ⬜ 错误处理：沙箱执行失败时返回 `error` 字段，Agent 可据此建议修改

### T11: parse_sql_to_dag + rewire_dag_edge
- ⬜ `parse_sql_to_dag(sql_text)` — 解析 Flink SQL 为 DAG 节点
  - 正则提取 FROM / WHERE / GROUP BY / INSERT INTO
  - LLM 辅助：复杂嵌套 SQL 交给 LLM 拆解
  - 返回 `{ steps, edges }`
- ⬜ `rewire_dag_edge(remove_edges[], add_edges[])` — 修改连线关系
  - 校验：不允许环（DFS 检测）、SOURCE 不能有入边、SINK 必须有入边
  - 返回 `{ edges }` 更新后的完整边列表

### T12: 集成测试
- ⬜ 启动 web-app + Agent 后端
- ⬜ 快捷命令逐个测试:
  1. 添加过滤 — 验证 FILTER 节点生成 + 连线正确
  2. 添加去重 — 验证 DEDUPLICATE 节点 + key_fields 配置
  3. 添加 JOIN — 验证双输入 + join_type/keys 配置
  4. 生成完整流程 — 验证从 SOURCE 到 SINK 全链路生成
  5. 优化 SQL — 验证分析建议可读且 node_id 准确
  6. 数据质量 — 验证节点插入（占位）
  7. 解释流程 — 验证自然语言描述准确
  8. 导出 Flink SQL — 验证生成的 SQL 语法合法
- ⬜ 自由对话测试：修改节点 / 删除节点 / 多轮追问
- ⬜ 边界测试：空画布生成 / 复杂 DAG（>10 节点）/ 校验失败自动修复
- ⬜ 前端画布渲染验证：生成的节点位置合理、连线正确、可沙箱执行

---

## 验收标准

| 标准 | 说明 |
|------|------|
| ✅ 8/8 快捷命令 | 全部 8 个快捷命令有真实 LLM 响应，非 Mock |
| ✅ 自由对话 | 支持"加节点/改配置/删节点/解释/优化"等自然语言指令 |
| ✅ 生成质量 | AI 生成的 DAG 通过 validate_dag 校验率 > 80% |
| ✅ 前端渲染 | 生成的节点能正确显示在画布上，连线正确，可交互编辑 |
| ✅ Session 多轮 | 支持多轮对话，上下文不丢失 |
| ✅ 不改 zhice-paas | 所有改动在 workflow-engine-demo 和 web-ui 对接层 |
