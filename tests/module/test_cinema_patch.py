"""Tests for the Cinema dark theme, frosted glass, and frame-interaction audio patch."""

from __future__ import annotations

from pathlib import Path

import av
import numpy as np
import pytest
from click.testing import CliRunner

from manim import (
    BLACK,
    BLUE,
    CINEMA_CHAMPAGNE,
    CINEMA_ICE,
    DOWN,
    RED,
    RIGHT,
    UP,
    CinemaPostFX,
    CinemaScene,
    Circle,
    Dot,
    ExplodeStack,
    FadeIn,
    GlassBadge,
    GlassCallout,
    GlassCode,
    GlassPanel,
    GlassStack,
    LaggedStart,
    Line,
    Manager,
    NarrationScript,
    PlopSpring,
    ReactiveText,
    Rectangle,
    Scene,
    SmoothSpring,
    SpringSpec,
    Square,
    Text,
    ValueTracker,
    VGroup,
    apply_accent_gradient,
    attach_spring_follower,
    cinema_dramatic,
    cinema_ease,
    cinema_smooth_out,
    cinema_snappy,
    cinema_spring_plop,
    cinema_spring_smooth,
    cubic_bezier,
    cuda_available,
    cuda_device_name,
    harmonize_color,
    install_cinema_skill,
    make_ambient_background_image,
    nvenc_available,
    render_contact_sheet,
    spring_duration,
    spring_rate,
    tempconfig,
)
from manim.cinema.synth import (
    SAMPLE_RATE,
    SFX_GLASS_CHIME,
    SFX_GLASS_TAP,
    SFX_SOFT_TICK,
    SYNTH_PRESETS,
    synthesize_preset,
)
from manim.scene.audio_mixer import _Sound, _SoundMix


def _decode_stereo_audio(path):
    with av.open(str(path)) as container:
        stream = container.streams.audio[0]
        chunks = []
        for frame in container.decode(stream):
            arr = frame.to_ndarray()
            if not frame.format.is_planar:
                arr = arr.reshape(-1, frame.layout.nb_channels).T
            arr_f = arr.astype(np.float32)
            if arr.dtype.kind == "i":
                arr_f /= float(np.iinfo(arr.dtype).max)
            chunks.append(arr_f)
        return np.concatenate(chunks, axis=1), stream.rate


def test_cubic_bezier_and_cinema_easings():
    for fn in (
        cinema_ease,
        cinema_smooth_out,
        cinema_snappy,
        cinema_dramatic,
        cubic_bezier(0.2, 0.8, 0.3, 1.0),
    ):
        assert fn(-0.5) == 0.0
        assert fn(0.0) == pytest.approx(0.0, abs=1e-6)
        assert fn(1.0) == pytest.approx(1.0, abs=1e-6)
        assert fn(1.5) == 1.0
        xs = np.linspace(0.0, 1.0, 21)
        ys = [fn(float(x)) for x in xs]
        assert all(ys[i] <= ys[i + 1] + 1e-6 for i in range(len(ys) - 1))


