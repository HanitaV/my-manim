"""CLI command to install the mandatory ``manim.cinema`` skill and ``AGENTS.md`` rule."""

from __future__ import annotations

from pathlib import Path

import cloup

from manim._config import console
from manim.cinema.skill import install_cinema_skill
from manim.constants import CONTEXT_SETTINGS

__all__ = ["cinema_skill"]


@cloup.command(
    "cinema-skill",
    context_settings=CONTEXT_SETTINGS,
    help="Install the mandatory manim.cinema agent skill and AGENTS.md rule into a video project.",
)
@cloup.argument(
    "target_dir",
    type=cloup.Path(path_type=Path),
    default=Path("."),
    required=False,
)
@cloup.option(
    "--global",
    "global_install",
    is_flag=True,
    default=False,
    help="Install into user-global ~/.agents and ~/.gemini skill directories.",
)
@cloup.option(
    "--claude/--no-claude",
    default=False,
    help="Also install under .claude/skills/cinema-director.",
)
@cloup.option(
    "--agents-md/--no-agents-md",
    default=True,
    help="Create or update AGENTS.md with the mandatory manim.cinema rule.",
)
def cinema_skill(
    target_dir: Path,
    global_install: bool,
    claude: bool,
    agents_md: bool,
) -> None:
    """Install ``cinema-director`` skill and ``AGENTS.md`` rule into ``target_dir``."""
    written = install_cinema_skill(
        target_dir,
        global_install=global_install,
        write_agents_md=agents_md,
        claude=claude,
    )
    console.print(f"[green]Installed cinema-director skill ({len(written)} files):[/green]")
    for path in written:
        console.print(f"  - {path}")
