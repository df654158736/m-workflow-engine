---
name: prd-status
description: "PRD 发布版本追踪与需求点（AC）进度聚合。按发布版本和需求池组织 PRD，生成 PRD-STATUS.md 矩阵视图。状态机自下而上聚合 Task→AC→PRD→Release。"
---

# PRD 状态追踪（/prd-status）

## 核心模型

三级追踪颗粒度：

```
Release (v2026-04-30, v2026-05-30, pool)
  └─ PRD (PRD-001 用户管理)
       └─ AC (AC-001-01 需求点/验收单位)
            └─ Task (tasks-{gitid}.md 里 [x]/[ ] 的 checkbox)
```

**状态聚合方向**：Task → AC → PRD → Release（由 skill 自动算，人不手填进度）

**状态机**：

```
AC:  ⬜ 未开始 → 🟡 开发中 → 🟢 已自测 → ✅ 已验收 (PM 确认)
                                    ↓
                            🔴 验收未通过

PRD:  draft → reviewed → in-dev → delivered
                              ↓
                         deferred / archived
```

---

## 目录结构

```
sprints/backlog/requirements/
├── {domain}/                                     ← PRD 原文所在
│   └── PRD-001-User-Management.md
└── _releases/                                    ← 版本视图层（本 skill 管理）
    ├── v2026-04-30/
    │   ├── PRD-STATUS.md                         ← 自动生成
    │   └── release-plan.md                       ← 人手写
    ├── v2026-05-30/
    │   └── PRD-STATUS.md
    └── pool/
        └── PRD-STATUS.md                         ← 需求池视图
```

---

## 命令集

| 命令 | 作用 | 是否落盘 |
|------|------|---------|
| `/prd-status` | 全版本一屏概览 | 不落盘 |
| `/prd-status v2026-04-30` | 查看特定版本详情 | 不落盘 |
| `/prd-status prd PRD-001` | 查看 PRD 级进度 | 不落盘 |
| `/prd-status ac AC-001-01` | 查单个需求点详情 | 不落盘 |
| `/prd-status update` | 全量重算所有 PRD-STATUS.md | ✅ 落盘 |
| `/prd-status assign PRD-030 v2026-05-30` | 把 PRD 分配到版本 | ✅ 落盘 |
| `/prd-status mark-tested AC-001-01 "证据"` | 标 AC 自测通过 | ✅ 落盘 |
| `/prd-status accept AC-001-01` | PM 标 AC 验收通过 | ✅ 落盘 |
| `/prd-status reject AC-001-01 "理由"` | PM 标 AC 验收未通过 | ✅ 落盘 |
| `/prd-status check` | 一致性校验（六类异常） | 不落盘 |
| `/prd-status migrate` | 历史 PRD 批量加 frontmatter | ✅ 落盘 |

---

## 核心工作流

### `/prd-status update` — 核心聚合逻辑

```
1. 扫描所有 PRD
   glob: sprints/backlog/requirements/**/PRD-*.md
   解析 YAML frontmatter → {prd_id, release_version, status, priority, owners, ...}
   解析"## 需求点"章节 → AC 列表

2. 扫描所有任务文件
   glob: sprints/active/**/tasks-*.md
   解析每个 task 的 "关联需求点" 和 checkbox [x]/[ ]
   建立 AC → Task 反向索引

3. 为每个 AC 聚合状态
   - 关联 0 个 task        → ⬜ 未分配
   - 所有 checkbox [x]     → 🟢 已自测
   - 部分 [x]              → 🟡 开发中
   - 全部 [ ]              → ⬜ 已排期未开工

4. 为每个 PRD 聚合状态
   - 所有 P0/P1 AC ✅ → delivered
   - 有 AC 🟡/🟢     → in-dev
   - 全 ⬜           → planned

5. 按 release_version 分组渲染
   写入 _releases/v{日期}/PRD-STATUS.md
```

### `/prd-status check` — 六类异常

| 异常 | 检测方式 | 严重性 |
|------|---------|-------|
| 孤儿 Task | task 文件未写关联需求点 | 🔴 阻断 |
| 失踪 AC | task 引用了不存在的 AC ID | 🔴 阻断 |
| 未覆盖 AC | PRD in-dev 但某 P0 AC 无 task | 🟡 预警 |
| 状态漂移 | AC 标 ✅ 但关联 task 还有 ⬜ | 🔴 阻断 |
| 跨版本穿越 | task 在 v1 Wave 里但引用 v2 的 AC | 🟡 预警 |
| Changelog 缺失 | AC 描述变了但 changelog 未更新 | 🟡 预警 |

---

## PRD-STATUS.md 输出格式

```markdown
# PRD-STATUS — v2026-04-30

> **发布目标日期**: 2026-04-30
> **版本状态**: in-dev
> **生成时间**: 2026-04-16 14:32
> **总体进度**: 58% (7/12 PRD delivered, 85/120 AC 完成)

## PRD 进度总览

| PRD | 标题 | 优先级 | 状态 | AC 进度 | 开发负责人 | 风险 |
|-----|------|--------|------|--------|----------|------|
| PRD-001 | 用户管理 | P0 | ✅ delivered | 15/15 | dev-a | - |
| PRD-002 | 数据导入 | P0 | 🟡 in-dev | 8/12 | dev-b | - |
```

---

## 与其他 Skill 的集成

| Skill | 集成方式 |
|------|---------|
| `/doc-sync` | 末尾自动调用 `/prd-status update`（增量） |
| `/doc-sync-after-dev` | 末尾自动调用 `/prd-status update` + `/prd-status check` |
| `/sprint-management` | 创建 task 时强制写关联需求点 |

---

## 语言规则

**中文优先** — 与用户交互、PRD-STATUS.md 渲染、错误提示都用中文。专业术语保持英文。
