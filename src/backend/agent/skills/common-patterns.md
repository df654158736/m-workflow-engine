# 常见工作流模式

## 模式 1：数据采集 → AI 分析 → 条件分支

```
FlinkSQL(查数据) → LLM(AI分析) → Condition(判断结果) → Tool/Approval
```

适用：风险评估、异常检测、数据质量分析

## 模式 2：AI 分析 → 人工审批 → 执行

```
LLM(分析) → Approval(人工确认) → Condition(审批结果) → Tool(执行) / Tool(通知)
```

适用：高风险操作（拉黑供应商、大额支付、删除数据）

## 模式 3：多源汇聚 → AI 综合

```
FlinkSQL(数据源A) ──┐
                    ├→ LLM(综合分析) → Tool(输出)
FlinkSQL(数据源B) ──┘
```

适用：报告生成、多维度对比、综合评估

## 模式 4：串行多轮 AI

```
LLM(需求解析) → LLM(方案生成) → LLM(方案评估) → Condition → ...
```

适用：复杂推理、分步思考、多角度分析

## 模式 5：采集 → 处理 → 告警

```
FlinkSQL(检测) → Function(计算) → Condition(阈值) → Tool(告警) + Approval(升级)
```

适用：监控告警、数据质量、SLA 检查

## 反模式（避免）

- ❌ LLM 节点直接接 Tool 执行，中间没有人工确认（危险操作）
- ❌ Condition 节点的 expression 是硬编码 "True"（没有意义的分支）
- ❌ 孤立节点（没有任何 edge 连接）
- ❌ 所有节点串成一条线且没有分支（说明需求分解不够）
