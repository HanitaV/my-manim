"""Visual-essay storytelling, transient focus overlays, and 2D physics actors."""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from typing import Literal

import numpy as np

from manim._config import config
from manim.animation.creation import Create
from manim.animation.fading import FadeIn, FadeOut
from manim.animation.updaters.update import UpdateFromAlphaFunc
from manim.constants import BOLD, DOWN, LEFT, ORIGIN, RIGHT, SEMIBOLD, UP
from manim.mobject.geometry.arc import Circle
from manim.mobject.geometry.boolean_ops import Difference
from manim.mobject.geometry.line import Arrow, DashedVMobject, Line
from manim.mobject.geometry.polygram import Polygon, Rectangle
from manim.mobject.mobject import Mobject
from manim.mobject.text.text_mobject import Text
from manim.mobject.types.vectorized_mobject import VGroup, VMobject
from manim.scene.scene import Scene
from manim.utils.color import ManimColor, ParsableManimColor
from manim.utils.rate_functions import cinema_smooth_out, cinema_spring_smooth, linear

from .palette import (
    CINEMA_AMBER,
    CINEMA_BLACK,
    CINEMA_CHAMPAGNE,
    CINEMA_EMERALD,
    CINEMA_GRAPHITE,
    CINEMA_ICE,
    CINEMA_IVORY,
    CINEMA_MUTED,
    CINEMA_OBSIDIAN,
    CINEMA_PLATINUM,
    CINEMA_ROSE,
    CINEMA_SILVER,
    CINEMA_SLATE,
    apply_mono_gradient,
)
from .synth import (
    SFX_CHAPTER_CHORD,
    SFX_KEY_TICK,
    SFX_PEN_STROKE,
    SFX_SHIMMER,
    SFX_SOFT_TICK,
    SFX_WHOOSH,
)

__all__ = [
    "SEMANTIC_VECTOR_COLORS",
    "PhysicsVector",
    "StageGround",
    "SplitViewport",
    "SpeedLines",
    "AirflowStreamlines",
    "StrobeTrail",
    "typewriter_reveal",
    "sketch_highlight",
    "make_spotlight_mask",
    "play_spotlight",
    "play_chapter_card",
    "play_diagonal_wipe",
]

SEMANTIC_VECTOR_COLORS: dict[str, str] = {
    "velocity": CINEMA_IVORY,
    "v": CINEMA_IVORY,
    "accel": CINEMA_EMERALD,
    "acceleration": CINEMA_EMERALD,
    "a": CINEMA_EMERALD,
    "force": CINEMA_EMERALD,
    "drive": CINEMA_EMERALD,
    "friction": CINEMA_ROSE,
    "drag": CINEMA_ROSE,
    "resist": CINEMA_ROSE,
    "reaction": CINEMA_ROSE,
    "oppose": CINEMA_ROSE,
    "displacement": CINEMA_CHAMPAGNE,
    "position": CINEMA_CHAMPAGNE,
    "momentum": CINEMA_CHAMPAGNE,
    "energy": CINEMA_CHAMPAGNE,
    "normal": CINEMA_ICE,
    "reference": CINEMA_ICE,
    "component": CINEMA_ICE,
}


