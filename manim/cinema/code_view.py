"""Frosted-glass code block with monochrome-mineral highlighting, spotlight, and diffing."""

from __future__ import annotations

import difflib
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from pygments.style import Style
from pygments.token import (
    Comment,
    Keyword,
    Name,
    Number,
    Operator,
    Punctuation,
    String,
)
from pygments.token import (
    Text as TextToken,
)

from manim.animation.animation import Animation
from manim.animation.fading import FadeIn, FadeOut
from manim.animation.transform import Transform
from manim.animation.updaters.update import UpdateFromAlphaFunc
from manim.constants import LEFT, RIGHT, UP
from manim.mobject.geometry.arc import Dot
from manim.mobject.glass import GlassPanel
from manim.mobject.text.code_mobject import Code
from manim.mobject.text.text_mobject import Text
from manim.mobject.types.vectorized_mobject import VGroup, VMobject
from manim.utils.rate_functions import RateFunction, cinema_spring_smooth

from .palette import CINEMA_SILVER
from .synth import SFX_SOFT_TICK

if TYPE_CHECKING:
    from manim.scene.scene import Scene

__all__ = [
    "CinemaMonochromeStyle",
    "GlassCode",
]


class CinemaMonochromeStyle(Style):
    """Restrained dark-luxury Pygments palette (monochrome hierarchy + mineral accents)."""

    background_color = "#0A0A0A"
    highlight_color = "#1F1F1F"
    line_number_color = "#6E6E6E"

    styles = {
        TextToken: "#EDEDED",
        Keyword: "#9CC2DC",
        Keyword.Constant: "#D8C39E",
        Name: "#FAFAFA",
        Name.Function: "#FFFFFF",
        Name.Class: "#E5E5E5",
        Name.Decorator: "#D8C39E",
        String: "#D8C39E",
        Number: "#6EC49E",
        Operator: "#B8B8B8",
        Punctuation: "#949494",
        Comment: "italic #737373",
    }


def _expand_line_targets(specs: Sequence[int | tuple[int, int]], max_lines: int) -> set[int]:
    chosen: set[int] = set()
    for item in specs:
        if isinstance(item, tuple):
            lo, hi = int(item[0]), int(item[1])
            for ln in range(min(lo, hi), max(lo, hi) + 1):
                if 1 <= ln <= max_lines:
                    chosen.add(ln)
        else:
            ln = int(item)
            if 1 <= ln <= max_lines:
                chosen.add(ln)
    return chosen


def _vmob_alpha(vmob: VMobject) -> float:
    if hasattr(vmob, "fill_rgbas") and len(vmob.fill_rgbas) > 0:
        return float(vmob.fill_rgbas[0, 3])
    if len(vmob.submobjects) > 0 and isinstance(vmob.submobjects[0], VMobject):
        return _vmob_alpha(vmob.submobjects[0])
    return 1.0


def _collect_glyph_targets(
    vmobs: Sequence[tuple[VMobject, float]],
    *,
    run_time: float,
    rate_func: RateFunction,
    owner: VMobject,
) -> Animation:
    entries = [(m, _vmob_alpha(m), float(target_op)) for m, target_op in vmobs]

    def _update(_mob: Any, alpha: float) -> None:
        for m, a0, a1 in entries:
            m.set_opacity(a0 * (1.0 - alpha) + a1 * alpha)

    return UpdateFromAlphaFunc(owner, _update, run_time=run_time, rate_func=rate_func)


