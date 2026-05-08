# PRD ↔ AC ↔ SPEC ↔ Code 引用规则速查

> **用途**：`/need-to-code` 解析"文档与代码的相互引用"时使用的语法规则与正则。
> 任何修改本文件 = 修改 `/need-to-code map` 的解析行为，必须通过 PR 评审。

---

## 1. 全景图

```
PRD-001 ←─ frontmatter.related_specs ──→ SPEC-001
   │                                          │
   │ "## 需求点"                              │ "> 关联需求"
   ↓                                          ↓
AC-001-01 ←─── "> **详设**: SPEC-001 §3.1" ────→ SPEC-001 §3.1
   │                                          │
   │ task checkbox "(AC-001-01)"              │ ```python / ```yaml
   ↓                                          ↓
tasks-{gitid}.md                        Code symbols
   │                                          │
   │ "关联需求点" + "关联详设"                │ grep / search
   └────────── code commit message ──────────→ backend/services/user_service.py:90
```

每条边都是**机读可解析**的双向引用，本文件定义每条边的解析规则。

---

## 2. PRD ↔ SPEC

### 2.1 PRD → SPEC（正向）

**位置**：PRD frontmatter 的 `related_specs` 字段

**语法**：
```yaml
---
id: PRD-001
related_specs:
  - docs/specs/backend/SPEC-001-user-management.md
  - docs/specs/frontend/SPEC-002-user-import-ui.md
---
```

**解析**：
- 用 YAML 解析器读 frontmatter
- 取 `related_specs` 数组，每项是 SPEC 文件相对路径
- 路径必须存在；否则 `/prd-status check` 会报错

### 2.2 SPEC → PRD（反向）

**位置**：SPEC 顶部的 blockquote 元数据区

**语法**：
```markdown
# 后端详设 — PRD-001 用户管理

> **文档编号**: SPEC-001
> **版本**: 1.2
> **关联需求**: PRD-001-User-Management.md
```

**解析正则**：
```regex
^>\s*\*\*关联需求\*\*\s*:\s*(.+)$
```
取捕获组，按 `,` 分隔，每项可能是文件名或全路径。文件名要 Glob 转全路径。

### 2.3 一致性校验

| 异常 | 说明 |
|------|------|
| PRD 引用了不存在的 SPEC 文件 | 🔴 |
| SPEC 引用的 PRD 没有反向 `related_specs` 指回来 | 🟡 |
| SPEC 文件名与 `> **文档编号**` 不一致 | 🟡 |

---

## 3. PRD ↔ AC ↔ SPEC

AC 是 PRD 内的章节，但同时引用 SPEC 章节，是三方桥梁。

### 3.1 AC ID 格式

```regex
AC-\d{3}[A-Z]?-\d{2}
```

示例：`AC-001-01` / `AC-002-05` / `AC-010-12`

### 3.2 AC 章节内的元数据块（SPEC 引用所在）

```markdown
### AC-001-01 支持用户批量导入（CSV/JSON）  `P0`

> **状态**: 开发✅ · 验收已验收
> **负责**: dev={gitid} · qa=self-test
> **详设**: SPEC-001 §3.1
> **预估**: 2 人日
```

**解析正则**：

```regex
# AC ID + 标题 + 优先级
^###\s+(AC-\d{3}[A-Z]?-\d{2})\s+(.+?)\s+`(P[012])`\s*$

# 详设引用（核心！跳到 SPEC 章节）
^>\s*\*\*详设\*\*\s*:\s*(SPEC-[A-Z]?-?\d+)(?:\s*§\s*([\d.]+))?
```

`§` 后面是章节号（可选）。例：`SPEC-001 §3.1`、`SPEC-002 §4`。

### 3.3 SPEC 章节内的 AC 反向引用（可选但推荐）

```markdown
### 3.1 批量导入数据模型

> **关联 AC**: AC-001-01, AC-001-02

（章节正文）
```

**解析正则**：
```regex
^>\s*\*\*关联 AC\*\*\s*:\s*([A-Z\-,\s\d]+)$
```

