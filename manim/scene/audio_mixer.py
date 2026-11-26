"""Probe, decode, and mix scene sounds for media assembly.

Sounds are placed at scene times and mixed into one track for the whole scene. A
movie or section video contains the parts of that track that fall into the scene
intervals it shows.
"""

from __future__ import annotations

__all__: list[str] = []

import functools
import math
import os
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path

import av
import numpy as np

from ..cinema.synth import parse_synth_name, synth_duration, synthesize_preset
from ..utils.sounds import get_full_sound_file_path

SAMPLE_RATE = 48_000
"""Sample rate of mixed audio, in Hz."""

LAYOUT = "stereo"
"""Channel layout of mixed audio."""

_BLOCK_SIZE = SAMPLE_RATE  # one second of samples per mixed block


@dataclass(frozen=True, slots=True)
class _Sound:
    """A sound added to a scene, placed on the scene clock.

    One record per ``add_sound()`` call, from the call to the mix: the run loop
    passes it to its listeners, the timeline records it, the file writer keeps
    it and the mixer plays it. Make it with :meth:`at`, which checks the file.

    Attributes
    ----------
    file
        The sound file as the scene named it, which timelines record.
    path
        The file's resolved path, which is read.
    start
        Scene time in seconds at which the sound starts. May be negative, in which
        case the part before zero is never heard.
    gain
        Gain applied to the sound, in dB.
    gain_to_background
        Gain applied to all previously added sounds while this one plays, in dB.
    """

    file: str
    path: Path | None
    start: float
    gain: float | None = None
    gain_to_background: float | None = None
    pan: float = 0.0
    pitch: float = 0.0
    fade_in: float = 0.0
    fade_out: float = 0.0
    synth: str | None = None

    @classmethod
    def at(
        cls,
        file: str | os.PathLike[str],
        start: float,
        assets_dir: Path,
        gain: float | None = None,
        gain_to_background: float | None = None,
        pan: float = 0.0,
        pitch: float = 0.0,
        fade_in: float = 0.0,
        fade_out: float = 0.0,
    ) -> _Sound:
        """The sound of ``file`` at scene time ``start``, with the file found
        directly or in ``assets_dir`` and checked to hold audio.

        Raises
        ------
        OSError
            If the sound file does not exist.
        ValueError
            If the sound file cannot be read as audio or synth/parameters are invalid.
        """
        pan_f = float(pan)
        pitch_f = float(pitch)
        fade_in_f = float(fade_in)
        fade_out_f = float(fade_out)
        if not math.isfinite(pan_f):
            raise ValueError("Sound pan must be finite.")
        if not math.isfinite(pitch_f):
            raise ValueError("Sound pitch must be finite.")
        if not math.isfinite(fade_in_f) or fade_in_f < 0.0:
            raise ValueError("Sound fade_in must be finite and non-negative.")
        if not math.isfinite(fade_out_f) or fade_out_f < 0.0:
            raise ValueError("Sound fade_out must be finite and non-negative.")
        pan_f = max(-1.0, min(1.0, pan_f))

        file_str = str(file)
        preset = parse_synth_name(file_str)
        if preset is not None:
            return cls(
                file_str,
                None,
                float(start),
                gain,
                gain_to_background,
                pan=pan_f,
                pitch=pitch_f,
                fade_in=fade_in_f,
                fade_out=fade_out_f,
                synth=preset,
            )

        path = get_full_sound_file_path(file, assets_dir)
        _probe_duration(path)
        return cls(
            file_str,
            path,
            float(start),
            gain,
            gain_to_background,
            pan=pan_f,
            pitch=pitch_f,
            fade_in=fade_in_f,
            fade_out=fade_out_f,
            synth=None,
        )

    @property
    def duration(self) -> float | None:
        """The sound's duration in seconds, from its file's headers or synth."""
        if self.synth is not None:
            return synth_duration(self.synth)
        assert self.path is not None
        return _probe_duration(self.path)


def _probe_duration(path: Path) -> float | None:
    """Return the duration of the first audio stream of ``path`` without decoding.

    Returns ``None`` if the container headers do not state a duration. The result
    is kept while the file is unchanged: a timeline and the file writer both ask
    for it, and scenes often play the same sound file many times.

    Raises
    ------
    ValueError
        If the file cannot be read as media or contains no audio stream.
    """
    try:
        stamp = os.stat(path)
    except OSError as error:
        raise ValueError(f"Could not read audio from {path}: {error}") from error
    return _probe_unchanged(str(path), stamp.st_mtime_ns, stamp.st_size)


@functools.lru_cache(maxsize=1024)
def _probe_unchanged(path: str, mtime_ns: int, size: int) -> float | None:
    try:
        with av.open(str(path)) as container:
            if not container.streams.audio:
                raise ValueError(f"Could not read audio from {path}: no audio stream.")
            stream = container.streams.audio[0]
            if stream.duration is not None and stream.time_base is not None:
                return float(stream.duration * stream.time_base)
            if container.duration is not None:
                return float(container.duration / av.time_base)
            return None
    except av.FFmpegError as error:
        raise ValueError(f"Could not read audio from {path}: {error}") from error


