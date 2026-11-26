"""Camera rig, GPU optical blur transitions, aspect presets, narration beats, and QA tools."""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any

import av
import numpy as np
from PIL import Image, ImageDraw

from manim.animation.animation import Animation
from manim.animation.composition import AnimationGroup
from manim.constants import LEFT, ORIGIN
from manim.mobject.geometry.polygram import RoundedRectangle
from manim.mobject.mobject import Mobject
from manim.mobject.value_tracker import ValueTracker
from manim.utils.rate_functions import RateFunction, cinema_spring_smooth

from .postfx import CinemaPostFX
from .synth import SFX_SUB_IMPACT, SFX_WHOOSH

if TYPE_CHECKING:
    from manim.scene.scene import Scene

__all__ = [
    "ASPECT_PRESETS",
    "WordCue",
    "NarrationScript",
    "compute_safe_rect",
    "play_blur_transition",
    "play_slide_transition",
    "camera_focus",
    "camera_reset",
    "camera_impulse",
    "check_scene_layout",
    "render_contact_sheet",
]

ASPECT_PRESETS: dict[str, dict[str, Any]] = {
    "16:9": {
        "pixel_width": 1920,
        "pixel_height": 1080,
        "frame_width": 14.222222222222221,
        "frame_height": 8.0,
        "safe_margin": (0.85, 0.55),
    },
    "9:16": {
        "pixel_width": 1080,
        "pixel_height": 1920,
        "frame_width": 8.0,
        "frame_height": 14.222222222222221,
        "safe_margin": (0.55, 1.45),
    },
    "1:1": {
        "pixel_width": 1080,
        "pixel_height": 1080,
        "frame_width": 8.0,
        "frame_height": 8.0,
        "safe_margin": (0.65, 0.65),
    },
}


def compute_safe_rect(
    aspect: str = "16:9",
    *,
    frame_width: float | None = None,
    frame_height: float | None = None,
) -> RoundedRectangle:
    """Return an invisible layout boundary guide matching landscape/portrait safe zones."""
    preset = ASPECT_PRESETS.get(aspect, ASPECT_PRESETS["16:9"])
    fw = float(preset["frame_width"] if frame_width is None else frame_width)
    fh = float(preset["frame_height"] if frame_height is None else frame_height)
    mx, my = preset["safe_margin"]
    return RoundedRectangle(
        width=max(1.0, fw - 2.0 * float(mx)),
        height=max(1.0, fh - 2.0 * float(my)),
        corner_radius=0.2,
        stroke_width=1.0,
        stroke_opacity=0.25,
        fill_opacity=0.0,
    )


def _normalize_word(text: str) -> str:
    return re.sub(r"\W+", "", text.lower())


@dataclass(frozen=True, slots=True)
class WordCue:
    """Timed word/segment cue extracted from a narration transcript JSON."""

    word: str
    start: float
    end: float


