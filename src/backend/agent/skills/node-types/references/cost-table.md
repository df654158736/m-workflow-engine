# 节点成本速查

## 各节点类型成本

| 节点类型 | 平均 tokens | 平均耗时 | 每次成本 |
|---------|------------|---------|---------|
| LLM | 2000 | 8s | ¥0.02 |
| FlinkSQL | 0 | 5s | ¥0.005 |
| Sandbox | 0 | 3s | ¥0.002 |
| Tool | 0 | 2s | ¥0.001 |
| Function | 0 | 1s | ¥0.0005 |
| Condition | 0 | 0.1s | ¥0 |
| Approval | 0 | — | ¥0 |

## 节点组合推荐

| 场景 | 推荐组合 | 真实工作流参考 |
|------|---------|-------------|
| 数据查询 → AI 分析 | `FlinkSQL → LLM` | wf-plan-supplier-risk |
| AI 分析 → 条件分支 | `LLM → Condition → (分支)` | wf-plan-data-anomaly |
| 危险操作 | `LLM → Approval → Condition → Tool` | wf-plan-supplier-risk |
| 多源汇聚 | `FlinkSQL ×N → LLM` | — |
| 异常检测+修复 | `FlinkSQL → LLM → Condition → Tool(修复) + Tool(通知)` | wf-data-quality-alert |
| 监控告警 | `FlinkSQL → Function → Condition → Tool` | — |

## 典型工作流成本估算

正常执行（5 节点）：
```
FlinkSQL(5s/¥0.005) → LLM(8s/¥0.02) → Condition(0.1s/¥0) → Approval(—/¥0) → Tool(2s/¥0.001)
总计: 15.1s / ¥0.026
```

最坏情况（FlinkSQL+LLM 各重试 2 次）：
```
总计: 41.1s / ¥0.076（成本 3x）
```
