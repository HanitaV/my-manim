"""Clean dark-glass mobjects and styling primitives."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from manim.mobject.geometry.polygram import RoundedRectangle
from manim.utils.color import WHITE, ManimColor, ParsableManimColor

__all__ = [
    "GlassStyle",
    "GlassPanel",
    "GlassBadge",
]


@dataclass(slots=True)
class GlassStyle:
    """Optical parameters for a clean dark-glass ``VMobject`` surface."""

    blur_radius: float = 12.0
    saturation: float = 1.08
    brightness: float = 1.0
    tint_color: ManimColor = field(default_factory=lambda: ManimColor("#0A0A0A"))
    tint_opacity: float = 0.68
    rim_color: ManimColor = field(default_factory=lambda: ManimColor(WHITE))
    rim_opacity: float = 0.55
    rim_width: float = 1.25
    sheen_opacity: float = 0.0
    frost_noise: float = 0.0
    refraction: float = 0.0


class GlassPanel(RoundedRectangle):
    """A rounded dark-theme glass card with backdrop blur and crisp rim highlight.

    Works seamlessly with ``FadeIn``, ``FadeOut``, ``Transform``, and ``.animate``.
    """

    def __init__(
        self,
        width: float = 4.5,
        height: float = 2.6,
        corner_radius: float | list[float] = 0.28,
        *,
        blur_radius: float = 12.0,
        tint_color: ParsableManimColor = "#0A0A0A",
        tint_opacity: float = 0.68,
        saturation: float = 1.08,
        brightness: float = 1.0,
        rim_color: ParsableManimColor = WHITE,
        rim_opacity: float = 0.55,
        rim_width: float = 1.25,
        sheen_opacity: float = 0.0,
        frost_noise: float = 0.0,
        refraction: float = 0.0,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            corner_radius=corner_radius,
            width=width,
            height=height,
            **kwargs,
        )
        self.set_glass(
            blur_radius=blur_radius,
            tint_color=tint_color,
            tint_opacity=tint_opacity,
            saturation=saturation,
            brightness=brightness,
            rim_color=rim_color,
            rim_opacity=rim_opacity,
            rim_width=rim_width,
            sheen_opacity=sheen_opacity,
            frost_noise=frost_noise,
            refraction=refraction,
        )


class GlassBadge(GlassPanel):
    """A compact pill-shaped dark-glass badge/chip for HUD tags and metrics."""

    def __init__(
        self,
        width: float = 2.4,
        height: float = 0.62,
        corner_radius: float | list[float] | None = None,
        *,
        blur_radius: float = 10.0,
        tint_color: ParsableManimColor = "#121212",
        tint_opacity: float = 0.72,
        rim_opacity: float = 0.56,
        rim_width: float = 1.15,
        sheen_opacity: float = 0.0,
        **kwargs: Any,
    ) -> None:
        resolved_radius = height / 2.0 if corner_radius is None else corner_radius
        super().__init__(
            width=width,
            height=height,
            corner_radius=resolved_radius,
            blur_radius=blur_radius,
            tint_color=tint_color,
            tint_opacity=tint_opacity,
            rim_opacity=rim_opacity,
            rim_width=rim_width,
            sheen_opacity=sheen_opacity,
            **kwargs,
        )
