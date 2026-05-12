# Tasks — 丁昂 (2026-05-09 Wave 1)

## 目标
Agent 接入本体对象探查流程 + 通用交互卡片协议

## 任务

### T1: 设计通用交互卡片 DSL 协议
- ✅ 定义卡片类型（review_table / selection / info）
- ✅ 定义 SSE 事件 `interactive_card` 的 payload 规范
- ✅ 定义用户决策回传的数据格式

### T2: 后端 — tool_registry 扩展确认类型
- ✅ `requires_confirmation` 从 `bool` 扩展为 `bool | str`
- ✅ `execute()` 返回 `confirmation_type` + `card_data` 字段
- ✅ `tool()` 装饰器参数类型同步更新

### T3: 后端 — 新增 submit_compare_decisions 工具
- ✅ Pydantic 模型 `SubmitCompareDecisionsArgs`
- ✅ 工具实现：批量调用 web-app setDecision API
- ✅ 标记 `requires_confirmation="interactive_card"`
- ✅ card_data 通过 args 传入并由 tool_registry 透传

### T4: 后端 — planner.py SSE 事件扩展
- ✅ 流式模式：检测 `confirmation_type` 发送 `interactive_card` 事件
- ✅ 非流式模式：`pending_tool` 携带 `confirmation_type` + `card_data`
- ✅ 修复 `pending_confirmation` 元组携带 `tool_result`（避免引用错误）
- ✅ DATAFIRST_TOOLS 新增 `submit_compare_decisions`
- ✅ DATAFIRST_PROMPT_TEMPLATE 更新探查流程 + card_data 构造规范

### T5: 前端 — 通用卡片渲染器
- ✅ `_dfConsumeStream()` 新增 `interactive_card` case
- ✅ `_dfSendLegacy()` 支持 interactive_card 类型确认
- ✅ 通用渲染函数 `dfRenderInteractiveCard(evtData)`
- ✅ `review_table` 类型渲染（表格 + 每行操作按钮 + 提交按钮）
- ✅ 决策状态管理 `_interactiveCardState`
- ✅ 提交逻辑 `dfSubmitCardDecisions()` 复用 `confirmed_tool` 回传
- ✅ CSS 样式（卡片、徽章、百分比条、按钮组）

### T6: 集成测试
- ⬜ 启动 web-app + Agent 后端
- ⬜ 对话触发探查流程，验证卡片渲染
- ⬜ 点击确认/驳回，验证决策回传和后续流程
