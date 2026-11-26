"""Dark luxury cinema theme, ambient backdrop, and full ``CinemaScene`` rig."""

from __future__ import annotations

import functools
from collections.abc import Callable, Sequence
from typing import Any, Literal

import manimpango
import numpy as np
from PIL import Image

from manim._config import config, tempconfig
from manim._config.output import OutputFormat
from manim.animation.composition import AnimationGroup
from manim.constants import DOWN, LEFT, ORIGIN, RIGHT, UP
from manim.mobject.geometry.polygram import RoundedRectangle
from manim.mobject.glass import GlassBadge, GlassPanel
from manim.mobject.mobject import Mobject
from manim.mobject.text.text_mobject import Text
from manim.mobject.types.image_mobject import ImageMobject
from manim.mobject.types.vectorized_mobject import VMobject
from manim.scene.scene import Scene
from manim.utils.color import ManimColor, ParsableManimColor

from .code_view import GlassCode
from .components import ExplodeStack, GlassCallout, GlassStack
from .cuda import nvenc_available
from .director import (
    ASPECT_PRESETS,
    NarrationScript,
    camera_focus,
    camera_impulse,
    camera_reset,
    check_scene_layout,
    compute_safe_rect,
    play_blur_transition,
    play_slide_transition,
)
from .essay import (
    AirflowStreamlines,
    PhysicsVector,
    SpeedLines,
    SplitViewport,
    StageGround,
    StrobeTrail,
    play_chapter_card,
    play_diagonal_wipe,
    play_spotlight,
    sketch_highlight,
    typewriter_reveal,
)
from .palette import (
    CINEMA_AMBER,
    CINEMA_BLACK,
    CINEMA_CHAMPAGNE,
    CINEMA_CYAN,
    CINEMA_EMERALD,
    CINEMA_GRAPHITE,
    CINEMA_ICE,
    CINEMA_IVORY,
    CINEMA_MIDNIGHT,
    CINEMA_MONO_GRADIENT,
    CINEMA_MUTED,
    CINEMA_OBSIDIAN,
    CINEMA_PLATINUM,
    CINEMA_ROSE,
    CINEMA_SILVER,
    CINEMA_SLATE,
    CINEMA_VIOLET,
    apply_accent_gradient,
    apply_mono_gradient,
    harmonize_color,
)
from .postfx import CinemaPostFX
from .signals import Signal

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
    "AmbientOrb",
    "harmonize_color",
    "apply_mono_gradient",
    "apply_accent_gradient",
    "make_ambient_background_image",
    "make_ambient_background",
    "CinemaScene",
]

AmbientOrb = tuple[tuple[float, float], ParsableManimColor, float, float]

_DEFAULT_ORBS: tuple[AmbientOrb, ...] = (
    ((-0.52, 0.48), "#FFFFFF", 0.85, 0.09),
    ((0.48, -0.22), "#D4D4D4", 0.82, 0.05),
    ((0.0, 0.15), "#FAFAFA", 0.95, 0.035),
)


def make_ambient_background_image(
    width: int = 960,
    height: int = 540,
    *,
    base_color: ParsableManimColor = CINEMA_OBSIDIAN,
    orbs: Sequence[AmbientOrb] | None = None,
    gradient_strength: float = 0.06,
    seed: int = 42,
) -> Image.Image:
    """Create a dithered monochrome dark ambient backdrop PIL ``Image``.

    Used by :meth:`CinemaScene.add_ambient_background` via ``camera.background_image``
    so Cairo caches and copies it at native memory speed without per-frame homography.
    """
    resolved_orbs = _DEFAULT_ORBS if orbs is None else orbs
    base_rgb = ManimColor(base_color).to_rgb().astype(np.float32)

    y = np.linspace(-1.0, 1.0, height, dtype=np.float32)
    x = np.linspace(-1.0, 1.0, width, dtype=np.float32)
    yy, xx = np.meshgrid(y, x, indexing="ij")
    aspect = width / max(height, 1)

    canvas = np.broadcast_to(base_rgb, (height, width, 3)).astype(np.float32).copy()
    if gradient_strength != 0.0:
        diag = np.clip(((-0.65 * xx + 0.75 * yy) + 1.4) * 0.5, 0.0, 1.0)[..., None]
        canvas += float(gradient_strength) * (diag ** 1.8)

    for (ox, oy), color, radius, intensity in resolved_orbs:
        dx = (xx - float(ox)) * aspect
        dy = yy - float(oy)
        dist2 = (dx * dx + dy * dy) / max(float(radius) ** 2, 1e-4)
        falloff = np.exp(-2.2 * dist2)[..., None]
        orb_rgb = ManimColor(color).to_rgb().astype(np.float32)
        canvas += orb_rgb * (float(intensity) * falloff)

    # Luminance TPDF dither before uint8 quantization (zero chromatic speckle)
    rng = np.random.default_rng(seed)
    u1 = rng.random((height, width, 1), dtype=np.float32)
    u2 = rng.random((height, width, 1), dtype=np.float32)
    canvas += (u1 - u2) * (1.0 / 255.0)

    rgb_u8 = np.clip(canvas * 255.0 + 0.5, 0.0, 255.0).astype(np.uint8)
    rgba_u8 = np.empty((height, width, 4), dtype=np.uint8)
    rgba_u8[..., :3] = rgb_u8
    rgba_u8[..., 3] = 255
    return Image.fromarray(rgba_u8, mode="RGBA")


