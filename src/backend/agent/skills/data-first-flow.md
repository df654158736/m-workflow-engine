# 数据接入全流程指南（Data-First Flow）

## 标准 6 步流程

用户给出自然语言需求时，按以下顺序执行数据接入：

### Step 1: 查看数据源
调用 `list_datasources` 查看已有数据源。如果目标数据源不存在，告知用户需要先在系统中添加数据源。

### Step 2: 扫描表结构
调用 `scan_table_columns` 获取目标表的列元数据（列名、类型、是否主键）。这些信息是后续本体设计的依据。

### Step 3: 设计本体（ObjectType）
有两种方式：
- **AI 推荐**：调用 `ai_infer_properties`，让 AI 根据表列推荐 ObjectType 属性
- **手动设计**：根据表列和业务含义，Agent 自行推荐属性方案

设计完成后，向用户展示方案并征得确认。

### Step 4: 创建 ObjectType
用户确认后，调用 `create_object_type` 创建本体对象类型。

### Step 5: 创建编织任务 + 字段映射
1. 调用 `create_fabric_task` 创建数据编织任务
2. 调用 `trigger_ai_analysis` 触发 AI 语义分析
3. 调用 `get_field_mappings` 获取字段映射建议

### Step 6: 生成 Pipeline
调用 `generate_pipeline` 生成 Pipeline DSL。向用户展示 DSL 和校验结果。

## 关键原则

1. **写操作必须确认** — 创建 ObjectType、创建编织任务前，必须向用户展示方案
2. **渐进式推进** — 每步完成后汇报结果，等用户确认再继续
3. **错误恢复** — API 调用失败时，给出有意义的提示，而不是直接失败
4. **已有资源复用** — 操作前先查已有 ObjectType 和数据源，避免重复创建

## 典型对话

用户："帮我把 PostgreSQL 的 supplier 表接入系统"

Agent 行动序列：
1. `list_datasources(keyword="postgres")` → 找到 PostgreSQL 数据源
2. `scan_table_columns(ds_id, "supplier")` → 获取列信息
3. `list_object_types(keyword="supplier")` → 检查是否已有 Supplier 类型
4. 向用户展示推荐的 ObjectType 属性方案
5. 用户确认 → `create_object_type(...)` → 创建
6. `create_fabric_task(...)` → 创建编织任务
7. `trigger_ai_analysis(...)` → AI 分析
8. `get_field_mappings(...)` → 字段映射
9. `generate_pipeline(...)` → 生成 Pipeline
10. 向用户展示最终 Pipeline DSL
