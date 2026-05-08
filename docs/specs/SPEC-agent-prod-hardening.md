# SPEC: Agent 生产化加固 (P0)

> **编号**: SPEC-agent-prod-hardening
> **版本**: 1.0
> **作者**: 丁昂
> **日期**: 2026-05-08
> **状态**: Draft
> **来源**: `sprints/backlog/tech-debt/agent-production-hardening.md` TD-01 ~ TD-03

---

## 1. 概述

本 SPEC 覆盖 Agent 模块的三项 P0 生产化改进：

| ID | 改进项 | 核心变更文件 |
|----|--------|-------------|
| TD-01 | Session 持久化到 SQLite | `session.py` |
| TD-02 | 写操作代码层拦截 | `tool_registry.py`, `planner.py`, `server.py`, 前端 |
| TD-03 | 工具执行超时 | `tool_registry.py`, `planner.py` |

---

## 2. TD-01: Session 持久化到 SQLite

### 2.1 现状

`SessionStore` (`src/backend/agent/session.py:117-161`) 使用内存 dict 存储 Session：

```python
class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}
```

模块级单例 `_store = SessionStore()` 在进程退出时全部丢失。

### 2.2 设计

**存储方案**: SQLite（零外部依赖，单文件，适合单实例部署）

**数据库位置**: `data/sessions.db`（与 `data/memory/` 同级）

**表结构**:

```sql
CREATE TABLE IF NOT EXISTS sessions (
    session_id   TEXT PRIMARY KEY,
    mode         TEXT NOT NULL,
    messages     TEXT NOT NULL,           -- JSON 序列化
    tool_calls_log TEXT NOT NULL DEFAULT '[]',  -- JSON 序列化
    created_at   REAL NOT NULL,
    last_active  REAL NOT NULL
);
```

**接口不变**: `SessionStore` 的公开接口 `create()`, `get()`, `delete()` 签名保持不变，内部实现改为读写 SQLite。

### 2.3 关键决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 同步 vs 异步 SQLite | 用 `aiosqlite` | 保持全程 async，不阻塞事件循环 |
| 每次操作都写库 vs 批量 | 每次写库 | Session 数据不能丢，写频率不高（每轮 ReAct iteration 一次） |
| WAL 模式 | 开启 | 提升并发读性能 |
| messages 存储格式 | JSON string | 简单直接，messages 本身就是 list[dict] |

### 2.4 改动细节

**`session.py` — SessionStore 改写**:

```python
class SessionStore:
    def __init__(self, db_path: Path | None = None) -> None:
        if db_path is None:
            db_path = Path(__file__).parent.parent.parent / "data" / "sessions.db"
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

    async def _get_db(self) -> aiosqlite.Connection:
        # 懒初始化连接，开启 WAL 模式
        ...

    async def create(self, mode: str, system_messages: list[dict]) -> Session:
        # 创建 Session 对象 + INSERT INTO sessions
        ...

    async def get(self, session_id: str) -> Session | None:
        # SELECT → 反序列化 → 检查过期 → 返回
        ...

    async def save(self, session: Session) -> None:
        # UPDATE messages, tool_calls_log, last_active WHERE session_id = ?
        ...

    async def delete(self, session_id: str) -> None:
        # DELETE FROM sessions WHERE session_id = ?
        ...

    async def cleanup_expired(self) -> int:
        # DELETE FROM sessions WHERE last_active < (now - TTL)
        ...
```

**影响面**:
- `planner.py` — `chat()` 方法中 `self.sessions.create/get` 需改为 `await`
- `server.py` — 无需改动（`_planning_agent.chat()` 已经是 async）
- 新增依赖: `aiosqlite`（加到 `pyproject.toml`）

### 2.5 迁移策略

- 首次启动时自动建表（`CREATE TABLE IF NOT EXISTS`）
- 无需数据迁移（旧的内存 Session 本身就是临时的）

---

## 3. TD-02: 写操作代码层拦截

### 3.1 现状

`ToolRegistry.execute()` (`tool_registry.py:57-66`) 直接调用 handler，无任何拦截：

```python
async def execute(self, name: str, arguments: dict[str, Any]) -> dict:
    defn = self._tools.get(name)
    result = await defn.handler(**arguments)
    return result
```

写操作工具的"需用户确认"仅在 prompt 中声明，LLM 可能忽略。

### 3.2 设计

**拦截机制**:

1. `@tool` 装饰器新增 `requires_confirmation: bool = False` 参数
2. `ToolDefinition` 新增 `requires_confirmation` 字段
3. `ToolRegistry.execute()` 新增 `confirmed: bool = False` 参数
4. 当 `requires_confirmation=True` 且 `confirmed=False` 时，返回特殊结构而非执行

**需标记的工具**:

| 工具 | 操作类型 | requires_confirmation |
|------|---------|----------------------|
| `create_object_type` | 写入 | True |
| `delete_object_type` | 删除 | True |
| `update_object_type_properties` | 修改 | True |
| `finalize_and_publish` | 状态变更 | True |
| `create_fabric_task` | 写入 | True |
| `generate_pipeline` | 写入 | True |

### 3.3 改动细节

**`tool_registry.py`**:

