# `/PRD` skill 的 AC 拆分增强建议

> **目标**：让用户级 `/PRD` skill（`~/.claude/skills/PRD/SKILL.md`）强制执行 AC 拆分，并新增 `add-ac` 子命令给已有 PRD 补 AC。
> **原则**：**不改写用户的全局 skill 文件**，本文档是"建议差异"（diff）。由用户自己决定是否编辑 `~/.claude/skills/PRD/SKILL.md` 把这些增强点吸收进去。
> **替代方案**：不编辑用户全局 skill，而是在本项目创建一个**项目级 PRD skill**（`.claude/skills/PRD-project/SKILL.md`）覆盖全局。推荐用这种，保持全局 skill 通用性。

---

## 方案选择

| 方案 | 说明 | 推荐度 |
|------|------|-------|
| A. 编辑用户全局 `~/.claude/skills/PRD/SKILL.md` | 一次改动全生效，其他项目也受影响 | ⭐⭐ 影响面大 |
| B. 项目级 skill `.claude/skills/PRD-project/SKILL.md` 覆盖 | 只在本项目生效，其他项目原样 | ⭐⭐⭐⭐⭐ 推荐 |
| C. 只在 CLAUDE.md 里加一条硬规则 | 最轻，但规则分散 | ⭐⭐⭐ |

**推荐方案 B**，原因：
- 用户全局 `/PRD` skill 设计为通用的 SDD/BDD 生成器，不绑定任何项目
- 本项目 有自己的 AC ID 命名、frontmatter 规范，属于项目特化需求
- 全局 skill 作为底座，项目 skill 作为强化层，符合"skill 叠加"模式

---

## 项目级 PRD skill 的骨架（待实施）

### 目录

```
.claude/skills/PRD-project/
├── SKILL.md                         ← 项目特化规则
└── references/
    ├── ac-template.md               ← 本项目 AC 格式模板（AC-XXX-YY）
    └── prd-frontmatter-example.yaml ← YAML frontmatter 示例
```

### SKILL.md 草案内容

```yaml
---
name: PRD-project
description: "本项目 项目 PRD 撰写（在全局 /PRD 基础上叠加项目特化规则）。
强制: YAML frontmatter、AC ID 格式 AC-XXX-YY、BDD 验收、AC 完整性检查。
AUTO-TRIGGER：在 本项目 仓库工作目录下，用户说 '写需求'/'PRD'/'需求文档'/'新功能' 时优先用本 skill。
子命令：/PRD add-ac PRD-XXX（给已有 PRD 补 AC）。"
---

# 本项目 PRD 撰写（项目特化）

## 与全局 /PRD skill 的关系

本 skill **叠加**在全局 `/PRD` skill 之上：
- 全局 skill 负责 SDD/BDD 结构、苏格拉底式提问、验证脚本
- 本 skill 负责 本项目 项目特化的字段规范和 AC 管理

## 强制规则（超越全局 /PRD 的加强项）

### 规则 1：frontmatter 必须是 YAML

- 遵循 docs/standards/PRD-frontmatter.md
- 不再使用旧的 `> **字段**: 值` blockquote 格式
- 必填字段：id / title / version / status / priority / release / owners / dates / related_specs / changelog

### 规则 2：AC 章节必填且格式严格

- 遵循 docs/standards/AC-tracking.md
- AC ID 格式：`AC-{PRD编号}-{两位序号}`（如 AC-002D-01）
- 每个 AC 必须有：标题+优先级、状态元数据块、描述、BDD 三段式
- **PRD 状态 >= reviewed 时，不允许 "## 需求点" 章节为空**

### 规则 3：AC 粒度约束

- 每个 AC 预估 0.5 ~ 3 人日
- 超过 3 人日要询问用户是否拆更细
- 一个 PRD 典型 AC 数：5 ~ 15 个
- 过少（<3）提示"是否过于笼统"；过多（>20）提示"是否过于细碎"

### 规则 4：AC 冻结与变更

- `status: reviewed` → AC 冻结
- 此后任何 AC 新增/修改/废弃，必须自动触发 `/doc-sync` 追加 changelog

### 规则 5：生成完毕自动调 /prd-status

- PRD 写完保存后，自动执行 `/prd-status update`
- 刷新对应 release 的 PRD-STATUS.md

## 子命令：/PRD add-ac PRD-002D

用于给已有 PRD 补 AC（本项目独有）。

### 流程

```
Step 1: 读 PRD-002D 正文
Step 2: 扫描以下章节识别潜在 AC：
        - "## 功能需求" / "## 功能列表"
        - "## 验收标准" （如果是老格式 AC-01 需重编号为 AC-002D-01）
        - "## 用户故事"
Step 3: 对每个潜在 AC，生成草稿：
        - 建议 AC ID（沿用原序号 + 加 PRD 前缀）
        - 建议标题、优先级、描述
        - BDD 骨架（Given/When/Then 空壳）
Step 4: PM 逐条确认 / 调整 / 补充 BDD
Step 5: 按 AC-tracking.md §3 格式写入 PRD 的 "## 需求点" 章节
Step 6: 自动触发 /prd-status update
```

### 迁移老 AC 的特殊规则

老 PRD 里的 `AC-01` / `AC-02` 等裸编号：
- 自动加前缀：`AC-002D-01`
- 原文对应的描述原样保留
- 如果没有 BDD 段，生成空 BDD 骨架让 PM 补

## 苏格拉底式提问的补充

在全局 skill 的 7 个核心问题之后，追加 2 个：

8. **发布版本** — "这个需求计划在哪个版本发布？当前有 v2026-04-30 和 v2026-05-30 两个版本。如果暂不确定，先放需求池（pool）。"

9. **负责人分配** — "开发负责人是谁？qa 字段先写 self-test（研发自测 + PM 验收）。"

## 自检门控增强

全局 Self-Correction Gate 之上追加：

- [ ] frontmatter 是合法 YAML 且字段完整
- [ ] AC ID 格式符合 AC-XXX-YY
- [ ] 每个 AC 有 BDD 三段式
- [ ] AC 数量在 5-15 之间（超出要和 PM 确认）
- [ ] 每个 AC 有明确的 dev 负责人
- [ ] release 字段指向存在的 _releases 目录或 pool

## 资源引用

- docs/standards/PRD-frontmatter.md
- docs/standards/AC-tracking.md
- sprints/backlog/requirements/_releases/  ← 可选的版本目录
```

---

## 实施步骤（待用户批准后执行）

1. **创建** `.claude/skills/PRD-project/SKILL.md`（基于上面的草案）
2. **创建** `.claude/skills/PRD-project/references/ac-template.md`（AC 模板，给 Claude 填空）
3. **更新** `CLAUDE.md` 的"项目自定义 Skills"表格，加入 `/PRD-project` 和 `/prd-status` 两行
4. **验证** 在本项目下调用 `/PRD` 时，Claude 优先匹配 `/PRD-project`

---

## 不做的事

- ❌ 不改写用户全局 `~/.claude/skills/PRD/SKILL.md`
- ❌ 不强制全部项目采用 YAML frontmatter（只在 本项目 内生效）
- ❌ 不在全局 skill 的 references/ 加项目特化模板
