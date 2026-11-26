"""CUDA acceleration kernels (CuPy) and NVENC hardware encoding helpers."""

from __future__ import annotations

import contextlib
import functools
import io
import math
import os
import sys
import warnings
from pathlib import Path
from typing import Any

import av
import numpy as np

__all__ = [
    "cinema_cuda_config",
    "cuda_apply_postfx",
    "cuda_available",
    "cuda_device_name",
    "cuda_gaussian_blur_rgb",
    "cuda_process_glass_roi",
    "cuda_resize_bilinear",
    "nvenc_available",
]

_DLL_HANDLES: list[object] = []


def _register_nvidia_dll_dirs() -> None:
    """Register wheel-bundled NVIDIA CUDA DLL directories on Windows."""
    if os.name != "nt":
        return
    candidates = [
        Path(sys.prefix) / "Lib" / "site-packages" / "nvidia",
        Path(__file__).resolve().parents[2] / ".venv" / "Lib" / "site-packages" / "nvidia",
    ]
    seen: set[Path] = set()
    for root in candidates:
        if not root.is_dir():
            continue
        cuda_runtime_dir = root / "cuda_runtime"
        if cuda_runtime_dir.is_dir():
            os.environ.setdefault("CUDA_PATH", str(cuda_runtime_dir))
        for bin_dir in root.glob("*/bin"):
            resolved = bin_dir.resolve()
            if resolved.is_dir() and resolved not in seen:
                seen.add(resolved)
                with contextlib.suppress(OSError):
                    _DLL_HANDLES.append(os.add_dll_directory(str(resolved)))


@functools.lru_cache(maxsize=1)
def _load_cupy() -> Any | None:
    """Import CuPy and run a tiny kernel warmup; return ``None`` if unavailable."""
    _register_nvidia_dll_dirs()
    try:
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message="CUDA path could not be detected.*",
            )
            import cupy as cp  # type: ignore[import-not-found]

        if cp.cuda.runtime.getDeviceCount() <= 0:
            return None
        probe = cp.zeros(4, dtype=cp.float32) + 1.0
        _ = float(probe.sum())
        return cp
    except Exception:
        return None


def cuda_available() -> bool:
    """Return ``True`` when a working CUDA GPU + CuPy runtime is available."""
    return _load_cupy() is not None


@functools.lru_cache(maxsize=1)
def cuda_device_name() -> str | None:
    """Return the active CUDA GPU device name, or ``None`` if unavailable."""
    cp = _load_cupy()
    if cp is None:
        return None
    try:
        props = cp.cuda.runtime.getDeviceProperties(0)
        raw_name = props["name"]
        return raw_name.decode("utf-8") if isinstance(raw_name, bytes) else str(raw_name)
    except Exception:
        return None


@functools.lru_cache(maxsize=8)
def nvenc_available(codec: str = "h264_nvenc") -> bool:
    """Return ``True`` if ``codec`` is available and opens a real NVENC session."""
    if codec not in av.codecs_available:
        return False
    try:
        buf = io.BytesIO()
        container = av.open(buf, mode="w", format="mp4")
        try:
            stream = container.add_stream(
                codec,
                rate=24,
                options={"preset": "p4", "rc": "vbr", "cq": "19"},
            )
            stream.pix_fmt = "yuv420p"
            stream.width = 256
            stream.height = 144
            frame = av.VideoFrame.from_ndarray(
                np.zeros((144, 256, 4), dtype=np.uint8),
                format="rgba",
            )
            frame.pts = 0
            for packet in stream.encode(frame):
                container.mux(packet)
            for packet in stream.encode():
                container.mux(packet)
        finally:
            container.close()
        return True
    except Exception:
        return False


def cinema_cuda_config(
    *,
    codec: str = "h264_nvenc",
    cq: int = 19,
    preset: str = "p4",
    max_inflight_encoders: int = 2,
) -> dict[str, Any]:
    """Return a ``tempconfig``-compatible dict enabling hardware NVENC if available."""
    if not nvenc_available(codec):
        return {}
    return {
        "video_codec": codec,
        "video_encoder_options": {
            "preset": preset,
            "rc": "vbr",
            "cq": str(cq),
        },
        "max_inflight_encoders": max_inflight_encoders,
    }