def test_glass_panel_renders_real_backdrop_blur_and_fade_in(tmp_path):
    class GlassBlurScene(Scene):
        def construct(self):
            self.camera.background_color = BLACK
            # High-contrast vertical stripe behind the left half of the glass panel
            stripe = Rectangle(
                width=2.0,
                height=4.0,
                fill_color=RED,
                fill_opacity=1.0,
                stroke_width=0,
            ).shift([-1.0, 0.0, 0.0])
            glass = GlassPanel(
                width=4.0,
                height=2.5,
                blur_radius=36.0,
                tint_opacity=0.25,
                rim_opacity=0.6,
                frost_noise=0.0,
            )
            self.add(stripe, glass)

    with tempconfig(
        {
            "pixel_width": 160,
            "pixel_height": 90,
            "frame_rate": 10,
            "media_dir": str(tmp_path / "media"),
            "progress_bar": "none",
        }
    ):
        scene = GlassBlurScene()
        scene.setup()
        scene.construct()
        img = np.asarray(scene.get_image())
        assert img.shape == (90, 160, 4)

        # Across the stripe boundary (x around center=80), glass must blur the sharp
        # red->black transition across multiple intermediate pixels.
        mid_row = img[45, 70:91, 0].astype(np.float32)
        assert mid_row[0] > mid_row[-1] + 15.0
        diffs = np.abs(np.diff(mid_row))
        assert np.max(diffs) < 60.0
        assert int(np.sum(diffs > 3.0)) >= 4

        # Default GlassPanel is clean dark glass (zero shadow, zero sheen bands, zero liquid refraction)
        default_glass = GlassPanel(width=4.0, height=2.5)
        assert default_glass._glass_style is not None
        assert default_glass._glass_style.refraction == 0.0
        assert default_glass._glass_style.frost_noise == 0.0
        assert default_glass._glass_style.sheen_opacity == 0.0

        class CleanGlassScene(Scene):
            def construct(self):
                self.camera.background_color = BLACK
                self.add(GlassPanel(width=4.0, height=2.5))

        clean_scene = CleanGlassScene()
        clean_scene.setup()
        clean_scene.construct()
        clean_img = np.asarray(clean_scene.get_image())
        # Interior is uniform (no diagonal shading bands); exterior stays pure black (zero drop shadow)
        upper_left_luma = float(np.mean(clean_img[34:38, 62:68, :3]))
        lower_right_luma = float(np.mean(clean_img[52:56, 92:98, :3]))
        assert abs(upper_left_luma - lower_right_luma) < 1.5
        assert int(np.max(clean_img[85:90, 60:100, :3])) == 0

        class GlassFadeScene(CinemaScene):
            def construct(self):
                badge = GlassBadge(width=2.0, height=0.5)
                self.play(FadeIn(badge), run_time=0.3)

        Manager(GlassFadeScene()).evaluate()


def test_cinema_postfx_preserves_shape_and_boosts_highlights():
    fx = CinemaPostFX(
        bloom_intensity=0.4,
        bloom_threshold=0.6,
        bloom_radius=12.0,
        halation=0.1,
        vignette=0.2,
        grain=0.005,
        dither=True,
    )
    frame = np.zeros((120, 160, 4), dtype=np.uint8)
    frame[..., 3] = 255
    frame[55:65, 75:85, :3] = 255

    out = fx.apply(frame, frame_index=3)
    assert out.shape == (120, 160, 4)
    assert out.dtype == np.uint8
    assert out.flags.c_contiguous
    assert np.all(out[..., 3] == 255)
    # Bloom spills outward from the bright center square (55..65, 75..85)
    assert int(out[53, 80, 0]) > 5


def test_synth_presets_and_missing_file_behavior(dry_run):
    for preset in SYNTH_PRESETS:
        wave = synthesize_preset(preset)
        assert wave.ndim == 2
        assert wave.shape[0] == 2
        assert wave.shape[1] > 100
        assert wave.dtype == np.float32
        assert float(np.max(np.abs(wave))) <= 0.86

    class BadSynth(Scene):
        def construct(self):
            self.add_sound("synth:nonexistent_fx")

    with pytest.raises(ValueError, match="Unknown synth preset"):
        Manager(BadSynth()).evaluate()

    class MissingWav(Scene):
        def construct(self):
            self.add_sound("missing-file.wav")

    with pytest.raises(OSError, match="missing-file"):
        Manager(MissingWav()).evaluate()


