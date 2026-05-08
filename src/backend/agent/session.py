"""Session Store — 服务端会话管理（SQLite 持久化）。

每个对话维护一个 Session，持有完整的 messages 数组（含 tool_call / tool_result）。
用户新消息追加到同一个 messages 继续 ReAct 循环，而不是每次重建。

上下文管理策略：
1. tool_result 超长时截断（最大的上下文占用来源）
2. 对话轮数过多时，压缩早期的 tool_result 为摘要
3. Session 超时自动清理（默认 30 分钟）

持久化策略：
- SQLite（零外部依赖），WAL 模式
- 每轮 ReAct iteration 结束后 save()
- 进程重启可恢复所有未过期 Session
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import aiosqlite
import structlog

logger = structlog.get_logger()

_TOOL_RESULT_MAX_CHARS = 2000
_SESSION_TTL_SECONDS = 30 * 60
_MAX_MESSAGES = 120
_COMPACT_TRIGGER = 80

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id   TEXT PRIMARY KEY,
    mode         TEXT NOT NULL,
    messages     TEXT NOT NULL,
    tool_calls_log TEXT NOT NULL DEFAULT '[]',
    created_at   REAL NOT NULL,
    last_active  REAL NOT NULL
)
"""


@dataclass
class Session:
    session_id: str
    mode: str
    messages: list[dict[str, Any]] = field(default_factory=list)
    tool_calls_log: list[dict] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)

    def touch(self) -> None:
        self.last_active = time.time()

    @property
    def expired(self) -> bool:
        return time.time() - self.last_active > _SESSION_TTL_SECONDS

    @property
    def message_count(self) -> int:
        return len(self.messages)

    def needs_compact(self) -> bool:
        return len(self.messages) > _COMPACT_TRIGGER

    def compact(self) -> None:
        """压缩早期消息，保留 system prompt + 最近的对话。"""
        if len(self.messages) <= _COMPACT_TRIGGER:
            return

        system_msgs = []
        rest_msgs = []
        for m in self.messages:
            if m.get("role") == "system":
                system_msgs.append(m)
            else:
                rest_msgs.append(m)

        keep_recent = 40
        if len(rest_msgs) <= keep_recent:
            return

        early = rest_msgs[:-keep_recent]
        recent = rest_msgs[-keep_recent:]

        summary_parts = []
        for m in early:
            role = m.get("role", "")
            content = m.get("content", "")
            if role == "user":
                summary_parts.append(f"[用户] {content[:100]}")
            elif role == "assistant":
                text = content[:150] if content else "(tool_call)"
                summary_parts.append(f"[助手] {text}")
            elif role == "tool":
                tc_content = content[:80] if content else ""
                summary_parts.append(f"[工具结果] {tc_content}")

        summary = {
            "role": "user",
            "content": "【系统：以下是早期对话摘要，供你参考上下文】\n" + "\n".join(summary_parts[-20:]),
        }
        ack = {
            "role": "assistant",
            "content": "好的，我了解之前的对话上下文，继续当前任务。",
        }

        self.messages = system_msgs + [summary, ack] + recent
        logger.info(
            "Session compacted",
            session_id=self.session_id,
            before=len(system_msgs) + len(early) + len(recent),
            after=len(self.messages),
        )


def truncate_tool_result(content: str) -> str:
    """截断过长的 tool_result，保留头尾。"""
    if len(content) <= _TOOL_RESULT_MAX_CHARS:
        return content
    head = content[:1200]
    tail = content[-600:]
    return head + '\n... [结果已截断] ...\n' + tail


class SessionStore:
    """SQLite 持久化的 Session 管理器。"""

    def __init__(self, db_path: Path | None = None) -> None:
        if db_path is None:
            db_path = Path(__file__).parent.parent.parent.parent / "data" / "sessions.db"
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db: aiosqlite.Connection | None = None

    async def _get_db(self) -> aiosqlite.Connection:
        if self._db is None or not self._db.is_alive:
            self._db = await aiosqlite.connect(str(self._db_path))
            await self._db.execute("PRAGMA journal_mode=WAL")
            await self._db.execute(_CREATE_TABLE_SQL)
            await self._db.commit()
        return self._db

    async def create(self, mode: str, system_messages: list[dict[str, Any]]) -> Session:
        session_id = str(uuid.uuid4())[:8]
        now = time.time()
        session = Session(
            session_id=session_id,
            mode=mode,
            messages=list(system_messages),
            created_at=now,
            last_active=now,
        )
        db = await self._get_db()
        await db.execute(
            "INSERT INTO sessions (session_id, mode, messages, tool_calls_log, created_at, last_active) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                session_id,
                mode,
                json.dumps(session.messages, ensure_ascii=False),
                "[]",
                now,
                now,
            ),
        )
        await db.commit()
        await self._cleanup_expired()
        logger.info("Session created", session_id=session_id, mode=mode)
        return session

    async def get(self, session_id: str) -> Session | None:
        db = await self._get_db()
        async with db.execute(
            "SELECT session_id, mode, messages, tool_calls_log, created_at, last_active "
            "FROM sessions WHERE session_id = ?",
            (session_id,),
        ) as cursor:
            row = await cursor.fetchone()
        if not row:
            return None

        session = Session(
            session_id=row[0],
            mode=row[1],
            messages=json.loads(row[2]),
            tool_calls_log=json.loads(row[3]),
            created_at=row[4],
            last_active=row[5],
        )
        if session.expired:
            await self.delete(session_id)
            logger.info("Session expired", session_id=session_id)
            return None

        session.touch()
        return session

    async def save(self, session: Session) -> None:
        db = await self._get_db()
        await db.execute(
            "UPDATE sessions SET messages = ?, tool_calls_log = ?, last_active = ? "
            "WHERE session_id = ?",
            (
                json.dumps(session.messages, ensure_ascii=False),
                json.dumps(session.tool_calls_log, ensure_ascii=False),
                session.last_active,
                session.session_id,
            ),
        )
        await db.commit()

    async def delete(self, session_id: str) -> None:
        db = await self._get_db()
        await db.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
        await db.commit()

    async def _cleanup_expired(self) -> None:
        cutoff = time.time() - _SESSION_TTL_SECONDS
        db = await self._get_db()
        cursor = await db.execute(
            "DELETE FROM sessions WHERE last_active < ?", (cutoff,)
        )
        if cursor.rowcount and cursor.rowcount > 0:
            logger.info("Cleaned up expired sessions", count=cursor.rowcount)
        await db.commit()

    async def close(self) -> None:
        if self._db:
            await self._db.close()
            self._db = None


_store = SessionStore()


def get_session_store() -> SessionStore:
    return _store