@functools.lru_cache(maxsize=128)
def _gaussian_weights_1d(sigma_key: float) -> tuple[int, tuple[float, ...]]:
    radius = min(32, max(1, math.ceil(2.5 * sigma_key)))
    xs = np.arange(-radius, radius + 1, dtype=np.float64)
    w = np.exp(-0.5 * (xs / sigma_key) ** 2)
    w /= np.sum(w)
    return radius, tuple(float(v) for v in w)


def cuda_gaussian_blur_rgb(arr_gpu: Any, sigma: float) -> Any:
    """Edge-padded separable 1D Gaussian blur on a ``(H, W, C)`` CuPy float32 array."""
    if sigma <= 0.1 or arr_gpu.shape[0] < 2 or arr_gpu.shape[1] < 2:
        return arr_gpu
    cp = _load_cupy()
    assert cp is not None
    radius, weights = _gaussian_weights_1d(round(float(sigma), 2))
    h, w, _ = arr_gpu.shape

    padded_h = cp.pad(arr_gpu, ((0, 0), (radius, radius), (0, 0)), mode="edge")
    horiz = cp.zeros_like(arr_gpu)
    for idx, weight in enumerate(weights):
        horiz += weight * padded_h[:, idx : idx + w, :]

    padded_v = cp.pad(horiz, ((radius, radius), (0, 0), (0, 0)), mode="edge")
    vert = cp.zeros_like(horiz)
    for idx, weight in enumerate(weights):
        vert += weight * padded_v[idx : idx + h, :, :]
    return vert


def cuda_resize_bilinear(arr_gpu: Any, out_h: int, out_w: int) -> Any:
    """Vectorized bilinear resize on a ``(H, W, C)`` CuPy float32 array."""
    cp = _load_cupy()
    assert cp is not None
    in_h, in_w, _ = arr_gpu.shape
    if in_h == out_h and in_w == out_w:
        return arr_gpu
    yy = cp.linspace(0.0, max(0.0, in_h - 1.0001), out_h, dtype=cp.float32)[:, None]
    xx = cp.linspace(0.0, max(0.0, in_w - 1.0001), out_w, dtype=cp.float32)[None, :]
    iy0 = yy.astype(cp.int32)
    ix0 = xx.astype(cp.int32)
    iy1 = cp.minimum(iy0 + 1, in_h - 1)
    ix1 = cp.minimum(ix0 + 1, in_w - 1)
    fy = (yy - iy0)[..., None]
    fx = (xx - ix0)[..., None]
    c00 = arr_gpu[iy0, ix0]
    c01 = arr_gpu[iy0, ix1]
    c10 = arr_gpu[iy1, ix0]
    c11 = arr_gpu[iy1, ix1]
    return (c00 * (1.0 - fx) + c01 * fx) * (1.0 - fy) + (
        c10 * (1.0 - fx) + c11 * fx
    ) * fy


@functools.lru_cache(maxsize=8)
def _vignette_grid_gpu(height: int, width: int) -> Any:
    cp = _load_cupy()
    assert cp is not None
    y = cp.linspace(-1.0, 1.0, height, dtype=cp.float32)
    x = cp.linspace(-1.0, 1.0, width, dtype=cp.float32)
    yy, xx = cp.meshgrid(y, x, indexing="ij")
    aspect = width / max(height, 1)
    r2 = (xx * xx) + (yy * yy) / max(aspect * 0.65, 1.0)
    return cp.clip(r2 * 0.55, 0.0, 1.5)[..., None]


@functools.lru_cache(maxsize=2)
def _dither_tile_gpu(size: int = 256) -> Any:
    cp = _load_cupy()
    assert cp is not None
    rng = np.random.default_rng(1337)
    u1 = rng.random((size, size, 1), dtype=np.float32)
    u2 = rng.random((size, size, 1), dtype=np.float32)
    return cp.asarray((u1 - u2) * (1.0 / 255.0))


@functools.lru_cache(maxsize=2)
def _grain_tile_gpu(size: int = 256) -> Any:
    cp = _load_cupy()
    assert cp is not None
    rng = np.random.default_rng(7331)
    return cp.asarray(rng.normal(0.0, 1.0, size=(size, size, 1)).astype(np.float32))


@functools.lru_cache(maxsize=2)
def _frost_tile_gpu(size: int = 128) -> Any:
    cp = _load_cupy()
    assert cp is not None
    yy = np.arange(size, dtype=np.float32)[:, None]
    xx = np.arange(size, dtype=np.float32)[None, :]
    hashed = np.sin(xx * 12.9898 + yy * 78.233) * 43758.5453
    return cp.asarray(((hashed - np.floor(hashed)) - 0.5) * 2.0)


