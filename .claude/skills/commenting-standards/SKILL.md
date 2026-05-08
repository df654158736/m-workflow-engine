---
name: commenting-standards
description: 注释规范检查与提示。查看全栈注释规范，检查当前文件或整个模块是否符合注释要求。
user_invocable: true
---

# 注释规范检查 Skill

## 触发条件

- 用户输入 `/commenting-standards`
- 用户询问注释相关问题

## 工作流

### 1. 显示规范摘要

向用户展示适用于当前上下文的规范要点。

### 2. 检查当前文件（如果有打开的文件）

根据文件类型执行对应检查：

#### Python 文件
- 检查模块是否有顶层 docstring
- 检查类和公开函数是否有 Google 风格 docstring
- 运行: `ruff check --select D` 验证

#### TypeScript / React 文件
- 检查导出函数是否有 JSDoc
- 检查 React 组件是否有文件头注释（如有必要）
- 运行: `pnpm lint` 验证

### 3. 批量扫描模式

如果用户请求扫描整个模块，使用以下命令：

```bash
# Python
cd backend && ruff check --select D src/ 2>&1 | head -50

# TypeScript
cd frontend && pnpm lint 2>&1 | grep jsdoc | head -50
```

### 4. 输出格式

对每个问题输出：
- 文件路径 + 行号
- 缺失的注释类型（类注释 / 函数注释 / 组件注释）
- 建议的注释模板

## 注释模板速查

### Python 函数 (Google 风格)
```python
def method_name(self, param: Type) -> ReturnType:
    """一句话描述功能。

    Args:
        param: 参数说明。

    Returns:
        返回值说明。

    Raises:
        ErrorType: 异常说明。
    """
```

### TypeScript 导出函数
```typescript
/**
 * 一句话描述功能。
 *
 * @param paramName - 参数说明
 * @returns 返回值说明
 */
```

### React 组件
```typescript
/**
 * ComponentName — 一句话描述组件用途。
 *
 * @param props.propName - 说明
 */
```
