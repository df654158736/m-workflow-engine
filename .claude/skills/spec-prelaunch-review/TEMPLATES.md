# Spec Pre-launch Review — 产出物模板

> Agent 按 SKILL.md 流程执行后，直接把产出填到下列模板中。
> 如需正式评审留痕（重大 spec 评审），用最后的"完整评审结论文档模板"生成 `tests/{gitid}/` 或 sprint `coordination.md` 条目。

---

## Template 1：代码实体引用清单（Step 1 产出）

```markdown
## Spec 代码引用清单

来源：`{spec 路径}` v{版本号}

| # | 引用类型 | Spec 位置 | 具体引用 |
|---|---------|----------|---------|
| 1 | 类/方法 | §3.2 | `UserService.batch_import(file_path, options)` |
| 2 | Model 字段 | §4.1 | `UserModel { email: str, name: str, status: str }` |
| 3 | REST 端点 | §5.1 | `POST /api/users/batch` |
| 4 | 枚举 | §3.4 | `UserStatus { ACTIVE, INACTIVE, SUSPENDED }` |
| ... | | | |
```

---

## Template 2：落地障碍清单（Step 3 产出，核心产物）

```markdown
## 落地障碍清单

| # | 等级 | Spec 位置 | Spec 描述（摘录） | 代码实据 | 核验结论 |
|---|------|----------|------------------|---------|---------|
| 1 | 编译级 | §3.2 Step 4 | `batch_import(file_path, options)` | `user_service.py:90-93` 实际 4 参 | 按 spec 调用会报错 |
| 2 | 运行时级 | §4.1 | 在 user_id 生成前创建 UserModel | `models.py:20` `user_id: str` 必填 | Pydantic ValidationError |
| 3 | 架构设计级 | §3.3 | Service 直接依赖外部 API | `user_service.py:30-45` 违反分层 | 违反 CLAUDE.md 技术红线 |
| 4 | 数据一致性级 | §3.5 | UserStatus 从 ACTIVE 直跳 SUSPENDED | `user_service.py` 按档回退 | 回退逻辑踩坑 |
| 5 | 契约一致性级 | §2.3 | Model 有 `role` 字段 | `api/users.py:41-43` 端点未暴露 | 字段静默丢失 |

统计：编译级 N1 / 运行时级 N2 / 架构级 N3 / 数据级 N4 / 契约级 N5，合计 N。
```

---

## Template 3：关键决策分歧（Step 4 产出，如有则用）

```markdown
## 关键决策分歧（需 spec 作者 / 评审人决策）

### Q1 — {主题一句话}

**Spec 当前选择（v{版本}）**：A 方案 — {一句话概述}

**替代方案**：B 方案 — {一句话概述}

**代价对比**：
- A 方案代价：{具体代价}
- B 方案代价：{具体代价}

**Agent 推荐**：{A/B/待决策} — {一句话理由}

**影响范围**：{文件清单 / 任务项}

---

### Q2 — {主题一句话}
...（同上）
```

---

## Template 4：Spec 修订方向（Step 5 产出，发给 spec 作者）

```markdown
## Spec 修订方向

### 必改项（对应落地障碍清单）
- [ ] §3.2 Step 4：修正 `batch_import` 签名为 4 参
- [ ] §4.1 数据模型：UserModel 创建时机改为 `user_id` 就绪之后
- [ ] §3.3：移除 Service 层对外部 API 的直接依赖，改为通过接口注入
- [ ] ...

### 待决策项（对应关键决策分歧）
- [ ] Q1：Service 依赖边界 — Agent 推荐 B 方案（零改动）
- [ ] Q2：导入失败是否阻塞主流程 — 待决策
- [ ] ...

### 建议版本跃迁
当前 v{X.Y} → 修订后 v{X.(Y+1)}
理由：{重大偏差清单 / 设计分歧清单}
```

---

## Template 5：开工结论（Step 6 产出）

```markdown
## 开工结论

**结论**：🟢 直接开工 / 🟡 spec 微调后开工 / 🟠 spec 版本升级后开工 / 🔴 需要重做设计

**理由**：
{基于障碍清单 + 决策分歧的综合判断，3-5 句话}

**开工门槛**（Action Items）：
- [ ] spec 作者完成修订方向中的"必改项"
- [ ] 决策人回答"待决策项"
- [ ] spec 版本升级到 v{新版本}
- [ ] spec 新版本走 `/doc-sync` 留 changelog

**门槛满足后可开的第一个任务**：{T1 名称}
```

---

## Template 6：完整评审结论文档（重大评审才用）

> 文件命名：`tests/{gitid}/{wave或spec-id}-review-result.md`
> 或放到 sprint 协作文件：`sprints/active/{date}/{wave}/coordination.md`

````markdown
# {Wave / Spec 名称} — Spec 评审结论

> **评审日期**：{YYYY-MM-DD}
> **评审人**：{gitid}
> **被评审人**：{gitid}
> **评审对象**：
> - [spec 路径](relative/path.md) v{版本}
> - [tasks 文件](relative/path.md)
> - [其他关联文档](relative/path.md)
> **审核状态**：🟢 Approved / 🟡 Approved with changes / 🟠 Revise and resubmit / 🔴 Rejected

---

## 一、结论

{1 段话总结，明确说可/不可开工，核心理由}

---

## 二、N 处落地障碍代码核验

{Template 2 的表格}

**核验结论**：{一句话定性}

---

## 三、关键决策评审意见

### Q1 — {主题}

**{✅ Approved / ⚠️ Approved with one change / ❌ Rejected}**

{评审意见正文}

---

### Q2 — ...

---

## 四、补充建议（开工前必须吸收）

### 建议 1：{简短标题}
{具体建议 + 实现方案}

### 建议 2：...

---

## 五、开工前 Action Items

- [ ] 更新 spec v{X.Y} → v{X.(Y+1)}：吸收调整 + 补充建议，走 `/doc-sync`
- [ ] 评审记录归档：移到 sprint `coordination.md` 作为评审留痕
- [ ] 按 T1→TN 顺序开工
- [ ] 合并前跑 `/doc-sync-after-dev`

---

## 六、备注（非本次范围）

{团队/流程层面的观察，不占本 Sprint 工时的后续行动项}

---

## 附录 A：评审人核验清单

为避免"评审只听 spec 作者一面之词"，评审人独立读取并核验了以下代码文件：

| 文件 | 核验点 |
|------|-------|
| `path/to/file.py:L-L` | {核验什么} |
| `path/to/another.py` | {核验什么} |

核验结论：{一句话}

---

**审核人**：{gitid}
**审核状态**：{与开头一致}
**开工门槛**：完成 Action Items N 后可开 T1
````

---

## 附：等级判定速查

| 等级 | 判定关键词 | 举例 |
|------|----------|-----|
| **编译级** | 方法签名不对、类名错、字段名错、返回类型不匹配 | spec 写 `batch_import(2 参)`，代码是 `batch_import(4 参)` |
| **运行时级** | Pydantic 必填字段违反、枚举不存在、类型不匹配导致异常 | spec 在 user_id 就绪前建 UserModel，但 user_id 是必填 |
| **数据一致性级** | 状态机跳跃、回退路径失效、默认值冲突 | 跳过 INACTIVE 直接到 SUSPENDED，回退逻辑回不到正确档位 |
| **架构设计级** | 违反分层约束、违反 CLAUDE.md 技术红线、单一职责破坏 | 给 Service 层强塞外部 API 直连 |
| **契约一致性级** | API 定义 / Model / 数据库 三层字段对不齐 | spec 要求的字段 Model 有但 API 端点没暴露 |