class NarrationScript:
    """One-take narration marker and word-timestamp index for master-clock scene sync."""

    def __init__(
        self,
        *,
        beats: dict[str, float] | None = None,
        words: Sequence[WordCue] = (),
    ) -> None:
        self.beats: dict[str, float] = {k: float(v) for k, v in (beats or {}).items()}
        self.words: list[WordCue] = list(words)

    @classmethod
    def load(
        cls,
        source: str | Path | dict[str, Any] | list[dict[str, Any]],
    ) -> NarrationScript:
        """Load beats/word timestamps from a JSON file path, JSON string, or Python object."""
        data: Any
        if isinstance(source, Path):
            data = json.loads(source.read_text(encoding="utf-8"))
        elif isinstance(source, str):
            stripped = source.strip()
            if stripped.startswith("{") or stripped.startswith("["):
                data = json.loads(stripped)
            else:
                data = json.loads(Path(source).read_text(encoding="utf-8"))
        else:
            data = source

        beats: dict[str, float] = {}
        words: list[WordCue] = []
        if isinstance(data, dict):
            if "beats" in data and isinstance(data["beats"], dict):
                beats = {str(k): float(v) for k, v in data["beats"].items()}
            if "words" in data and isinstance(data["words"], list):
                raw_words = data["words"]
            elif "segments" in data and isinstance(data["segments"], list):
                raw_words = [
                    {
                        "word": seg.get("text", ""),
                        "start": seg.get("start", 0.0),
                        "end": seg.get("end", seg.get("start", 0.0)),
                    }
                    for seg in data["segments"]
                ]
            else:
                raw_words = []
                if not beats:
                    beats = {
                        str(k): float(v)
                        for k, v in data.items()
                        if isinstance(v, (int, float))
                    }
            words.extend(
                WordCue(
                    word=str(item.get("word", item.get("text", ""))),
                    start=float(item.get("start", 0.0)),
                    end=float(item.get("end", item.get("start", 0.0))),
                )
                for item in raw_words
            )
        elif isinstance(data, list):
            words.extend(
                WordCue(
                    word=str(item.get("word", item.get("text", ""))),
                    start=float(item.get("start", 0.0)),
                    end=float(item.get("end", item.get("start", 0.0))),
                )
                for item in data
            )
        else:
            raise ValueError("Unsupported narration source structure.")

        return cls(beats=beats, words=words)

    def add_beat(self, name: str, timestamp: float) -> NarrationScript:
        self.beats[name] = float(timestamp)
        return self

    def time_of(self, query: str) -> float | None:
        """Return timestamp in seconds for a named beat, word, or phrase."""
        if query in self.beats:
            return self.beats[query]
        tokens = [_normalize_word(t) for t in query.split() if _normalize_word(t)]
        if not tokens:
            return None
        norm_words = [_normalize_word(w.word) for w in self.words]
        span = len(tokens)
        for idx in range(len(norm_words) - span + 1):
            if norm_words[idx : idx + span] == tokens:
                return self.words[idx].start
        return None


def play_blur_transition(
    scene: Scene,
    swap_fn: Callable[[], None],
    *,
    max_defocus: float = 18.0,
    dip_exposure: float = 0.65,
    run_time: float = 0.75,
    sound: str | None = SFX_WHOOSH,
) -> None:
    """Transition across scene states via GPU/CPU optical camera defocus & exposure dip."""
    base_fx = scene.post_fx if scene.post_fx is not None else CinemaPostFX()
    blur_sig = ValueTracker(0.0)
    scene.add(blur_sig)

    def _apply_fx(dt: float = 0.0) -> None:
        val = float(np.clip(blur_sig.get_value(), 0.0, 1.0))
        scene.post_fx = replace(
            base_fx,
            defocus=float(max_defocus) * val,
            exposure=1.0 + (float(dip_exposure) - 1.0) * val,
        )

    scene.add_updater(_apply_fx)
    try:
        if sound:
            scene.add_sound(sound, gain=-3.0)
        half_in = max(0.08, float(run_time) * 0.45)
        half_out = max(0.08, float(run_time) * 0.55)
        scene.play(blur_sig.animate(rate_func=cinema_spring_smooth).set_value(1.0), run_time=half_in)
        swap_fn()
        scene.play(blur_sig.animate(rate_func=cinema_spring_smooth).set_value(0.0), run_time=half_out)
    finally:
        scene.remove_updater(_apply_fx)
        scene.remove(blur_sig)
        scene.post_fx = base_fx


def play_slide_transition(
    scene: Scene,
    outgoing: Mobject,
    incoming: Mobject,
    *,
    direction: np.ndarray = LEFT,
    run_time: float = 0.75,
    rate_func: RateFunction = cinema_spring_smooth,
    sound: str | None = SFX_WHOOSH,
) -> None:
    """Slide ``outgoing`` off-frame while smoothly bringing ``incoming`` into center."""
    shift_vec = np.asarray(direction, dtype=float)
    span = float(scene.camera.frame_width) + 1.0
    if abs(shift_vec[1]) > abs(shift_vec[0]):
        span = float(scene.camera.frame_height) + 1.0
    delta = shift_vec * span
    incoming.move_to(-delta)
    scene.add(incoming)
    if sound:
        scene.add_sound(sound, gain=-3.0)
    scene.play(
        outgoing.animate(rate_func=rate_func).shift(delta),
        incoming.animate(rate_func=rate_func).move_to(ORIGIN),
        run_time=run_time,
    )
    scene.remove(outgoing)