class PhysicsVector(VGroup):
    """Semantic 2D physics vector with crisp shaft, tip, and non-overlapping label."""

    def __init__(
        self,
        start: Sequence[float] = ORIGIN,
        direction: Sequence[float] = RIGHT * 1.8,
        label: str | VMobject | None = None,
        *,
        role: str = "velocity",
        color: ParsableManimColor | None = None,
        stroke_width: float = 3.2,
        tip_length: float = 0.22,
        label_buff: float = 0.22,
        font_size: int = 22,
    ) -> None:
        super().__init__()
        resolved = (
            ManimColor(color)
            if color is not None
            else ManimColor(SEMANTIC_VECTOR_COLORS.get(role.lower(), CINEMA_IVORY))
        )
        self.vector_color = resolved
        self.stroke_w = float(stroke_width)
        self.tip_len = float(tip_length)
        self.label_buff = float(label_buff)

        self._start = np.array(start, dtype=float)
        self._vec = np.array(direction, dtype=float)

        self.arrow = Arrow(
            ORIGIN,
            RIGHT,
            buff=0.0,
            stroke_width=self.stroke_w,
            tip_length=self.tip_len,
            max_tip_length_to_length_ratio=0.42,
            color=self.vector_color,
        )
        self.add(self.arrow)

        self.label_mob: VMobject | None = None
        if isinstance(label, str):
            self.label_mob = Text(
                label,
                font_size=font_size,
                weight=SEMIBOLD,
                color=self.vector_color,
            )
            self.add(self.label_mob)
        elif isinstance(label, VMobject):
            self.label_mob = label
            self.add(self.label_mob)

        self.set_vector(self._start, self._vec)

    def set_vector(
        self,
        start: Sequence[float],
        direction: Sequence[float],
    ) -> PhysicsVector:
        """Update origin and vector components cleanly without NaN artifacts."""
        p0 = np.array(start, dtype=float)
        vec = np.array(direction, dtype=float)
        self._start = p0
        self._vec = vec
        norm = float(np.linalg.norm(vec[:2]))

        if norm < 1e-3:
            self.arrow.put_start_and_end_on(p0, p0 + np.array([1e-3, 0.0, 0.0]))
            self.arrow.set_opacity(0.0)
            if self.label_mob is not None:
                self.label_mob.set_opacity(0.0)
            return self

        p1 = p0 + vec
        eff_tip = min(self.tip_len, norm * 0.42)
        rebuilt = Arrow(
            p0,
            p1,
            buff=0.0,
            stroke_width=self.stroke_w,
            tip_length=max(eff_tip, 0.08),
            max_tip_length_to_length_ratio=0.45,
            color=self.vector_color,
        )
        self.arrow.become(rebuilt)
        self.arrow.set_opacity(1.0)

        if self.label_mob is not None:
            unit = vec / norm
            perp = np.array([-unit[1], unit[0], 0.0])
            if perp[1] < -0.15:
                perp = -perp
            anchor = p1 + unit * (self.label_buff * 0.45) + perp * (self.label_buff * 0.85)
            self.label_mob.move_to(anchor)
            self.label_mob.set_opacity(1.0)
        return self


class StageGround(VGroup):
    """Minimalist visual-essay ground plane with reference ticks."""

    def __init__(
        self,
        width: float = 15.0,
        y_level: float = -2.55,
        thickness: float = 1.45,
        *,
        surface_type: Literal["matte", "ice"] = "matte",
        tick_spacing: float = 1.1,
    ) -> None:
        super().__init__()
        self.surface_y = float(y_level)
        self.ground_width = float(width)

        is_ice = surface_type == "ice"
        slab_color = CINEMA_ICE if is_ice else CINEMA_SLATE
        slab_opacity = 0.10 if is_ice else 0.62
        line_color = CINEMA_ICE if is_ice else CINEMA_MUTED

        self.slab = Rectangle(
            width=width,
            height=thickness,
            fill_color=slab_color,
            fill_opacity=slab_opacity,
            stroke_width=0.0,
        ).move_to([0.0, y_level - thickness * 0.5, 0.0])

        self.horizon = Line(
            [-width * 0.5, y_level, 0.0],
            [width * 0.5, y_level, 0.0],
            stroke_color=line_color,
            stroke_width=1.8 if is_ice else 1.5,
            stroke_opacity=0.82,
        )

        self.ticks = VGroup()
        n_ticks = max(2, int(width / max(tick_spacing, 0.25)))
        xs = np.linspace(-width * 0.48, width * 0.48, n_ticks)
        for x in xs:
            tick = Line(
                [float(x), y_level, 0.0],
                [float(x) - 0.14, y_level - 0.16, 0.0],
                stroke_color=line_color,
                stroke_width=1.1,
                stroke_opacity=0.32 if not is_ice else 0.45,
            )
            self.ticks.add(tick)

        self.add(self.slab, self.ticks, self.horizon)
        self.set_z_index(-5)


