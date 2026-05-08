"""Session Store — 服务端会话管理。

每个对话维护一个 Session，持有完整的 messages 数组（含 tool_call / tool_result）。
用户新消息追加到同一个 messages 继续 ReAct 循环，而不是每次重建。

上下文管理策略：
1. tool_result 超长时截断（最大的上下文占用来源）
2. 对话轮数过多时，压缩早期的 tool_result 为摘要
3. Session 超时自动清理（默认 30 分钟）
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

import structlog

logger = structlog.get_logger()

_TOOL_RESULT_MAX_CHARS = 2000
_SESSION_TTL_SECONDS = 30 * 60
_MAX_MESSAGES = 120
_COMPACT_TRIGGER = 80


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
        """压缩早期消息，保留 system prompt + 最近的对话。

        策略：保留 system 消息 + 最近 40 条消息，
        中间的 tool_result 压缩为摘要。
        """
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
    """内存中的 Session 管理器。"""

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}

    def create(self, mode: str, system_messages: list[dict[str, Any]]) -> Session:
        """创建新 Session，注入 system prompt。"""
        session_id = str(uuid.uuid4())[:8]
        session = Session(
            session_id=session_id,
            mode=mode,
            messages=list(system_messages),
        )
        self._sessions[session_id] = session
        self._cleanup_expired()
        logger.info("Session created", session_id=session_id, mode=mode)
        return session

    def get(self, session_id: str) -> Session | None:
        session = self._sessions.get(session_id)
        if session and session.expired:
            del self._sessions[session_id]
            logger.info("Session expired", session_id=session_id)
            return None
        if session:
            session.touch()
        return session

    def delete(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    def _cleanup_expired(self) -> None:
        expired = [sid for sid, s in self._sessions.items() if s.expired]
        for sid in expired:
            del self._sessions[sid]
        if expired:
            logger.info("Cleaned up expired sessions", count=len(expired))


_store = SessionStore()


def get_session_store() -> SessionStore:
    return _store
