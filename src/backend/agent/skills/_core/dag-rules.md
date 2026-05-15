---
name: dag-core
type: core
mode: dag
---

# Pipeline DAG 编辑核心规则（始终生效）

## 输出格式（唯一合法结构）

```json
{
  "action": "add | modify | remove | replace_all",
  "steps": [{ "id": "...", "type": "...", "label": "...", "config": {...}, "sqlFragment": "...", "description": "..." }],
  "edges": [{ "source": "node_a", "target": "node_b" }]
}
```

- `action` 必填，决定前端如何处理
- `edges` 用 `source` / `target`，**不是** `from` / `to`
- **不传 position** — 前端 `buildFlowGraph()` 自动按拓扑深度布局（X=320, Y=130 间距）

## action 语义

| action | steps 含义 | edges 含义 | 场景 |
|--------|-----------|-----------|------|
| `add` | 新增的节点 | **改动后的完整边列表**（原有保留边 + 新增边） | "加一个过滤节点"、"在 A 和 B 之间插入 C" |
| `modify` | 被修改的节点（只含 id + 变化字段） | 变化的边（可选） | "把过滤条件改成 >100" |
| `remove` | 空，改用 `remove_node_ids: [...]` | 重连后的新边 | "删掉去重节点" |
| `replace_all` | 完整 DAG 的全部节点 | 完整 DAG 的全部边 | "帮我生成完整流程" |

## ⚠️ add 操作的 edges 是完整边列表（最重要的规则）

`add_dag_node` 的 edges 参数是**改动后 DAG 的全部边**，前端会整体替换边数组。

操作步骤：
1. **先调 `read_dag_state`** 获取当前所有节点和边
2. 在当前边列表基础上，去掉被新节点取代的旧边，加入新节点的连线
3. 将结果作为 `edges` 传给 `add_dag_node`

示例：当前边为 `[A→B, B→C]`，要在 B 和 C 之间插入 D：
- edges = `[A→B, B→D, D→C]`（去掉旧的 B→C，加入 B→D 和 D→C）

## 节点 ID 规则

- 格式：`{type_lower}-{random_6chars}`（如 `filter-a3b2c1`、`join-x7y8z9`）
- **禁止** `step1` / `step2` / `node_1` 等无语义命名

## 强制规则

1. **config 必须非空** — 每个节点的 config 必须包含该类型的必填字段，不能返回 `{}`
2. **sqlFragment 必填**（SQL 类节点） — FILTER / JOIN / SQL_TRANSFORM / TRANSFORM / QUERY / DEDUPLICATE / GROUP_AGGREGATION / WINDOW_AGGREGATION / UNION 必须生成对应 Flink SQL
3. **description 必填** — 用中文描述该节点的加工逻辑
4. **不操作 SOURCE 节点** — SOURCE 是数据锚点，删后下游悬空无法恢复
5. **不操作 `is_gold_mirror=true` 节点** — 前端自动生成的金层镜像虚拟节点
6. **不操作 SINK 节点**（除 replace_all） — SINK 由前端自动管理

## type 取值（20 种，去 STEP_TYPE_ 前缀）

QUERY / TRANSFORM / WRITE / SQL_TRANSFORM / JOIN / UNION / WINDOW_AGGREGATION / GROUP_AGGREGATION / FILTER / DEDUPLICATE / DATA_QUALITY / ONTOLOGY_MAPPING / ONTOLOGY_LINK / REASONING / DECISION / ACTION / SUB_PIPELINE / BRANCH / WAIT / ENTITY_RESOLUTION

## genericConfig 序列化规则

前端保存时将 DagNodeData 转为 proto 的 `generic_config`：
- `sqlFragment` → `generic_config.sql`
- `description` → `generic_config.description`
- `label` → `generic_config.label`
- `config` 的其余字段展开进 `generic_config`

## 自动保存机制

- 每次 add / modify / remove / replace_all 操作后，**前端自动将完整 DAG 同步到 zhice-paas**（1.5 秒防抖），无需手动调 `save_dag`
- 用户说"保存"时直接回复"每次编辑已自动同步到 zhice-paas"
- `save_dag` 仅作为自动保存失败时的兜底手段
- **保存使用 `PUT /api/v1/pipelines/{id}/draft`（updateDraft 端点）**，直接就地更新，pipeline ID 不变

## Pipeline 生命周期（必须知道）

- **DRAFT**（草稿）：可编辑 DAG、可发布，**不可运行**
- **PUBLISHED**（已发布）：只读、可运行、可 Fork，**不可编辑 DAG**（需先 unpublish 恢复为 DRAFT）
- 编辑前必须检查 `pipeline_status`，PUBLISHED 状态调 save_dag 会被拒绝
- 状态转换工具：`publish_pipeline`（DRAFT→PUBLISHED）、`unpublish_pipeline`（PUBLISHED→DRAFT）
- Fork：`fork_pipeline` 创建独立 DRAFT 副本，不影响原 Pipeline

## 保存端点变更

- **旧端点**：`PUT /api/v1/pipelines/{id}`（updatePipeline）— 内部做 delete+recreate，ID 会变
- **新端点**：`PUT /api/v1/pipelines/{id}/draft`（updateDraft）— 就地更新，ID 不变
- `save_dag` 已改用新端点，pipeline ID 保持稳定
- **连续多次编辑必须防抖**（1.5 秒），避免并发保存竞态

## remove_dag_node 注意事项

- 只需传 `node_id` + `pipeline_id`，工具内部自动从 API 读取当前 DAG 状态并计算重连
- **不要让 LLM 构造 dag_state 参数** — LLM 容易遗漏字段导致校验失败

## 需要更多细节时

调用 `get_skill_detail` 工具查询：
- `"dag-editing"` — action 协议详解 + 前端集成 + undo/redo 机制
  - section `"node-configs"` — 20 种节点的 config 字段详表（代码实证）
  - section `"flink-sql"` — Flink SQL 语法速查