class SplitViewport(VGroup):
    """Multi-pane reference-frame divider (2-column, 2-row, or 3-column triptych)."""

    def __init__(
        self,
        layout: Literal["2x1", "1x2", "3x1"] = "2x1",
        *,
        frame_width: float | None = None,
        frame_height: float | None = None,
        margin: float = 0.42,
        labels: Sequence[str] | None = None,
        accent: ParsableManimColor = CINEMA_SILVER,
    ) -> None:
        super().__init__()
        fw = float(frame_width if frame_width is not None else config.frame_width)
        fh = float(frame_height if frame_height is not None else config.frame_height)
        self.layout = layout
        self.panes: list[Rectangle] = []
        self.dividers = VGroup()
        self.headers = VGroup()

        usable_w = fw - 2.0 * margin
        usable_h = fh - 2.0 * margin

        if layout == "1x2":
            pane_h = usable_h * 0.5 - 0.08
            centers = [
                np.array([0.0, usable_h * 0.25 + 0.04, 0.0]),
                np.array([0.0, -usable_h * 0.25 - 0.04, 0.0]),
            ]
            self.panes.extend(
                Rectangle(width=usable_w, height=pane_h, stroke_opacity=0.0).move_to(c)
                for c in centers
            )
            self.dividers.add(
                Line(
                    [-usable_w * 0.48, 0.0, 0.0],
                    [usable_w * 0.48, 0.0, 0.0],
                    stroke_color=CINEMA_GRAPHITE,
                    stroke_width=1.6,
                )
            )
        elif layout == "3x1":
            col_w = usable_w / 3.0 - 0.10
            xs = (-usable_w / 3.0, 0.0, usable_w / 3.0)
            self.panes.extend(
                Rectangle(width=col_w, height=usable_h, stroke_opacity=0.0).move_to(
                    [x, 0.0, 0.0]
                )
                for x in xs
            )
            for split_x in (-usable_w / 6.0, usable_w / 6.0):
                self.dividers.add(
                    Line(
                        [split_x, -usable_h * 0.46, 0.0],
                        [split_x, usable_h * 0.46, 0.0],
                        stroke_color=CINEMA_GRAPHITE,
                        stroke_width=1.5,
                    )
                )
        else:  # "2x1"
            col_w = usable_w * 0.5 - 0.12
            self.panes.extend(
                Rectangle(width=col_w, height=usable_h, stroke_opacity=0.0).move_to(
                    [x, 0.0, 0.0]
                )
                for x in (-usable_w * 0.25 - 0.03, usable_w * 0.25 + 0.03)
            )
            self.dividers.add(
                Line(
                    [0.0, -usable_h * 0.46, 0.0],
                    [0.0, usable_h * 0.46, 0.0],
                    stroke_color=CINEMA_GRAPHITE,
                    stroke_width=1.6,
                )
            )

        if labels:
            for idx, txt in enumerate(labels[: len(self.panes)]):
                hdr = Text(txt.upper(), font_size=15, weight=SEMIBOLD, color=accent)
                hdr.move_to(self.panes[idx].get_top() + DOWN * 0.26)
                self.headers.add(hdr)

        self.add(self.dividers, self.headers)
        self.set_z_index(-3)

    def pane_center(self, index: int) -> np.ndarray:
        return self.panes[index].get_center().copy()

    def pane_rect(self, index: int) -> Rectangle:
        return self.panes[index]


class SpeedLines(VGroup):
    """Animated linear streak lines conveying high speed or moving reference frames."""

    def __init__(
        self,
        width: float = 5.4,
        height: float = 2.6,
        *,
        count: int = 10,
        direction: Sequence[float] = LEFT,
        color: ParsableManimColor = CINEMA_SILVER,
        speed: float = 6.5,
        seed: int = 17,
    ) -> None:
        super().__init__()
        vec = np.array(direction, dtype=float)
        norm = max(float(np.linalg.norm(vec[:2])), 1e-6)
        self._unit = vec / norm
        self._perp = np.array([-self._unit[1], self._unit[0], 0.0])
        self._span = float(width)
        self._spread = float(height)
        self._speed = float(speed)
        self._active = True

        rng = np.random.default_rng(seed)
        self._offsets = rng.uniform(-0.5 * self._span, 0.5 * self._span, size=count)
        self._lanes = np.linspace(-0.46 * self._spread, 0.46 * self._spread, count)
        self._lengths = rng.uniform(0.45, 1.15, size=count)
        self._opacities = rng.uniform(0.16, 0.42, size=count)

        self.streaks = VGroup()
        for i in range(count):
            seg = Line(
                ORIGIN,
                self._unit * float(self._lengths[i]),
                stroke_color=color,
                stroke_width=1.5,
                stroke_opacity=float(self._opacities[i]),
            )
            self.streaks.add(seg)
        self.add(self.streaks)
        self.set_z_index(-2)
        self._origin_anchor = np.zeros(3, dtype=float)
        self._refresh_positions()
        self.add_updater(self._tick)

    def _refresh_positions(self) -> None:
        half = 0.5 * self._span
        for i, seg in enumerate(self.streaks):
            u = ((float(self._offsets[i]) + half) % self._span) - half
            p0 = self._origin_anchor + self._unit * u + self._perp * float(self._lanes[i])
            p1 = p0 + self._unit * float(self._lengths[i])
            seg.put_start_and_end_on(p0, p1)

    def move_to(self, point_or_mobject: Mobject | Sequence[float], *args: object, **kwargs: object) -> SpeedLines:
        super().move_to(point_or_mobject, *args, **kwargs)
        self._origin_anchor = self.get_center().copy()
        self._refresh_positions()
        return self

    def _tick(self, mob: SpeedLines, dt: float) -> None:
        if not mob._active or dt <= 0.0:
            return
        mob._offsets = mob._offsets + dt * mob._speed
        mob._refresh_positions()


