# Sprint: Data-First Agent — 自然语言驱动的数据接入全流程

> 在 workflow-engine-demo 中接入 zhice-paas 真实 REST API，用户通过自然语言完成：数据源接入 → 本体发现 → 字段映射 → Pipeline 生成

## 背景

Phase 1-5 已完成 Planning Agent 核心（ReAct Loop + 9 Tools + 7 Skills + Memory）。
本 Sprint 将 Agent 的 Tool 从 mock 替换为真实 zhice-paas web-app REST API 调用，实现端到端的数据接入流程。

### 认证方案

使用 `dev-mock-token`（web-app 内置开发模式），零配置直连。

### 已验证的 API 连通性

| API | 状态 | 备注 |
|-----|------|------|
| POST /api/v1/projects | ✅ | 需要 space_id |
| GET /ontology | ✅ | control-plane 正常 |
| POST /ontology/object-types | ✅ | snake_case 字段 |
| GET /datasources | ❌ | data-plane 未启动（IO exception） |
| POST /data-fabric/tasks | 待验证 | 依赖 data-plane |

### 测试项目

- projectId: `019e006c-7876-7413-8247-acae4614e273`
- worldId: `019e006c-7880-70c8-953a-635672ae0ade`

---

## Task 清单

### Phase 6A: 基础设施（HTTP Client + Config）

- ✅ **T1**: `api_client.py` — 统一 HTTP 客户端
  - 基于 `httpx.AsyncClient`
  - 从 config.yaml 读取 `web_app.base_url` / `project_id` / `world_id` / `auth_token`
  - 自动注入 Headers: `Authorization`, `X-Project-Id`, `X-World-Id`, `Content-Type`
  - 统一响应解析：提取 `data` 字段，非 200 抛异常
  - 超时 / 重试 / 错误日志

- ✅ **T2**: `config.yaml` 扩展
  - 新增 `web_app` 配置段
  - `base_url`, `project_id`, `world_id`, `auth_token` 四个字段
  - planner.py / server.py 初始化时加载

### Phase 6B: 数据源 Tools（2 个）

- ✅ **T3**: `list_datasources` Tool — 列出已接入的数据源
  - GET `/api/v1/projects/{projectId}/datasources`
  - 返回 {id, name, type, status, tableCount}
  - 支持 type/keyword 过滤

- ✅ **T4**: `scan_table_columns` Tool — 扫描表的列元数据
  - GET `/api/v1/projects/{projectId}/datasources/{dsId}/metadata/{tableName}/columns`
  - 返回 {name, type, nullable, pk, comment}
  - Agent 需要这些信息来推荐 ObjectType 属性

### Phase 6C: 本体管理 Tools（3 个）

- ✅ **T5**: `list_object_types` Tool — 列出已有的 ObjectType
  - GET `/api/v1/projects/{projectId}/ontology`
  - 返回 {name, displayName, status, version, propertyCount}
  - Agent 用来避免重复创建

- ✅ **T6**: `create_object_type` Tool — 创建 ObjectType + 属性
  - POST `/api/v1/projects/{projectId}/ontology/object-types`
  - 入参：type_name, display_name, description, properties[]
  - 属性：property_name, type, required, is_primary_key
  - ⚠️ 写操作，Agent 应先展示方案让用户确认

- ✅ **T7**: `ai_infer_properties` Tool — AI 属性推断
  - POST `/api/v1/projects/{projectId}/ontology/ai/infer-properties`
  - 输入：datasourceId, tableName, columns[]
  - 返回：推荐的属性列表（name, type, description）
  - 对齐 intelligence-plane 的 LLM 推断能力

### Phase 6D: 数据编织 Tools（4 个）

- ✅ **T8**: `create_fabric_task` Tool — 创建数据编织任务
  - POST `/api/v1/projects/{projectId}/data-fabric/tasks`
  - 入参：name, datasourceIds[], selectedTables[]
  - 返回 taskId，后续步骤都基于此 taskId

- ✅ **T9**: `trigger_ai_analysis` Tool — 触发 AI 语义分析
  - POST `/api/v1/projects/{projectId}/data-fabric/tasks/{taskId}/analyze`
  - 轮询 GET `.../analyze/status` 等待完成
  - 返回候选对象列表 (compare-results)

- ✅ **T10**: `get_field_mappings` Tool — 获取/生成字段映射
  - POST `.../mappings/{compareResultId}/generate` 生成建议
  - GET `.../mappings/{compareResultId}` 获取映射列表
  - 返回 {sourceColumn, targetPropertyName, status, confidence}

- ✅ **T11**: `generate_pipeline` Tool — 生成 Pipeline DSL
  - POST `/api/v1/projects/{projectId}/data-fabric/tasks/{taskId}/generate-pipeline`
  - 返回 YAML DSL 内容
  - 可选：POST `.../validate-pipeline` 校验

### Phase 6E: Domain Skills（3 个 Markdown）

- ✅ **T12**: `data-first-flow.md` — 数据接入全流程指南
  - 6 步标准流程说明（数据源 → 扫描 → 本体 → 映射 → Pipeline → 执行）
  - 每步对应的 Tool 调用
  - 典型对话示例

- ✅ **T13**: `ontology-design-rules.md` — 本体设计规范
  - ObjectType 命名规则（PascalCase、业务含义）
  - 属性类型选择指南
  - 主键设计原则
  - 常见实体模式（供应商、订单、产品等）

- ✅ **T14**: `field-mapping-rules.md` — 字段映射规范
  - 列名 → 属性名的转换规则
  - 类型映射表（SQL Type → Ontology Type）
  - 常见映射模式和陷阱

### Phase 6F: Agent 集成

- ✅ **T15**: System Prompt 改造
  - 新增 "data-first" 模式的 system prompt
  - 引导 Agent 按 6 步流程执行
  - 写操作前必须征得用户确认
  - 注入可用 Tool 和 Skill 描述

- ✅ **T16**: 端到端联调测试
  - 启动 web-app + control-plane
  - 测试全流程：自然语言 → Agent 调用真实 API → 本体创建 → Pipeline 生成
  - 验证错误处理（API 不可用、参数错误等）

---

## 依赖关系

```
T1 + T2 先行（基础设施）
  ↓
T3~T11 并行（各 Tool 独立，都依赖 T1 的 api_client）
T12~T14 并行（纯 Markdown，无代码依赖）
  ↓
T15 依赖 T3~T14 全部完成
  ↓
T16 依赖 T15
```

## 验收标准

1. `config.yaml` 配好 web_app 段后，Agent 可直接调用真实 API
2. Agent 能根据自然语言（如"帮我把 PostgreSQL 里的 supplier 表接入系统"）自动编排 Tool 调用
3. 写操作（创建 ObjectType、创建 Pipeline）前 Agent 展示方案，等用户确认
4. API 异常时 Agent 给出有意义的错误提示，不崩溃
5. 全流程可演示：数据源列表 → 表扫描 → AI 推荐本体 → 创建 ObjectType → 字段映射 → 生成 Pipeline