def test_spatial_pan_and_pitch_shift(tmp_path):
    left = _Sound.at(SFX_GLASS_TAP, 0.0, tmp_path, pan=-1.0)
    right = _Sound.at(SFX_GLASS_TAP, 0.2, tmp_path, pan=1.0)
    pitched_up = _Sound.at(SFX_GLASS_TAP, 0.0, tmp_path, pitch=12.0)

    mix_pan = _SoundMix([left, right], [(0.0, 0.4)])
    audio = np.concatenate(list(mix_pan.blocks(0.0, 0.4)), axis=1)
    left_slice = audio[:, : round(0.1 * SAMPLE_RATE)]
    right_slice = audio[:, round(0.2 * SAMPLE_RATE) : round(0.3 * SAMPLE_RATE)]

    assert np.sum(left_slice[0] ** 2) > 50.0 * np.sum(left_slice[1] ** 2) + 1e-4
    assert np.sum(right_slice[1] ** 2) > 50.0 * np.sum(right_slice[0] ** 2) + 1e-4

    # +12 semitones halves waveform duration
    mix_base = _SoundMix([_Sound.at(SFX_GLASS_TAP, 0.0, tmp_path)], [(0.0, 0.2)])
    mix_up = _SoundMix([pitched_up], [(0.0, 0.2)])
    assert mix_up._prepared[0].shape[1] == pytest.approx(
        mix_base._prepared[0].shape[1] / 2.0, abs=2
    )


def test_animation_and_frame_interaction_audio_render(tmp_path):
    class InteractiveAudioScene(CinemaScene):
        ambient_background = False

        def construct(self):
            cards = [
                GlassPanel(width=1.8, height=1.2).shift([-5.0, 0.0, 0.0]),
                GlassPanel(width=1.8, height=1.2).shift([5.0, 0.0, 0.0]),
            ]
            self.play(
                LaggedStart(
                    FadeIn(cards[0]),
                    FadeIn(cards[1]),
                    lag_ratio=0.5,
                ).with_staggered_sound(SFX_GLASS_CHIME, pitch_step=3.0),
                run_time=0.8,
            )

            tracker = ValueTracker(0.0)
            self.add(tracker)
            self.bind_value_tick(tracker, SFX_SOFT_TICK, step=2.0, cooldown=0.05)

            probe = Dot(color=BLUE).move_to([-6.0, 0.0, 0.0])
            self.add(probe)
            self.on_proximity_sound(probe, cards, SFX_GLASS_TAP, cooldown=0.05)

            self.play(
                tracker.animate.set_value(6.0),
                probe.animate.move_to([6.0, 0.0, 0.0]),
                run_time=0.8,
            )

    with tempconfig(
        {
            "pixel_width": 160,
            "pixel_height": 90,
            "frame_rate": 15,
            "format": "mp4",
            "media_dir": str(tmp_path / "media"),
            "progress_bar": "none",
            "disable_caching": True,
        }
    ):
        scene = InteractiveAudioScene()
        scene.render()
        out_path = scene.manager.file_writer.final_file_path
        assert out_path is not None
        assert out_path.exists()

    audio, rate = _decode_stereo_audio(out_path)
    assert rate == 48_000
    # Left card enters at 0.0s; right card enters around 0.27s; probe sweeps to right card around 1.2..1.5s
    assert float(np.max(np.abs(audio))) > 0.05
    left_only = audio[:, : round(0.22 * rate)]
    right_sweep = audio[:, round(1.15 * rate) : round(1.55 * rate)]
    assert np.sum(left_only[0] ** 2) > np.sum(left_only[1] ** 2) * 2.0
    assert np.sum(right_sweep[1] ** 2) > np.sum(right_sweep[0] ** 2) * 2.0