class AirflowStreamlines(VGroup):
    """Animated streamlines parting smoothly around a moving body (drag / aerodynamics)."""

    def __init__(
        self,
        obstacle: Mobject,
        *,
        length: float = 4.6,
        spread: float = 2.4,
        lines_count: int = 6,
        flow_direction: Sequence[float] = UP,
        color: ParsableManimColor = CINEMA_ICE,
        speed: float = 2.6,
    ) -> None:
        super().__init__()
        self.obstacle = obstacle
        vec = np.array(flow_direction, dtype=float)
        norm = max(float(np.linalg.norm(vec[:2])), 1e-6)
        self._unit = vec / norm
        self._perp = np.array([-self._unit[1], self._unit[0], 0.0])
        self._length = float(length)
        self._spread = float(spread)
        self._lines_count = max(2, int(lines_count))
        self._color = ManimColor(color)
        self._speed = float(speed)
        self._phase = 0.0

        self._rebuild_lines()
        self.set_z_index(-2)
        self.add_updater(self._step_flow)

    def _rebuild_lines(self) -> None:
        self.remove(*self.submobjects)
        center = self.obstacle.get_center()
        obs_r = max(self.obstacle.width, self.obstacle.height) * 0.58 + 0.14

        lanes = [
            v
            for v in np.linspace(-0.5 * self._spread, 0.5 * self._spread, self._lines_count + 1)
            if abs(float(v)) > 0.08
        ][: self._lines_count]

        s_vals = np.linspace(-0.5 * self._length, 0.5 * self._length, 36)
        for lane in lanes:
            sign = 1.0 if lane >= 0 else -1.0
            pts: list[np.ndarray] = []
            for s in s_vals:
                # Smooth bell deflection around obstacle center
                deflect = sign * obs_r * math.exp(-((float(s) / max(obs_r * 1.25, 0.25)) ** 2)) * (
                    1.0 / (1.0 + 1.4 * abs(float(lane)))
                )
                pt = center + self._unit * float(s) + self._perp * (float(lane) + deflect)
                pts.append(pt)

            curve = VMobject(stroke_color=self._color, stroke_width=1.6, stroke_opacity=0.45)
            curve.set_points_smoothly(pts)
            dashed = DashedVMobject(
                curve,
                num_dashes=9,
                dashed_ratio=0.52,
                dash_offset=self._phase % 1.0,
            )
            self.add(dashed)

    def _step_flow(self, mob: AirflowStreamlines, dt: float) -> None:
        if dt <= 0.0:
            return
        mob._phase = (mob._phase + dt * mob._speed) % 1.0
        mob._rebuild_lines()


