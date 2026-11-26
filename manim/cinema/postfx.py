"""Post-processing pipeline for dark cinema scenes (bloom, halation, vignette, dithering)."""

from __future__ import annotations

import functools
import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter

from .cuda import cuda_apply_postfx, cuda_available

if TYPE_CHECKING:
    from manim.typing import RGBAPixelArray

__all__ = ["CinemaPostFX"]


@functools.lru_cache(maxsize=4)
def _tpdf_dither_tile(size: int = 256) -> np.ndarray:
    """Cached ``(size, size, 1)`` luminance TPDF dither tile in ``[-1/255, 1/255]``."""
    rng = np.random.default_rng(1337)
    u1 = rng.random((size, size, 1), dtype=np.float32)
    u2 = rng.random((size, size, 1), dtype=np.float32)
    return (u1 - u2) * (1.0 / 255.0)


@functools.lru_cache(maxsize=4)
def _grain_tile(size: int = 256) -> np.ndarray:
    """Cached ``(size, size, 1)`` unit-variance Gaussian film grain tile."""
    rng = np.random.default_rng(7331)
    return rng.normal(0.0, 1.0, size=(size, size, 1)).astype(np.float32)


@functools.lru_cache(maxsize=8)
def _radial_vignette_grid(height: int, width: int) -> np.ndarray:
    """Cached normalized radial squared-distance grid ``(H, W, 1)``."""
    y = np.linspace(-1.0, 1.0, height, dtype=np.float32)
    x = np.linspace(-1.0, 1.0, width, dtype=np.float32)
    yy, xx = np.meshgrid(y, x, indexing="ij")
    aspect = width / max(height, 1)
    # Slightly elliptical cinema vignette matching frame aspect
    r2 = (xx * xx) + (yy * yy) / max(aspect * 0.65, 1.0)
    return np.clip(r2 * 0.55, 0.0, 1.5)[..., None]


