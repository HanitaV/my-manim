"""Frame-accurate interaction audio triggers for Manim scenes."""

from __future__ import annotations

import math
import random
from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from manim.mobject.mobject import Mobject
    from manim.mobject.value_tracker import ValueTracker
    from manim.scene.scene import Scene

__all__ = [
    "attach_frame_trigger",
    "attach_proximity_sound",
    "attach_value_tick",
]


def _deterministic_jitter(scene_time: float, salt: int, jitter: float) -> float:
    if jitter <= 0.0:
        return 0.0
    seed = round(scene_time * 1000.0) * 131 + salt * 17
    return random.Random(seed).uniform(-jitter, jitter)


def attach_frame_trigger(
    scene: Scene,
    condition: Callable[[], bool],
    sound: str = "synth:glass_tap",
    *,
    cooldown: float = 0.05,
    gain: float | None = None,
    gain_fn: Callable[[], float] | None = None,
    pitch: float = 0.0,
    pitch_jitter: float = 0.35,
    mobject: Mobject | None = None,
    pan: float | None = None,
) -> Callable[[float], None]:
    """Attach a rising-edge per-frame sound trigger to ``scene`` and return its updater."""
    state: dict[str, object] = {
        "prev": bool(condition()),
        "last_time": -math.inf,
        "count": 0,
    }

    def _updater(_dt: float) -> None:
        curr = bool(condition())
        prev = bool(state["prev"])
        state["prev"] = curr
        if not prev and curr:
            now = scene.time
            last_time = float(state["last_time"])  # type: ignore[arg-type]
            if now - last_time >= cooldown - 1e-9:
                state["last_time"] = now
                count = int(state["count"]) + 1  # type: ignore[arg-type]
                state["count"] = count
                resolved_gain = gain_fn() if gain_fn is not None else gain
                resolved_pitch = pitch + _deterministic_jitter(now, count, pitch_jitter)
                scene.add_sound(
                    sound,
                    gain=resolved_gain,
                    pitch=resolved_pitch,
                    pan=pan,
                    mobject=mobject,
                )

    scene.add_updater(_updater)
    return _updater


def attach_value_tick(
    scene: Scene,
    source: ValueTracker | Callable[[], float],
    sound: str = "synth:soft_tick",
    *,
    step: float = 1.0,
    cooldown: float = 0.03,
    gain: float | None = -8.0,
    pitch_base: float = 0.0,
    pitch_per_unit: float = 0.0,
    mobject: Mobject | None = None,
    pan: float | None = None,
) -> Callable[[float], None]:
    """Play a quantized tick sound whenever ``source`` crosses a ``step`` boundary."""
    if step <= 0.0:
        raise ValueError("Value tick step must be positive.")

    def _read_value() -> float:
        if callable(source):
            return float(source())
        return float(source.get_value())

    state: dict[str, object] = {
        "bucket": math.floor(_read_value() / step + 1e-9),
        "last_time": -math.inf,
    }

    def _updater(_dt: float) -> None:
        val = _read_value()
        bucket = math.floor(val / step + 1e-9)
        prev_bucket = int(state["bucket"])  # type: ignore[arg-type]
        if bucket != prev_bucket:
            state["bucket"] = bucket
            now = scene.time
            last_time = float(state["last_time"])  # type: ignore[arg-type]
            if now - last_time >= cooldown - 1e-9:
                state["last_time"] = now
                scene.add_sound(
                    sound,
                    gain=gain,
                    pitch=pitch_base + val * pitch_per_unit,
                    pan=pan,
                    mobject=mobject,
                )

    scene.add_updater(_updater)
    return _updater


def attach_proximity_sound(
    scene: Scene,
    probe: Mobject,
    targets: Sequence[Mobject],
    sound: str = "synth:hover_shimmer",
    *,
    radius: float | None = None,
    cooldown: float = 0.08,
    gain: float | None = -4.0,
    pitch_base: float = 0.0,
    pitch_step: float = 2.0,
) -> Callable[[float], None]:
    """Trigger spatialized sound on the exact frame ``probe`` enters each target."""

    def _is_inside(target: Mobject) -> bool:
        px, py = probe.get_center()[:2]
        if radius is not None:
            tx, ty = target.get_center()[:2]
            return float(np.hypot(px - tx, py - ty)) <= radius
        left = float(target.get_left()[0])
        right = float(target.get_right()[0])
        bottom = float(target.get_bottom()[1])
        top = float(target.get_top()[1])
        return left <= px <= right and bottom <= py <= top

    prev_inside = [_is_inside(target) for target in targets]
    last_times = [-math.inf for _ in targets]

    def _updater(_dt: float) -> None:
        now = scene.time
        for idx, target in enumerate(targets):
            curr = _is_inside(target)
            if not prev_inside[idx] and curr and now - last_times[idx] >= cooldown - 1e-9:
                last_times[idx] = now
                scene.add_sound(
                    sound,
                    gain=gain,
                    pitch=pitch_base + idx * pitch_step,
                    mobject=target,
                )
            prev_inside[idx] = curr

    scene.add_updater(_updater)
    return _updater
