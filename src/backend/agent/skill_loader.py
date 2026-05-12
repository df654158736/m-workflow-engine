"""Skill Loader v2 — 三层技能架构。

Layer 1: Core Rules (_core/) — 始终注入 system prompt 的硬规则
Layer 2: Skill Catalog — 技能索引表，Agent 知道有什么可以查
Layer 3: Skill Detail — Agent 通过 get_skill_detail 工具按需加载

Skills 以文件夹形式存放在 skills/ 目录下：
  skills/
  ├── _core/              # Layer 1: 核心规则
  │   ├── workflow-rules.md
  │   └── datafirst-rules.md
  ├── {skill-name}/       # Layer 3: 按需查询
  │   ├── SKILL.md        # 摘要 + frontmatter (含 catalog 字段)
  │   └── references/     # 详细内容
  │       ├── section-a.md
  │       └── section-b.md
  └── domain/             # 领域子目录
      └── {domain-name}/
          ├── SKILL.md
          └── references/

Frontmatter 格式 (_core):
---
name: workflow-core
type: core
mode: workflow
---

Frontmatter 格式 (SKILL.md):
---
name: skill-name
description: 一行描述
mode: workflow | datafirst | all
catalog: 技能目录中显示的一句话（Agent 看到这句话决定是否查询）
sections:
  - section-name: section 描述
---
"""

from __future__ import annotations

import re
from pathlib import Path
from dataclasses import dataclass, field

import yaml


@dataclass
class CoreRule:
    name: str
    mode: str
    content: str


@dataclass
class Skill:
    name: str
    description: str
    mode: str
    catalog_entry: str
    sections: dict[str, str]
    skill_md_content: str
    base_path: Path


class SkillLoader:
    """三层技能加载器。"""

    def __init__(self, skills_dir: Path | None = None) -> None:
        if skills_dir is None:
            skills_dir = Path(__file__).parent / "skills"
        self._skills_dir = skills_dir
        self._core_rules: list[CoreRule] = []
        self._skills: dict[str, Skill] = {}
        self._load_all()

    _FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)

    def _parse_frontmatter(self, raw: str) -> tuple[dict, str]:
        m = self._FRONTMATTER_RE.match(raw)
        if not m:
            return {}, raw
        try:
            meta = yaml.safe_load(m.group(1)) or {}
        except yaml.YAMLError:
            meta = {}
        body = raw[m.end():]
        return meta, body

    def _load_all(self) -> None:
        self._load_core_rules()
        self._load_skills()

    def _load_core_rules(self) -> None:
        core_dir = self._skills_dir / "_core"
        if not core_dir.exists():
            return
        for md_file in sorted(core_dir.glob("*.md")):
            raw = md_file.read_text(encoding="utf-8")
            meta, body = self._parse_frontmatter(raw)
            if meta.get("type") != "core":
                continue
            self._core_rules.append(CoreRule(
                name=meta.get("name", md_file.stem),
                mode=meta.get("mode", "all"),
                content=body,
            ))

    def _load_skills(self) -> None:
        if not self._skills_dir.exists():
            return
        for skill_md in self._skills_dir.rglob("SKILL.md"):
            skill_dir = skill_md.parent
            raw = skill_md.read_text(encoding="utf-8")
            meta, body = self._parse_frontmatter(raw)

            name = meta.get("name", skill_dir.name)
            rel = skill_dir.relative_to(self._skills_dir)
            if str(rel) != skill_dir.name:
                name = str(rel).replace("\\", "/")

            sections_meta = meta.get("sections", [])
            sections: dict[str, str] = {}
            refs_dir = skill_dir / "references"
            if refs_dir.exists():
                for ref_file in refs_dir.glob("*.md"):
                    section_name = ref_file.stem
                    sections[section_name] = ref_file.read_text(encoding="utf-8")

            self._skills[name] = Skill(
                name=name,
                description=meta.get("description", ""),
                mode=meta.get("mode", "all"),
                catalog_entry=meta.get("catalog", meta.get("description", "")),
                sections=sections,
                skill_md_content=body,
                base_path=skill_dir,
            )

    def _mode_match(self, item_mode: str, request_mode: str) -> bool:
        if item_mode == "all":
            return True
        return item_mode == request_mode

    # ── Layer 1: Core Rules ──

    def load_core(self, mode: str) -> str:
        """返回指定模式的核心规则（始终注入 system prompt）。"""
        parts = []
        for rule in self._core_rules:
            if self._mode_match(rule.mode, mode):
                parts.append(rule.content)
        return "\n".join(parts)

    # ── Layer 2: Skill Catalog ──

    def load_catalog(self, mode: str) -> str:
        """返回技能目录索引（始终注入 system prompt）。"""
        lines = ["| 技能名 | 用途 |", "|--------|------|"]
        for name, skill in sorted(self._skills.items()):
            if not self._mode_match(skill.mode, mode):
                continue
            sections_hint = ""
            if skill.sections:
                section_names = ", ".join(f'"{s}"' for s in skill.sections.keys())
                sections_hint = f"（sections: {section_names}）"
            lines.append(f"| `{name}` | {skill.catalog_entry}{sections_hint} |")
        return "\n".join(lines)

    # ── Layer 3: Skill Detail ──

    def get_skill_detail(self, skill_name: str, section: str | None = None) -> dict:
        """按需返回技能详细内容（供 Agent 工具调用）。

        skill_name: 技能名（如 "dag-quality", "domain/supply-chain"）
        section: 可选，指定 section 名（如 "validate-errors"）。
                 为空返回 SKILL.md 内容 + 可用 sections 列表。
        """
        skill = self._skills.get(skill_name)
        if not skill:
            available = [n for n in self._skills.keys()]
            return {
                "error": f"技能 '{skill_name}' 不存在",
                "available_skills": available,
            }

        if section is None:
            result: dict = {
                "skill": skill_name,
                "content": skill.skill_md_content,
            }
            if skill.sections:
                result["available_sections"] = list(skill.sections.keys())
                result["hint"] = "调用 get_skill_detail(skill_name, section) 查看具体 section 的详细内容"
            return result

        content = skill.sections.get(section)
        if content is None:
            return {
                "error": f"技能 '{skill_name}' 没有 section '{section}'",
                "available_sections": list(skill.sections.keys()),
            }

        return {
            "skill": skill_name,
            "section": section,
            "content": content,
        }

    # ── 兼容旧接口（过渡期保留） ──

    def load_relevant(
        self,
        user_input: str,
        mode: str = "workflow",
        max_skills: int = 5,
        max_total_chars: int = 32000,
    ) -> str:
        """兼容旧接口：返回 core rules + catalog（不再返回全部 skill 内容）。"""
        core = self.load_core(mode)
        catalog = self.load_catalog(mode)
        parts = []
        if core:
            parts.append(core)
        if catalog:
            parts.append(
                "\n## 可用领域知识\n\n"
                "需要详细的规则、示例或 few-shot 时，调用 `get_skill_detail(skill_name, section)` 工具查询。\n\n"
                + catalog
            )
        return "\n".join(parts)

    # ── 工具列表 ──

    def list_skills(self, mode: str | None = None) -> list[dict]:
        """列出所有 Skill。"""
        result = []
        for name, skill in self._skills.items():
            if mode and not self._mode_match(skill.mode, mode):
                continue
            result.append({
                "name": name,
                "description": skill.description,
                "mode": skill.mode,
                "catalog": skill.catalog_entry,
                "sections": list(skill.sections.keys()),
            })
        return result
