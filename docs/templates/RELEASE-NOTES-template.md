# Release Notes: v{X.Y.Z}

> **Release Date**: YYYY-MM-DD
> **Release Type**: Major | Minor | Patch | Hotfix
> **Previous Version**: v{X.Y.W}

---

## Highlights

{本次发布的主要亮点，2-3 个要点}

- **{Feature 1}**: {简要描述}
- **{Feature 2}**: {简要描述}
- **{Improvement}**: {简要描述}

---

## New Features

### {Feature Name 1}

{功能详细描述}

**Usage**:
```python
# 示例代码
from ontology_sdk import Client

client = Client(world_id="world_001")
result = client.new_feature()
```

**Related PRD**: {Link to PRD}

### {Feature Name 2}

{功能详细描述}

---

## Improvements

### {Improvement 1}

{改进描述}

### {Improvement 2}

{改进描述}

---

## Bug Fixes

- **{BUG-XXX}**: {Bug 描述} - {修复说明}
- **{BUG-XXX}**: {Bug 描述} - {修复说明}

---

## Breaking Changes

⚠️ **本版本包含破坏性变更，请在升级前阅读迁移指南。**

### {Breaking Change 1}

**Before (v{X.Y.W})**:
```python
# 旧用法
client.old_method()
```

**After (v{X.Y.Z})**:
```python
# 新用法
client.new_method()
```

**Migration**: 参见 [Migration Guide](./migration/from-v{X.Y.W}.md)

---

## Deprecations

以下功能已被标记为 Deprecated，将在 v{X+1}.0.0 中移除：

| Deprecated | Replacement | Remove in |
|------------|-------------|-----------|
| `old_method()` | `new_method()` | v{X+1}.0.0 |

---

## API Changes

### New APIs

| API | Type | Description |
|-----|------|-------------|
| `POST /api/v1/new-resource` | REST | 新增资源 |
| `GET /api/v1/resources/{id}` | REST | 获取资源详情 |

### Modified APIs

| API | Change | Migration |
|-----|--------|-----------|
| `GET /api/v1/entities` | 新增 `filter` 参数 | 向后兼容 |

### Removed APIs

| API | Alternative |
|-----|-------------|
| `GET /api/v1/old-endpoint` | 使用 `GET /api/v1/new-endpoint` |

---

## Configuration Changes

### New Configuration

```yaml
# application.yaml
onto:
  new_feature:
    enabled: true
    timeout: 30s
```

### Changed Configuration

| Key | Old Default | New Default | Notes |
|-----|-------------|-------------|-------|
| `onto.cache.ttl` | `60s` | `300s` | 提高缓存效率 |

---

## Performance Improvements

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Query Latency (P99) | 200ms | 100ms | 50% faster |
| Throughput | 500 QPS | 1000 QPS | 2x increase |

---

## Security Updates

- {安全更新 1}
- {安全更新 2}

---

## Dependency Updates

| Dependency | Old Version | New Version | Notes |
|------------|-------------|-------------|-------|
| pydantic | 2.0.0 | 2.5.0 | Performance improvements |
| fastapi | 0.100.0 | 0.110.0 | Security fixes |

---

## Known Issues

| Issue | Workaround | Target Fix |
|-------|------------|------------|
| {问题描述} | {临时解决方案} | v{X.Y.Z+1} |

---

## Upgrade Instructions

### Prerequisites

- Python >= 3.10
- Java >= 21
- {其他前置条件}

### Upgrade Steps

1. **Backup** existing data and configuration
2. **Update** dependencies:
   ```bash
   pip install --upgrade ontology-sdk==X.Y.Z
   ```
3. **Migrate** configuration (if applicable)
4. **Test** core functionality
5. **Deploy** to production

### Rollback

如需回滚到 v{X.Y.W}：
```bash
pip install ontology-sdk==X.Y.W
```

---

## Documentation

- [API Reference](./docs/api/)
- [User Guide](./docs/guide/)
- [Migration Guide](./migration/from-v{X.Y.W}.md)

---

## Contributors

感谢以下贡献者：

- @contributor1
- @contributor2
- @contributor3

---

## Changelog

完整变更日志请参见 [CHANGELOG.md](./CHANGELOG.md)

---

## Feedback

如有问题或建议，请：
- 提交 Issue: {Issue 链接}
- 联系支持: {支持渠道}

---

**Full Changelog**: v{X.Y.W}...v{X.Y.Z}
