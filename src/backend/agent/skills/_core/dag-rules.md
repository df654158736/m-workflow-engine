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
| `add` | 新增的节点 | 新增的边 | "加一个过滤节点" |
| `modify` | 被修改的节点（只含 id + 变化字段） | 变化的边（可选） | "把过滤条件改成 >100" |
| `remove` | 空，改用 `remove_node_ids: [...]` | 重连后的新边 | "删掉去重节点" |
| `replace_all` | 完整 DAG 的全部节点 | 完整 DAG 的全部边 | "帮我生成完整流程" |

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

## 需要更多细节时

调用 `get_skill_detail` 工具查询：
- `"dag-editing"` — action 协议详解 + 前端集成 + undo/redo 机制
  - section `"node-configs"` — 20 种节点的 config 字段详表（代码实证）
  - section `"flink-sql"` — Flink SQL 语法速查