def _decode(path: Path) -> np.ndarray:
    """Decode the first audio stream of ``path`` to 16-bit stereo samples.

    The result has shape ``(2, n)`` at :data:`SAMPLE_RATE`, as ``int16``: decoded
    sounds stay in memory while the movie and its sections are assembled, and
    16 bits take half the memory of floats (as pydub did). The mixer converts
    the samples it needs block by block; see :func:`_to_float`. Mono sources are copied
    to both channels at full level; sources with more than two channels are
    downmixed by libswresample.

    Raises
    ------
    ValueError
        If the file's audio data cannot be decoded.
    """
    try:
        with av.open(str(path)) as container:
            stream = container.streams.audio[0]
            layout = "mono" if stream.codec_context.channels == 1 else LAYOUT
            resampler = av.AudioResampler(
                format="s16p", layout=layout, rate=SAMPLE_RATE
            )
            chunks = [
                resampled.to_ndarray()
                for frame in container.decode(stream)
                for resampled in resampler.resample(frame)
            ]
        chunks += [resampled.to_ndarray() for resampled in resampler.resample(None)]
    except av.FFmpegError as error:
        raise ValueError(f"Could not read audio from {path}: {error}") from error
    channels = 1 if layout == "mono" else 2
    samples = (
        np.concatenate(chunks, axis=1)
        if chunks
        else np.zeros((channels, 0), dtype=np.int16)
    )
    if channels == 1:
        samples = np.repeat(samples, 2, axis=0)
    return samples.astype(np.int16, copy=False)


_INT16_SCALE = 2**15
"""Samples of 16-bit audio per unit of level: int16 covers ``[-1, 1)``."""


def _to_float(samples: np.ndarray) -> np.ndarray:
    """Convert 16-bit samples to float32 in ``[-1, 1)``."""
    return samples.astype(np.float32) / _INT16_SCALE


def _db_to_factor(gain: float) -> float:
    """The amplitude factor of a gain in decibels: ``20 * log10(factor) == gain``."""
    return float(10 ** (gain / 20))


def _seconds_to_samples(seconds: float) -> int:
    return round(seconds * SAMPLE_RATE)


def _prepare_sound_samples(
    samples: np.ndarray,
    *,
    pitch: float,
    pan: float,
    fade_in: float,
    fade_out: float,
    is_float: bool,
) -> np.ndarray:
    """Convert raw decoded/synth audio to float32 ``(2, n)`` with pitch, fades, and pan."""
    audio = samples.astype(np.float32, copy=True) if is_float else _to_float(samples)

    if pitch != 0.0 and audio.shape[1] > 1:
        factor = 2.0 ** (pitch / 12.0)
        new_len = max(1, round(audio.shape[1] / factor))
        src_x = np.arange(audio.shape[1], dtype=np.float64)
        dst_x = np.linspace(0.0, audio.shape[1] - 1, new_len, dtype=np.float64)
        audio = np.vstack(
            [
                np.interp(dst_x, src_x, audio[0]).astype(np.float32),
                np.interp(dst_x, src_x, audio[1]).astype(np.float32),
            ]
        )

    n = audio.shape[1]
    if fade_in > 0.0 and n > 0:
        n_in = min(n, round(fade_in * SAMPLE_RATE))
        if n_in > 0:
            t = np.linspace(0.0, math.pi, n_in, endpoint=True, dtype=np.float32)
            audio[:, :n_in] *= 0.5 * (1.0 - np.cos(t))
    if fade_out > 0.0 and n > 0:
        n_out = min(n, round(fade_out * SAMPLE_RATE))
        if n_out > 0:
            t = np.linspace(0.0, math.pi, n_out, endpoint=True, dtype=np.float32)
            audio[:, -n_out:] *= 0.5 * (1.0 + np.cos(t))

    if pan != 0.0:
        if pan < 0.0:
            gain_l = 1.0
            gain_r = math.cos(-pan * math.pi / 2.0)
        else:
            gain_l = math.cos(pan * math.pi / 2.0)
            gain_r = 1.0
        audio[0] *= gain_l
        audio[1] *= gain_r

    return audio


def _soft_limit_inplace(block: np.ndarray, knee: float = 0.9) -> None:
    """Soft-knee limiter preserving samples within ``[-knee, knee]``."""
    abs_val = np.abs(block)
    over = abs_val > knee
    if np.any(over):
        headroom = 1.0 - knee
        excess = abs_val[over] - knee
        limited = knee + headroom * np.tanh(excess / headroom)
        block[over] = np.copysign(limited, block[over])
    np.clip(block, -1.0, 1.0, out=block)


def _movie_time(intervals: Sequence[tuple[float, float]], scene_time: float) -> float:
    """Return the movie time at which ``scene_time`` is shown.

    ``intervals`` are the ordered, non-overlapping scene-time spans ``(start,
    end)`` that the movie shows, one after the other. Parts of the scene left
    out take no movie time, so the result never decreases and a scene interval
    maps to one contiguous movie interval. The file writer places sections and
    subcaptions with it, and the mixer its intervals' sample boundaries.
    """
    return sum(max(0.0, min(scene_time, end) - start) for start, end in intervals)