def _tiled_crop_gpu(tile: Any, height: int, width: int, oy: int, ox: int) -> Any:
    cp = _load_cupy()
    assert cp is not None
    th, tw = tile.shape[:2]
    ry = oy % th
    rx = ox % tw
    ny = math.ceil((height + ry) / th)
    nx = math.ceil((width + rx) / tw)
    tiled = cp.tile(tile, (ny, nx, 1))
    return tiled[ry : ry + height, rx : rx + width]


def cuda_apply_postfx(
    pixels: np.ndarray,
    *,
    bloom_intensity: float,
    bloom_threshold: float,
    bloom_radius: float,
    halation: float,
    vignette: float,
    grain: float,
    dither: bool,
    defocus: float = 0.0,
    exposure: float = 1.0,
    frame_index: int = 0,
) -> np.ndarray:
    """Execute the full ``CinemaPostFX`` pass on CUDA and return ``uint8`` RGBA."""
    cp = _load_cupy()
    if cp is None:
        raise RuntimeError("CUDA runtime is not available.")

    height, width = pixels.shape[:2]
    gpu_rgba = cp.asarray(pixels)
    rgb = gpu_rgba[..., :3].astype(cp.float32) * (1.0 / 255.0)

    if defocus > 0.05:
        scale_px = max(height / 1080.0, 0.35)
        sigma = float(defocus) * scale_px
        ds = 2 if sigma > 4.0 and min(height, width) >= 64 else 1
        if ds > 1:
            blurred_small = cuda_gaussian_blur_rgb(rgb[::ds, ::ds], sigma / ds)
            rgb = cuda_resize_bilinear(blurred_small, height, width)
        else:
            rgb = cuda_gaussian_blur_rgb(rgb, sigma)

    if exposure != 1.0:
        rgb *= float(exposure)

    if bloom_intensity > 0.0 or halation > 0.0:
        scale_px = max(height / 1080.0, 0.35)
        ds = 4 if min(height, width) >= 240 else 2 if min(height, width) >= 64 else 1
        small = rgb[::ds, ::ds]
        luma = 0.2126 * small[..., 0] + 0.7152 * small[..., 1] + 0.0722 * small[..., 2]
        thresh = min(max(bloom_threshold, 0.0), 0.98)
        highlight_mask = cp.clip((luma - thresh) / max(1.0 - thresh, 1e-4), 0.0, 1.0)
        highlights = small * (highlight_mask * highlight_mask)[..., None]

        sigma_small = max(0.8, (bloom_radius * scale_px) / ds)
        glow_tight = cuda_gaussian_blur_rgb(highlights, sigma_small * 0.45)
        glow_wide = cuda_gaussian_blur_rgb(highlights, sigma_small * 1.15)
        glow_small = 0.55 * glow_tight + 0.45 * glow_wide

        glow = (
            cuda_resize_bilinear(glow_small, height, width)
            if ds > 1
            else glow_small
        )
        if bloom_intensity > 0.0:
            rgb += float(bloom_intensity) * glow
        if halation > 0.0:
            halation_tint = cp.asarray([1.0, 0.42, 0.16], dtype=cp.float32)
            rgb += float(halation) * glow * halation_tint

    if vignette > 0.0:
        r2 = _vignette_grid_gpu(height, width)
        vig = cp.clip(1.0 - float(vignette) * r2, 0.25, 1.0)
        rgb *= vig

    if grain > 0.0 or dither:
        oy = frame_index * 73
        ox = frame_index * 137
        if grain > 0.0:
            rgb += _tiled_crop_gpu(_grain_tile_gpu(256), height, width, oy, ox) * float(grain)
        if dither:
            rgb += _tiled_crop_gpu(_dither_tile_gpu(256), height, width, oy, ox)

    gpu_rgba[..., :3] = cp.clip(rgb * 255.0 + 0.5, 0.0, 255.0).astype(cp.uint8)
    return np.ascontiguousarray(cp.asnumpy(gpu_rgba))


