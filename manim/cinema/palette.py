"""Curated monochrome black-to-white palette and harmonized mineral accent helpers."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

import numpy as np

from manim.constants import RIGHT
from manim.mobject.types.vectorized_mobject import VMobject
from manim.utils.color import ManimColor, ParsableManimColor

__all__ = [
    "CINEMA_BLACK",
    "CINEMA_OBSIDIAN",
    "CINEMA_MIDNIGHT",
    "CINEMA_SLATE",
    "CINEMA_GRAPHITE",
    "CINEMA_IVORY",
    "CINEMA_PLATINUM",
    "CINEMA_SILVER",
    "CINEMA_MUTED",
    "CINEMA_MONO_GRADIENT",
    "CINEMA_ICE",
    "CINEMA_CYAN",
    "CINEMA_VIOLET",
    "CINEMA_EMERALD",
    "CINEMA_CHAMPAGNE",
    "CINEMA_AMBER",
    "CINEMA_ROSE",
    "harmonize_color",
    "apply_mono_gradient",
    "apply_accent_gradient",
]

# Curated monochrome black-to-white luxury palette (pure neutral luminance stops)
CINEMA_BLACK = ManimColor("#040404")
CINEMA_OBSIDIAN = ManimColor("#080808")
CINEMA_MIDNIGHT = ManimColor("#121212")
CINEMA_SLATE = ManimColor("#1E1E1E")
CINEMA_GRAPHITE = ManimColor("#333333")
CINEMA_MUTED = ManimColor("#737373")
CINEMA_SILVER = ManimColor("#B8B8B8")
CINEMA_PLATINUM = ManimColor("#E5E5E5")
CINEMA_IVORY = ManimColor("#FAFAFA")
CINEMA_MONO_GRADIENT: tuple[ManimColor, ...] = (
    CINEMA_MIDNIGHT,
    CINEMA_GRAPHITE,
    CINEMA_SILVER,
    CINEMA_IVORY,
)

# Restrained mineral/metallic accents tuned to harmonize on the dark monochrome base
CINEMA_ICE = ManimColor("#9CC2DC")
CINEMA_CYAN = ManimColor("#7CC4D8")
CINEMA_VIOLET = ManimColor("#A799D6")
CINEMA_EMERALD = ManimColor("#6EC49E")
CINEMA_CHAMPAGNE = ManimColor("#D8C39E")
CINEMA_AMBER = ManimColor("#D9B26F")
CINEMA_ROSE = ManimColor("#D68A98")


def harmonize_color(
    color: ParsableManimColor,
    *,
    max_chroma: float = 0.28,
    min_luma: float = 0.22,
    max_luma: float = 0.92,
) -> ManimColor:
    """Soften vivid colors into desaturated mineral tones suited for dark monochrome themes."""
    rgb = ManimColor(color).to_rgb().astype(np.float32)
    y = float(0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2])
    y_clamped = float(np.clip(y, min_luma, max_luma))
    c = rgb - y
    peak_c = float(np.max(np.abs(c)))
    if peak_c <= 1e-6:
        out = np.array([y_clamped, y_clamped, y_clamped], dtype=np.float32)
        return ManimColor(out)
    scale = min(1.0, float(max_chroma) / peak_c)
    out = np.clip(y_clamped + c * scale, 0.0, 1.0)
    return ManimColor(out)


def apply_mono_gradient(
    vmobject: VMobject,
    colors: Sequence[ParsableManimColor] | None = None,
    direction: np.ndarray = RIGHT,
    *,
    fill: bool = True,
    stroke: bool = True,
) -> VMobject:
    """Apply a smooth black-to-white monochrome gradient across a ``VMobject`` or group."""
    stops = (
        list(colors)
        if colors is not None
        else [CINEMA_GRAPHITE, CINEMA_SILVER, CINEMA_IVORY]
    )
    vmobject.set_sheen_direction(direction)
    if len(vmobject.points) == 0 and len(vmobject.submobjects) > 0:
        vmobject.set_color_by_gradient(*stops)
        vmobject.set_sheen_direction(direction)
        return vmobject
    if fill and np.any(vmobject.get_fill_opacities() > 0):
        vmobject.set_fill(color=stops, family=False)
    if stroke and vmobject.get_stroke_width() > 0:
        vmobject.set_stroke(color=stops, family=False)
    return vmobject


def apply_accent_gradient(
    vmobject: VMobject,
    accent: ParsableManimColor,
    *,
    anchor: Literal["dark", "light", "both"] = "both",
    direction: np.ndarray = RIGHT,
    harmonize: bool = True,
    fill: bool = True,
    stroke: bool = True,
) -> VMobject:
    """Apply a theme-anchored gradient pairing dark/light monochrome stops with a refined accent."""
    acc = harmonize_color(accent) if harmonize else ManimColor(accent)
    if anchor == "dark":
        stops: list[ParsableManimColor] = [CINEMA_SLATE, acc]
    elif anchor == "light":
        stops = [acc, CINEMA_IVORY]
    else:
        stops = [CINEMA_SLATE, acc, CINEMA_IVORY]
    return apply_mono_gradient(
        vmobject,
        colors=stops,
        direction=direction,
        fill=fill,
        stroke=stroke,
    )
