---
name: git-team-collaboration
description: 多人 + 多 Claude Code 会话并行协作规则。一人多终端、模块隔离、冲突预防。
trigger: 用户提到"多人协作"、"多终端"、"多session"、"冲突"、"协作"
---

# 多人团队协作规则

## 团队模型

```
developer-a (git user)                developer-b (git user)
├── Claude Code 终端 1: Backend 开发  ├── Claude Code 终端 1: Frontend 开发
├── Claude Code 终端 2: API 修改      └── Claude Code 终端 2: 测试
└── Claude Code 终端 3: 跑测试

所有终端共享同一 Git 身份 + 同一 feature branch
```

**核心原则**: Git 账号 = 身份标识。不需要 Agent 命名体系。

---

## 模块隔离规则

| 规则 | 说明 |
|------|------|
| 一人一模块一分支 | 同一模块同一时间只有一个人有 active feature branch |
| 检查方法 | `git branch -r \| grep feature/{module}` |
| 违规处理 | 在 coordination.md 协调，后创建者让步 |

---

## ⚠️ 多 Session 注意事项

一人可以同时运行多个 Claude Code 终端，但需要：

1. **共享同一 Git 分支**: 所有终端都在同一个 feature branch
2. **避免同时编辑同一文件**: 多终端别同时改同一个文件
3. **提交前检查**: `git status` 确认无覆盖风险
4. **每次 push 前必须 pull --rebase**: 即使是自己的另一个终端刚 push 过

---

## PR 审查规则（2 人团队）

| PR 类型 | Review 要求 |
|---------|------------|
| 自己模块内的变更 | 自审 + CI 通过即可 |
| 共享文件（types / config / API 定义） | 对方 Review + CI 通过 |
| 跨模块变更 | 相关模块负责人 Review + 验证 |

---

## 冲突预防清单

每天开始工作前：
```bash
# 同步主干
git fetch origin main
git rebase origin/main

# 检查远程分支
git branch -r | grep feature/
```

共享 API 定义变更单独 PR（不混入业务代码）。

---

## 团队成员

<!-- TODO: 填写你的团队成员 -->

| Git User | GitID | 主要负责 |
|----------|-------|---------|
| `{Your Name}` | `{yourname}` | <!-- TODO --> |