class StrobeTrail(VGroup):
    """Equal-time stroboscopic ghost snapshots + ``0s, 1s, 2s`` kinematic markers."""

    def __init__(
        self,
        target: Mobject,
        *,
        interval: float = 0.45,
        max_ghosts: int = 8,
        ghost_opacity: float = 0.28,
        show_time_labels: bool = True,
        label_offset: Sequence[float] = DOWN * 0.38,
        font_size: int = 15,
        sound: str | None = SFX_SOFT_TICK,
        scene: Scene | None = None,
    ) -> None:
        super().__init__()
        self.target = target
        self.interval = max(float(interval), 0.05)
        self.max_ghosts = max(1, int(max_ghosts))
        self.ghost_opacity = float(ghost_opacity)
        self.show_time_labels = show_time_labels
        self.label_offset = np.array(label_offset, dtype=float)
        self.font_size = font_size
        self.sound = sound
        self.scene = scene

        self._elapsed = 0.0
        self._step_index = 0
        self._last_pos: np.ndarray | None = None
        self.ghosts = VGroup()
        self.labels = VGroup()
        self.add(self.ghosts, self.labels)
        self.set_z_index(-2)
        self._drop_snapshot(play_sfx=False)
        self.add_updater(self._update_trail)

    def _drop_snapshot(self, *, play_sfx: bool) -> None:
        pos = self.target.get_center().copy()
        if self._last_pos is not None and float(np.linalg.norm(pos - self._last_pos)) < 0.08:
            return
        self._last_pos = pos

        ghost = self.target.copy()
        ghost.clear_updaters(recursive=True)
        ghost.set_opacity(self.ghost_opacity)
        self.ghosts.add(ghost)

        if self.show_time_labels:
            lbl = Text(
                f"{self._step_index}s",
                font_size=self.font_size,
                color=CINEMA_MUTED,
            ).move_to(pos + self.label_offset)
            self.labels.add(lbl)

        self._step_index += 1
        while len(self.ghosts) > self.max_ghosts:
            self.ghosts.remove(self.ghosts[0])
        while len(self.labels) > self.max_ghosts:
            self.labels.remove(self.labels[0])

        if play_sfx and self.sound and self.scene is not None:
            self.scene.add_sound(self.sound, gain=-10.0, mobject=ghost)

    def _update_trail(self, mob: StrobeTrail, dt: float) -> None:
        if dt <= 0.0:
            return
        mob._elapsed += dt
        while mob._elapsed >= mob.interval:
            mob._elapsed -= mob.interval
            mob._drop_snapshot(play_sfx=True)


def typewriter_reveal(
    scene: Scene,
    text_mob: VMobject,
    *,
    cursor_color: ParsableManimColor = CINEMA_IVORY,
    char_delay: float = 0.038,
    run_time: float | None = None,
    sound: bool = True,
    tick_every: int = 2,
    hold_cursor: float = 0.16,
) -> VMobject:
    """Reveal ``text_mob`` sequentially with a leading solid block cursor and key ticks."""
    glyphs = [m for m in text_mob.submobjects if m.family_members_with_points()]
    if not glyphs:
        glyphs = text_mob.family_members_with_points()
    if not glyphs:
        scene.add(text_mob)
        return text_mob

    saved_states: list[list[tuple[VMobject, np.ndarray, np.ndarray]]] = []
    for g in glyphs:
        members = [m for m in g.get_family() if isinstance(m, VMobject)]
        saved_states.append(
            [(m, m.fill_rgbas.copy(), m.stroke_rgbas.copy()) for m in members]
        )
        for m in members:
            m.fill_rgbas[:, 3] = 0.0
            m.stroke_rgbas[:, 3] = 0.0

    cursor_h = max(text_mob.height * 0.92, 0.22)
    cursor_w = max(cursor_h * 0.42, 0.11)
    cursor = Rectangle(
        width=cursor_w,
        height=cursor_h,
        fill_color=cursor_color,
        fill_opacity=0.95,
        stroke_width=0.0,
    ).set_z_index(text_mob.z_index + 2)
    cursor.move_to(
        [glyphs[0].get_left()[0] + cursor_w * 0.5, text_mob.get_center()[1], 0.0]
    )

    scene.add(text_mob, cursor)
    n_glyphs = len(glyphs)
    duration = (
        float(run_time)
        if run_time is not None
        else float(np.clip(n_glyphs * char_delay, 0.25, 2.5))
    )

    if sound:
        step = max(1, int(tick_every))
        for idx in range(0, n_glyphs, step):
            offset = duration * (idx / max(n_glyphs, 1))
            pitch = ((idx * 7) % 5 - 2) * 0.35
            scene.add_sound(
                SFX_KEY_TICK,
                time_offset=offset,
                gain=-10.0,
                pitch=pitch,
                mobject=glyphs[idx],
            )

    def _type_step(_mob: VMobject, alpha: float) -> None:
        visible_n = min(n_glyphs, int(math.floor(alpha * n_glyphs + 1e-6)))
        for idx in range(n_glyphs):
            show = idx < visible_n or alpha >= 1.0 - 1e-6
            for m, f_rgba, s_rgba in saved_states[idx]:
                if show:
                    m.fill_rgbas[:] = f_rgba
                    m.stroke_rgbas[:] = s_rgba
                else:
                    m.fill_rgbas[:, 3] = 0.0
                    m.stroke_rgbas[:, 3] = 0.0

        active_idx = max(0, min(n_glyphs - 1, visible_n - 1))
        anchor_x = (
            glyphs[0].get_left()[0]
            if visible_n == 0
            else glyphs[active_idx].get_right()[0] + 0.05
        )
        cursor.move_to([anchor_x + cursor_w * 0.5, text_mob.get_center()[1], 0.0])

    scene.play(UpdateFromAlphaFunc(text_mob, _type_step, run_time=duration, rate_func=linear))
    if hold_cursor > 1e-3:
        scene.play(FadeOut(cursor, run_time=hold_cursor))
    scene.remove(cursor, *cursor.get_family())
    return text_mob