def make_ambient_background(
    width: int = 640,
    height: int = 360,
    *,
    base_color: ParsableManimColor = CINEMA_OBSIDIAN,
    orbs: Sequence[AmbientOrb] | None = None,
    gradient_strength: float = 0.06,
    seed: int = 42,
) -> ImageMobject:
    """Create a dithered monochrome dark ambient backdrop ``ImageMobject``."""
    img = make_ambient_background_image(
        width=width,
        height=height,
        base_color=base_color,
        orbs=orbs,
        gradient_strength=gradient_strength,
        seed=seed,
    )
    backdrop = ImageMobject(np.asarray(img, dtype=np.uint8))
    backdrop.stretch_to_fit_width(config.frame_width)
    backdrop.stretch_to_fit_height(config.frame_height)
    backdrop.set_z_index(-100)
    return backdrop


_STANDARD_16_9_RES = {(1920, 1080), (1280, 720), (854, 480)}
_PREFERRED_CINEMA_FONTS: tuple[str, ...] = (
    "Inter",
    "Segoe UI",
    "SF Pro Display",
    "Helvetica Neue",
    "Noto Sans",
    "Arial",
    "DejaVu Sans",
)


@functools.lru_cache(maxsize=1)
def default_cinema_font() -> str:
    """Pick the best installed Unicode/Vietnamese-capable sans-serif font."""
    available = set(manimpango.list_fonts())
    for candidate in _PREFERRED_CINEMA_FONTS:
        if candidate in available:
            return candidate
    return ""


