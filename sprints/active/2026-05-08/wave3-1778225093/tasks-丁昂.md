# Tasks — 丁昂 — 2026-05-08 Wave3

> **Sprint**: 2026-05-08
> **模块**: Backend / Frontend / Agent
> **分支**: `feature/agent-production-hardening`（继续 Wave1/2 分支）
> **设计依据**: 无详设（功能补全，不涉及架构变更）
> **预估工时**: 0.5 人日
> **分配人**: 丁昂
>
> **关联需求点**:
>   - SR-01 后端历史查询端点
>   - SR-02 前端 Session 持久化 + 页面加载回填

---

## 开工前必读（现状核对）

> 接手前必须确认以下代码现状，防止踩坑：

- [ ] Wave2 P1 改动已提交（流式响应 + 并行工具调用）
- [ ] SessionStore 已有 SQLite 持久化（`session.py`）
- [ ] `Session.messages` 包含完整的 system/user/tool_call/tool_result/assistant 消息
- [ ] 读过 PROGRESS.md 确认无冲突工作

---

## Tasks

### T1: 后端历史查询端点 (SR-01)

**目标**: 新增 API 端点，根据 session_id 返回可供前端渲染的对话历史。

**交付物**:
- `src/backend/server.py` — 新增 `GET /api/datafirst/sessions/{session_id}/history`

**验收**:
- [x] 返回 session 中 user 和 assistant 消息（过滤掉 system / tool_call / tool_result 内部消息）
- [x] session 不存在时返回 404
- [x] 返回 session_id 和 created_at 供前端使用
- [x] tool_calls_log 附在响应中（可选展示工具调用记录）

---

### T2: 前端 Session 持久化 + 页面加载回填 (SR-02)

**目标**: 刷新页面后自动恢复上一次对话的聊天记录和 session_id。

**交付物**:
- `src/frontend/index.html` — localStorage 读写 + 页面加载回填逻辑

**验收**:
- [x] 对话时自动将 session_id 存入 localStorage
- [x] 页面加载时检查 localStorage 中的 session_id，调用 T1 端点获取历史
- [x] 历史消息按 user / agent 角色正确回填到 Chat UI
- [x] session 过期或不存在时自动清除 localStorage，显示新对话
- [x] "重置对话"按钮同时清除 localStorage
- [x] 多 Tab 不冲突（同一 key 即可）

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
- [ ] PROGRESS.md 已更新
- [ ] `/doc-sync-after-dev` 已执行
- [ ] PR 已创建

---

## 风险 / 遗留

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| Session 过期后前端仍持有旧 session_id | 回填失败 | API 返回 404 时清除 localStorage，显示新对话 |
| messages 中含大量 tool_result 内容 | 历史接口响应过大 | 只返回 user/assistant 消息，tool 细节走 tool_calls_log 摘要 |