def test_cuda_postfx_and_cpu_parity():
    if not cuda_available():
        pytest.skip("No CUDA GPU available")
    assert cuda_device_name() is not None

    frame = np.zeros((240, 320, 4), dtype=np.uint8)
    frame[..., 3] = 255
    frame[90:150, 130:190, :3] = 240
    frame[40:80, 40:100, 0] = 180

    fx_cpu = CinemaPostFX(
        bloom_intensity=0.3,
        bloom_threshold=0.65,
        bloom_radius=18.0,
        halation=0.08,
        vignette=0.22,
        grain=0.0,
        dither=False,
        use_cuda=False,
    )
    fx_gpu = CinemaPostFX(
        bloom_intensity=0.3,
        bloom_threshold=0.65,
        bloom_radius=18.0,
        halation=0.08,
        vignette=0.22,
        grain=0.0,
        dither=False,
        use_cuda=True,
    )
    out_cpu = fx_cpu.apply(frame, frame_index=2)
    out_gpu = fx_gpu.apply(frame, frame_index=2)
    assert out_gpu.shape == out_cpu.shape
    assert out_gpu.dtype == np.uint8
    assert out_gpu.flags.c_contiguous
    max_diff = int(np.max(np.abs(out_cpu.astype(np.int16) - out_gpu.astype(np.int16))))
    assert max_diff <= 4


def test_nvenc_cinema_scene_encoding(tmp_path):
    if not nvenc_available("h264_nvenc"):
        pytest.skip("NVENC hardware encoder unavailable")

    class SmallNvencScene(CinemaScene):
        ambient_background = False

        def construct(self):
            card = GlassPanel(width=2.5, height=1.5)
            self.play(FadeIn(card), run_time=0.25)

    with tempconfig(
        {
            "pixel_width": 320,
            "pixel_height": 180,
            "frame_rate": 24,
            "format": "mp4",
            "media_dir": str(tmp_path / "media"),
            "progress_bar": "none",
            "disable_caching": True,
        }
    ):
        scene = SmallNvencScene()
        assert scene.session_spec.video_encoder is not None
        assert scene.session_spec.video_encoder.codec == "h264_nvenc"
        scene.render()
        out_path = scene.manager.file_writer.final_file_path
        assert out_path is not None
        assert out_path.exists()


def test_monochrome_palette_and_zero_color_cast(tmp_path):
    bg = np.asarray(make_ambient_background_image(width=128, height=72))
    assert np.array_equal(bg[..., 0], bg[..., 1])
    assert np.array_equal(bg[..., 1], bg[..., 2])
    assert int(np.max(bg[..., 0])) > int(np.min(bg[..., 0]))

    gray_frame = np.zeros((120, 160, 4), dtype=np.uint8)
    gray_frame[..., 3] = 255
    gray_frame[30:90, 40:120, :3] = 210

    fx_cpu = CinemaPostFX(use_cuda=False)
    assert fx_cpu.halation == 0.0
    out_cpu = fx_cpu.apply(gray_frame, frame_index=1)
    assert np.array_equal(out_cpu[..., 0], out_cpu[..., 1])
    assert np.array_equal(out_cpu[..., 1], out_cpu[..., 2])

    if cuda_available():
        out_gpu = CinemaPostFX(use_cuda=True).apply(gray_frame, frame_index=1)
        assert np.array_equal(out_gpu[..., 0], out_gpu[..., 1])
        assert np.array_equal(out_gpu[..., 1], out_gpu[..., 2])

    class MonoGlassScene(Scene):
        def construct(self):
            self.camera.background_color = BLACK
            self.add(GlassPanel(width=4.0, height=2.5))

    with tempconfig(
        {
            "pixel_width": 160,
            "pixel_height": 90,
            "frame_rate": 10,
            "media_dir": str(tmp_path / "media"),
            "progress_bar": "none",
        }
    ):
        scene = MonoGlassScene()
        scene.setup()
        scene.construct()
        img = np.asarray(scene.get_image())
        assert np.array_equal(img[..., 0], img[..., 1])
        assert np.array_equal(img[..., 1], img[..., 2])


