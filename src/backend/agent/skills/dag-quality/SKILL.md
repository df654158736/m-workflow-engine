---
name: dag-quality
description: validate_dag 完整报错对照表 + 违规→修复 few-shot
mode: workflow
catalog: 生成/修复 DAG 时查看 validate_dag 报错和修复示例
sections:
  - validate-errors: validate_dag 17 个 error + 3 个 warning 完整对照表
  - fix-examples: 2 个违规→修复 few-shot（孤立节点/缺审批）
---

# DAG 质量校验详情

## validate_dag 报错速查（17 errors + 3 warnings）

调用 `get_skill_detail("dag-quality", "validate-errors")` 查看完整报错表。

## 违规→修复 Few-shot

调用 `get_skill_detail("dag-quality", "fix-examples")` 查看示例。

常见校验错误：
| validate_dag 报错 | 修复 |
|------------------|------|
| `节点 'X' 是孤立的` | 补充 edge 连接 |
| `edges[N] 的 from 'Y' 不在 nodes 中` | 检查 id 拼写 |
| `DAG 中存在环` | 断开回路 |
| `节点 'X' 的 type 'Y' 无效` | 用 7 种合法 type |
