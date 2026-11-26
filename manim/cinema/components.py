"""Teardown & auto-layout cinema components (``GlassStack``, ``GlassCallout``, ``ExplodeStack``, ``GlassCaption``)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np

from manim.animation.animation import Animation
from manim.animation.composition import AnimationGroup
from manim.animation.fading import FadeIn
from manim.animation.transform import Transform
from manim.animation.updaters.update import UpdateFromAlphaFunc
from manim.constants import BOLD, DOWN, ORIGIN, RIGHT, UP
from manim.mobject.geometry.arc import Circle, Dot
from manim.mobject.glass import GlassBadge, GlassPanel
from manim.mobject.mobject import Mobject
from manim.mobject.text.text_mobject import Text
from manim.mobject.types.vectorized_mobject import VGroup, VMobject
from manim.utils.color import WHITE, ParsableManimColor
from manim.utils.rate_functions import RateFunction, cinema_spring_smooth

from .palette import (
    CINEMA_ICE,
    CINEMA_IVORY,
    CINEMA_SILVER,
    apply_accent_gradient,
    harmonize_color,
)

__all__ = [
    "GlassStack",
    "GlassCallout",
    "ExplodeStack",
    "GlassCaption",
]


def _set_vmob_opacity_scale(vmob: VMobject, orig_fill: np.ndarray | None, orig_stroke: np.ndarray | None, scale: float) -> None:
    if orig_fill is not None and hasattr(vmob, "fill_rgbas") and len(vmob.fill_rgbas) == len(orig_fill):
        vmob.fill_rgbas[:, 3] = orig_fill * scale
    if orig_stroke is not None and hasattr(vmob, "stroke_rgbas") and len(vmob.stroke_rgbas) == len(orig_stroke):
        vmob.stroke_rgbas[:, 3] = orig_stroke * scale


class GlassStack(VGroup):
    """Flexbox-inspired auto-sizing frosted-glass container supporting live push reflow."""

    def __init__(
        self,
        *items: Mobject,
        direction: np.ndarray = DOWN,
        gap: float = 0.22,
        padding: tuple[float, float] = (0.45, 0.38),
        align_edge: np.ndarray = ORIGIN,
        corner_radius: float = 0.26,
        min_width: float = 2.0,
        min_height: float = 1.0,
        **glass_kwargs: Any,
    ) -> None:
        super().__init__()
        self._direction = np.asarray(direction, dtype=float)
        self._gap = float(gap)
        self._pad_x = float(padding[0])
        self._pad_y = float(padding[1])
        self._align_edge = np.asarray(align_edge, dtype=float)
        self._corner_radius = float(corner_radius)
        self._min_width = float(min_width)
        self._min_height = float(min_height)
        self._glass_kwargs = dict(glass_kwargs)
        self._glass_kwargs.setdefault("sheen_opacity", 0.04)

        self.items = VGroup(*items)
        if len(self.items) > 0:
            self.items.arrange(
                self._direction,
                buff=self._gap,
                aligned_edge=self._align_edge,
            )
            w = max(self._min_width, float(self.items.width) + 2.0 * self._pad_x)
            h = max(self._min_height, float(self.items.height) + 2.0 * self._pad_y)
            center = self.items.get_center()
        else:
            w, h = self._min_width, self._min_height
            center = ORIGIN

        self.panel = GlassPanel(
            width=w,
            height=h,
            corner_radius=self._corner_radius,
            **self._glass_kwargs,
        ).move_to(center)
        self.add(self.panel, self.items)

    def reflow(self) -> GlassStack:
        """Re-arrange children and resize the backing ``GlassPanel`` immediately."""
        center = self.panel.get_center()
        if len(self.items) > 0:
            self.items.arrange(
                self._direction,
                buff=self._gap,
                aligned_edge=self._align_edge,
            )
            self.items.move_to(center)
            w = max(self._min_width, float(self.items.width) + 2.0 * self._pad_x)
            h = max(self._min_height, float(self.items.height) + 2.0 * self._pad_y)
        else:
            w, h = self._min_width, self._min_height

        new_panel = GlassPanel(
            width=w,
            height=h,
            corner_radius=self._corner_radius,
            **self._glass_kwargs,
        ).move_to(center)
        new_panel.set_z_index(self.panel.z_index)
        self.panel.become(new_panel)
        return self

    def animate_push(
        self,
        item: Mobject,
        *,
        run_time: float = 0.55,
        rate_func: RateFunction = cinema_spring_smooth,
    ) -> AnimationGroup:
        """Append ``item`` and return an animation smoothly reflowing the stack and glass."""
        center = self.panel.get_center()
        copies = [m.copy() for m in self.items.submobjects] + [item.copy()]
        tmp = VGroup(*copies)
        tmp.arrange(
            self._direction,
            buff=self._gap,
            aligned_edge=self._align_edge,
        )
        tmp.move_to(center)

        target_w = max(self._min_width, float(tmp.width) + 2.0 * self._pad_x)
        target_h = max(self._min_height, float(tmp.height) + 2.0 * self._pad_y)
        target_panel = GlassPanel(
            width=target_w,
            height=target_h,
            corner_radius=self._corner_radius,
            **self._glass_kwargs,
        ).move_to(center)
        target_panel.set_z_index(self.panel.z_index)

        item.move_to(copies[-1].get_center())
        item.set_z_index(max(self.panel.z_index + 1, self.items.z_index))
        existing = list(self.items.submobjects)
        self.items.add(item)

        anims: list[Animation] = [
            Transform(self.panel, target_panel, rate_func=rate_func),
            *(
                mob.animate(rate_func=rate_func).move_to(cp.get_center())
                for mob, cp in zip(existing, copies[:-1], strict=True)
            ),
            FadeIn(item, shift=self._direction * 0.16, rate_func=rate_func),
        ]
        return AnimationGroup(*anims, run_time=run_time)


class GlassCallout(VGroup):
    """Product-film pinned HUD label connected to a live anchor point by an elbow line."""

    def __init__(
        self,
        target: Mobject | Sequence[float],
        title: str,
        subtitle: str | None = None,
        *,
        offset: Sequence[float] = (1.65, 0.95, 0.0),
        accent: ParsableManimColor = CINEMA_ICE,
        target_anchor: Sequence[float] = ORIGIN,
        follow: bool = True,
        corner_radius: float = 0.16,
    ) -> None:
        super().__init__()
        self._target = target
        self._offset = np.asarray(offset, dtype=float)
        self._target_anchor = np.asarray(target_anchor, dtype=float)
        self._acc = harmonize_color(accent)

        title_txt = Text(title, font_size=18, weight=BOLD, color=CINEMA_IVORY)
        title_txt.set_color_by_gradient("#CCCCCC", "#FFFFFF")
        if subtitle:
            sub_txt = Text(subtitle, font_size=14, color=CINEMA_SILVER)
            label_grp = VGroup(title_txt, sub_txt).arrange(DOWN, buff=0.07)
        else:
            label_grp = VGroup(title_txt)

        badge_w = max(1.6, float(label_grp.width) + 0.56)
        badge_h = max(0.52, float(label_grp.height) + 0.30)
        self.badge = GlassBadge(
            width=badge_w,
            height=badge_h,
            corner_radius=corner_radius,
            sheen_opacity=0.04,
        )
        self.label = label_grp
        self.halo = Circle(
            radius=0.14,
            fill_color=self._acc,
            fill_opacity=0.32,
            stroke_width=0,
        )
        self.pin = Dot(radius=0.055, color=WHITE)
        self.leader = VMobject(stroke_width=1.6, fill_opacity=0.0)
        self.leader.set_points_as_corners([ORIGIN, RIGHT * 0.4, RIGHT * 0.8])
        self._style_leader()

        self.add(self.leader, self.halo, self.pin, self.badge, self.label)
        self._last_anchor: np.ndarray | None = None
        self._reposition(force=True)

        if follow and isinstance(target, Mobject):
            self.add_updater(lambda _mob: self._reposition(force=False))

    def _style_leader(self) -> None:
        grad_dir = (
            self.badge.get_center() - self.pin.get_center()
            if float(np.linalg.norm(self.badge.get_center() - self.pin.get_center())) > 1e-6
            else RIGHT
        )
        apply_accent_gradient(
            self.leader,
            self._acc,
            anchor="light",
            direction=-grad_dir,
            fill=False,
            stroke=True,
        )

    def _compute_anchor(self) -> np.ndarray:
        if isinstance(self._target, Mobject):
            if float(np.linalg.norm(self._target_anchor)) > 1e-6:
                return np.asarray(
                    self._target.get_boundary_point(self._target_anchor),
                    dtype=float,
                )
            return np.asarray(self._target.get_center(), dtype=float)
        return np.asarray(self._target, dtype=float)

    def _reposition(self, *, force: bool = False) -> None:
        anchor = self._compute_anchor()
        if (
            not force
            and self._last_anchor is not None
            and float(np.linalg.norm(anchor - self._last_anchor)) <= 1e-5
        ):
            return
        self._last_anchor = anchor.copy()
        self.halo.move_to(anchor)
        self.pin.move_to(anchor)

        badge_center = anchor + self._offset
        self.badge.move_to(badge_center)
        self.label.move_to(badge_center)

        attach = (
            self.badge.get_left()
            if badge_center[0] >= anchor[0]
            else self.badge.get_right()
        )
        elbow_x = anchor[0] + 0.55 * (attach[0] - anchor[0])
        elbow = np.array([elbow_x, attach[1], anchor[2]], dtype=float)
        self.leader.set_points_as_corners([anchor, elbow, attach])
        self._style_leader()


class ExplodeStack(VGroup):
    """Teardown stack of layered panels that can explode, focus a layer, and collapse."""

    def __init__(
        self,
        *layers: Mobject,
        axis: Sequence[float] = UP,
        collapsed_gap: float = 0.14,
    ) -> None:
        super().__init__()
        vec = np.asarray(axis, dtype=float)
        norm = float(np.linalg.norm(vec))
        self._axis = vec / norm if norm > 1e-6 else np.array(UP, dtype=float)
        self._collapsed_gap = float(collapsed_gap)

        self.layers = list(layers)
        if self.layers:
            VGroup(*self.layers).arrange(self._axis, buff=self._collapsed_gap)
        self.add(*self.layers)

        center = self.get_center()
        self._collapsed_offsets = [
            np.asarray(layer.get_center(), dtype=float) - center for layer in self.layers
        ]
        self._layer_scales = [1.0 for _ in self.layers]
        # Snapshot exact per-submobject RGBA opacities so focus/restore preserves GlassPanel optics
        self._saved_opacities: list[
            list[tuple[VMobject, np.ndarray | None, np.ndarray | None]]
        ] = []
        for layer in self.layers:
            entries: list[tuple[VMobject, np.ndarray | None, np.ndarray | None]] = []
            for sub in layer.family_members_with_points():
                if isinstance(sub, VMobject):
                    f = sub.fill_rgbas[:, 3].copy() if hasattr(sub, "fill_rgbas") else None
                    s = sub.stroke_rgbas[:, 3].copy() if hasattr(sub, "stroke_rgbas") else None
                    entries.append((sub, f, s))
            self._saved_opacities.append(entries)

    def explode(
        self,
        spread: float = 0.90,
        *,
        run_time: float = 0.85,
        rate_func: RateFunction = cinema_spring_smooth,
    ) -> Animation:
        """Separate layers outward along ``axis`` to expose internal structure."""
        center = self.get_center()
        mid = 0.5 * max(len(self.layers) - 1, 0)
        starts = [np.asarray(layer.get_center(), dtype=float) for layer in self.layers]
        targets = [
            center + base_off + self._axis * ((i - mid) * float(spread))
            for i, base_off in enumerate(self._collapsed_offsets)
        ]

        def _update(_mob: Mobject, alpha: float) -> None:
            for layer, p0, p1 in zip(self.layers, starts, targets, strict=True):
                layer.move_to(p0 * (1.0 - alpha) + p1 * alpha)

        return UpdateFromAlphaFunc(self, _update, run_time=run_time, rate_func=rate_func)

    def collapse(
        self,
        *,
        run_time: float = 0.75,
        rate_func: RateFunction = cinema_spring_smooth,
    ) -> Animation:
        """Return exploded layers smoothly back to their compact stacked positions."""
        center = self.get_center()
        starts = [np.asarray(layer.get_center(), dtype=float) for layer in self.layers]
        targets = [center + base_off for base_off in self._collapsed_offsets]

        def _update(_mob: Mobject, alpha: float) -> None:
            for layer, p0, p1 in zip(self.layers, starts, targets, strict=True):
                layer.move_to(p0 * (1.0 - alpha) + p1 * alpha)

        return UpdateFromAlphaFunc(self, _update, run_time=run_time, rate_func=rate_func)

    def _animate_scales(
        self,
        target_scales: list[float],
        *,
        run_time: float,
        rate_func: RateFunction,
    ) -> Animation:
        start_scales = list(self._layer_scales)

        def _update(_mob: Mobject, alpha: float) -> None:
            for i, entries in enumerate(self._saved_opacities):
                s = start_scales[i] * (1.0 - alpha) + target_scales[i] * alpha
                self._layer_scales[i] = s
                for sub, orig_f, orig_s in entries:
                    _set_vmob_opacity_scale(sub, orig_f, orig_s, s)

        return UpdateFromAlphaFunc(self, _update, run_time=run_time, rate_func=rate_func)

    def focus_layer(
        self,
        index: int,
        *,
        dim_opacity: float = 0.22,
        run_time: float = 0.45,
        rate_func: RateFunction = cinema_spring_smooth,
    ) -> Animation:
        """Highlight layer ``index`` at full clarity while dimming sibling layers."""
        targets = [
            1.0 if i == index else float(dim_opacity) for i in range(len(self.layers))
        ]
        return self._animate_scales(targets, run_time=run_time, rate_func=rate_func)

    def restore_layers(
        self,
        *,
        run_time: float = 0.40,
        rate_func: RateFunction = cinema_spring_smooth,
    ) -> Animation:
        """Restore all layers to their exact initial fill and glass rim opacities."""
        targets = [1.0 for _ in self.layers]
        return self._animate_scales(targets, run_time=run_time, rate_func=rate_func)


class GlassCaption(VGroup):
    """Compact frosted-glass subtitle pill for voiceover / narration captions."""

    def __init__(
        self,
        text: str = "",
        *,
        font_size: float = 20,
        max_width: float = 11.2,
    ) -> None:
        super().__init__()
        self._font_size = font_size
        self._max_width = max_width
        self.label = Text(text or " ", font_size=font_size, color=CINEMA_IVORY)
        w = min(self._max_width, max(3.2, float(self.label.width) + 0.72))
        h = max(0.56, float(self.label.height) + 0.30)
        self.badge = GlassBadge(width=w, height=h, sheen_opacity=0.04)
        self.label.move_to(self.badge)
        if not text:
            self.label.set_opacity(0.0)
        self.add(self.badge, self.label)

    def set_caption(self, text: str) -> GlassCaption:
        center = self.badge.get_center()
        new_lbl = Text(text or " ", font_size=self._font_size, color=CINEMA_IVORY)
        if float(new_lbl.width) > self._max_width - 0.72:
            new_lbl.scale_to_fit_width(self._max_width - 0.72)
        w = min(self._max_width, max(3.2, float(new_lbl.width) + 0.72))
        h = max(0.56, float(new_lbl.height) + 0.30)
        new_badge = GlassBadge(width=w, height=h, sheen_opacity=0.04).move_to(center)
        new_badge.set_z_index(self.badge.z_index)
        new_lbl.move_to(center)
        new_lbl.set_z_index(self.label.z_index)
        if not text:
            new_lbl.set_opacity(0.0)
        self.badge.become(new_badge)
        self.label.become(new_lbl)
        return self