def test_harmonize_color_and_accent_gradient_with_glass(tmp_path):
    soft_green = harmonize_color("#00FF00").to_rgb()
    assert float(np.max(soft_green) - np.min(soft_green)) < 0.55
    assert soft_green[1] > soft_green[0]
    assert soft_green[1] > soft_green[2]

    gray = harmonize_color("#808080").to_rgb()
    assert gray[0] == pytest.approx(gray[1], abs=1e-6)
    assert gray[1] == pytest.approx(gray[2], abs=1e-6)

    line = Line([-1.0, 0.0, 0.0], [1.0, 0.0, 0.0], stroke_width=2.0)
    apply_accent_gradient(line, CINEMA_ICE, anchor="both")
    assert len(line.get_stroke_colors()) >= 3

    group = VGroup(Square(), Circle())
    apply_accent_gradient(group, "#38BDF8", anchor="light")
    assert group[0].get_color() != group[1].get_color()

    class ColoredBehindGlassScene(Scene):
        def construct(self):
            self.camera.background_color = BLACK
            strip = Rectangle(
                width=2.2,
                height=3.0,
                fill_color=CINEMA_ICE,
                fill_opacity=1.0,
                stroke_width=0,
            ).shift([-0.8, 0.0, 0.0])
            glass = GlassPanel(width=4.0, height=2.5, tint_opacity=0.45)
            self.add(strip, glass)

    with tempconfig(
        {
            "pixel_width": 160,
            "pixel_height": 90,
            "frame_rate": 10,
            "media_dir": str(tmp_path / "media"),
            "progress_bar": "none",
        }
    ):
        scene = ColoredBehindGlassScene()
        scene.setup()
        scene.construct()
        img = np.asarray(scene.get_image())
        # Neutral dark glass lets restrained theme accents shine cleanly through blurred backdrop
        left_patch = img[45, 55:65, :3].astype(np.float32)
        assert float(np.mean(left_patch[:, 2] - left_patch[:, 0])) > 10.0


def test_spring_physics_and_presets():
    assert 0.15 <= spring_duration(SmoothSpring) <= 3.0
    assert spring_duration(PlopSpring) >= spring_duration(SmoothSpring)

    for fn in (cinema_spring_smooth, spring_rate(SmoothSpring, duration=0.6)):
        assert fn(0.0) == pytest.approx(0.0, abs=1e-6)
        assert fn(1.0) == pytest.approx(1.0, abs=1e-6)
        ys = [fn(float(x)) for x in np.linspace(0.0, 1.0, 25)]
        assert all(ys[i] <= ys[i + 1] + 1e-6 for i in range(len(ys) - 1))

    # PlopSpring deliberately overshoots > 1.0 then settles at 1.0
    plop_samples = [cinema_spring_plop(float(x)) for x in np.linspace(0.0, 1.0, 41)]
    assert plop_samples[0] == pytest.approx(0.0, abs=1e-6)
    assert max(plop_samples) > 1.01
    assert plop_samples[-1] == pytest.approx(1.0, abs=1e-6)

    custom = spring_rate(SpringSpec(mass=1.0, stiffness=200.0, damping=20.0))
    assert custom(-0.2) == 0.0
    assert custom(1.2) == 1.0


def test_signals_reactive_text_and_spring_follower(tmp_path):
    class SignalScene(CinemaScene):
        ambient_background = False

        def construct(self):
            sig = self.signal(0.0)
            doubled = sig * 2.0 + 10.0
            assert doubled.get() == pytest.approx(10.0)

            txt = ReactiveText(lambda: f"{sig():.0f}%")
            leader = Dot()
            follower = Dot()
            attach_spring_follower(follower, leader, offset=[0.5, 0.0, 0.0], stiffness=220.0, damping=22.0)
            self.add(txt, leader, follower)

            self.play(
                sig.tween(50.0, spring=SmoothSpring, run_time=0.4),
                leader.animate.shift(RIGHT * 2.0),
                run_time=0.4,
            )
            assert sig.get() == pytest.approx(50.0, abs=1e-3)
            assert doubled.get() == pytest.approx(110.0, abs=1e-2)
            assert txt._last_val == "50%"
            assert follower.get_x() > 0.3

    with tempconfig(
        {
            "pixel_width": 160,
            "pixel_height": 90,
            "frame_rate": 12,
            "media_dir": str(tmp_path / "media"),
            "progress_bar": "none",
            "disable_caching": True,
        }
    ):
        Manager(SignalScene()).evaluate()


