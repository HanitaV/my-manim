"""Procedural 48 kHz stereo UI and frosted-glass sound synthesizer."""

from __future__ import annotations

import functools
import math

import numpy as np

__all__ = [
    "SAMPLE_RATE",
    "SFX_GLASS_TAP",
    "SFX_GLASS_CHIME",
    "SFX_SOFT_TICK",
    "SFX_UI_POP",
    "SFX_WHOOSH",
    "SFX_SUB_IMPACT",
    "SFX_SHIMMER",
    "SYNTH_PRESETS",
    "parse_synth_name",
    "synth_duration",
    "synthesize_preset",
]

SAMPLE_RATE = 48_000

SFX_GLASS_TAP = "synth:glass_tap"
SFX_GLASS_CHIME = "synth:glass_chime"
SFX_SOFT_TICK = "synth:soft_tick"
SFX_UI_POP = "synth:ui_pop"
SFX_WHOOSH = "synth:airy_whoosh"
SFX_SUB_IMPACT = "synth:sub_impact"
SFX_SHIMMER = "synth:hover_shimmer"

SYNTH_PRESETS: frozenset[str] = frozenset(
    {
        "glass_tap",
        "glass_chime",
        "soft_tick",
        "ui_pop",
        "airy_whoosh",
        "sub_impact",
        "hover_shimmer",
    }
)


def parse_synth_name(sound_file: str) -> str | None:
    """Return the validated preset name for ``synth:<name>``, or ``None``."""
    if not sound_file.startswith("synth:"):
        return None
    preset = sound_file.removeprefix("synth:")
    if preset not in SYNTH_PRESETS:
        available = ", ".join(sorted(SYNTH_PRESETS))
        raise ValueError(
            f"Unknown synth preset {sound_file!r}. Available presets: {available}."
        )
    return preset


def _raised_cosine_attack(num_samples: int, attack_seconds: float, rate: int) -> np.ndarray:
    n_attack = min(num_samples, max(1, round(attack_seconds * rate)))
    env = np.ones(num_samples, dtype=np.float32)
    t = np.linspace(0.0, math.pi, n_attack, endpoint=True, dtype=np.float32)
    env[:n_attack] = 0.5 * (1.0 - np.cos(t))
    return env


def _smooth_tail_fade(num_samples: int, fade_seconds: float, rate: int) -> np.ndarray:
    n_fade = min(num_samples, max(1, round(fade_seconds * rate)))
    env = np.ones(num_samples, dtype=np.float32)
    t = np.linspace(0.0, math.pi, n_fade, endpoint=True, dtype=np.float32)
    env[-n_fade:] = 0.5 * (1.0 + np.cos(t))
    return env


def _synth_glass_tap(rate: int) -> np.ndarray:
    duration = 0.095
    n = round(duration * rate)
    t = np.arange(n, dtype=np.float32) / rate
    attack = _raised_cosine_attack(n, 0.0012, rate)
    tail = _smooth_tail_fade(n, 0.015, rate)

    # Inharmonic tempered-glass modal partials with subtle L/R stereo detune.
    f0 = 1480.0
    modes = ((1.0, 0.58, 42.0), (2.31, 0.28, 68.0), (3.86, 0.14, 105.0))
    stereo = np.zeros((2, n), dtype=np.float32)
    for ch, detune in enumerate((0.997, 1.003)):
        sig = np.zeros(n, dtype=np.float32)
        for ratio, amp, decay in modes:
            sig += amp * np.sin(2.0 * math.pi * (f0 * ratio * detune) * t) * np.exp(-decay * t)
        # Soft 1.5 ms mallet transient click
        click = 0.22 * np.exp(-1800.0 * t) * np.sin(2.0 * math.pi * 4200.0 * t)
        stereo[ch] = (sig + click) * attack * tail
    return np.clip(stereo * 0.72, -0.85, 0.85).astype(np.float32)


def _synth_glass_chime(rate: int) -> np.ndarray:
    duration = 0.42
    n = round(duration * rate)
    t = np.arange(n, dtype=np.float32) / rate
    attack = _raised_cosine_attack(n, 0.0035, rate)
    tail = _smooth_tail_fade(n, 0.06, rate)

    modes = (
        (880.0, 0.42, 7.5),
        (1320.0, 0.30, 9.2),
        (1980.0, 0.18, 12.5),
        (2640.0, 0.10, 16.0),
    )
    stereo = np.zeros((2, n), dtype=np.float32)
    for ch, detune in enumerate((0.9985, 1.0015)):
        sig = np.zeros(n, dtype=np.float32)
        for freq, amp, decay in modes:
            sig += amp * np.sin(2.0 * math.pi * (freq * detune) * t) * np.exp(-decay * t)
        stereo[ch] = sig * attack * tail
    return np.clip(stereo * 0.75, -0.85, 0.85).astype(np.float32)


def _synth_soft_tick(rate: int) -> np.ndarray:
    duration = 0.018
    n = round(duration * rate)
    t = np.arange(n, dtype=np.float32) / rate
    attack = _raised_cosine_attack(n, 0.0005, rate)
    tail = _smooth_tail_fade(n, 0.004, rate)

    # Smooth exponential pitch drop 2400 Hz -> 1100 Hz
    phase = 2.0 * math.pi * (1100.0 * t + (1300.0 / 260.0) * (1.0 - np.exp(-260.0 * t)))
    mono = np.sin(phase) * np.exp(-240.0 * t) * attack * tail
    mono = mono - float(np.mean(mono))
    stereo = np.vstack([mono, mono]) * 0.65
    return np.clip(stereo, -0.85, 0.85).astype(np.float32)


