"""Reactive signals, computed values, UI bindings, and spring-inertia followers."""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from typing import Any

import numpy as np

from manim.animation.animation import Animation
from manim.animation.transform import ApplyMethod
from manim.constants import LEFT
from manim.mobject.mobject import Mobject
from manim.mobject.text.text_mobject import Text
from manim.mobject.types.vectorized_mobject import VGroup, VMobject
from manim.mobject.value_tracker import ValueTracker
from manim.utils.color import ParsableManimColor
from manim.utils.rate_functions import (
    RateFunction,
    SpringSpec,
    cinema_spring_smooth,
    spring_duration,
    spring_rate,
)

from .palette import CINEMA_IVORY

__all__ = [
    "ComputedSignal",
    "Signal",
    "ReactiveText",
    "bind_progress_bar",
    "attach_spring_follower",
]


def _as_float(val: ComputedSignal | Callable[[], float] | float) -> float:
    if callable(val):
        return float(val())
    return float(val)


class ComputedSignal:
    """Lazy, composable scalar signal derived from other signals."""

    def __init__(self, fn: Callable[[], float]) -> None:
        self._fn = fn

    def get(self) -> float:
        return float(self._fn())

    def __call__(self) -> float:
        return self.get()

    def derive(self, mapper: Callable[[float], float]) -> ComputedSignal:
        return ComputedSignal(lambda: float(mapper(self.get())))

    def __add__(self, other: ComputedSignal | Callable[[], float] | float) -> ComputedSignal:
        return ComputedSignal(lambda: self.get() + _as_float(other))

    def __radd__(self, other: ComputedSignal | Callable[[], float] | float) -> ComputedSignal:
        return ComputedSignal(lambda: _as_float(other) + self.get())

    def __sub__(self, other: ComputedSignal | Callable[[], float] | float) -> ComputedSignal:
        return ComputedSignal(lambda: self.get() - _as_float(other))

    def __rsub__(self, other: ComputedSignal | Callable[[], float] | float) -> ComputedSignal:
        return ComputedSignal(lambda: _as_float(other) - self.get())

    def __mul__(self, other: ComputedSignal | Callable[[], float] | float) -> ComputedSignal:
        return ComputedSignal(lambda: self.get() * _as_float(other))

    def __rmul__(self, other: ComputedSignal | Callable[[], float] | float) -> ComputedSignal:
        return ComputedSignal(lambda: _as_float(other) * self.get())

    def __truediv__(self, other: ComputedSignal | Callable[[], float] | float) -> ComputedSignal:
        return ComputedSignal(lambda: self.get() / _as_float(other))


class Signal(ComputedSignal):
    """Animatable scalar signal wrapping ``ValueTracker`` with spring tween support.

    Must be added to the scene (or bound to a mobject via :func:`ReactiveText` /
    :func:`bind_progress_bar`) before calling :meth:`tween` if no ``mobject`` holds
    its tracker — :meth:`tween` animates its internal ``tracker`` directly.
    """

    def __init__(self, initial: float = 0.0) -> None:
        self.tracker = ValueTracker(float(initial))
        super().__init__(self.tracker.get_value)

    def set(self, value: float) -> Signal:
        self.tracker.set_value(float(value))
        return self

    def tween(
        self,
        target: float,
        *,
        run_time: float | None = None,
        spring: SpringSpec | None = None,
        rate_func: RateFunction | None = None,
    ) -> Animation:
        """Create an animation smoothly tweening this signal toward ``target``."""
        if spring is not None:
            rt = spring_duration(spring) if run_time is None else float(run_time)
            rf = spring_rate(spring, duration=rt)
        else:
            rt = 0.8 if run_time is None else float(run_time)
            rf = cinema_spring_smooth if rate_func is None else rate_func
        return ApplyMethod(
            self.tracker.set_value,
            float(target),
            run_time=rt,
            rate_func=rf,
        )


class ReactiveText(VGroup):
    """``Text`` mobject that re-renders automatically when its formatting signal changes."""

    def __init__(
        self,
        text_fn: Callable[[], str],
        *,
        font_size: float = 28,
        color: ParsableManimColor = CINEMA_IVORY,
        gradient: Sequence[ParsableManimColor] | None = None,
        **text_kwargs: Any,
    ) -> None:
        super().__init__()
        self._text_fn = text_fn
        self._font_size = font_size
        self._color = color
        self._gradient = list(gradient) if gradient is not None else None
        self._text_kwargs = dict(text_kwargs)

        initial_str = str(text_fn())
        self._last_val = initial_str
        self._glyphs = self._make_text(initial_str)
        self.add(self._glyphs)
        self.add_updater(self._sync_text)

    def _make_text(self, value: str) -> Text:
        txt = Text(
            value,
            font_size=self._font_size,
            color=self._color,
            **self._text_kwargs,
        )
        if self._gradient is not None:
            txt.set_color_by_gradient(*self._gradient)
        return txt

    def _sync_text(self, mob: Mobject) -> None:
        cur = str(self._text_fn())
        if cur == self._last_val:
            return
        self._last_val = cur
        new_txt = self._make_text(cur)
        new_txt.move_to(self._glyphs.get_center())
        new_txt.set_z_index(self._glyphs.z_index)
        self._glyphs.become(new_txt)


def bind_progress_bar(
    bar: VMobject,
    track: VMobject,
    source: Signal | ComputedSignal | Callable[[], float],
    *,
    min_value: float = 0.0,
    max_value: float = 100.0,
) -> VMobject:
    """Bind a fill bar's width and left alignment to a reactive scalar source."""
    span = max(float(max_value - min_value), 1e-6)

    def _updater(mob: VMobject) -> None:
        val = float(source())
        frac = float(np.clip((val - min_value) / span, 0.02, 1.0))
        mob.stretch_to_fit_width(max(track.width * frac, 1e-3))
        mob.align_to(track, LEFT)
        mob.set_y(track.get_y())

    _updater(bar)
    bar.add_updater(_updater)
    return bar


def attach_spring_follower(
    follower: Mobject,
    target: Mobject | Callable[[], Sequence[float]],
    *,
    offset: Sequence[float] = (0.0, 0.0, 0.0),
    stiffness: float = 180.0,
    damping: float = 24.0,
) -> Callable[[Mobject, float], None]:
    """Attach a second-order spring-inertia follower updater to ``follower``."""
    off = np.asarray(offset, dtype=float)
    pos = np.array(follower.get_center(), dtype=float)
    vel = np.zeros(3, dtype=float)

    def _goal() -> np.ndarray:
        base = target.get_center() if isinstance(target, Mobject) else target()
        return np.asarray(base, dtype=float) + off

    def _updater(mob: Mobject, dt: float) -> None:
        if dt <= 0.0:
            return
        nonlocal pos, vel
        dt_clamped = min(float(dt), 0.1)
        steps = max(1, math.ceil(dt_clamped / 0.008))
        h = dt_clamped / steps
        goal = _goal()
        for _ in range(steps):
            acc = float(stiffness) * (goal - pos) - float(damping) * vel
            vel = vel + acc * h
            pos = pos + vel * h
        mob.move_to(pos)

    follower.add_updater(_updater)
    return _updater