def test_glass_stack_callout_and_explode_stack(tmp_path):
    class TeardownComponentsScene(CinemaScene):
        ambient_background = False

        def construct(self):
            stack = GlassStack(Text("Row A", font_size=20), padding=(0.4, 0.3))
            old_h = stack.panel.height
            self.add(stack)
            self.play(stack.animate_push(Text("Row B", font_size=20), run_time=0.25))
            assert stack.panel.height > old_h

            layers = [GlassPanel(width=2.4, height=0.7) for _ in range(3)]
            orig_fill_alpha = float(layers[0].get_fill_opacity())
            exploded = ExplodeStack(*layers, axis=UP, collapsed_gap=0.1)
            callout = GlassCallout(layers[2], "TOP LAYER", "Optical Glass", accent=CINEMA_ICE)
            self.add(exploded, callout)
            y_before = layers[2].get_y()
            self.play(exploded.explode(spread=0.6, run_time=0.25))
            assert layers[2].get_y() > y_before + 0.3
            assert callout.pin.get_y() == pytest.approx(layers[2].get_y(), abs=0.05)

            self.play(exploded.focus_layer(2, dim_opacity=0.25, run_time=0.2))
            assert float(layers[0].fill_rgbas[0, 3]) < orig_fill_alpha * 0.5
            self.play(exploded.restore_layers(run_time=0.2))
            assert float(layers[0].fill_rgbas[0, 3]) == pytest.approx(orig_fill_alpha, abs=1e-3)
            self.play(exploded.collapse(run_time=0.2))

    with tempconfig(
        {
            "pixel_width": 160,
            "pixel_height": 90,
            "frame_rate": 10,
            "media_dir": str(tmp_path / "media"),
            "progress_bar": "none",
            "disable_caching": True,
        }
    ):
        Manager(TeardownComponentsScene()).evaluate()


def test_glass_code_spotlight_and_diff(tmp_path):
    class CodeDiffScene(CinemaScene):
        ambient_background = False

        def construct(self):
            code = GlassCode("x = 1\ny = x + 2\nprint(y)", title="sample.py", font_size=18)
            self.add(code)
            self.play(code.focus_lines(2, dim_opacity=0.2, run_time=0.2))
            assert float(code.code_lines[0][0].fill_rgbas[0, 3]) < 0.35
            assert float(code.code_lines[1][0].fill_rgbas[0, 3]) > 0.85

            self.play(code.focus_token(2, "x + 2", dim_opacity=0.2, run_time=0.2))
            self.play(code.reset_focus(run_time=0.15))

            updated = code.animate_diff(
                self,
                "x = 1\nz = x * 3\ny = z + 2\nprint(y)",
                run_time=0.25,
                sound=False,
            )
            assert updated in self.mobjects
            assert code not in self.mobjects
            assert len(updated.raw_lines) == 4

    with tempconfig(
        {
            "pixel_width": 320,
            "pixel_height": 180,
            "frame_rate": 10,
            "media_dir": str(tmp_path / "media"),
            "progress_bar": "none",
            "disable_caching": True,
        }
    ):
        Manager(CodeDiffScene()).evaluate()