def _synth_ui_pop(rate: int) -> np.ndarray:
    duration = 0.048
    n = round(duration * rate)
    t = np.arange(n, dtype=np.float32) / rate
    attack = _raised_cosine_attack(n, 0.002, rate)
    tail = _smooth_tail_fade(n, 0.010, rate)

    # Droplet upward sweep 310 -> 590 Hz
    u = t / duration
    freq = 310.0 + 280.0 * (1.0 - np.exp(-6.0 * u))
    phase = 2.0 * math.pi * np.cumsum(freq, dtype=np.float32) / rate
    sig = (0.78 * np.sin(phase) + 0.22 * np.sin(2.0 * phase)) * np.exp(-52.0 * t)
    mono = (sig * attack * tail).astype(np.float32)
    return np.clip(np.vstack([mono, mono]) * 0.72, -0.85, 0.85).astype(np.float32)


def _synth_airy_whoosh(rate: int) -> np.ndarray:
    duration = 0.28
    n = round(duration * rate)
    t = np.arange(n, dtype=np.float32) / rate
    u = t / duration

    # Smooth asymmetric bell envelope
    env = np.sin(math.pi * np.power(u, 0.75)) ** 2
    env *= _smooth_tail_fade(n, 0.03, rate)

    rng = np.random.default_rng(2026)
    freqs = np.fft.rfftfreq(n, d=1.0 / rate).astype(np.float32)
    stereo = np.zeros((2, n), dtype=np.float32)
    for ch in range(2):
        noise = rng.standard_normal(n).astype(np.float32)
        spec = np.fft.rfft(noise)
        # Dual-band airy velvet filter: warm body around 520 Hz + silky air around 1600 Hz
        band1 = np.exp(-0.5 * ((freqs - 520.0) / 260.0) ** 2)
        band2 = 0.65 * np.exp(-0.5 * ((freqs - 1550.0) / 520.0) ** 2)
        shaped = np.fft.irfft(spec * (band1 + band2), n=n).astype(np.float32)
        peak = max(float(np.max(np.abs(shaped))), 1e-6)
        stereo[ch] = (shaped / peak) * env * 0.58
    return np.clip(stereo, -0.85, 0.85).astype(np.float32)


def _synth_sub_impact(rate: int) -> np.ndarray:
    duration = 0.48
    n = round(duration * rate)
    t = np.arange(n, dtype=np.float32) / rate
    attack = _raised_cosine_attack(n, 0.006, rate)
    tail = _smooth_tail_fade(n, 0.09, rate)

    # Exponential pitch drop 92 Hz -> 34 Hz
    freq = 34.0 + 58.0 * np.exp(-11.0 * t)
    phase = 2.0 * math.pi * np.cumsum(freq, dtype=np.float32) / rate
    sub = np.sin(phase) + 0.25 * np.tanh(1.6 * np.sin(2.0 * phase))
    click = 0.14 * np.exp(-90.0 * t) * np.sin(2.0 * math.pi * 220.0 * t)
    mono = ((sub * np.exp(-5.2 * t) + click) * attack * tail).astype(np.float32)
    stereo = np.vstack([mono, mono]) * 0.78
    return np.clip(stereo, -0.85, 0.85).astype(np.float32)


def _synth_hover_shimmer(rate: int) -> np.ndarray:
    duration = 0.18
    n = round(duration * rate)
    t = np.arange(n, dtype=np.float32) / rate
    attack = _raised_cosine_attack(n, 0.014, rate)
    tail = _smooth_tail_fade(n, 0.04, rate)

    stereo = np.zeros((2, n), dtype=np.float32)
    for ch, detune in enumerate((0.9975, 1.0025)):
        sig = (
            0.55 * np.sin(2.0 * math.pi * 1760.0 * detune * t) * np.exp(-14.0 * t)
            + 0.45 * np.sin(2.0 * math.pi * 2637.0 * detune * t) * np.exp(-18.0 * t)
        )
        stereo[ch] = sig * attack * tail * 0.55
    return np.clip(stereo, -0.85, 0.85).astype(np.float32)


_BUILDERS = {
    "glass_tap": _synth_glass_tap,
    "glass_chime": _synth_glass_chime,
    "soft_tick": _synth_soft_tick,
    "ui_pop": _synth_ui_pop,
    "airy_whoosh": _synth_airy_whoosh,
    "sub_impact": _synth_sub_impact,
    "hover_shimmer": _synth_hover_shimmer,
}


@functools.lru_cache(maxsize=32)
def synthesize_preset(name: str, sample_rate: int = SAMPLE_RATE) -> np.ndarray:
    """Return cached stereo ``float32`` waveform ``(2, n)`` for a synth preset."""
    if name not in _BUILDERS:
        available = ", ".join(sorted(SYNTH_PRESETS))
        raise ValueError(
            f"Unknown synth preset {name!r}. Available presets: {available}."
        )
    audio = _BUILDERS[name](sample_rate)
    audio.flags.writeable = False
    return audio


def synth_duration(name: str, sample_rate: int = SAMPLE_RATE) -> float:
    """Return the exact duration in seconds of a built-in synth preset."""
    return synthesize_preset(name, sample_rate).shape[1] / sample_rate