class GlassCode(VGroup):
    """Frosted-glass syntax-highlighted code window with line/token focus and live diffing."""

    def __init__(
        self,
        code_string: str,
        *,
        language: str = "python",
        title: str | None = None,
        font_size: float = 20,
        add_line_numbers: bool = True,
        padding: tuple[float, float] = (0.48, 0.42),
        corner_radius: float = 0.26,
        **glass_kwargs: Any,
    ) -> None:
        super().__init__()
        self.raw_code = code_string.strip("\n")
        self.raw_lines = self.raw_code.splitlines() or [""]
        self._language = language
        self._title = title
        self._font_size = font_size
        self._add_line_numbers = add_line_numbers
        self._padding = (float(padding[0]), float(padding[1]))
        self._corner_radius = float(corner_radius)
        self._glass_kwargs = dict(glass_kwargs)
        self._glass_kwargs.setdefault("sheen_opacity", 0.04)

        inner = Code(
            code_string=self.raw_code,
            language=language,
            formatter_style=CinemaMonochromeStyle,
            add_line_numbers=add_line_numbers,
            background="rectangle",
            background_config={"fill_opacity": 0.0, "stroke_width": 0.0},
            paragraph_config={"font_size": font_size, "line_spacing": 0.65},
        )
        self.code_lines = inner.code_lines
        self.line_numbers = getattr(inner, "line_numbers", None)

        code_block = VGroup(self.code_lines)
        if self.line_numbers is not None:
            code_block.add(self.line_numbers)

        header_dots = VGroup(
            Dot(radius=0.055, color="#333333", stroke_width=0),
            Dot(radius=0.055, color="#525252", stroke_width=0),
            Dot(radius=0.055, color="#737373", stroke_width=0),
        ).arrange(RIGHT, buff=0.09)
        if title:
            title_lbl = Text(title, font_size=max(13, font_size * 0.68), color=CINEMA_SILVER)
            header = VGroup(header_dots, title_lbl).arrange(RIGHT, buff=0.18)
        else:
            header = header_dots

        header.next_to(code_block, UP, buff=0.22).align_to(code_block, LEFT)
        self.header = header

        content = VGroup(self.header, code_block)
        w = float(content.width) + 2.0 * self._padding[0]
        h = float(content.height) + 2.0 * self._padding[1]
        self.panel = GlassPanel(
            width=max(2.6, w),
            height=max(1.2, h),
            corner_radius=self._corner_radius,
            **self._glass_kwargs,
        ).move_to(content.get_center())

        self.add(self.panel, self.header)
        if self.line_numbers is not None:
            self.add(self.line_numbers)
        self.add(self.code_lines)

    def focus_lines(
        self,
        *lines_or_ranges: int | tuple[int, int],
        dim_opacity: float = 0.20,
        run_time: float = 0.45,
        rate_func: RateFunction = cinema_spring_smooth,
    ) -> Animation:
        """Spotlight selected 1-based lines (or ``(start, end)`` tuples) while dimming others."""
        chosen = _expand_line_targets(lines_or_ranges, len(self.code_lines))
        targets: list[tuple[VMobject, float]] = []
        for idx, line in enumerate(self.code_lines, start=1):
            op = 1.0 if idx in chosen else float(dim_opacity)
            targets.append((line, op))
            if self.line_numbers is not None and idx - 1 < len(self.line_numbers):
                targets.append((self.line_numbers[idx - 1], op))
        return _collect_glyph_targets(targets, run_time=run_time, rate_func=rate_func, owner=self)

    def focus_token(
        self,
        line_no: int,
        token: str,
        *,
        occurrence: int = 0,
        dim_opacity: float = 0.20,
        run_time: float = 0.45,
        rate_func: RateFunction = cinema_spring_smooth,
    ) -> Animation:
        """Spotlight a specific ``token`` substring on 1-based ``line_no``."""
        if not (1 <= line_no <= len(self.raw_lines)):
            raise IndexError(f"Line {line_no} out of range (1..{len(self.raw_lines)}).")
        raw_line = self.raw_lines[line_no - 1]
        pos = -1
        search_from = 0
        for _ in range(occurrence + 1):
            pos = raw_line.find(token, search_from)
            if pos < 0:
                raise ValueError(f"Token {token!r} not found on line {line_no}.")
            search_from = pos + len(token)

        glyph_start = sum(1 for ch in raw_line[:pos] if not ch.isspace())
        glyph_len = sum(1 for ch in token if not ch.isspace())
        targets: list[tuple[VMobject, float]] = []

        for idx, line in enumerate(self.code_lines, start=1):
            if idx != line_no:
                targets.append((line, dim_opacity))
                if self.line_numbers is not None and idx - 1 < len(self.line_numbers):
                    targets.append((self.line_numbers[idx - 1], dim_opacity))
                continue

            if self.line_numbers is not None and idx - 1 < len(self.line_numbers):
                targets.append((self.line_numbers[idx - 1], 1.0))
            hi = min(glyph_start + glyph_len, len(line.submobjects))
            for g_idx, glyph in enumerate(line.submobjects):
                op = 1.0 if glyph_start <= g_idx < hi else float(dim_opacity)
                targets.append((glyph, op))

        return _collect_glyph_targets(targets, run_time=run_time, rate_func=rate_func, owner=self)

    def reset_focus(
        self,
        *,
        run_time: float = 0.40,
        rate_func: RateFunction = cinema_spring_smooth,
    ) -> Animation:
        """Restore full opacity across all lines and line numbers."""
        targets: list[tuple[VMobject, float]] = [(line, 1.0) for line in self.code_lines]
        if self.line_numbers is not None:
            targets.extend((ln, 1.0) for ln in self.line_numbers)
        return _collect_glyph_targets(targets, run_time=run_time, rate_func=rate_func, owner=self)

    def animate_diff(
        self,
        scene: Scene,
        new_code: str,
        *,
        run_time: float = 0.85,
        rate_func: RateFunction = cinema_spring_smooth,
        sound: bool = True,
    ) -> GlassCode:
        """Morph smoothly from ``self`` to ``new_code`` via line-level ``difflib`` opcodes."""
        nxt = GlassCode(
            new_code,
            language=self._language,
            title=self._title,
            font_size=self._font_size,
            add_line_numbers=self._add_line_numbers,
            padding=self._padding,
            corner_radius=self._corner_radius,
            **self._glass_kwargs,
        )
        nxt.move_to(self.get_center())
        nxt.set_z_index(self.z_index)

        matcher = difflib.SequenceMatcher(None, self.raw_lines, nxt.raw_lines)
        anims: list[Animation] = [
            Transform(self.panel, nxt.panel.copy(), rate_func=rate_func),
            Transform(self.header, nxt.header.copy(), rate_func=rate_func),
        ]
        if self.line_numbers is not None and nxt.line_numbers is not None:
            anims.append(
                Transform(self.line_numbers, nxt.line_numbers.copy(), rate_func=rate_func)
            )

        temp_added: list[VMobject] = []
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                anims.extend(
                    Transform(
                        self.code_lines[oi],
                        nxt.code_lines[nj].copy(),
                        rate_func=rate_func,
                    )
                    for oi, nj in zip(range(i1, i2), range(j1, j2), strict=True)
                )
            else:
                anims.extend(
                    FadeOut(self.code_lines[oi], shift=LEFT * 0.22, rate_func=rate_func)
                    for oi in range(i1, i2)
                )
                for nj in range(j1, j2):
                    in_line = nxt.code_lines[nj].copy()
                    temp_added.append(in_line)
                    anims.append(
                        FadeIn(in_line, shift=RIGHT * 0.22, rate_func=rate_func)
                    )

        if sound:
            scene.add_sound(SFX_SOFT_TICK, gain=-4.0, mobject=self)
        scene.play(*anims, run_time=run_time)
        scene.remove(self, *self.get_family(), *temp_added)
        scene.add(nxt)
        return nxt
