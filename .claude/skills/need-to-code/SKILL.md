---
name: need-to-code
description: |
  需求 ↔ 文档 ↔ 代码 全链路定位与改动地图生成器。给一句需求 / PRD / AC / SPEC / 代码文件，
  反向/正向跳转到所有关联文档与代码符号，输出"改动地图"（主要修改文件 + 影响面 + 同步文档清单 +
  推荐 next skill），让 Agent 在 30 秒内把"提需求"变成"知道动哪里"。
  AUTO-TRIGGER：用户说"我想改 XX"/"做 XX 功能要动哪里"/"PRD-XXX 怎么落"/"AC-XXX 在哪实现"/
  "这个文件属于哪个需求"/"XXX 影响面"/"这块代码怎么来的"，或 Agent 拿到一份新需求/Bug 准备开工
  但还没定位代码时。
user-invocable: true
---

# /need-to-code — 需求到代码的全链路定位

## 一句话定位

**输入**：自然语言需求 / PRD-XXX / AC-XXX / SPEC-XXX / 代码文件路径
**输出**：改动地图（要动哪些文件 + 影响面 + 要同步哪些文档 + 推荐下一步 skill）

> 不写代码、不改文档，只做"提需求 → 找到一切相关物 → 给出动手蓝图"。

---

## 何时用

| 场景 | 用法 |
|------|------|
| 用户拿到一句模糊需求 | `/need-to-code "支持用户批量导入"` |
| 用户给出 PRD 编号准备开工 | `/need-to-code prd PRD-001` |
| 用户给出 AC 编号要做最小开发单元 | `/need-to-code ac AC-001-01` |
| 用户拿到 SPEC 但不知道改哪些代码 | `/need-to-code spec SPEC-BE-001` |
| 用户在代码里看到陌生函数，想知道它属于哪个需求 | `/need-to-code from-code backend/services/user_service.py:90` |

---

## 标准工作流

### 工作流 A：自然语言入口

```
用户: /need-to-code "支持用户批量导入"
  ↓
Step 1：语义检索 PRD/AC
  - Glob sprints/backlog/requirements/**/*.md
  - Grep 关键词组合：用户 + 批量 + 导入
  - 命中 top-3 候选 AC，问用户确认
  ↓
Step 2：用户确认锚点 → 跳到工作流 C（AC 入口）
```

### 工作流 B：PRD 入口

```
用户: /need-to-code prd PRD-001
  ↓
Step 1：读 PRD 全文，解析元数据和 AC 列表
Step 2：聚合 AC 状态（复用 /prd-status）
Step 3：对每个未完成 AC 跳到工作流 C
Step 4：合并输出"PRD 级改动地图"
  - 按 layer 汇总（backend / frontend）
  - 列出关联 SPEC 是否需要 doc-sync
```

### 工作流 C：AC 入口（最精确）

```
用户: /need-to-code ac AC-001-01
  ↓
Step 1：读 AC 元数据 — 定位 PRD 文件，提取 BDD、详设引用
Step 2：读 SPEC 对应章节 — 提取代码实体清单
Step 3：用 Grep/Glob 把实体清单变成文件定位
  - 对每个核心符号搜索代码，找到定义和调用位置
Step 4：反向校验 SPEC ↔ Code — 确认实体是否存在
Step 5：拉影响面 — 搜索调用者，列出直接/间接依赖
Step 6：定位关联 Task — Grep sprints/active/**/tasks-*.md
Step 7：产出改动地图（见下文格式）
Step 8：推荐 next skill
```

### 工作流 D：SPEC 入口

```
用户: /need-to-code spec SPEC-BE-001
  ↓
Step 1：读 SPEC 元数据，反向找到所有 PRD
Step 2：扫描 SPEC 内的所有 AC 引用
Step 3：对每个 AC 跳到工作流 C
Step 4：合并输出"SPEC 级改动地图"
```

### 工作流 E：反向（代码入口）

```
用户: /need-to-code from-code backend/services/user_service.py:90
  ↓
Step 1：读代码片段，提取关键符号（函数名、类名）
Step 2：反查 SPEC — Grep <符号名> docs/specs/**/*.md
Step 3：反查 PRD/AC — 从 SPEC 反向找 PRD
Step 4：反查 commit 历史 — git log 找引入 commit
Step 5：产出"反向溯源报告"
```

---

## 改动地图输出格式（核心产物）

```markdown
# 改动地图 — AC-001-01「支持用户批量导入」

## 1. 需求锚点
- **PRD**: PRD-001
- **AC**: AC-001-01  状态: 🟡 开发中
- **详设**: SPEC-BE-001 §3.1

## 2. 关联代码（按 layer 分组）

### Backend
| 文件 | 符号 | 当前状态 |
|------|------|---------|
| backend/services/user_service.py:120 | `batch_import()` | ⚠ 需新增 |
| backend/api/users.py:45 | `POST /api/users/batch` | ⚠ 需新增 |

### Frontend
| 文件 | 符号 | 当前状态 |
|------|------|---------|
| frontend/src/pages/UserImport.tsx | 批量导入页面 | ⚠ 需新增 |

## 3. 影响面
- 直接调用 `UserService` 的位置：
  - `backend/api/users.py` — 需要新增路由
  - `frontend/src/services/userApi.ts` — 需要新增 API 调用

## 4. SPEC ↔ Code 一致性
- ✅ `UserService.create_user` 签名匹配
- ❌ `UserService.batch_import` 代码中不存在 → 需新增

## 5. 关联 Task
- 已有 task / 无 task（建议在今日 Wave 创建）

## 6. 文档同步清单
- [ ] PRD AC 状态更新
- [ ] SPEC 补充批量导入接口定义

## 7. 推荐下一步
1. `/spec-prelaunch-review`（确认 SPEC 与代码对齐）
2. 开 Task 写代码
3. `/doc-sync` 同步文档
```

---

## 硬性约束

- ❌ 本 skill **不写代码、不改文档**，只做定位与建议
- ❌ 自然语言入口找到候选 AC 时，**不得**直接进 Step 3，必须让用户确认锚点
- ✅ 所有定位结果必须附"文件:行号"链接或"文件#章节"锚点
- ✅ 关系图谱落盘到 `docs/_index/relation-map.json`，纳入 git 追踪

---

## 与其他 skill 的边界

| 场景 | 走哪个 skill |
|------|------------|
| 提需求 → 不知道改哪 | `need-to-code`（入口） |
| 已知 AC，开工前核验 spec ↔ code | `/spec-prelaunch-review` |
| 看 PRD/AC 进度 | `/prd-status` |
| 改完代码同步文档 | `/doc-sync` |
