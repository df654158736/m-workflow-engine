---
name: gitlab-auto-commit
description: ZTC GitLab 自动提交配置。满足 pre-receive hook 的中文前缀格式要求。
trigger: 用户提到"自动提交"、"gitlab"、"auto-commit"、"pre-receive"、"push失败"
---

# GitLab 自动提交配置

## ⚠️ 强制规则：提交推送三步曲

```bash
# Step 1: 拉取远程最新代码（必须！不可跳过！）
git pull --rebase origin <当前分支>

# Step 2: 提交本地变更
git add <files>
git commit -m "<前缀>: <描述>"

# Step 3: 推送到远程
git push origin <当前分支>
```

**为什么 Step 1 不可跳过？**
- 多人 + 多 Agent 并行工作，远程随时可能有新提交
- 不 pull 直接 push → `rejected (fetch first)`
- `--rebase` 保持线性历史

**如果 pull 有冲突：**
```bash
# 解决冲突文件后
git add <resolved-files>
git rebase --continue
# 然后继续 commit + push
```

---

## ⚠️ Commit Message 格式（pre-receive hook 强制）

| 前缀 | 用途 |
|------|------|
| `更新:` | 一般性更新 |
| `修复:` | Bug 修复 |
| `增加:` | 新功能 |
| `删除:` | 删除代码 |
| `临时:` | WIP 临时提交 |
| `测试:` | 测试相关 |
| `恢复:` | 回滚/恢复 |
| `合并:` | 合并分支 |

支持 TAPD 关联：`--task=ID`、`--story=ID`、`--bug=ID`

---

## 远程仓库配置

```
<!-- TODO: 替换为你的实际仓库地址 -->
URL: {your-git-url}
Remote: origin
主干分支: main
```

---

## 自动提交脚本

Windows: `.opencode/scripts/auto-commit.bat`
Unix: `.opencode/scripts/auto-commit.sh`

```bash
# 使用方法
bash .opencode/scripts/auto-commit.sh "更新: <描述>"
```

---

## 常见错误处理

| 错误 | 原因 | 解决 |
|------|------|------|
| `rejected (fetch first)` | 未先 pull | `git pull --rebase origin <分支>` |
| `pre-receive hook declined` | commit 格式错误 | 使用中文前缀格式 |
| `non-fast-forward` | 远程有新提交 | `git pull --rebase` |