def test_postfx_defocus_aspect_narration_and_qa_contact_sheet(tmp_path):
    frame = np.zeros((120, 160, 4), dtype=np.uint8)
    frame[..., 3] = 255
    frame[50:70, 70:90, :3] = 240
    sharp_out = CinemaPostFX(defocus=0.0, dither=False, grain=0.0, use_cuda=False).apply(frame)
    blur_out = CinemaPostFX(
        defocus=14.0, exposure=0.6, dither=False, grain=0.0, use_cuda=False
    ).apply(frame)
    # Defocus spreads center energy outward while lower exposure darkens peak white
    assert int(blur_out[47, 80, 0]) > int(sharp_out[47, 80, 0]) + 10
    assert int(blur_out[60, 80, 0]) < int(sharp_out[60, 80, 0]) - 20

    nar = NarrationScript.load(
        {
            "beats": {"intro_end": 0.4},
            "words": [
                {"word": "Hello", "start": 0.05, "end": 0.2},
                {"word": "glass", "start": 0.55, "end": 0.8},
            ],
        }
    )
    assert nar.time_of("intro_end") == pytest.approx(0.4)
    assert nar.time_of("glass") == pytest.approx(0.55)

    class PortraitQAScene(CinemaScene):
        aspect = "9:16"
        ambient_background = False

        def construct(self):
            assert self.camera.frame_height > self.camera.frame_width
            self.load_beats({"beats": {"beat1": 0.3}})
            guide = self.safe_rect()
            card = GlassPanel(width=4.0, height=2.0).shift(DOWN * 1.2)
            dot = Dot(color=CINEMA_CHAMPAGNE).shift(UP * 2.5)
            self.add(card, dot)
            assert self.check_layout(safe_rect=guide) == []
            self.play(FadeIn(card), run_time=0.15)
            self.wait_until("beat1", default_wait=0.1)
            assert self.time >= 0.3 - 1e-3

    with tempconfig(
        {
            "pixel_width": 180,
            "pixel_height": 320,
            "frame_rate": 10,
            "format": "mp4",
            "media_dir": str(tmp_path / "media"),
            "progress_bar": "none",
            "disable_caching": True,
        }
    ):
        scene = PortraitQAScene()
        scene.render()
        out_mp4 = scene.manager.file_writer.final_file_path
        assert out_mp4 is not None
        assert out_mp4.exists()

    sheet = render_contact_sheet(
        out_mp4,
        output_path=tmp_path / "qa_sheet.png",
        cols=2,
        rows=2,
        thumb_width=120,
    )
    assert sheet.exists()
    assert sheet.stat().st_size > 1000


def test_cinema_skill_bundle_and_cli_installer(tmp_path):
    from manim.__main__ import main

    repo_root = Path(__file__).resolve().parents[2]
    repo_skill = repo_root / ".agents" / "skills" / "cinema-director" / "SKILL.md"
    bundled_skill = (
        repo_root / "manim" / "cinema" / "_skill_assets" / "SKILL.md"
    )
    assert repo_skill.read_text(encoding="utf-8") == bundled_skill.read_text(
        encoding="utf-8"
    )

    proj_dir = tmp_path / "video_proj"
    proj_dir.mkdir()
    agents_file = proj_dir / "AGENTS.md"
    agents_file.write_text("# My Custom Project Notes\n\nKeep audio loud.\n", encoding="utf-8")

    written = install_cinema_skill(proj_dir, claude=True)
    assert (proj_dir / ".agents" / "skills" / "cinema-director" / "SKILL.md") in written
    assert (
        proj_dir
        / ".agents"
        / "skills"
        / "cinema-director"
        / "references"
        / "api-cheatsheet.md"
    ).exists()
    assert (
        proj_dir
        / ".agents"
        / "skills"
        / "cinema-director"
        / "examples"
        / "kinematics_cinema_example.py"
    ).exists()
    assert (proj_dir / ".claude" / "skills" / "cinema-director" / "SKILL.md").exists()

    # Re-running preserves user prose and does not duplicate the marker block
    install_cinema_skill(proj_dir, claude=True)
    agents_text = agents_file.read_text(encoding="utf-8")
    assert "# My Custom Project Notes" in agents_text
    assert agents_text.count("<!-- manim-cinema:start -->") == 1

    cli_dir = tmp_path / "cli_proj"
    cli_dir.mkdir()
    result = CliRunner().invoke(main, ["cinema-skill", str(cli_dir)])
    assert result.exit_code == 0, result.output
    assert (cli_dir / ".agents" / "skills" / "cinema-director" / "SKILL.md").exists()
    assert (cli_dir / "AGENTS.md").exists()