class CinemaScene(Scene):
    """Preconfigured ``Scene`` with Dark Monochrome Glass, Signals, Director Rig, Audio, and NVENC."""

    cinema_background_color: ParsableManimColor = CINEMA_OBSIDIAN
    cinema_font: str | None = "auto"
    enable_post_fx: bool = True
    ambient_background: bool = True
    use_nvenc: bool = True
    aspect: Literal["16:9", "9:16", "1:1"] | None = None

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        cfg_overrides: dict[str, Any] = {}
        if self.aspect in ASPECT_PRESETS:
            preset = ASPECT_PRESETS[self.aspect]
            cfg_overrides["frame_width"] = preset["frame_width"]
            cfg_overrides["frame_height"] = preset["frame_height"]
            cur_res = (int(config.pixel_width), int(config.pixel_height))
            if self.aspect == "9:16" and cur_res in _STANDARD_16_9_RES:
                cfg_overrides["pixel_width"] = cur_res[1]
                cfg_overrides["pixel_height"] = cur_res[0]
            elif self.aspect == "1:1" and cur_res in _STANDARD_16_9_RES:
                cfg_overrides["pixel_width"] = cur_res[1]
                cfg_overrides["pixel_height"] = cur_res[1]

        eff_w = int(cfg_overrides.get("pixel_width", config.pixel_width))
        eff_h = int(cfg_overrides.get("pixel_height", config.pixel_height))
        should_use_nvenc = (
            self.use_nvenc
            and config.video_codec == "auto"
            and not config.transparent
            and OutputFormat.parse(config.format)
            in (OutputFormat.AUTO, OutputFormat.MP4, OutputFormat.MOV)
            and eff_w >= 256
            and eff_h >= 144
            and nvenc_available("h264_nvenc")
        )
        if should_use_nvenc:
            cfg_overrides.update(
                {
                    "video_codec": "h264_nvenc",
                    "video_encoder_options": (
                        dict(config.video_encoder_options)
                        if config.video_encoder_options
                        else {"preset": "p4", "rc": "vbr", "cq": "19"}
                    ),
                    "max_inflight_encoders": max(int(config.max_inflight_encoders), 2),
                }
            )

        if cfg_overrides:
            with tempconfig(cfg_overrides):
                super().__init__(*args, **kwargs)
        else:
            super().__init__(*args, **kwargs)

        self.narration: NarrationScript = NarrationScript()
        self._applied_cinema_font: bool = False

    def setup(self) -> None:
        super().setup()
        if self.cinema_font and Text.__init__ is Text._original__init__:
            resolved_font = (
                default_cinema_font() if self.cinema_font == "auto" else self.cinema_font
            )
            if resolved_font:
                Text.set_default(font=resolved_font)
                self._applied_cinema_font = True
        self.camera.background_color = ManimColor(self.cinema_background_color)
        if self.enable_post_fx and self.post_fx is None:
            self.post_fx = CinemaPostFX()
        if self.ambient_background:
            self.add_ambient_background()

    def tear_down(self) -> None:
        if self._applied_cinema_font:
            Text.set_default()
            self._applied_cinema_font = False
        super().tear_down()

    def add_ambient_background(
        self,
        *,
        base_color: ParsableManimColor | None = None,
        orbs: Sequence[AmbientOrb] | None = None,
        gradient_strength: float = 0.06,
        seed: int = 42,
    ) -> Image.Image:
        """Build and assign a fast cached dark ambient background on the camera."""
        if self.aspect == "9:16":
            bg_w, bg_h = 540, 960
        elif self.aspect == "1:1":
            bg_w, bg_h = 720, 720
        else:
            bg_w, bg_h = 960, 540
        backdrop = make_ambient_background_image(
            width=bg_w,
            height=bg_h,
            base_color=self.cinema_background_color if base_color is None else base_color,
            orbs=orbs,
            gradient_strength=gradient_strength,
            seed=seed,
        )
        self.camera.background_image = backdrop
        return backdrop

    # --- UI & Teardown Builders ---

    @staticmethod
    def glass_panel(
        width: float = 4.5,
        height: float = 2.6,
        corner_radius: float | list[float] = 0.28,
        **kwargs: Any,
    ) -> GlassPanel:
        """Create a luxury frosted-glass card."""
        return GlassPanel(
            width=width,
            height=height,
            corner_radius=corner_radius,
            **kwargs,
        )

    @staticmethod
    def glass_badge(
        width: float = 2.4,
        height: float = 0.62,
        corner_radius: float | list[float] | None = None,
        **kwargs: Any,
    ) -> GlassBadge:
        """Create a pill-shaped frosted-glass badge."""
        return GlassBadge(
            width=width,
            height=height,
            corner_radius=corner_radius,
            **kwargs,
        )

    @staticmethod
    def glass_stack(*items: Mobject, **kwargs: Any) -> GlassStack:
        """Create an auto-sizing Flexbox-like ``GlassStack``."""
        return GlassStack(*items, **kwargs)

    @staticmethod
    def explode_stack(*layers: Mobject, axis: Sequence[float] = UP, **kwargs: Any) -> ExplodeStack:
        """Create a layered teardown ``ExplodeStack``."""
        return ExplodeStack(*layers, axis=axis, **kwargs)

    @staticmethod
    def callout(
        target: Mobject | Sequence[float],
        title: str,
        subtitle: str | None = None,
        **kwargs: Any,
    ) -> GlassCallout:
        """Create a product-film pinned ``GlassCallout`` HUD label."""
        return GlassCallout(target, title, subtitle, **kwargs)

    @staticmethod
    def glass_code(code_string: str, **kwargs: Any) -> GlassCode:
        """Create a frosted-glass ``GlassCode`` block with spotlight & diffing."""
        return GlassCode(code_string, **kwargs)

    def signal(self, initial: float = 0.0) -> Signal:
        """Create and register a reactive ``Signal`` tracked by the scene."""
        sig = Signal(initial)
        self.add(sig.tracker)
        return sig

    def safe_rect(self) -> RoundedRectangle:
        """Return safe layout guide matching the scene's aspect ratio."""
        return compute_safe_rect(
            self.aspect or "16:9",
            frame_width=self.camera.frame_width,
            frame_height=self.camera.frame_height,
        )

    # --- Director Camera & Transitions ---

    def camera_focus(self, target: Mobject, **kwargs: Any) -> AnimationGroup:
        return camera_focus(self, target, **kwargs)

    def camera_reset(self, **kwargs: Any) -> AnimationGroup:
        return camera_reset(self, **kwargs)

    def camera_impulse(self, **kwargs: Any) -> None:
        camera_impulse(self, **kwargs)

    def blur_transition(self, swap_fn: Callable[[], None], **kwargs: Any) -> None:
        play_blur_transition(self, swap_fn, **kwargs)

    def slide_transition(
        self,
        outgoing: Mobject,
        incoming: Mobject,
        *,
        direction: np.ndarray = LEFT,
        **kwargs: Any,
    ) -> None:
        play_slide_transition(self, outgoing, incoming, direction=direction, **kwargs)

    def diagonal_wipe(self, swap_fn: Callable[[], None], **kwargs: Any) -> None:
        """Sweep an angled wipe shutter across the frame, swapping content mid-wipe."""
        play_diagonal_wipe(self, swap_fn, **kwargs)

    # --- Visual Essay & 2D Physics Storytelling ---

    def chapter_card(self, part_label: str, title: str, **kwargs: Any) -> None:
        """Play a minimalist breathing chapter card with warm piano chime."""
        play_chapter_card(self, part_label, title, **kwargs)

    def typewriter(self, text_mob: VMobject, **kwargs: Any) -> VMobject:
        """Reveal ``text_mob`` sequentially with a solid block cursor and key ticks."""
        return typewriter_reveal(self, text_mob, **kwargs)

    def sketch_highlight(self, target: Mobject, **kwargs: Any) -> None:
        """Draw a transient hand-sketched mineral loop around ``target`` and fade out."""
        sketch_highlight(self, target, **kwargs)

    def spotlight(self, target: Mobject | Sequence[float], **kwargs: Any) -> None:
        """Dim everything outside a crisp circular spotlight around ``target``."""
        play_spotlight(self, target, **kwargs)

    def split_viewport(
        self,
        layout: Literal["2x1", "1x2", "3x1"] = "2x1",
        **kwargs: Any,
    ) -> SplitViewport:
        """Create a 2-way or 3-way reference-frame divider matching this scene's frame."""
        kwargs.setdefault("frame_width", self.camera.frame_width)
        kwargs.setdefault("frame_height", self.camera.frame_height)
        return SplitViewport(layout, **kwargs)

    @staticmethod
    def stage_ground(
        width: float = 15.0,
        y_level: float = -2.55,
        **kwargs: Any,
    ) -> StageGround:
        """Create a minimalist physics stage ground plane."""
        return StageGround(width=width, y_level=y_level, **kwargs)

    @staticmethod
    def physics_vector(
        start: Sequence[float] = ORIGIN,
        direction: Sequence[float] = RIGHT * 1.8,
        label: str | VMobject | None = None,
        **kwargs: Any,
    ) -> PhysicsVector:
        """Create a semantic ``PhysicsVector`` (velocity/accel/friction/displacement)."""
        return PhysicsVector(start=start, direction=direction, label=label, **kwargs)

    @staticmethod
    def speed_lines(
        width: float = 5.4,
        height: float = 2.6,
        **kwargs: Any,
    ) -> SpeedLines:
        """Create animated linear streak lines conveying high velocity."""
        return SpeedLines(width=width, height=height, **kwargs)

    @staticmethod
    def streamlines(obstacle: Mobject, **kwargs: Any) -> AirflowStreamlines:
        """Create animated airflow streamlines curving around ``obstacle``."""
        return AirflowStreamlines(obstacle, **kwargs)

    def strobe_trail(self, target: Mobject, **kwargs: Any) -> StrobeTrail:
        """Attach an equal-time stroboscopic ghost trail + ``0s, 1s, 2s`` markers."""
        kwargs.setdefault("scene", self)
        return StrobeTrail(target, **kwargs)

    # --- One-Take Narration & Beat Clock ---

    def load_beats(self, source: Any) -> NarrationScript:
        """Load beats or word timestamps into ``self.narration``."""
        self.narration = NarrationScript.load(source)
        return self.narration

    def set_narration(
        self,
        transcript: Any,
        *,
        audio_file: str | None = None,
        gain: float = 0.0,
        bgm: str | None = None,
        bgm_gain: float = -14.0,
        bgm_duck: float = -8.0,
    ) -> NarrationScript:
        """Configure one-take voiceover, background music ducking, and word timestamps."""
        self.narration = NarrationScript.load(transcript)
        if bgm is not None:
            self.add_sound(bgm, gain=bgm_gain)
        if audio_file is not None:
            self.add_sound(
                audio_file,
                gain=gain,
                gain_to_background=bgm_duck if bgm is not None else None,
            )
        return self.narration

    def mark_beat(self, name: str, offset: float = 0.0) -> float:
        """Record a named beat at ``self.time + offset``."""
        ts = self.time + float(offset)
        self.narration.add_beat(name, ts)
        return ts

    def wait_until(
        self,
        marker_or_word: str,
        *,
        default_wait: float = 0.5,
        frozen_frame: bool = True,
    ) -> None:
        """Wait until a named beat or spoken phrase timestamp (or ``default_wait`` if unset)."""
        target_t = self.narration.time_of(marker_or_word)
        delta = (target_t - self.time) if target_t is not None else float(default_wait)
        if delta > 1e-4:
            self.wait(delta, frozen_frame=frozen_frame)

    def check_layout(self, **kwargs: Any) -> list[str]:
        """Run automated clipping & overlap QA checks on foreground mobjects."""
        return check_scene_layout(self, **kwargs)


_ = (DOWN, ORIGIN)
