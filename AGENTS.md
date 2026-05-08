# AGENTS.md - Multi-Agent Collaboration Protocol

> **Version**: 1.0
> **Project**: Workflow Engine Demo

---

## 1. Project Overview

基于 Temporal + DAG + LLM 的智能工作流引擎，支持自然语言规划、多类型节点执行、人工审批与故障恢复。

### 1.1 项目结构

```
workflow-engine-demo/
├── AGENTS.md                    # 本文件：多 Agent 协作规范
├── PROGRESS.md                  # 项目整体进度追踪
├── CLAUDE.md                    # Claude Code 项目规则
├── .claude/                     # Claude Code 配置目录
│   ├── settings.json            # 权限配置
│   └── skills/                  # 自定义 Skills
├── docs/                        # 文档目录
│   ├── design/                  # 技术设计文档
│   │   └── 00-overview.md       # 架构总览
│   ├── specs/                   # 详细设计文档
│   └── templates/               # 文档模板
├── sprints/                     # Sprint 管理目录
│   ├── backlog/                 # 待办事项池
│   │   ├── requirements/        # 产品需求池
│   │   ├── tech-debt/           # 技术债务
│   │   ├── bugs/                # Bug 池
│   │   └── features/            # Feature 池
│   ├── active/                  # 当前活跃 Sprint
│   └── archive/                 # 已完成 Sprint 归档
├── run.py                       # 启动入口
├── config.yaml                  # 运行配置
├── pyproject.toml               # 依赖与构建
├── workflows/                   # YAML 工作流定义
└── src/
    ├── frontend/
    │   └── index.html           # Web UI（DAG 可视化 + 执行追踪）
    └── backend/
        ├── server.py            # FastAPI 服务
        ├── dsl_parser.py        # DSL 解析 + 拓扑排序
        ├── models.py            # 数据模型
        ├── routing.py           # 队列路由
        ├── spi.py               # 执行器接口
        ├── temporal/            # Temporal 编排
        ├── executors/           # 节点执行器（6 种）
        └── agent/               # Planning Agent（ReAct + Tools + Skills + Memory）
```

### 1.2 模块责任域

| 模块 | 职责 | 技术栈 | 目录 |
|------|------|--------|------|
| Server | REST API、WebSocket、配置管理 | FastAPI + Uvicorn | `src/backend/server.py` |
| DSL | 工作流定义解析与校验 | Pydantic + YAML | `src/backend/dsl_parser.py` |
| Temporal | 持久化 Workflow 编排 | temporalio | `src/backend/temporal/` |
| Executors | 节点执行（LLM/Tool/FlinkSQL/Function/Condition/Approval） | Python async | `src/backend/executors/` |
| Agent | 自然语言 → DAG 规划 | OpenAI SDK + Qwen | `src/backend/agent/` |
| Frontend | DAG 可视化 + 执行时间线 | Vanilla HTML/JS | `src/frontend/` |

---

## 2. Agent 身份识别

**核心原则**: Git 账号 = 身份标识。不需要 Agent 命名体系。

- GitID 从 `git config user.name` 派生：去空格 → 全小写
- 示例：`Zhang San` → `zhangsan`
- 每人的任务文件：`tasks-{gitid}.md`

---

## 3. 开工 Checklist（每次开始开发前必做）

```markdown
- [ ] 读 PROGRESS.md — 确认当前谁在做什么
- [ ] 读自己的 tasks-{gitid}.md — 确认待办任务
- [ ] 确认分支 — `git branch` 检查当前在正确的 feature branch
- [ ] 拉取最新 — `git pull --rebase origin <branch>`
- [ ] 读相关 SPEC — 确认详设与代码一致
```

---

## 4. 分支策略

| 分支类型 | 命名格式 | 示例 |
|---------|---------|------|
| Feature | `feature/{module}-{task}` | `feature/agent-memory-optimization` |
| Bugfix | `bugfix/{module}-{desc}` | `bugfix/temporal-signal-timeout` |
| Hotfix | `hotfix/{desc}` | `hotfix/api-cors-fix` |

---

## 5. 多 Session 协作规则

一人可以同时运行多个 Claude Code 终端，但需要：

1. **共享同一 Git 分支**: 所有终端都在同一个 feature branch
2. **避免同时编辑同一文件**: 多终端别同时改同一个文件
3. **提交前检查**: `git status` 确认无覆盖风险
4. **每次 push 前必须 pull --rebase**: 即使是自己的另一个终端刚 push 过

---

## 6. PR 审查规则

| PR 类型 | Review 要求 |
|---------|------------|
| 自己模块内的变更 | 自审 + CI 通过即可 |
| 共享文件（models / config / API 定义） | 对方 Review + CI 通过 |
| 跨模块变更 | 相关模块负责人 Review |

---

## 7. 冲突预防

| 规则 | 说明 |
|------|------|
| 一人一模块一分支 | 同一模块同一时间只有一个人有 active feature branch |
| 检查方法 | `git branch -r \| grep feature/{module}` |
| 违规处理 | 在 coordination.md 协调，后创建者让步 |
