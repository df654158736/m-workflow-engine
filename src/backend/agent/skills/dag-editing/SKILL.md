---
name: dag-editing
description: Pipeline DAG 编辑协议 — action 类型、20 种节点 config、前端集成约束、undo/redo 机制
mode: dag
catalog: Pipeline DAG 编辑时查看 action 协议、节点 config 字段详表、前端集成规则
sections:
  - node-configs: 20 种 Pipeline 节点类型的 config 字段详表（基于 proto + 前端代码实证）
  - flink-sql: Flink SQL 语法速查（CREATE TABLE / INSERT INTO / 窗口函数 / 去重）
---

# Pipeline DAG 编辑 Skill

## 概述

本 Skill 覆盖 Pipeline DAG 编辑器的 AI 助手场景：用户通过自然语言指令读取、新增、修改、删除 DAG 节点，AI 返回结构化 `dag_update` 事件，前端按 action 类型分发执行。

## 前端数据模型

```typescript
interface DagNodeData {
  id: string
  type: StepType | 'SOURCE' | 'SINK'
  label: string
  config: Record<string, unknown>
  description: string    // 中文加工逻辑描述
  sqlFragment: string    // Flink SQL 代码
  status: 'unconfigured' | 'configured' | 'test_passed' | 'test_failed'
  outputSchema: ColumnDef[]
}
interface DagEdgeData { id: string; source: string; target: string }
```

## action 协议详解

### add — 新增节点（含插入）

用户说"加一个过滤节点"、"在 JOIN 后面加聚合"、"在 transform 和 sink 之间插入过滤"。

**edges 是改动后的完整边列表**，前端整体替换。先调 `read_dag_state` 获取当前边，在此基础上增删。

**尾部追加**示例（当前边: [src-df_order → sink-yyy]，在末尾添加过滤）：
```json
{
  "action": "add",
  "steps": [{
    "id": "filter-a3b2c1",
    "type": "FILTER",
    "label": "过滤无效订单",
    "config": { "conditions": [{ "field": "status", "operator": "!=", "value": "CANCELED" }] },
    "sqlFragment": "SELECT * FROM input\nWHERE status != 'CANCELED'",
    "description": "过滤掉已取消的订单"
  }],
  "edges": [
    { "source": "src-df_order", "target": "filter-a3b2c1" },
    { "source": "filter-a3b2c1", "target": "sink-yyy" }
  ]
}
```

**中间插入**示例（当前边: [src-order → transform-xxx, transform-xxx → sink-yyy]，在 transform 和 sink 之间插入过滤）：
```json
{
  "action": "add",
  "steps": [{
    "id": "filter-a3b2c1",
    "type": "FILTER",
    "label": "过滤 id=1",
    "config": { "condition": "id = 1" },
    "sqlFragment": "SELECT * FROM input WHERE id = 1",
    "description": "只保留 id=1 的记录"
  }],
  "edges": [
    { "source": "src-order", "target": "transform-xxx" },
    { "source": "transform-xxx", "target": "filter-a3b2c1" },
    { "source": "filter-a3b2c1", "target": "sink-yyy" }
  ]
}
```
注意：原来的 transform-xxx → sink-yyy 不在新 edges 中（被新节点取代），前端整体替换边数组。

### modify — 修改已有节点

用户说"把过滤条件改成金额大于100"、"修改 JOIN 条件"。

返回示例（只含变化字段 + id）：
```json
{
  "action": "modify",
  "steps": [{
    "id": "filter-a3b2c1",
    "config": { "conditions": [{ "field": "total_amount", "operator": ">", "value": "100" }] },
    "sqlFragment": "SELECT * FROM input\nWHERE total_amount > 100"
  }]
}
```

### remove — 删除节点

用户说"删掉去重节点"、"移除过滤步骤"。

返回示例（自动重连上下游）：
```json
{
  "action": "remove",
  "remove_node_ids": ["dedup-x7y8z9"],
  "edges": [{ "source": "filter-a3b2c1", "target": "agg-m4n5o6" }]
}
```

### replace_all — 整体替换

用户说"帮我生成完整的清洗流程"、"从头设计这个 Pipeline"。

返回完整 DAG 的所有 steps 和 edges。

## 前端集成要点

1. **Undo/Redo**：前端在执行任何 dag_update 前调用 `pushHistory()` 压入 undo 栈（最多 50 条），用户可 Ctrl+Z 撤销 AI 操作
2. **自动布局**：`buildFlowGraph()` 按拓扑深度自动计算位置（X=320, Y=130 间距），AI 不需要也不应该传 position
3. **边 ID 生成**：前端用 `e-${source}-${target}` 格式自动生成
4. **状态初始化**：新增节点 status 设为 `'configured'`（因为 AI 已填充 config）

## 保护规则

- SOURCE 节点：数据锚点，不可删除/修改 type，AI 可读取其 schema 信息
- SINK 节点：前端自动管理，AI 不操作（除 replace_all 场景）
- `is_gold_mirror=true` 节点：前端为金层镜像自动创建的虚拟节点，AI 完全忽略
- 读取 dag_state 时必须过滤掉上述虚拟节点再传给 LLM

## 持久化与生命周期（运维要点）

### 自动保存
- 前端在每次 dag_update（add/modify/remove/replace_all）后自动调 `PUT /api/v1/pipelines/{id}/draft` 同步到 zhice-paas
- 内置 1.5 秒防抖 + 并发锁：连续多次操作（如批量删除）只触发一次保存，避免竞态
- **使用 updateDraft 端点（非旧的 updatePipeline）**，就地更新，pipeline ID 保持不变

### Pipeline 生命周期
- **DRAFT** → 可编辑 DAG、可发布，不可运行
- **PUBLISHED** → 只读、可运行、可 Fork，不可编辑（需先 unpublish）
- 编辑前检查 `pipeline_status`，PUBLISHED 状态的 save 会被拒绝
- 工具：`publish_pipeline` / `unpublish_pipeline` / `fork_pipeline`

### 请求体格式
- 请求体格式与 zhice 前端一致：camelCase 字段名（`stepId`、`genericConfig`、`connectionId` 等）
