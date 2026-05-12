# validate_dag 完整报错对照表

## errors（阻断性错误）

| 报错文本 | 原因 |
|---------|------|
| `YAML 语法错误: ...` | YAML 格式错误（缩进/引号/特殊字符） |
| `YAML 顶层必须是字典` | 传入的不是 YAML 对象 |
| `缺少 workflow_id 字段` | 顶层没有 workflow_id |
| `缺少 nodes 字段或为空` | 没有 nodes 或为空列表 |
| `nodes[N] 不是字典` | nodes 数组中某元素格式错误 |
| `nodes[N] 缺少 id` | 节点没有 id 字段 |
| `节点 id 重复: 'xxx'` | 两个节点用了相同 id |
| `节点 'xxx' 缺少 type` | 节点没有 type 字段 |
| `节点 'xxx' 的 type 'BadType' 无效，可选: ['Approval', 'Condition', 'FlinkSQL', 'Function', 'LLM', 'Sandbox', 'Tool']` | type 拼写错误或不支持 |
| `edges[N] 不是字典` | edges 数组中某元素格式错误 |
| `edges[N] 缺少 from` | edge 没有 from 字段 |
| `edges[N] 缺少 to` | edge 没有 to 字段 |
| `edges[N] 的 from 'xxx' 不在 nodes 中` | edge 的 from 引用了不存在的节点 |
| `edges[N] 的 to 'xxx' 不在 nodes 中` | edge 的 to 引用了不存在的节点 |
| `DAG 中存在环（循环依赖），无法拓扑排序` | 节点间形成闭环 |
| `节点 'xxx' 的 inputs.data 引用了不存在的节点 'yyy'` | `${yyy.outputs.field}` 中 yyy 不在 nodes 里 |
| `节点 'xxx' 的 inputs.data 引用了 'yyy'，但 'yyy' 不是其上游节点（数据流方向错误）` | 引用了下游或无关节点 |

## warnings（非阻断警告）

| 报错文本 | 原因 |
|---------|------|
| `有多个节点但没有 edges 定义，节点之间无依赖关系` | 节点间无依赖关系 |
| `节点 'xxx' 是孤立的（没有入边也没有出边）` | 忘记在 edges 连接 |
| `节点 'xxx' 没有 config 配置` | 节点缺少 config 块 |

## validate_dag 返回结构

```json
{
  "valid": true,
  "errors": [],
  "warnings": ["节点 'orphan_node' 是孤立的（没有入边也没有出边）"],
  "workflow_id": "wf-example",
  "node_count": 5,
  "edge_count": 4
}
```

## when 与 Condition expression 语法规范

以 `.get()` 格式为标准：

```yaml
# ✅ 标准写法
when: "risk_level_check.get('branch') == 'high_risk'"
when: "escalate_approval.get('decision') == 'APPROVED'"

# ⚠️ 兼容写法（功能等价）
when: "${risk_level_check.outputs.branch} == 'high_risk'"
```

Condition 的 expression 必须引用上游输出：
```yaml
# ✅ 正确
expression: "'critical' in str(text).lower()"

# ❌ 硬编码
expression: "True"
```