> 如果 SPEC 章节没写"关联 AC"，反向查询要靠 PRD 内的"详设"字段。**强烈推荐 SPEC 写明**，方便 from-code 反查。

---

## 4. AC ↔ Task

### 4.1 Task 头部（粗粒度）

```markdown
# Tasks — {gitid} — 2026-04-16 Wave3

> **关联需求点**:
>   - AC-001-01 支持用户批量导入
>   - AC-001-02 导入结果查询与导出
>
> **关联详设**: SPEC-001 §3.1-3.3, SPEC-002 §4
```

**解析**：
- `> **关联需求点**:` 之后到下一个 `>` 空行之间，每行匹配 AC ID
- `> **关联详设**:` 后取所有 `SPEC-XXX(?:\s*§\s*[\d.\-,]+)?`

### 4.2 Task checkbox（细粒度，最重要）

```markdown
- [x] 实现 UserImportService (AC-001-01)
- [x] 新增 POST /api/users/batch 接口 (AC-001-01)
- [ ] 单元测试覆盖 (AC-001-01, AC-001-02)
```

**解析正则**：
```regex
^[\s-]*\[([ x])\]\s+.+?\(([A-Z\-\d,\s]+)\)\s*$
```

捕获组 1 = checkbox 状态（`x` 或空格），捕获组 2 = 括号内 AC ID 列表（按 `,` 分割再 trim）。

> AC ID 必须用**英文圆括号**，不用方括号（避免与 markdown checkbox 冲突）。

### 4.3 一致性校验

| 异常 | 说明 |
|------|------|
| Task checkbox 引用了不存在的 AC | 🔴 阻断（`/prd-status check` 会发现） |
| Task 头部 `关联需求点` 与 checkbox `(AC-XXX)` 不匹配 | 🟡 |
| AC 状态 ✅ 但关联 task 还有 `[ ]` | 🔴 |

---

## 5. SPEC ↔ Code

### 5.1 SPEC → Code（正向）

SPEC 章节里以两种形式提及代码符号：

#### 5.1.1 代码块

````markdown
```python
class UserImportService:
    def batch_import(self, file_path: str, options: ImportOptions) -> ImportResult:
        ...
```
````

**解析**：抽取代码块语言（python/typescript/yaml），提取类名、方法签名、字段名。

#### 5.1.2 反引号标识符

```markdown
调用 `UserImportService.batch_import()` 完成批量导入...
```

**解析正则**（捕获 Class.method 形态）：
```regex
`([A-Z][A-Za-z0-9_]+(?:\.[a-z][A-Za-z0-9_]+)+)(?:\(\))?`
```

### 5.2 Code → SPEC（反向）

代码侧通过 2 种方式回指 SPEC：

#### 5.2.1 Commit message

```
增加: SPEC-001 §3.1 批量导入功能实现 (AC-001-01)
```

**解析正则**：
```regex
(SPEC-[A-Z]?-?\d+(?:\s*§\s*[\d.]+)?|AC-\d{3}[A-Z]?-\d{2}|PRD-\d{3}[A-Z]?)
```

> 团队约定：commit message 中**至少**带一个 `AC-XXX` 或 `SPEC-XXX`（与 git commit 前缀规范并存）。

#### 5.2.2 文件头注释（可选，不强制）

```python
"""
实现 SPEC-001 §3.1 批量导入功能
关联 AC: AC-001-01
"""
class UserImportService:
```

**解析正则**：同 5.2.1

> 不强制写，写了 `/need-to-code from-code` 反查会更快。

---

## 6. AC ↔ Code（间接）

AC 与代码之间没有直接引用，必须经过 SPEC 或 Task 桥接：

```
AC-001-01 ─→ SPEC-001 §3.1 ─→ UserImportService（代码块）
AC-001-01 ─→ tasks-{gitid}.md "(AC-001-01)" 行 ─→ git log 该 task 期间的 commit ─→ 文件
AC-001-01 ←─ commit message "(AC-001-01)" ←─ 文件改动
```

