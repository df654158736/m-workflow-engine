---
name: git-workflow
description: Git 工作流：分支管理、提交规范（中文前缀）、PR 流程。
trigger: 用户提到"git"、"提交"、"commit"、"push"、"分支"、"branch"、"PR"
---

# Git 工作流

## ⚠️ 提交三步曲（多人协作铁律）

**每次 commit + push 必须按顺序：**

```bash
# Step 1: 先拉取远程最新代码（必须！）
git pull --rebase origin <当前分支>

# Step 2: 提交本地变更
git add <files>
git commit -m "<中文前缀>: <描述>"

# Step 3: 推送到远程
git push origin <当前分支>
```

> 不 pull 直接 push → rejected（non-fast-forward）
> 禁止 `git push --force`

---

## ⚠️ Commit Message 格式（GitLab pre-receive hook 强制）

英文 Conventional Commits（`feat:`, `fix:` 等）**会被服务器拒绝**。

| 前缀 | 用途 | 示例 |
|------|------|------|
| `更新:` | 更新现有功能/文档 | `更新: 用户管理模块查询优化` |
| `修复:` | 修复 Bug | `修复: 登录超时问题` |
| `增加:` | 新增功能/文件 | `增加: 用户批量导入功能` |
| `删除:` | 删除文件/功能 | `删除: 过期的临时文档` |
| `临时:` | WIP 临时提交 | `临时: 保存数据导入进度` |
| `测试:` | 测试相关 | `测试: 添加用户服务单元测试` |
| `恢复:` | 回退/恢复 | `恢复: 回退 API 路由变更` |
| `合并:` | 合并分支 | `合并: 合并 main 到 feature 分支` |

---

## 分支策略

```
main (主干分支)
├── feature/{module}-{task}     ← 按模块隔离，一人一模块一分支
├── chore/{description}         ← 共享文件变更，必须 PR
├── release/v{version}          ← Release 准备
└── hotfix/{description}        ← 紧急修复
```

### 创建功能分支

```bash
git checkout main
git pull origin main
git checkout -b feature/{module}-{task-name}
```

---

## PR 创建规范

```bash
git push origin feature/backend-{task-name}

gh pr create \
  --base main \
  --head feature/{module}-{task-name} \
  --title "增加: 用户批量导入功能" \
  --body "$(cat <<'EOF'
## Summary
- 实现批量导入 API
- 添加数据校验逻辑

## Testing
- Unit tests: ✅
- Integration tests: ✅

## Checklist
- [x] 代码符合项目规范
- [x] 仅修改自己负责的模块
- [x] PROGRESS.md 已更新
EOF
)"
```

---

## 每天开始工作

```bash
git checkout main
git pull origin main
git branch -r | grep feature/       # 检查有无模块冲突
git checkout feature/{module}-{task}
git rebase main
```

---

## 冲突解决

```bash
git rebase origin/main
# CONFLICT → 编辑文件解决
git add <resolved-files>
git rebase --continue
```