def camera_focus(
    scene: Scene,
    target: Mobject,
    *,
    margin: float = 1.2,
    dim_mobjects: Sequence[Mobject] = (),
    dim_opacity: float = 0.25,
    run_time: float = 0.75,
    rate_func: RateFunction = cinema_spring_smooth,
    sound: str | None = None,
) -> AnimationGroup:
    """Build (or play) a smooth camera zoom onto ``target`` with optional background dimming."""
    if not hasattr(scene.camera.frame, "saved_state") or scene.camera.frame.saved_state is None:
        scene.camera.frame.save_state()
    if sound:
        scene.add_sound(sound, gain=-4.0, mobject=target)
    anims: list[Animation] = [scene.camera.auto_zoom([target], margin=margin)]
    anims[0].rate_func = rate_func
    anims.extend(
        mob.animate(rate_func=rate_func).set_opacity(dim_opacity) for mob in dim_mobjects
    )
    return AnimationGroup(*anims, run_time=run_time)


def camera_reset(
    scene: Scene,
    *,
    restore_mobjects: Sequence[Mobject] = (),
    run_time: float = 0.75,
    rate_func: RateFunction = cinema_spring_smooth,
) -> AnimationGroup:
    """Restore camera frame framing and any dimmed mobjects."""
    frame = scene.camera.frame
    if getattr(frame, "saved_state", None) is not None:
        cam_anim: Animation = frame.animate(rate_func=rate_func).become(frame.saved_state)
    else:
        cam_anim = (
            frame.animate(rate_func=rate_func)
            .move_to(ORIGIN)
            .set(width=scene.camera.frame_width)
        )
    anims: list[Animation] = [cam_anim]
    anims.extend(
        mob.animate(rate_func=rate_func).set_opacity(1.0) for mob in restore_mobjects
    )
    return AnimationGroup(*anims, run_time=run_time)


def camera_impulse(
    scene: Scene,
    *,
    strength: float = 0.08,
    duration: float = 0.25,
    sound: str | None = SFX_SUB_IMPACT,
) -> None:
    """Trigger a damped micro camera shake synced with impact audio."""
    frame = scene.camera.frame
    origin = np.array(frame.get_center(), dtype=float)
    elapsed = [0.0]

    def _shake(dt: float = 0.0) -> None:
        elapsed[0] += float(dt)
        t = elapsed[0]
        if t >= duration:
            frame.move_to(origin)
            scene.remove_updater(_shake)
            return
        decay = float(np.exp(-10.0 * t / max(duration, 1e-4)))
        dx = strength * decay * np.sin(52.0 * t)
        dy = strength * 0.65 * decay * np.cos(67.0 * t)
        frame.move_to(origin + np.array([dx, dy, 0.0]))

    if sound:
        scene.add_sound(sound, gain=-3.0)
    scene.add_updater(_shake)


def _is_glass_container(mob: Mobject) -> bool:
    cls_name = type(mob).__name__
    return "GlassPanel" in cls_name or "GlassBadge" in cls_name