```python
@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[..., Awaitable[dict]]
    requires_confirmation: bool = False  # 新增


def tool(name, description, parameters=None, requires_confirmation=False):
    # 装饰器新增 requires_confirmation 参数
    ...


class ToolRegistry:
    async def execute(self, name, arguments, confirmed=False) -> dict:
        defn = self._tools.get(name)
        if defn.requires_confirmation and not confirmed:
            return {
                "requires_confirmation": True,
                "tool": name,
                "args": arguments,
                "message": f"工具 '{name}' 是写操作，需要用户确认后才能执行。",
            }
        return await defn.handler(**arguments)
```

**`planner.py` — ReAct loop 处理确认**:

```python
# 在 tool_call 执行后检查返回值
tool_result = await self.tools.execute(fn_name, fn_args)

if tool_result.get("requires_confirmation"):
    # datafirst 模式：暂停循环，返回确认请求给用户
    # Agent 的 messages 中记录"等待确认"
    messages.append({
        "role": "tool",
        "tool_call_id": tool_call.id,
        "content": json.dumps({
            "status": "waiting_confirmation",
            "tool": fn_name,
            "args": fn_args,
            "message": "该操作需要用户确认，已暂停等待。",
        }, ensure_ascii=False),
    })
    # 返回特殊 PlanResult 标识需要确认
    ...
```

**`server.py` — API 透传**:

```python
@app.post("/api/datafirst")
async def datafirst_agent(payload: dict[str, Any]):
    # 新增 confirmed_tool 字段
    confirmed_tool = payload.get("confirmed_tool")  # {"tool": "xxx", "args": {...}}
    ...
```

**前端**:
- 收到 `requires_confirmation` 响应时，展示确认弹窗
- 用户确认 → 带 `confirmed_tool` 重新请求
- 用户拒绝 → 发送"用户拒绝了该操作"作为 user_input

### 3.4 交互流程

```
User: "创建一个 Supplier 本体"
  ↓
Agent: 调用 list_datasources → scan_table_columns → 设计方案
Agent: "建议创建 Supplier，属性如下...确认吗？"
  ↓
User: "确认"
  ↓
Agent: 调用 create_object_type(...)
  ↓
ToolRegistry: requires_confirmation=True, confirmed=False → 返回确认请求
  ↓
Server: 返回 {"requires_confirmation": true, "tool": "create_object_type", ...}
  ↓
Frontend: 弹窗 "Agent 即将创建 ObjectType 'Supplier'，确认执行？"
  ↓
User: 点击确认
  ↓
Frontend: POST /api/datafirst {"confirmed_tool": {"tool": "create_object_type", ...}, "session_id": "xxx"}
  ↓
Server → Agent: 执行 confirmed=True 的工具调用
  ↓
Agent: "Supplier 已创建成功！"
```

---

## 4. TD-03: 工具执行超时

### 4.1 现状

`ToolRegistry.execute()` 无超时保护。`api_client.py` 的 httpx `timeout=30.0` 只覆盖 HTTP 层，工具函数内部逻辑无限制。

`_react_loop` 整体也无超时，只有 `max_iterations=15` 限制轮次。

### 4.2 设计

**两层超时**:

| 层级 | 超时 | 位置 |
|------|------|------|
| 单工具 | 60 秒 | `ToolRegistry.execute()` |
| 整个 ReAct loop | 120 秒 | `PlanningAgent._react_loop()` / `chat()` |

### 4.3 改动细节

**`tool_registry.py`**:

```python
_TOOL_TIMEOUT_SECONDS = 60

class ToolRegistry:
    async def execute(self, name, arguments, confirmed=False) -> dict:
        defn = self._tools.get(name)
        ...
        try:
            result = await asyncio.wait_for(
                defn.handler(**arguments),
                timeout=_TOOL_TIMEOUT_SECONDS,
            )
            return result
        except asyncio.TimeoutError:
            return {"error": f"工具 '{name}' 执行超时（{_TOOL_TIMEOUT_SECONDS}s），请稍后重试或检查下游服务。"}
```

**`planner.py`**:

```python
_REACT_LOOP_TIMEOUT_SECONDS = 120

async def chat(self, user_input, session_id=None):
    ...
    try:
        result = await asyncio.wait_for(
            self._react_loop(session.messages, mode, tool_calls_log),
            timeout=_REACT_LOOP_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        return PlanResult(
            success=False,
            session_id=session.session_id if session else "",
            errors=["对话处理超时（120s），请重试。可能是下游服务响应过慢。"],
        )
```

---

## 5. 影响面汇总

| 文件 | TD-01 | TD-02 | TD-03 | 改动性质 |
|------|-------|-------|-------|---------|
| `session.py` | 重写 SessionStore | - | - | 核心改动 |
| `tool_registry.py` | - | 新增确认拦截 | 新增超时 | 核心改动 |
| `planner.py` | `sessions.create/get` 改 async | 处理确认中断 | loop 超时 | 中等改动 |
| `server.py` | - | API 透传 confirmed_tool | - | 小改动 |
| `index.html` | - | 确认弹窗 UI | - | 小改动 |
| `pyproject.toml` | 新增 aiosqlite | - | - | 依赖变更 |
| `ontology_tools.py` | - | @tool 加标记 | - | 标记变更 |
| `fabric_tools.py` | - | @tool 加标记 | - | 标记变更 |

---

## 6. 不在本次范围

- P1 流式响应（SSE）—— 改动大，单独 Sprint
- P1 并行工具调用 —— 单独做
- P2/P3 token 跟踪、向量化记忆、OpenTelemetry —— 后续迭代