def sketch_highlight(
    scene: Scene,
    target: Mobject,
    *,
    color: ParsableManimColor = CINEMA_AMBER,
    pad: float = 0.22,
    stroke_width: float = 3.0,
    draw_time: float = 0.35,
    hold_time: float = 0.45,
    fade_time: float = 0.28,
    sound: bool = True,
) -> None:
    """Draw a transient hand-sketched mineral loop around ``target`` and remove cleanly."""
    rx = max(target.width * 0.5 + pad, 0.28)
    ry = max(target.height * 0.5 + pad, 0.22)
    center = target.get_center()

    thetas = np.linspace(0.18 * math.pi, 2.32 * math.pi, 64)
    pts: list[np.ndarray] = []
    for th in thetas:
        wobble_x = 1.0 + 0.035 * math.sin(2.0 * float(th) + 0.4)
        wobble_y = 1.0 + 0.045 * math.cos(3.0 * float(th) - 0.3)
        drift = 0.025 * (float(th) / (2.0 * math.pi))
        pts.append(
            center
            + np.array(
                [
                    rx * (wobble_x + drift) * math.cos(float(th)),
                    ry * wobble_y * math.sin(float(th)),
                    0.0,
                ]
            )
        )

    loop = VMobject(stroke_color=color, stroke_width=stroke_width, stroke_opacity=0.92)
    loop.set_points_smoothly(pts)
    loop.set_z_index(max(target.z_index + 5, 30))

    anim = Create(loop, rate_func=cinema_smooth_out, run_time=draw_time)
    if sound:
        anim = anim.with_sound(SFX_PEN_STROKE, gain=-5.0)
    scene.play(anim)
    if hold_time > 1e-3:
        scene.wait(hold_time)
    scene.play(FadeOut(loop, run_time=fade_time))
    scene.remove(loop, *loop.get_family())


def make_spotlight_mask(
    target: Mobject | Sequence[float],
    *,
    radius: float = 1.15,
    dim_opacity: float = 0.78,
    rim_color: ParsableManimColor = CINEMA_PLATINUM,
) -> VGroup:
    """Build a crisp radial spotlight mask dimming everything outside ``radius``."""
    center = (
        target.get_center().copy()
        if isinstance(target, Mobject)
        else np.array(target, dtype=float)
    )
    outer = Rectangle(
        width=config.frame_width * 1.6,
        height=config.frame_height * 1.6,
    )
    hole = Circle(radius=radius).move_to(center)
    mask = Difference(
        outer,
        hole,
        fill_color=CINEMA_BLACK,
        fill_opacity=dim_opacity,
        stroke_width=0.0,
    )
    rim = Circle(
        radius=radius,
        stroke_color=rim_color,
        stroke_width=1.3,
        stroke_opacity=0.38,
    ).move_to(center)
    overlay = VGroup(mask, rim)
    overlay.set_z_index(60)
    return overlay


def play_spotlight(
    scene: Scene,
    target: Mobject | Sequence[float],
    *,
    radius: float = 1.15,
    dim_opacity: float = 0.78,
    fade_in: float = 0.30,
    hold_time: float = 0.60,
    fade_out: float = 0.28,
    sound: bool = True,
) -> None:
    """Temporarily dim the frame outside a crisp circular spotlight on ``target``."""
    overlay = make_spotlight_mask(target, radius=radius, dim_opacity=dim_opacity)
    enter = FadeIn(overlay, run_time=fade_in)
    if sound:
        enter = enter.with_sound(SFX_SHIMMER, gain=-7.0)
    scene.play(enter)
    if hold_time > 1e-3:
        scene.wait(hold_time)
    scene.play(FadeOut(overlay, run_time=fade_out))
    scene.remove(overlay, *overlay.get_family())