class _SoundMix:
    """Mix sounds and cut the mix to the parts of the scene the movie shows.

    Parameters
    ----------
    sounds
        Sounds in insertion order. The order matters for ``gain_to_background``,
        which affects only the sounds added before.
    intervals
        Ordered, non-overlapping scene-time intervals ``(start, end)`` that are
        shown in the movie. They are concatenated: movie time runs through each
        interval in turn.
    """

    def __init__(
        self,
        sounds: Sequence[_Sound],
        intervals: Sequence[tuple[float, float]],
    ) -> None:
        self._sounds = list(sounds)
        raw_files: dict[Path, np.ndarray] = {}
        prepared: list[np.ndarray] = []
        for sound in self._sounds:
            if sound.synth is not None:
                raw = synthesize_preset(sound.synth)
                is_float = True
            else:
                assert sound.path is not None
                if sound.path not in raw_files:
                    raw_files[sound.path] = _decode(sound.path)
                raw = raw_files[sound.path]
                is_float = False
            prepared.append(
                _prepare_sound_samples(
                    raw,
                    pitch=sound.pitch,
                    pan=sound.pan,
                    fade_in=sound.fade_in,
                    fade_out=sound.fade_out,
                    is_float=is_float,
                )
            )
        self._prepared = prepared

        # Each interval in samples: (scene start, movie start, length). An
        # interval ends at the sample where the next one starts, so rounding
        # never creates gaps or overlaps.
        self._intervals: list[tuple[int, int, int]] = []
        for start, end in intervals:
            movie_start = _seconds_to_samples(_movie_time(intervals, start))
            length = _seconds_to_samples(_movie_time(intervals, end)) - movie_start
            self._intervals.append((_seconds_to_samples(start), movie_start, length))
        self.duration = _movie_time(intervals, math.inf)
        """Total movie duration in seconds."""

        # Each sound's audible pieces: (movie start, source start, length).
        self._placements = [
            self._place(sound, samples.shape[1])
            for sound, samples in zip(self._sounds, self._prepared, strict=True)
        ]

    def _place(self, sound: _Sound, sample_count: int) -> list[tuple[int, int, int]]:
        start = _seconds_to_samples(sound.start)
        end = start + sample_count
        pieces = []
        for scene_start, movie_start, length in self._intervals:
            low = max(start, scene_start)
            high = min(end, scene_start + length)
            if low < high:
                pieces.append(
                    (movie_start + low - scene_start, low - start, high - low)
                )
        return pieces

    def blocks(self, start: float, end: float) -> Iterator[np.ndarray]:
        """Yield the mix between two movie times as float32 ``(2, n)`` blocks.

        Blocks are at most one second long and soft-limited to ``[-1, 1]``.
        """
        first, stop = _seconds_to_samples(start), _seconds_to_samples(end)
        ramp_samples = round(0.010 * SAMPLE_RATE)
        for block_start in range(first, stop, _BLOCK_SIZE):
            block_end = min(block_start + _BLOCK_SIZE, stop)
            block = np.zeros((2, block_end - block_start), dtype=np.float32)
            for sound, samples, pieces in zip(
                self._sounds, self._prepared, self._placements, strict=True
            ):
                for movie_start, source_start, length in pieces:
                    low = max(movie_start, block_start)
                    high = min(movie_start + length, block_end)
                    if low >= high:
                        continue
                    region = block[:, low - block_start : high - block_start]
                    if sound.gain_to_background is not None:
                        target_duck = _db_to_factor(sound.gain_to_background)
                        r_len = high - low
                        duck_env = np.full(r_len, target_duck, dtype=np.float32)
                        ramp = min(ramp_samples, length // 2)
                        if ramp > 1:
                            piece_end = movie_start + length
                            # Attack at start of piece
                            a_end = min(high, movie_start + ramp)
                            if low < a_end:
                                pos = np.arange(low, a_end, dtype=np.float32) - movie_start
                                w = 0.5 * (1.0 - np.cos(math.pi * pos / ramp))
                                duck_env[: a_end - low] = 1.0 + (target_duck - 1.0) * w
                            # Release at end of piece
                            r_start = max(low, piece_end - ramp)
                            if r_start < high:
                                pos = piece_end - np.arange(r_start, high, dtype=np.float32)
                                w = 0.5 * (1.0 - np.cos(math.pi * pos / ramp))
                                env_slice = duck_env[r_start - low :]
                                env_slice[:] = np.maximum(
                                    env_slice,
                                    1.0 + (target_duck - 1.0) * w,
                                )
                        region *= duck_env
                    offset = source_start + low - movie_start
                    source = samples[:, offset : offset + high - low]
                    if sound.gain is not None:
                        source = source * _db_to_factor(sound.gain)
                    region += source
            _soft_limit_inplace(block)
            yield block
