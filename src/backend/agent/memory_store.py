"""Memory Store — Agent 经验记忆持久化。

三类记忆：
- success: 用户确认执行过的 DAG（few-shot 来源）
- correction: 生成失败 → 修正成功的 pair（避免重复犯错）
- preference: 用户偏好（命名风格、审批人等）

存储格式：JSON 文件，每类一个文件，data/memory/ 目录下。
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any


@dataclass
class MemoryEntry:
    id: str
    type: str
    user_input: str
    yaml_text: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: float = 0.0

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = time.time()


class MemoryStore:
    """Agent 经验记忆存储。"""

    def __init__(self, data_dir: Path | None = None) -> None:
        if data_dir is None:
            data_dir = Path(__file__).parent.parent.parent / "data" / "memory"
        self._dir = data_dir
        self._dir.mkdir(parents=True, exist_ok=True)
        self._entries: dict[str, list[MemoryEntry]] = {
            "success": [],
            "correction": [],
            "preference": [],
        }
        self._load()

    def _file_path(self, mem_type: str) -> Path:
        return self._dir / f"{mem_type}.json"

    def _load(self) -> None:
        for mem_type in self._entries:
            path = self._file_path(mem_type)
            if path.exists():
                try:
                    raw = json.loads(path.read_text(encoding="utf-8"))
                    self._entries[mem_type] = [MemoryEntry(**e) for e in raw]
                except Exception:
                    self._entries[mem_type] = []

    def _persist(self, mem_type: str) -> None:
        path = self._file_path(mem_type)
        data = [asdict(e) for e in self._entries[mem_type]]
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def save(
        self,
        mem_type: str,
        user_input: str,
        yaml_text: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> MemoryEntry:
        """保存一条记忆。"""
        if mem_type not in self._entries:
            raise ValueError(f"Invalid memory type: {mem_type}. Must be: {list(self._entries.keys())}")

        entry = MemoryEntry(
            id=f"mem-{int(time.time() * 1000)}",
            type=mem_type,
            user_input=user_input,
            yaml_text=yaml_text,
            metadata=metadata or {},
        )
        self._entries[mem_type].append(entry)

        max_per_type = 50
        if len(self._entries[mem_type]) > max_per_type:
            self._entries[mem_type] = self._entries[mem_type][-max_per_type:]

        self._persist(mem_type)
        return entry

    def search(self, keyword: str, mem_type: str = "", max_results: int = 3) -> list[MemoryEntry]:
        """按关键词搜索记忆。"""
        kw = keyword.lower()
        candidates = []
        types_to_search = [mem_type] if mem_type else list(self._entries.keys())

        for t in types_to_search:
            for entry in self._entries.get(t, []):
                score = 0
                if kw in entry.user_input.lower():
                    score += 2
                if kw in entry.yaml_text.lower():
                    score += 1
                if score > 0:
                    candidates.append((score, entry))

        candidates.sort(key=lambda x: (-x[0], -x[1].timestamp))
        return [e for _, e in candidates[:max_results]]

    def list_all(self, mem_type: str = "") -> list[MemoryEntry]:
        """列出所有记忆。"""
        if mem_type:
            return list(self._entries.get(mem_type, []))
        result = []
        for entries in self._entries.values():
            result.extend(entries)
        result.sort(key=lambda e: -e.timestamp)
        return result

    def stats(self) -> dict[str, int]:
        return {t: len(entries) for t, entries in self._entries.items()}


_memory_store: MemoryStore | None = None


def get_memory_store() -> MemoryStore:
    global _memory_store
    if _memory_store is None:
        _memory_store = MemoryStore()
    return _memory_store