@dataclass(frozen=True, slots=True)
class CinemaPostFX:
    """Optical post-processing pass applied to rendered RGBA frames.

    Designed for dark themes and frosted-glass visuals: adds soft highlight
    bloom, subtle warm film halation, smooth optical vignette, micro film grain,
    and TPDF dithering to prevent 8-bit dark-gradient banding.
    """

    bloom_intensity: float = 0.22
    bloom_threshold: float = 0.70
    bloom_radius: float = 28.0
    halation: float = 0.0
    vignette: float = 0.22
    grain: float = 0.010
    dither: bool = True
    defocus: float = 0.0
    exposure: float = 1.0
    use_cuda: bool | Literal["auto"] = "auto"

    def cache_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dictionary for segment cache identity."""
        return {
            "bloom_intensity": self.bloom_intensity,
            "bloom_threshold": self.bloom_threshold,
            "bloom_radius": self.bloom_radius,
            "halation": self.halation,
            "vignette": self.vignette,
            "grain": self.grain,
            "dither": self.dither,
            "defocus": self.defocus,
            "exposure": self.exposure,
        }

    def _should_use_cuda(self, height: int, width: int) -> bool:
        if height * width < 4096:
            return False
        if self.use_cuda is True:
            return True
        if self.use_cuda == "auto":
            return cuda_available()
        return False

    def apply(self, pixels: RGBAPixelArray, frame_index: int = 0) -> RGBAPixelArray:
        """Apply post-processing to a top-left ``uint8`` RGBA frame."""
        height, width = pixels.shape[:2]
        if height == 0 or width == 0:
            return pixels

        if self._should_use_cuda(height, width):
            return cuda_apply_postfx(
                pixels,
                bloom_intensity=self.bloom_intensity,
                bloom_threshold=self.bloom_threshold,
                bloom_radius=self.bloom_radius,
                halation=self.halation,
                vignette=self.vignette,
                grain=self.grain,
                dither=self.dither,
                defocus=self.defocus,
                exposure=self.exposure,
                frame_index=frame_index,
            )

        rgb = pixels[..., :3].astype(np.float32) / 255.0
        alpha = pixels[..., 3:4]

        # 0. Optical rack-focus blur & exposure (for camera/scene transitions)
        if self.defocus > 0.05:
            scale_px = max(height / 1080.0, 0.35)
            sigma = float(self.defocus) * scale_px
            ds = 2 if sigma > 4.0 and min(height, width) >= 64 else 1
            if ds > 1:
                small_def = rgb[::ds, ::ds]
                blurred_small = gaussian_filter(
                    small_def, sigma=(sigma / ds, sigma / ds, 0.0)
                )
                def_u8 = np.clip(blurred_small * 255.0 + 0.5, 0.0, 255.0).astype(np.uint8)
                def_pil = Image.fromarray(def_u8, mode="RGB").resize(
                    (width, height), resample=Image.Resampling.BILINEAR
                )
                rgb = np.asarray(def_pil, dtype=np.float32) * (1.0 / 255.0)
            else:
                rgb = gaussian_filter(rgb, sigma=(sigma, sigma, 0.0))

        if self.exposure != 1.0:
            rgb *= float(self.exposure)

        # 1. Multi-scale downsampled bloom + warm halation
        if self.bloom_intensity > 0.0 or self.halation > 0.0:
            scale_px = max(height / 1080.0, 0.35)
            ds = 4 if min(height, width) >= 240 else 2 if min(height, width) >= 64 else 1
            small = rgb[::ds, ::ds]
            luma = (
                0.2126 * small[..., 0]
                + 0.7152 * small[..., 1]
                + 0.0722 * small[..., 2]
            )
            thresh = min(max(self.bloom_threshold, 0.0), 0.98)
            highlight_mask = np.clip((luma - thresh) / max(1.0 - thresh, 1e-4), 0.0, 1.0)
            highlights = small * (highlight_mask * highlight_mask)[..., None]

            sigma_small = max(0.8, (self.bloom_radius * scale_px) / ds)
            glow_tight = gaussian_filter(highlights, sigma=(sigma_small * 0.45, sigma_small * 0.45, 0.0))
            glow_wide = gaussian_filter(highlights, sigma=(sigma_small * 1.15, sigma_small * 1.15, 0.0))
            glow_small = 0.55 * glow_tight + 0.45 * glow_wide

            if ds > 1:
                glow_u8 = np.clip(glow_small * 255.0 + 0.5, 0.0, 255.0).astype(np.uint8)
                glow_pil = Image.fromarray(glow_u8, mode="RGB").resize(
                    (width, height), resample=Image.Resampling.BILINEAR
                )
                glow = np.asarray(glow_pil, dtype=np.float32) * (1.0 / 255.0)
            else:
                glow = glow_small

            if self.bloom_intensity > 0.0:
                rgb += self.bloom_intensity * glow
            if self.halation > 0.0:
                # Warm red-amber halation bleed around high-contrast bright strokes
                halation_tint = np.array([1.0, 0.42, 0.16], dtype=np.float32)
                rgb += self.halation * glow * halation_tint

        # 2. Smooth optical vignette
        if self.vignette > 0.0:
            r2 = _radial_vignette_grid(height, width)
            vig = np.clip(1.0 - self.vignette * r2, 0.25, 1.0)
            rgb *= vig

        # 3. Deterministic film grain + TPDF anti-banding dithering (contiguous tile crop)
        if self.grain > 0.0 or self.dither:
            ry = (frame_index * 73) & 255
            rx = (frame_index * 137) & 255
            ny = math.ceil((height + ry) / 256)
            nx = math.ceil((width + rx) / 256)
            if self.grain > 0.0:
                g_tile = np.tile(_grain_tile(256), (ny, nx, 1))
                rgb += g_tile[ry : ry + height, rx : rx + width] * self.grain
            if self.dither:
                d_tile = np.tile(_tpdf_dither_tile(256), (ny, nx, 1))
                rgb += d_tile[ry : ry + height, rx : rx + width]

        out_rgb = np.clip(rgb * 255.0 + 0.5, 0.0, 255.0).astype(np.uint8)
        out = np.empty((height, width, 4), dtype=np.uint8)
        out[..., :3] = out_rgb
        out[..., 3:4] = alpha
        return np.ascontiguousarray(out)
