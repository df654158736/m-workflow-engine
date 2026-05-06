# DAG Planning Agent 设计

## 核心理念

仿照 Claude Code 的架构：**Agent = ReAct Loop + Tools + Skills**

- **ReAct Loop**：推理-行动-观察循环（不变的骨架）
- **Tools**：Agent 可调用的能力（可扩展，未来只加工具）
- **Skills**：领域知识注入（可扩展，未来只加 Skill 文件）

用户只需要添加 Tool 或 Skill，不需要改 Agent 核心代码。

---

## 架构图

```
┌──────────────────────────────────────────────────────────┐
│                    DAG Planning Agent                     │
│                                                          │
│  ┌────────────────────────────────────────────────────┐  │
│  │              ReAct Loop (核心骨架)                  │  │
│  │                                                    │  │
│  │   用户需求                                         │  │
│  │      ↓                                             │  │
│  │   ① Think: 分析需求，决定下一步动作                │  │
│  │      ↓                                             │  │
│  │   ② Act: 调用 Tool（或直接输出 YAML）             │  │
│  │      ↓                                             │  │
│  │   ③ Observe: 拿到 Tool 返回结果                   │  │
│  │      ↓                                             │  │
│  │   ④ 判断: 完成？→ 输出 / 未完成？→ 回到 ①        │  │
│  │                                                    │  │
│  │   最多 max_iterations 轮（默认 5）                 │  │
│  └────────────────────────────────────────────────────┘  │
│                         │                                │
│              ┌──────────┼──────────┐                     │
│              ▼          ▼          ▼                     │
│  ┌──────────────┐ ┌──────────┐ ┌────────────────┐       │
│  │    Tools     │ │  Skills  │ │    Memory      │       │
│  │  (能力扩展)  │ │ (知识扩展)│ │ (经验积累)     │       │
│  └──────────────┘ └──────────┘ └────────────────┘       │
└──────────────────────────────────────────────────────────┘
```

---

## 三层扩展机制

### 1. Tools（Agent 可调用的工具）

Agent 通过 function calling 调用，每个 Tool 有明确的 input/output schema。

| Tool | 功能 | 何时调用 |
|------|------|---------|
| `validate_dag` | 校验 YAML 的 DAG 合法性（环检测、孤立节点、引用完整性） | 每次生成/修改 YAML 后 |
| `list_available_tools` | 查询系统中可用的 tool_id 列表及其参数 | 需要 Tool 节点时 |
| `list_available_functions` | 查询可用的 function_id 及其签名 | 需要 Function 节点时 |
| `query_table_schema` | 查询数据表结构（列名、类型） | 需要写 FlinkSQL 时 |
| `check_output_compatibility` | 校验节点间 inputs/outputs 类型是否匹配 | 连接节点时 |
| `estimate_cost` | 估算工作流执行成本（token 消耗、时间） | 规划完成前 |
| `render_dag_preview` | 生成 DAG 可视化描述（确认结构正确） | 最终确认前 |
| `search_similar_workflows` | 搜索历史相似工作流作为参考 | 规划开始时 |

**扩展方式**：新建一个 Tool 类，注册到 ToolRegistry，Agent 自动可见。

### 2. Skills（领域知识）

以 Markdown 文件形式存放，Agent 规划前按需加载到 context。

```
skills/
├── dag-quality-rules.md         # DAG 质量规则（必须遵守）
├── node-type-guide.md           # 各节点类型的最佳实践
├── common-patterns.md           # 常见工作流模式（审批流、ETL、告警...）
├── error-handling-guide.md      # on_error 策略选择指南
├── data-flow-conventions.md     # 数据传递规范
└── domain/
    ├── supply-chain.md          # 供应链领域知识
    ├── data-quality.md          # 数据治理领域知识
    └── procurement.md           # 采购领域知识
```

**扩展方式**：新建 .md 文件放入 skills/ 目录，Agent 按需加载。

### 3. Memory（经验积累）

| 类型 | 内容 | 作用 |
|------|------|------|
| 成功案例 | 用户确认执行过的 DAG | few-shot 示例来源 |
| 失败修正 | 生成失败 → 修正成功的对话对 | 避免重复犯错 |
| 用户偏好 | 偏好的节点命名风格、审批人等 | 个性化输出 |

---

## ReAct Loop 详细设计

```python
class PlanningAgent:
    """DAG Planning Agent — ReAct Loop + Tools + Skills."""

    def __init__(self, llm_client, tool_registry, skill_loader):
        self.llm = llm_client
        self.tools = tool_registry       # 所有可用工具
        self.skills = skill_loader       # Skill 加载器
        self.max_iterations = 5

    async def plan(self, user_input: str) -> PlanResult:
        # 1. 加载相关 Skills
        context = self.skills.load_relevant(user_input)

        # 2. 构建初始 messages
        messages = [
            {"role": "system", "content": self._build_system_prompt(context)},
            {"role": "user", "content": user_input},
        ]

        # 3. ReAct Loop
        for i in range(self.max_iterations):
            response = await self.llm.chat(
                messages=messages,
                tools=self.tools.schemas(),  # function calling schema
            )

            # 如果 LLM 直接输出文本（认为完成了）
            if response.finish_reason == "stop":
                yaml_text = response.content
                return self._finalize(yaml_text)

            # 如果 LLM 调用了工具
            if response.finish_reason == "tool_calls":
                for tool_call in response.tool_calls:
                    result = await self.tools.execute(
                        tool_call.function.name,
                        tool_call.function.arguments,
                    )
                    messages.append(response.message)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(result),
                    })
                # 继续循环，让 LLM 看到工具结果后决定下一步

        return PlanResult(success=False, error="达到最大迭代次数")
```

