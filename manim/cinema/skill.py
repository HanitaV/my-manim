"""Skill & AGENTS.md installer helpers bundled inside ``manim.cinema``."""

from __future__ import annotations

from pathlib import Path

__all__ = ["install_cinema_skill"]

_ASSETS_DIR = Path(__file__).resolve().parent / "_skill_assets"
_MARKER_START = "<!-- manim-cinema:start -->"
_MARKER_END = "<!-- manim-cinema:end -->"


def _upsert_agents_md(path: Path, section: str) -> Path:
    block = f"{_MARKER_START}\n{section.strip()}\n{_MARKER_END}\n"
    if path.exists():
        existing = path.read_text(encoding="utf-8")
        if _MARKER_START in existing and _MARKER_END in existing:
            pre, rest = existing.split(_MARKER_START, 1)
            _, post = rest.split(_MARKER_END, 1)
            updated = pre.rstrip()
            if updated:
                updated += "\n\n"
            updated += block
            if post.strip():
                updated += "\n" + post.lstrip()
            path.write_text(updated, encoding="utf-8")
            return path
        joined = existing.rstrip()
        if joined:
            joined += "\n\n"
        path.write_text(joined + block, encoding="utf-8")
        return path
    path.write_text(block, encoding="utf-8")
    return path


def _write_skill_tree(skill_root: Path) -> list[Path]:
    written: list[Path] = []
    skill_root.mkdir(parents=True, exist_ok=True)
    refs_dir = skill_root / "references"
    examples_dir = skill_root / "examples"
    refs_dir.mkdir(parents=True, exist_ok=True)
    examples_dir.mkdir(parents=True, exist_ok=True)

    mapping = (
        (_ASSETS_DIR / "SKILL.md", skill_root / "SKILL.md"),
        (_ASSETS_DIR / "api-cheatsheet.md", refs_dir / "api-cheatsheet.md"),
        (
            _ASSETS_DIR / "kinematics_cinema_example.py.tmpl",
            examples_dir / "kinematics_cinema_example.py",
        ),
    )
    for src, dst in mapping:
        dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        written.append(dst)
    return written


def install_cinema_skill(
    target_dir: str | Path = ".",
    *,
    global_install: bool = False,
    write_agents_md: bool = True,
    claude: bool = False,
) -> list[Path]:
    """Install the mandatory ``cinema-director`` skill and ``AGENTS.md`` rule.

    Parameters
    ----------
    target_dir
        Project root when ``global_install`` is ``False``.
    global_install
        Install into user-global agent skill directories instead of a project folder.
    write_agents_md
        Create or idempotently update ``AGENTS.md`` in ``target_dir``.
    claude
        Also install under ``.claude/skills/cinema-director``.
    """
    written: list[Path] = []
    if global_install:
        home = Path.home()
        targets = [
            home / ".agents" / "skills" / "cinema-director",
            home / ".gemini" / "config" / "skills" / "cinema-director",
        ]
        if claude:
            targets.append(home / ".claude" / "skills" / "cinema-director")
        for root in targets:
            written.extend(_write_skill_tree(root))
        return written

    root_dir = Path(target_dir).resolve()
    skill_roots = [root_dir / ".agents" / "skills" / "cinema-director"]
    if claude or (root_dir / ".claude").exists():
        skill_roots.append(root_dir / ".claude" / "skills" / "cinema-director")

    for skill_root in skill_roots:
        written.extend(_write_skill_tree(skill_root))

    if write_agents_md:
        rule_text = (_ASSETS_DIR / "AGENTS_RULE.md").read_text(encoding="utf-8")
        written.append(_upsert_agents_md(root_dir / "AGENTS.md", rule_text))

    return written