def check_scene_layout(
    scene: Scene,
    *,
    mobjects: Sequence[Mobject] | None = None,
    safe_rect: Mobject | None = None,
) -> list[str]:
    """Detect out-of-frame clipping and unintended bounding-box overlaps on foreground elements."""
    issues: list[str] = []
    bound = safe_rect
    if bound is not None:
        b_left, b_right = float(bound.get_left()[0]), float(bound.get_right()[0])
        b_bot, b_top = float(bound.get_bottom()[1]), float(bound.get_top()[1])
    else:
        fc = scene.camera.frame.get_center()
        hw = float(scene.camera.frame.width) * 0.5
        hh = float(scene.camera.frame.height) * 0.5
        b_left, b_right = float(fc[0] - hw), float(fc[0] + hw)
        b_bot, b_top = float(fc[1] - hh), float(fc[1] + hh)

    candidates = list(scene.mobjects if mobjects is None else mobjects)
    active: list[Mobject] = []
    for mob in candidates:
        if isinstance(mob, ValueTracker) or float(mob.z_index) < 0:
            continue
        if float(mob.width) <= 1e-4 or float(mob.height) <= 1e-4:
            continue
        active.append(mob)

    for mob in active:
        ml, mr = float(mob.get_left()[0]), float(mob.get_right()[0])
        mb, mt = float(mob.get_bottom()[1]), float(mob.get_top()[1])
        if ml < b_left - 0.05 or mr > b_right + 0.05 or mb < b_bot - 0.05 or mt > b_top + 0.05:
            issues.append(f"CLIPPING: {type(mob).__name__} exceeds layout bounds.")

    for i in range(len(active)):
        a = active[i]
        al, ar = float(a.get_left()[0]), float(a.get_right()[0])
        ab, at = float(a.get_bottom()[1]), float(a.get_top()[1])
        for j in range(i + 1, len(active)):
            b = active[j]
            # GlassPanel cards intentionally sit behind labels/controls unless overlapping another GlassPanel
            if (_is_glass_container(a) ^ _is_glass_container(b)):
                continue
            bl, br = float(b.get_left()[0]), float(b.get_right()[0])
            bb, bt = float(b.get_bottom()[1]), float(b.get_top()[1])
            ox = min(ar, br) - max(al, bl)
            oy = min(at, bt) - max(ab, bb)
            if ox > 0.08 and oy > 0.08:
                issues.append(
                    f"OVERLAP: {type(a).__name__} & {type(b).__name__} intersect ({ox:.2f}x{oy:.2f})."
                )
    return issues


def render_contact_sheet(
    video_path: str | Path,
    output_path: str | Path | None = None,
    *,
    cols: int = 4,
    rows: int = 3,
    thumb_width: int = 480,
) -> Path:
    """Decode evenly spaced frames from ``video_path`` into a dark QA contact-sheet grid."""
    src = Path(video_path)
    if not src.exists():
        raise FileNotFoundError(f"Video file not found: {src}")

    total_slots = max(1, cols * rows)
    decoded: list[tuple[int, float, Image.Image]] = []
    with av.open(str(src)) as container:
        stream = container.streams.video[0]
        tb = float(stream.time_base) if stream.time_base is not None else 1.0 / 24.0
        for idx, frame in enumerate(container.decode(stream)):
            ts = float(frame.pts * tb) if frame.pts is not None else float(idx) / 24.0
            decoded.append((idx, ts, frame.to_image()))

    if not decoded:
        raise ValueError(f"Video {src} produced zero video frames.")

    sample_indices = np.linspace(0, len(decoded) - 1, min(total_slots, len(decoded)), dtype=int)
    first_img = decoded[0][2]
    aspect = first_img.height / max(first_img.width, 1)
    thumb_h = max(1, round(thumb_width * aspect))
    pad = 16
    sheet_w = cols * thumb_width + (cols + 1) * pad
    sheet_h = rows * thumb_h + (rows + 1) * pad
    sheet = Image.new("RGB", (sheet_w, sheet_h), (8, 8, 8))
    draw = ImageDraw.Draw(sheet)

    for slot, src_i in enumerate(sample_indices):
        f_idx, ts, img = decoded[int(src_i)]
        thumb = img.resize((thumb_width, thumb_h), resample=Image.Resampling.BILINEAR)
        r = slot // cols
        c = slot % cols
        x0 = pad + c * (thumb_width + pad)
        y0 = pad + r * (thumb_h + pad)
        sheet.paste(thumb, (x0, y0))
        draw.rectangle([x0, y0, x0 + thumb_width - 1, y0 + thumb_h - 1], outline=(52, 52, 52), width=1)
        tag = f"#{f_idx}  {ts:.2f}s"
        draw.rectangle([x0 + 8, y0 + 8, x0 + 128, y0 + 30], fill=(10, 10, 10))
        draw.text((x0 + 14, y0 + 12), tag, fill=(235, 235, 235))

    dst = (
        src.with_name(f"{src.stem}_contact_sheet.png")
        if output_path is None
        else Path(output_path)
    )
    dst.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(dst)
    return dst