**`/need-to-code` 推荐策略**：
1. 优先走 `AC → SPEC → Code`（最稳）
2. 没有 SPEC 引用时，回落到 `AC → Task → git log → Code`
3. 没有 task 时，回落到 `AC → 全仓 git log grep "AC-001-01" → Code`
4. 三条路径都空 → 标记为"代码未落地"，建议补 task 或归档 AC

---

## 7. 解析器实现要点

### 7.1 性能

- PRD/SPEC 文件数量预估：10~50 量级
- AC 数量预估：50~500 量级
- 单次全量扫描应 < 2min，全靠 Grep + 简单 YAML/Markdown 解析，不用重 LLM
- LLM 只用于"自然语言入口"的语义匹配（且只对 AC 标题/描述做匹配，不读全文）

### 7.2 缓存

- `relation-map.json` 是单一事实源
- 增量刷新用 `git diff HEAD~1 HEAD` 限定改过的文件
- AC 状态字段不进 relation-map（它属于 `prd-status`，避免双写）

### 7.3 容错

| 场景 | 处理 |
|------|------|
| PRD 没有 frontmatter（老格式） | **退化解析** blockquote 元数据区（见 §7.4），不直接报错 |
| SPEC 顶部无 `关联需求` | 跳过反向引用 + 标记"反查弱" |
| Task 用了中文括号 `（AC-XXX）` | 容错支持，但提示用户改成英文 |
| AC ID 写成 `AC-001-1`（少前导 0） | 标记为格式错误，不纳入图谱 |
| PRD 章节锚点解析失败（如 `§6.4` 不在 PRD 内） | 标"锚点失效"，回落到全 PRD 引用 |

### 7.4 老 blockquote 格式的退化解析

部分历史 PRD 可能使用老 blockquote 元数据格式，本节定义 fallback 解析规则。

**老格式样例**：

```markdown
# PRD-001: 用户管理

> **文档编号**: PRD-001
> **版本**: 1.2
> **状态**: Draft
> **关联文档**: [SPEC-001 ...](path), [SPEC-002 ...](path)
> **Changelog**: [变更日志](./PRD-001-xxx.changelog.md)
```

**字段映射**：

| 老 blockquote 键 | 等价于新 frontmatter 字段 | 解析正则 |
|------------------|-------------------------|---------|
| `> **文档编号**:` | `id` | `^>\s*\*\*文档编号\*\*\s*:\s*(PRD-[\w]+)` |
| `> **版本**:` | `version` | `^>\s*\*\*版本\*\*\s*:\s*(.+)$` |
| `> **状态**:` | `status` | `^>\s*\*\*状态\*\*\s*:\s*(.+)$`（值需规范化：`Draft`→`draft` / `进行中`→`in-dev`）|
| `> **关联文档**:` | `related_specs` | 抽取 markdown link target + 抸取裸 `SPEC-\d+` 编号 |
| `> **作者**:` | `owners.pm` | `^>\s*\*\*作者\*\*\s*:\s*(\S+)` |

**format_version 标记**：

`relation-map.json` 中每条 PRD 必须带 `format_version` 字段：

```json
{
  "prd": {
    "PRD-001": {
      "format_version": "yaml",
      "specs": ["SPEC-001", "SPEC-002"],
      "acs": [
        {"id": "AC-001-01", "virtual": false}
      ]
    }
  }
}
```

---

## 8. 与现有规范的边界

| 规范文件 | 管辖 | 本文件 |
|---------|------|-------|
| `docs/standards/PRD-frontmatter.md` | PRD frontmatter 字段定义 | 引用其 `related_specs` |
| `docs/standards/AC-tracking.md` | AC ID / 元数据 / Task 引用语法 | 引用其格式 + 加上"反查方向" |
| `.claude/skills/spec-prelaunch-review/SKILL.md` | SPEC ↔ Code 一致性核验 | 在工作流 C Step 4 引用 |

> **本文件不重新定义任何规则**，只汇总和补充"反查方向"。任何引用语法的变更必须先改对应的标准文档。