---

## 关键设计决策

### Q: 为什么不是一次生成完就结束？

单次生成 → 质量完全依赖 prompt 工程，天花板很低。

ReAct 循环 → Agent 可以：
- 生成后自己调 `validate_dag` 检查
- 发现引用错误后自己修正
- 不确定时查 `list_available_tools` 确认
- 复杂需求分步规划（先拆步骤，再填细节）

### Q: Tools vs Skills 的边界？

| | Tools | Skills |
|--|-------|--------|
| 本质 | **能力** — Agent 能做什么 | **知识** — Agent 知道什么 |
| 形式 | 代码（有 input/output） | 文本（Markdown） |
| 触发 | Agent 主动调用 | 规划前自动注入 context |
| 举例 | `validate_dag()` 返回校验结果 | "Approval 节点后不应直接跟 Condition" |

### Q: 如何保证 DAG 质量？

质量保证是多层的：

```
Layer 1: Skills 注入    → LLM 生成时就遵循规范（预防）
Layer 2: validate_dag   → 结构合法性检查（基本功）
Layer 3: check_output   → 类型兼容性检查（语义级）
Layer 4: 自修正循环     → 发现错误 → 修复 → 重新检查（兜底）
Layer 5: 人工确认       → 用户看 DAG 预览后决定是否执行（最终关卡）
```

---

## 目录结构

```
src/backend/
├── agent/                          # ← 新增：Planning Agent
│   ├── __init__.py
│   ├── planner.py                  # ReAct Loop 核心
│   ├── tool_registry.py            # Tool 注册与发现
│   ├── skill_loader.py             # Skill 加载器
│   ├── memory_store.py             # 经验记忆
│   ├── tools/                      # 所有 Tools（可扩展）
│   │   ├── __init__.py
│   │   ├── validate_dag.py         # DAG 校验
│   │   ├── list_tools.py           # 查询可用工具
│   │   ├── list_functions.py       # 查询可用函数
│   │   ├── query_schema.py         # 查询表结构
│   │   ├── check_compatibility.py  # 输出兼容性检查
│   │   ├── estimate_cost.py        # 成本估算
│   │   └── search_workflows.py     # 搜索历史工作流
│   └── skills/                     # 所有 Skills（可扩展）
│       ├── dag-quality-rules.md
│       ├── node-type-guide.md
│       ├── common-patterns.md
│       └── domain/
│           └── supply-chain.md
├── server.py                       # API 层调用 agent.planner
├── ...
```

---

## 扩展示例

### 添加一个新 Tool（5 分钟）

```python
# src/backend/agent/tools/check_sql_syntax.py

from backend.agent.tool_registry import Tool, tool

@tool(
    name="check_sql_syntax",
    description="校验 FlinkSQL 语法是否合法，返回错误位置",
)
async def check_sql_syntax(sql: str) -> dict:
    """Agent 生成 FlinkSQL 节点后调用此工具确认语法正确。"""
    # 实际实现：调用 Flink SQL parser 或正则检查
    errors = _parse_flink_sql(sql)
    return {"valid": len(errors) == 0, "errors": errors}
```

注册后 Agent 自动可见，下次生成 FlinkSQL 节点时会主动调用校验。

### 添加一个新 Skill（2 分钟）

```markdown
<!-- src/backend/agent/skills/domain/finance.md -->
# 金融领域工作流规范

## 合规要求
- 涉及资金操作的节点，前面必须有 Approval 节点
- 金额超过 10 万的操作需要双人审批（两个串联 Approval）
- 所有金融数据查询必须带 audit_log 参数

## 常见模式
- 风控评估：数据采集 → AI 评分 → 阈值判断 → 审批/放行
- 对账流程：拉取双方数据 → 比对 → 差异标注 → 人工确认
```

放入 skills/domain/ 后，Agent 在处理金融相关需求时自动加载。

---

## 与当前 Demo 的差距

| 维度 | 当前 Demo | 目标设计 |
|------|----------|---------|
| LLM 调用 | 1 次，无反馈 | ReAct 循环，最多 5 轮 |
| 工具 | 无 | 8+ 个 Tools（可扩展） |
| 知识 | 固定 system prompt | Skills 文件按需加载 |
| 校验 | 生成后被动报错 | Agent 主动调用 validate_dag |
| 修正 | 失败就返回错误 | Agent 自己修正再验证 |
| 经验 | 无 | Memory 记录成功案例 |
| 扩展性 | 改 prompt | 加文件即可 |

---

## 实施路径

1. **Phase 1**: 实现 ReAct Loop 骨架 + `validate_dag` 工具 + 自修正循环
2. **Phase 2**: 添加 Skills 加载机制 + dag-quality-rules + node-type-guide
3. **Phase 3**: 添加 `list_tools` / `query_schema` 等查询类工具
4. **Phase 4**: 添加 Memory（成功案例存储 + few-shot 检索）
5. **Phase 5**: 领域 Skills 持续积累
