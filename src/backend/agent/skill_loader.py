"""Skill Loader — 按需加载领域知识到 Agent context。

Skills 以 Markdown 文件存放在 skills/ 目录下。
Agent 规划前根据用户输入的关键词匹配加载相关 Skill。
扩展方式：新建 .md 文件放入 skills/ 目录即可。
"""

from __future__ import annotations

import os
from pathlib import Path
from dataclasses import dataclass


@dataclass
class Skill:
    name: str
    path: str
    content: str
    keywords: list[str]


class SkillLoader:
    """加载和匹配 Skills。"""

    def __init__(self, skills_dir: Path | None = None) -> None:
        if skills_dir is None:
            skills_dir = Path(__file__).parent / "skills"
        self._skills_dir = skills_dir
        self._skills: list[Skill] = []
        self._load_all()

    def _load_all(self) -> None:
        """扫描 skills 目录，加载所有 .md 文件。"""
        if not self._skills_dir.exists():
            return
        for md_file in self._skills_dir.rglob("*.md"):
            content = md_file.read_text(encoding="utf-8")
            name = md_file.stem
            keywords = self._extract_keywords(content, name)
            self._skills.append(Skill(
                name=name,
                path=str(md_file.relative_to(self._skills_dir)),
                content=content,
                keywords=keywords,
            ))

    def _extract_keywords(self, content: str, name: str) -> list[str]:
        """从文件名和首行标题提取关键词。"""
        keywords = name.replace("-", " ").replace("_", " ").split()
        lines = content.strip().split("\n")
        if lines and lines[0].startswith("#"):
            title = lines[0].lstrip("#").strip()
            keywords.extend(title.lower().split())
        return [k.lower() for k in keywords if len(k) > 1]

    def load_relevant(self, user_input: str, max_skills: int = 3) -> str:
        """根据用户输入匹配最相关的 Skills，拼接为 context 文本。"""
        input_lower = user_input.lower()
        scored: list[tuple[int, Skill]] = []
        for skill in self._skills:
            score = sum(1 for kw in skill.keywords if kw in input_lower)
            if score > 0:
                scored.append((score, skill))

        # Always include dag-quality-rules if exists
        always_load = {"dag-quality-rules", "node-type-guide"}
        for skill in self._skills:
            if skill.name in always_load and skill not in [s for _, s in scored]:
                scored.append((0, skill))

        scored.sort(key=lambda x: -x[0])
        selected = scored[:max_skills]

        if not selected:
            # Load defaults if nothing matches
            for skill in self._skills:
                if skill.name in always_load:
                    selected.append((0, skill))

        parts = []
        for _, skill in selected:
            parts.append(f"--- Skill: {skill.name} ---\n{skill.content}\n")
        return "\n".join(parts)

    def list_skills(self) -> list[dict]:
        return [{"name": s.name, "path": s.path, "keywords": s.keywords} for s in self._skills]