def play_chapter_card(
    scene: Scene,
    part_label: str,
    title: str,
    *,
    subtitle: str | None = None,
    accent: ParsableManimColor = CINEMA_ICE,
    hold_time: float = 1.15,
    sound: str | None = SFX_CHAPTER_CHORD,
) -> None:
    """Play a minimalist breathing chapter card (``PHẦN X`` + single-line title)."""
    kicker = Text(part_label.upper(), font_size=17, weight=SEMIBOLD, color=accent)
    rule = Line(LEFT * 0.9, RIGHT * 0.9, stroke_color=CINEMA_GRAPHITE, stroke_width=1.4)
    heading = Text(title, font_size=44, weight=BOLD)
    apply_mono_gradient(heading, colors=[CINEMA_SILVER, CINEMA_IVORY])

    items: list[Mobject] = [kicker, rule, heading]
    if subtitle:
        items.append(Text(subtitle, font_size=20, color=CINEMA_MUTED))

    card = VGroup(*items).arrange(DOWN, buff=0.22).set_z_index(40)
    enter = FadeIn(card, shift=UP * 0.18, rate_func=cinema_spring_smooth, run_time=0.65)
    if sound:
        enter = enter.with_sound(sound, gain=-4.0)
    scene.play(enter)
    if hold_time > 1e-3:
        scene.wait(hold_time)
    scene.play(FadeOut(card, shift=UP * 0.12, run_time=0.42))
    scene.remove(card, *card.get_family())


def play_diagonal_wipe(
    scene: Scene,
    swap_fn: Callable[[], None],
    *,
    angle_deg: float = 14.0,
    run_time: float = 0.65,
    accent: ParsableManimColor = CINEMA_ICE,
    sound: str | None = SFX_WHOOSH,
) -> None:
    """Sweep an angled obsidian shutter across the frame, swapping scene contents mid-wipe."""
    fw = float(config.frame_width)
    fh = float(config.frame_height)
    slant = fh * math.tan(math.radians(angle_deg))
    w = fw * 1.45 + abs(slant) * 2.0
    h = fh * 1.35

    shutter = Polygon(
        [-w * 0.5 - slant, -h * 0.5, 0.0],
        [w * 0.5 - slant, -h * 0.5, 0.0],
        [w * 0.5 + slant, h * 0.5, 0.0],
        [-w * 0.5 + slant, h * 0.5, 0.0],
        fill_color=CINEMA_OBSIDIAN,
        fill_opacity=1.0,
        stroke_width=0.0,
    )
    lead_edge = Line(
        [w * 0.5 - slant, -h * 0.5, 0.0],
        [w * 0.5 + slant, h * 0.5, 0.0],
        stroke_color=accent,
        stroke_width=2.2,
        stroke_opacity=0.75,
    )
    trail_edge = Line(
        [-w * 0.5 - slant, -h * 0.5, 0.0],
        [-w * 0.5 + slant, h * 0.5, 0.0],
        stroke_color=CINEMA_PLATINUM,
        stroke_width=1.5,
        stroke_opacity=0.45,
    )
    rig = VGroup(shutter, lead_edge, trail_edge).set_z_index(80)

    start_x = -(fw * 0.5 + w * 0.5 + 0.6)
    end_x = fw * 0.5 + w * 0.5 + 0.6
    rig.move_to([start_x, 0.0, 0.0])
    scene.add(rig)

    half_t = max(run_time * 0.5, 0.12)
    if sound:
        scene.add_sound(sound, gain=-4.5)

    scene.play(
        UpdateFromAlphaFunc(
            rig,
            lambda m, a: m.move_to([(1.0 - a) * start_x, 0.0, 0.0]),
            run_time=half_t,
            rate_func=cinema_smooth_out,
        )
    )
    swap_fn()
    scene.play(
        UpdateFromAlphaFunc(
            rig,
            lambda m, a: m.move_to([a * end_x, 0.0, 0.0]),
            run_time=half_t,
            rate_func=cinema_smooth_out,
        )
    )
    scene.remove(rig, *rig.get_family())
