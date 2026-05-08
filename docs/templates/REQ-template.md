# REQ-{APP|PLT}-{NNN}: {需求标题}

## 基本信息

- **层次**: 应用层 (application) | 平台层 (platform)
- **优先级**: P0 (紧急) | P1 (高) | P2 (中) | P3 (低)
- **状态**: idea | refined | ready | in-sprint | done | cancelled
- **提出人**: {git user name}
- **创建时间**: YYYY-MM-DD
- **目标 Sprint**: {sprint-N 或待定}

---

## 需求描述

{用用户能理解的语言描述需求。不涉及技术实现细节。}

## 用户故事

**As a** {用户角色},
**I want to** {期望的功能},
**So that** {带来的价值}。

## 验收标准

1. WHEN {条件} THEN {预期结果}
2. WHEN {条件} THEN {预期结果}
3. ...

## 业务价值

- **用户影响**: {受影响的用户群体和规模}
- **业务目标**: {与哪个业务目标对齐}
- **不做的后果**: {如果不做会怎样}

---

## 关联（需求拆解后填写）

- **关联总纲需求**: `docs/requirements.md#Requirement-{N}` ← 可选
- **派生 Feature**: `FEAT-{NNN}` ← 工程拆解后补填
- **设计文档**: `docs/design/{xxx}.md` ← 可选
- **依赖需求**: `REQ-{XXX}-{NNN}` ← 可选

---

## 变更记录

| 日期 | 变更人 | 变更内容 |
|------|--------|---------|
| YYYY-MM-DD | {name} | 初始创建 |

<!--
## 编号规则
- 应用层: REQ-APP-001, REQ-APP-002, ...
- 平台层: REQ-PLT-001, REQ-PLT-002, ...

## 状态流转
idea → refined → ready → in-sprint → done
                                    → cancelled

## 层次说明
- **应用层 (application)**: 面向终端业务用户的功能需求（如：工作流编排界面、决策看板、数据探索工具）
- **平台层 (platform)**: 面向开发者/架构师的平台能力需求（如：推理引擎、Schema 管理、SDK 扩展）
-->
