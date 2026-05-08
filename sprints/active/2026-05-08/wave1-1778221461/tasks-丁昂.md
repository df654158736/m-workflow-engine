# Tasks — 丁昂 — 2026-05-08 Wave1

> **Sprint**: 2026-05-08
> **模块**: Backend / Agent
> **分支**: `feature/agent-production-hardening`
> **设计依据**: SPEC-agent-prod-hardening（待编写）
> **预估工时**: 1 人日
> **分配人**: 丁昂
>
> **关联需求点**:
>   - TD-01 Session 持久化到 SQLite
>   - TD-02 写操作代码层拦截
>   - TD-03 工具执行超时
>
> **关联详设**: docs/specs/SPEC-agent-prod-hardening.md

---

## 开工前必读（现状核对）

> 接手前必须确认以下代码现状，防止踩坑：

- [ ] 读过关联 SPEC，确认与代码一致
- [ ] 检查分支是否已存在：`git branch -r | grep feature/agent`
- [ ] 读过 PROGRESS.md 确认无冲突工作
- [ ] 本地代码已 `git pull --rebase origin main`

---

## Tasks

### T1: Session 持久化到 SQLite (TD-01)

**目标**: 进程重启不丢失用户多轮对话，用 SQLite 替代纯内存 dict。

**交付物**:
- `src/backend/agent/session.py` — 改写 SessionStore，底层用 SQLite
- `tests/test_session_persist.py` — 持久化测试

**验收**:
- [x] Session 创建后写入 SQLite
- [x] 进程重启后 get(session_id) 能恢复完整 messages
- [x] 过期 Session 自动清理仍生效
- [x] compact() 压缩后的 messages 正确持久化
- [ ] 单元测试覆盖

---

### T2: 写操作代码层拦截 (TD-02)

**目标**: 标记为危险的工具（create/delete/update）在代码层强制确认，防止 LLM 跳过确认直接执行。

**交付物**:
- `src/backend/agent/tool_registry.py` — 新增 `requires_confirmation` 标记 + 拦截逻辑
- `src/backend/agent/planner.py` — ReAct loop 处理确认中断
- `src/backend/server.py` — API 层透传确认态
- `src/frontend/index.html` — 确认弹窗 UI

**验收**:
- [x] `create_object_type` / `delete_object_type` 等写工具被标记
- [x] Agent 调用写工具时返回 `requires_confirmation` 而非直接执行
- [x] 前端展示确认弹窗，用户确认后工具才真正执行
- [x] 用户拒绝时 Agent 收到拒绝信息，继续对话
- [ ] 单元测试覆盖

---

### T3: 工具执行超时 (TD-03)

**目标**: 防止单个工具卡死导致整个 ReAct loop 无响应。

**交付物**:
- `src/backend/agent/tool_registry.py` — execute() 加 asyncio.wait_for 超时
- `src/backend/agent/planner.py` — _react_loop 整体超时

**验收**:
- [x] 单个工具超时 60s 后自动返回错误
- [x] 整个 ReAct loop 超时 120s 后返回错误
- [x] 超时错误信息清晰，Agent 能据此向用户解释
- [ ] 单元测试覆盖

---

## 技术红线自查（对齐 CLAUDE.md）

- [ ] 无硬编码密钥/密码/Token
- [ ] 无空 `except: pass` 块
- [ ] 全程 async/await，无同步阻塞
- [ ] 配置项走 config.yaml，不硬编码
- [ ] 不修改他人模块目录

---

## 合并前 Checklist（DoD）

- [ ] 所有 task checkbox 完成
- [ ] `ruff check src/` 通过
- [ ] `black --check src/ && isort --check src/` 通过
- [ ] `pytest` 全绿
- [ ] 新增代码覆盖率 ≥ 90%
- [ ] PROGRESS.md 已更新
- [ ] `/doc-sync-after-dev` 已执行
- [ ] PR 已创建

---

## 风险 / 遗留

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| SQLite 并发写入在高并发下可能成瓶颈 | Session 写入变慢 | WAL 模式 + 连接池；若不够再迁 Redis |
| 写操作拦截需前后端配合 | 前端需改动 | 先做后端拦截，前端可分步 |
