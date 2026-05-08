---
name: spec-prelaunch-review
description: |
  Sprint 任务开工前的全链路代码核验 — 用户说"开始开发我的 sprint 任务"时，
  Agent 必须先读任务文件里引用的 spec，把 spec 中所有"代码实体引用"（类名、方法签名、
  字段名、枚举值、DTO、状态机档位）与真实代码逐项比对，输出落地障碍清单与 spec 修订建议，
  避免按纸面方案开工后在编译/运行时连续踩坑。
user-invocable: true
---

# /spec-prelaunch-review — 详设开工前全链路核验

## 何时触发

### 主场景：Sprint 任务开工

用户说下列任一话术，Agent 不得直接动手写代码，必须先走本 skill：

- "开始开发我的 sprint 任务"
- "开始开发 wave{N} 任务"
- "按这份 spec 开工"

**Sprint 开工标准入口流程**：

```
用户: "开始开发我的 sprint 任务"
  ↓
Step A: Agent 定位任务文件
        读 sprints/active/{today}/wave{N}-*/tasks-{gitid}.md
  ↓
Step B: Agent 从任务文件里提取 spec 引用
  ↓
Step C: Agent 对每份引用的 spec 跑本 skill 的 Step 1-6
  ↓
Step D: 产出"开工结论"给用户 approve
  ↓
Step E: Approve 后才开 T1
```

### 不触发的场景

- 用户只是问 spec 的问题、不准备写代码 → 直接答
- 任务是纯 bug 修复 / 样式调整，没有关联 spec → 跳过
- 本会话之前已经跑过本 skill → 跳过

---

## 硬性约束

- ❌ 未经本 skill 核验，不得按 spec 写实现代码
- ❌ 不得仅凭 spec 里的类名/方法名写代码（必须 Grep/Read 验过真实存在）
- ❌ 发现落地障碍不得私自改 spec——必须反馈给 spec 作者
- ✅ 核验范围覆盖 spec 全文提及的所有代码实体
- ✅ 核验结论必须附代码实据（文件路径 + 行号）

---

## 标准流程

### Step 1：提取 spec 的"代码实体引用清单"

通读 spec 全文，把所有具体的代码引用提取成清单：

| 引用类型 | 提取什么 | 举例 |
|---------|---------|-----|
| **类 / 函数** | 类名 + 函数名 + 签名 | `UserService.batch_import(file, options)` |
| **Model / Schema** | 类名 + 字段清单 | `UserModel { email: str, name: str }` |
| **数据库字段 / 表** | 表名 + 字段名 + 类型 + 约束 | `users.email VARCHAR NOT NULL` |
| **REST 端点** | method + path + 请求/响应 schema | `POST /api/users/batch` |
| **配置项** | 配置 key + 默认值 | `BATCH_SIZE=100` |

### Step 2：逐项代码核验

对 Step 1 清单的每一条，用 Grep / Read / Glob 核验是否真实存在 + 签名/字段是否匹配。

**分类障碍等级**：

| 等级 | 含义 | 判定标准 |
|------|------|---------|
| **编译级** | 按 spec 写必然报错 | 方法签名错、类名错、字段名错 |
| **运行时级** | 不报错但运行时异常 | 违反 NOT NULL、字段丢失导致空值 |
| **数据一致性级** | 不抛异常但数据错 | 状态跳跃、默认值不符合预期 |
| **架构设计级** | 能跑但违反规范 | 违反 CLAUDE.md 技术红线 |

### Step 3：产出"落地障碍清单"

| # | 等级 | spec 位置 | spec 描述 | 代码实据 | 核验结论 |
|---|------|----------|----------|---------|---------|

每一行必须有代码实据（文件:行号）。

### Step 4：识别"关键决策分歧"

有些问题不是"对错"，而是"设计取舍"——需要让 spec 作者决策。

### Step 5：产出 spec 修订方向

不直接改 spec，给出修订点清单。

### Step 6：决定开工门槛

| 结论 | 适用情况 | 下一步 |
|------|---------|-------|
| 🟢 直接开工 | 0 处编译级 + 0 处运行时级障碍 | 按 spec 执行 |
| 🟡 spec 微调后开工 | ≤2 处编译级 + 有修复路径 | 小改后开 T1 |
| 🟠 spec 版本升级后开工 | ≥3 处编译级或 ≥1 处架构设计级 | spec +1 走 doc-sync |
| 🔴 需要重做设计 | 方案根基错误 | 发回 spec 作者重写 |

---

## Checklist（Agent 自检）

- [ ] Step 1 代码实体清单已完整提取
- [ ] Step 2 每条实体都有 Grep/Read 核验记录
- [ ] Step 3 每条障碍都有文件:行号实据
- [ ] Step 4 设计取舍已识别为 Q 问题
- [ ] Step 5 修订清单已产出
- [ ] Step 6 开工结论已产出，用户 approve
