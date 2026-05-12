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

### 2. Skills（领域知识）— 三层按需加载架构

仿照 Claude Code 的 Skill 机制，将领域知识从"始终全量注入"改为"三层按需加载"，减少 85-91% 的 system prompt 体积。

```
skills/
├── _core/                       # Layer 1: 核心规则（始终注入 ~2K chars/mode）
│   ├── workflow-rules.md        #   输出字段表 + 7 条强制规则 + 4 条反模式
│   └── datafirst-rules.md       #   SQL→本体映射表 + 决策树 + 反模式
├── dag-quality/                 # Layer 3: Agent 通过 get_skill_detail 按需查询
│   ├── SKILL.md                 #   摘要 + frontmatter（含 catalog 字段）
│   └── references/              #   详细内容（section 粒度加载）
│       ├── validate-errors.md
│       └── fix-examples.md
├── node-types/                  # configs / registries / cost-table
├── common-patterns/             # 5 种 DAG 模式 + 反模式
├── data-flow/                   # 数据传递约定 + 错误处理策略
├── ontology-design/             # 设计示例 + AI 修正规则
├── exploration-flow/            # 6 步探查 few-shot + 属性补全
├── field-mapping/               # 字段映射规则
└── domain/
    ├── supply-chain/            # 供应链工作流模板
    └── data-quality/            # 数据质量工作流模板
```

**三层加载机制**：
- **Layer 1 (Core)**：始终注入 system prompt 的硬规则，按 mode 过滤
- **Layer 2 (Catalog)**：始终注入的索引表，Agent 看到技能名 + 一句话描述 + sections 列表
- **Layer 3 (Detail)**：Agent 通过 `get_skill_detail(skill_name, section)` 工具按需加载完整内容

**扩展方式**：新建 `skills/{name}/SKILL.md` + `references/*.md`，SkillLoader 自动扫描。

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
├── agent/                          # Planning Agent
│   ├── __init__.py
│   ├── planner.py                  # ReAct Loop 核心 + 两种模式入口
│   ├── session.py                  # Session 持久化（SQLite WAL）
│   ├── tool_registry.py            # Tool 注册 + Pydantic 校验 + 超时执行
│   ├── skill_loader.py             # 三层技能加载器（Core / Catalog / Detail）
│   ├── api_client.py               # zhice-paas REST API 客户端
│   ├── memory_store.py             # 经验记忆（JSON 文件）
│   ├── tools/                      # 29 个工具（@tool 装饰即注册）
│   │   ├── __init__.py
│   │   ├── validate_dag.py         # DAG 校验（Kahn 环检测）
│   │   ├── datasource_tools.py     # 3 个数据源查询工具
│   │   ├── ontology_tools.py       # 9 个本体操作工具
│   │   ├── fabric_tools.py         # 5 个数据编织工具
│   │   ├── interaction_tools.py    # ask_user_choice
│   │   ├── skill_tools.py          # get_skill_detail（三层技能 Layer 3 入口）
│   │   ├── memory_tools.py         # save_to_memory, recall_memory
│   │   └── ...                     # estimate_cost, search_workflows 等
│   └── skills/                     # 三层领域知识体系（26 .md 文件）
│       ├── _core/                  # Layer 1: 核心规则（始终注入）
│       │   ├── workflow-rules.md
│       │   └── datafirst-rules.md
│       ├── {skill}/                # Layer 3: 按需查询
│       │   ├── SKILL.md            # 摘要 + frontmatter
│       │   └── references/         # 详细内容（section 粒度）
│       └── domain/                 # 领域子目录
│           ├── supply-chain/
│           └── data-quality/
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

### 添加一个新 Skill（5 分钟）

1. 创建目录 `skills/domain/finance/`
2. 创建 `SKILL.md`（带 frontmatter）:

```markdown
---
name: domain/finance
description: 金融领域工作流规范和合规要求
mode: workflow
catalog: 金融合规规则（资金操作审批、风控评估模式）
sections:
  - compliance: 合规要求（审批规则、审计日志）
  - patterns: 常见金融工作流模式
---

金融领域要求所有资金操作前置 Approval 节点，金额 > 10 万需双人审批。
```

3. 创建 `references/compliance.md` 和 `references/patterns.md`（详细内容）

SkillLoader 自动扫描发现，Agent 在 catalog 中看到索引后按需调用 `get_skill_detail("domain/finance", "compliance")` 获取完整规则。

---

## 当前实现状态

| 维度 | 状态 | 说明 |
|------|------|------|
| ReAct Loop | ✅ 已实现 | 最多 15 轮，支持流式/非流式 |
| 工具 | ✅ 29 个 | Pydantic 校验 + 确认机制 + 超时保护 |
| 知识 | ✅ 三层架构 | Core + Catalog + Detail（按需加载，减少 85-91% token） |
| 校验 | ✅ 主动校验 | Agent 生成后自动调 validate_dag |
| 修正 | ✅ 自修正 | 发现错误后自动修正再验证 |
| 经验 | ✅ Memory | JSON 文件存储成功/修正/偏好记忆 |
| Session | ✅ SQLite | 多轮对话持久化 + 压缩 + 手动删除 |
| 两种模式 | ✅ | Workflow（无状态） + DataFirst（有状态） |

---

## 实施路径

1. **Phase 1**: 实现 ReAct Loop 骨架 + `validate_dag` 工具 + 自修正循环
2. **Phase 2**: 添加 Skills 加载机制 + dag-quality-rules + node-type-guide
3. **Phase 3**: 添加 `list_tools` / `query_schema` 等查询类工具
4. **Phase 4**: 添加 Memory（成功案例存储 + few-shot 检索）
5. **Phase 5**: 领域 Skills 持续积累
