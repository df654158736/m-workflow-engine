---
name: sprint-management
description: 日期制无冲突 Sprint 管理（Wave 模式）。创建 sprint、添加任务、查看进度。
trigger: 用户提到"创建sprint"、"新建sprint"、"今天的任务"、"添加任务"、"加任务到sprint"、"sprint管理"、"新一波需求"、"加一波"、"下一波"、"wave"
---

# Sprint 管理（Wave 模式）

## 核心原则

1. **Sprint 按日期命名** — 目录名即日期（`YYYY-MM-DD`），无需协商编号
2. **每波需求一个 Wave 目录** — `wave{N}-{timestamp}/`，批次隔离
3. **每人一个任务文件** — `tasks-{gitid}.md`，只有本人编辑，零冲突
4. **Append-only 协调** — `coordination.md` 在日期级，只追加不修改他人条目

---

## 用户意图 → 操作映射

| 用户说 | 日期 | Wave 操作 |
|--------|------|-----------|
| "新建 sprint" / "创建 sprint" | **当天** | 创建日期目录 + **wave1** |
| "加任务到 sprint" | **当天** | 加入**最新 wave** |
| "新一波需求" / "加一波" / "下一波" | **当天** | 创建**新 wave**（N+1） |
| "新建 sprint 20260313" | **2026-03-13** | 创建日期目录 + **wave1** |
| "查看 sprint 进度" | **当天** | 读取所有 wave 的 tasks-*.md |

---

## 目录结构

```
sprints/
├── backlog/
├── active/
│   └── 2026-03-20/                    ← 日期目录
│       ├── README.md                  ← 当天总览
│       ├── coordination.md            ← 跨人协调（append-only）
│       ├── wave1-1710900000/          ← 第1波（timestamp防冲突）
│       │   ├── README.md             ← 波次范围描述
│       │   └── tasks-{gitid}.md      ← {Git User} 的任务
│       └── wave2-1710920000/
│           └── tasks-{gitid}.md
└── archive/
```

---

## 操作流程

### 创建新 Sprint（当天第一波）

1. 确认当前日期（`date +%Y-%m-%d`）
2. 确认 Git 用户名（`git config user.name`）→ 推导 gitid
3. 创建目录：`sprints/active/{YYYY-MM-DD}/`
4. 创建 `README.md`（当天总览）
5. 创建 `wave1-{timestamp}/`
6. 创建 `wave1-{timestamp}/README.md`（波次描述）
7. 创建 `wave1-{timestamp}/tasks-{gitid}.md`（任务文件）

### 任务文件格式（tasks-{gitid}.md）

> **默认使用模板**：[`sprints/_templates/tasks-template.md`](../../../sprints/_templates/tasks-template.md)
> 创建任务文件时**直接拷贝该模板**改写，确保字段完整 + 自动继承交付验收规范。

模板已内置：
- 元信息块（Sprint / 模块 / 分支 / 设计依据 / 工时 / 分配人）
- "开工前必读"现状核对段（防止接手者踩坑）
- 任务清单 T1~Tn 的"目标 / 交付物 / 验收"三段式
- 技术红线自查（对齐 CLAUDE.md）
- 合并前 Checklist（对齐 [交付验收规范 §7 DoD](../../../sprints/_templates/ACCEPTANCE-CRITERIA.md#7-definition-of-done合并前-10-条复核)）
- Wave 级风险 / 遗留

**简版（仅"已有大任务文件、临时追加小事项"时可用）**：

```markdown
# Tasks — {Git User} — {YYYY-MM-DD} Wave{N}

## Active
- ⬜ [TASK-ID] 任务描述 — 关键点说明

## Completed
- ✅ [TASK-ID] 已完成任务

## Blocked
- 🔴 [TASK-ID] 被阻塞的任务 — 原因
```

> ⚠️ **新建 Wave 一律用完整模板**，不要用简版。

### 默认验收规范（强制继承）

所有新建 `tasks-{gitid}.md` 默认适用 [`sprints/_templates/ACCEPTANCE-CRITERIA.md`](../../../sprints/_templates/ACCEPTANCE-CRITERIA.md)：

- **测试分层底线**：单元测试必选；涉及外部系统加集成测试；跨模块加 E2E
- **覆盖率门槛**：新增代码 ≥ 90%；核心模块 ≥ 80%
- **DoD 10 条**：测试全绿、覆盖率达标、契约对齐、可观测性、配置回滚、文档同步、PR 模板、PROGRESS.md
- **反模式禁止**：`@Ignore` 跳测试、空 catch、`assertTrue(true)`、删失败测试

任务文件**只有显式覆盖**才能偏离规范（在任务文件内写明"本任务不适用 §X，原因：xxx"）。

### 新增一波需求

```bash
# 获取当前时间戳
timestamp=$(date +%s)
# 创建新 wave 目录
mkdir sprints/active/{date}/wave{N+1}-{timestamp}/
```

### 查看进度

```bash
# 查看当天所有人的任务
cat sprints/active/$(date +%Y-%m-%d)/wave*/tasks-*.md
```

---

## GitID 映射

| Git User | GitID |
|----------|-------|
<!-- TODO: 填写你的团队成员 -->
| `{Your Name}` | `{yourname}` |

---

## 完成任务后

将任务从 Active 移到 Completed：
```
- ⬜ [TASK-ID] 描述  →  - ✅ [TASK-ID] 描述
```

同时更新 `PROGRESS.md` 的 "Recently Completed" 部分。
