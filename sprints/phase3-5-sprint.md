# Sprint: Planning Agent Phase 3-5 实现

> 基于 zhice-paas 架构对齐，完善 workflow-engine-demo 的 Planning Agent

## 背景

Phase 1-2 已完成 ReAct Loop 核心 + 3 Tools + 3 Skills。
本 Sprint 完成剩余所有设计目标，与 zhice-paas intelligence-plane 的模型和规范保持一致。

---

## Task 清单

### Phase 3: 补齐查询类 Tools（4 个）

- ✅ **T1**: `list_available_functions` — 查询可用 function_id
  - 对齐 zhice-paas FunctionExecutor 的 function_id 约定
  - 返回 function_id + 描述 + 参数签名
  - 支持关键词过滤（同 list_tools 模式）

- ✅ **T2**: `query_table_schema` — 查询数据表结构
  - Agent 写 FlinkSQL 节点时需要知道表有哪些列
  - 模拟返回表的列名 + 类型
  - 支持按表名查询

- ✅ **T3**: `estimate_cost` — 估算工作流执行成本
  - 对齐 zhice-paas 的 Cost/TokenCost/CostBudget 模型
  - 输入 YAML 文本，输出预估 token 消耗 + 时间 + 费用
  - 按节点类型分别估算（LLM 最贵，Condition 免费）

- ✅ **T4**: `search_similar_workflows` — 搜索历史工作流
  - 扫描 workflows/ 目录下已有 YAML 文件
  - 按关键词匹配 name + nodes 内容
  - 返回匹配的 workflow 摘要（id, name, node_count, 节点类型列表）
  - Agent 可作为 few-shot 参考

### Phase 4: Memory 系统

- ✅ **T5**: `memory_store.py` — 经验记忆存储
  - 三类记忆：成功案例 / 失败修正 / 用户偏好
  - JSON 文件持久化（`data/memory/` 目录）
  - 提供 save / search / list API
  - 成功案例：用户确认执行的 DAG → 自动存储
  - 失败修正：validate 失败 → 修正成功的 pair 存储

- ✅ **T6**: `save_to_memory` Tool — Agent 可主动保存经验
  - 注册为 Agent Tool，Agent 生成好 DAG 后可选调用
  - 保存 {user_input, yaml_text, metadata}

- ✅ **T7**: `recall_memory` Tool — Agent 可检索历史经验
  - 关键词搜索历史成功案例
  - 返回相似需求的 DAG 作为参考
  - 注入 planner.py 的 ReAct 循环（规划前自动召回）

- ✅ **T8**: Memory 自动化集成
  - planner.py: 规划成功后自动调 memory_store.save()
  - planner.py: 规划开始前自动 recall 相似案例注入 context
  - server.py: 用户确认执行工作流时触发案例保存

### Phase 5: 领域 Skills + 增强

- ✅ **T9**: 领域 Skill — `domain/supply-chain.md`
  - 供应链工作流规范（供应商评估、采购、物流）
  - 对齐 list_tools 中的 act-update-supplier-status 等

- ✅ **T10**: 领域 Skill — `domain/data-quality.md`
  - 数据治理工作流规范（质量检测、修复、告警）
  - 对齐 act-data-repair、act-trigger-pipeline

- ✅ **T11**: 增强 Skill — `error-handling-guide.md`
  - on_error 策略选择指南（RETRY/SKIP/FAIL）
  - 对齐 zhice-paas RetryPolicy + CompensationSpec 概念

- ✅ **T12**: 增强 Skill — `data-flow-conventions.md`
  - 节点间数据传递规范
  - ${node.outputs.field} 引用规则
  - 对齐 zhice-paas NodeOutput / StepArtifact 模型

---

## 依赖关系

```
T1~T4 并行（独立 Tools）
T5 先行 → T6, T7 依赖 T5 → T8 依赖 T6+T7
T9~T12 并行（独立 Skills，纯 Markdown）
```

## 验收标准

1. 每个 Tool 注册后 Agent 自动可见（`get_registry().list_names()` 包含）
2. Agent 实测能在规划中调用新 Tools（estimate_cost、search_similar_workflows）
3. Memory 持久化到文件，重启后可召回
4. 新 Skills 被 SkillLoader 正确匹配和加载
5. 全流程测试：输入需求 → Agent 规划 → 生成 DAG → 保存记忆 → 下次召回
