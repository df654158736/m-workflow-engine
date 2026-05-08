# 交付验收规范

> **适用范围**：所有 Sprint 任务文件（`tasks-{gitid}.md`）
> **核心原则**：测试是验收的前提，覆盖率是底线，DoD 是合并门槛

---

## 1. 测试分层

| 层 | 必选/可选 | 触发条件 | 工具 |
|----|---------|---------|------|
| **单元测试** | 必选 | 任何代码变更 | pytest / vitest |
| **集成测试** | 按需 | 涉及外部系统（DB/API） | pytest + testcontainers |
| **E2E 测试** | 按需 | 跨模块（Backend + Frontend） | playwright / cypress |
| **场景测试** | 按需 | 核心业务流程 | `/scenario-testing` |

---

## 2. 覆盖率门槛

| 范围 | 门槛 |
|------|------|
| 新增代码 | ≥ 90% |
| 核心模块 | ≥ 80% |
| 整体项目 | ≥ 70%（渐进提升） |

---

## 3. 特殊场景测试策略

| 场景 | 策略 |
|------|------|
| 外部 API 调用 | Mock（返回固定响应 + 模拟超时/错误） |
| 数据库操作 | SQLite in-memory 或 Testcontainers |
| 文件操作 | 使用 `tmp_path` fixture（pytest） |
| 异步操作 | 使用 `pytest-asyncio` |
| 前端组件 | `@testing-library/react` + vitest |

---

## 4. 反模式（禁止）

| 反模式 | 说明 |
|--------|------|
| 跳过失败测试 | 不得删除或 skip 失败的测试来"通过" |
| 空断言 | 不得写 `assert True` 凑覆盖率 |
| 空 catch/except | 不得吞掉异常 |
| 硬编码测试数据 | 不得依赖特定环境的数据 |

---

## 5. 代码质量门

| 检查项 | 工具 | 级别 |
|--------|------|------|
| Python lint | ruff | error |
| Python format | black + isort | error |
| Python typecheck | mypy / pyright | error |
| TypeScript lint | eslint | error |
| TypeScript typecheck | tsc --noEmit | error |

---

## 6. 安全检查

- [ ] 无硬编码密钥/密码/Token
- [ ] SQL 查询使用参数化（防注入）
- [ ] API 输入有校验（Pydantic model）
- [ ] 敏感数据不出现在日志中

---

## 7. Definition of Done（合并前 10 条复核）

1. [ ] 所有 task checkbox ✅
2. [ ] lint + typecheck 全通过
3. [ ] 单元测试全绿
4. [ ] 新增代码覆盖率 ≥ 90%
5. [ ] 无新增安全漏洞
6. [ ] API 文档已更新（如有 API 变更）
7. [ ] 设计文档已同步（`/doc-sync-after-dev`）
8. [ ] PROGRESS.md 已更新
9. [ ] PR 已创建、CI 通过
10. [ ] 无 console error / warning
