# Tasks — {Git User} — {YYYY-MM-DD} Wave{N}

> **Sprint**: {YYYY-MM-DD}
> **模块**: {Backend / Frontend / ...}
> **分支**: `feature/{module}-{task-name}`
> **设计依据**: {SPEC 编号或"无详设"}
> **预估工时**: {N} 人日
> **分配人**: {gitid}
>
> **关联需求点**:
>   - AC-XXX-01 {需求点标题}
>   - AC-XXX-02 {需求点标题}
>
> **关联详设**: SPEC-XXX §X.X

---

## 开工前必读（现状核对）

> 接手前必须确认以下代码现状，防止踩坑：

- [ ] 读过关联 SPEC，确认与代码一致
- [ ] 检查分支是否已存在：`git branch -r | grep feature/{module}`
- [ ] 读过 PROGRESS.md 确认无冲突工作
- [ ] 本地代码已 `git pull --rebase origin main`

---

## Tasks

### T1: {任务标题}

**目标**: {一句话描述}

**交付物**:
- `backend/services/xxx.py` — 新增
- `backend/tests/test_xxx.py` — 新增

**验收**:
- [ ] {功能验收点 1} (AC-XXX-01)
- [ ] {功能验收点 2} (AC-XXX-01)
- [ ] 单元测试覆盖 (AC-XXX-01)

---

### T2: {任务标题}

**目标**: {一句话描述}

**交付物**:
- `frontend/src/pages/xxx.tsx` — 新增

**验收**:
- [ ] {功能验收点} (AC-XXX-02)
- [ ] UI 手动验证通过 (AC-XXX-02)

---

## 技术红线自查（对齐 CLAUDE.md）

- [ ] 无硬编码密钥/密码/Token
- [ ] 无空 catch/except 块
- [ ] 无 `as any` / `@ts-ignore`（TypeScript 项目）
- [ ] 无 `except: pass`（Python 项目）
- [ ] Service 层不直接操作数据库（通过 Repository）
- [ ] 配置项走配置文件，不硬编码

---

## 合并前 Checklist（DoD）

- [ ] 所有 task checkbox ✅
- [ ] lint 检查通过
- [ ] 类型检查通过
- [ ] 单元测试全绿
- [ ] 新增代码覆盖率 ≥ 90%
- [ ] PROGRESS.md 已更新
- [ ] `/doc-sync-after-dev` 已执行
- [ ] PR 已创建

---

## 风险 / 遗留

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| {风险描述} | {影响} | {措施} |