def cuda_process_glass_roi(
    backdrop_u8: np.ndarray,
    dst_roi_u8: np.ndarray,
    mask_u8: np.ndarray,
    *,
    sigma: float,
    refraction: float,
    px_scale: float,
    saturation: float,
    brightness: float,
    tint_rgb: np.ndarray,
    tint_op: float,
    sheen_opacity: float,
    frost_noise: float,
    alpha_scale: float,
    x0: int,
    y0: int,
) -> np.ndarray:
    """Run optical glass backdrop blur, grading, and compositing on CUDA."""
    cp = _load_cupy()
    if cp is None:
        raise RuntimeError("CUDA runtime is not available.")

    roi_h, roi_w = mask_u8.shape
    backdrop_gpu = cp.asarray(backdrop_u8).astype(cp.float32) * (1.0 / 255.0)
    dst_gpu = cp.asarray(dst_roi_u8).astype(cp.float32) * (1.0 / 255.0)
    mask_gpu = cp.asarray(mask_u8).astype(cp.float32) * (1.0 / 255.0)

    if sigma > 8.0 and roi_h >= 32 and roi_w >= 32:
        ds = backdrop_gpu[::2, ::2]
        blurred_ds = cuda_gaussian_blur_rgb(ds, sigma * 0.5)
        blurred = cuda_resize_bilinear(blurred_ds, roi_h, roi_w)
    elif sigma > 0.1:
        blurred = cuda_gaussian_blur_rgb(backdrop_gpu, sigma)
    else:
        blurred = backdrop_gpu

    if refraction > 0.0 and roi_h >= 8 and roi_w >= 8:
        bevel = cuda_gaussian_blur_rgb(mask_gpu[..., None], max(1.5, 6.0 * px_scale))[..., 0]
        gy, gx = cp.gradient(bevel)
        disp = float(refraction) * 180.0 * float(px_scale)
        yy = cp.arange(roi_h, dtype=cp.float32)[:, None] - gy * disp
        xx = cp.arange(roi_w, dtype=cp.float32)[None, :] - gx * disp
        cp.clip(yy, 0.0, max(0.0, roi_h - 1.001), out=yy)
        cp.clip(xx, 0.0, max(0.0, roi_w - 1.001), out=xx)
        iy0 = yy.astype(cp.int32)
        ix0 = xx.astype(cp.int32)
        iy1 = cp.minimum(iy0 + 1, roi_h - 1)
        ix1 = cp.minimum(ix0 + 1, roi_w - 1)
        fy = (yy - iy0)[..., None]
        fx = (xx - ix0)[..., None]
        c00 = blurred[iy0, ix0]
        c01 = blurred[iy0, ix1]
        c10 = blurred[iy1, ix0]
        c11 = blurred[iy1, ix1]
        blurred = (c00 * (1.0 - fx) + c01 * fx) * (1.0 - fy) + (
            c10 * (1.0 - fx) + c11 * fx
        ) * fy

    luma = (
        0.2126 * blurred[..., 0]
        + 0.7152 * blurred[..., 1]
        + 0.0722 * blurred[..., 2]
    )[..., None]
    glass_rgb = cp.clip(
        (luma + (blurred - luma) * float(saturation)) * float(brightness),
        0.0,
        1.0,
    )

    tint_gpu = cp.asarray(tint_rgb, dtype=cp.float32)
    glass_rgb = glass_rgb * (1.0 - float(tint_op)) + tint_gpu * float(tint_op)

    if sheen_opacity > 0.0:
        v_loc = cp.linspace(0.0, 1.0, roi_h, dtype=cp.float32)[:, None, None]
        glass_rgb = cp.clip(glass_rgb + (1.0 - v_loc) * float(sheen_opacity), 0.0, 1.0)

    if frost_noise > 0.0:
        frost = _tiled_crop_gpu(
            _frost_tile_gpu(128)[..., None], roi_h, roi_w, y0, x0
        ) * float(frost_noise)
        glass_rgb = cp.clip(glass_rgb + frost, 0.0, 1.0)

    blend = (mask_gpu * float(alpha_scale))[..., None]
    out_rgb = dst_gpu[..., :3] * (1.0 - blend) + glass_rgb * blend
    out_a = dst_gpu[..., 3:4] + blend * (1.0 - dst_gpu[..., 3:4])

    out = cp.empty((roi_h, roi_w, 4), dtype=cp.uint8)
    out[..., :3] = cp.clip(out_rgb * 255.0 + 0.5, 0.0, 255.0).astype(cp.uint8)
    out[..., 3:4] = cp.clip(out_a * 255.0 + 0.5, 0.0, 255.0).astype(cp.uint8)
    return np.ascontiguousarray(cp.asnumpy(out))
