"""Flagship showcase combining Motion Canvas springs/signals/code-diff with Motion Educator teardown/FX/QA.

Render with:
    manim render -r 1920,1080 --fps 24 --format mp4 example_scenes/cinema_teardown_showcase.py CinemaTeardownShowcase
"""

from __future__ import annotations

from manim import *


class CinemaTeardownShowcase(CinemaScene):
    """Product teardown + GPU optical blur transition + reactive GlassStack + GlassCode diff."""

    def construct(self) -> None:
        # 1. Architectural monochrome backdrop lines
        hairline_top = Line([-7.0, 2.2, 0.0], [7.0, 1.3, 0.0]).set_z_index(-20)
        hairline_top.set_sheen_direction(RIGHT)
        hairline_top.set_stroke(color=["#080808", "#FFFFFF", "#121212"], width=1.8, opacity=0.28)
        hairline_bot = Line([-7.0, -2.1, 0.0], [7.0, -1.1, 0.0]).set_z_index(-20)
        hairline_bot.set_sheen_direction(RIGHT)
        hairline_bot.set_stroke(color=["#121212", "#D4D4D4", "#080808"], width=1.8, opacity=0.22)
        self.add(hairline_top, hairline_bot)

        # 2. Top glass header
        header = self.glass_badge(width=5.4, height=0.58, sheen_opacity=0.04).to_edge(UP, buff=0.45)
        header_txt = Text("CINEMA TEARDOWN & MOTION KIT", font_size=19, weight=SEMIBOLD).move_to(header)
        apply_mono_gradient(header_txt, colors=["#9E9E9E", "#FFFFFF", "#B8B8B8"])
        header.set_z_index(15)
        header_txt.set_z_index(16)

        self.add_sound(SFX_SUB_IMPACT, gain=-3.0)
        self.play(
            FadeIn(header, shift=DOWN * 0.2, rate_func=cinema_spring_smooth).with_sound(
                SFX_WHOOSH, at_alpha=0.05, gain=-4.0
            ),
            FadeIn(header_txt, shift=DOWN * 0.15, rate_func=cinema_spring_smooth),
            run_time=0.75,
        )

        # 3. Phase 1: Exploded Stack + Pinned Callouts + Camera Focus (Motion Educator)
        def _make_layer(title: str, sub: str, accent: ParsableManimColor) -> VGroup:
            panel = self.glass_panel(width=4.2, height=0.92, corner_radius=0.20, sheen_opacity=0.04)
            t = Text(title, font_size=19, weight=BOLD)
            t.set_color_by_gradient("#A3A3A3", "#FFFFFF")
            s = Text(sub, font_size=15, color=CINEMA_SILVER)
            rule = Line([-0.65, 0.0, 0.0], [0.65, 0.0, 0.0], stroke_width=1.4)
            apply_accent_gradient(rule, accent, anchor="light")
            content = VGroup(t, s, rule).arrange(DOWN, buff=0.07).move_to(panel)
            panel.set_z_index(10)
            content.set_z_index(11)
            return VGroup(panel, content)

        layer_audio = _make_layer("SPATIAL AUDIO MIX", "48 kHz Stereo + Ducking", CINEMA_CHAMPAGNE)
        layer_glass = _make_layer("CLEAN DARK GLASS", "Zero Shadow · CUDA Blur", CINEMA_SILVER)
        layer_fx = _make_layer("OPTICAL POST-FX", "Bloom + Anti-Banding LUT", CINEMA_ICE)

        stack = self.explode_stack(layer_audio, layer_glass, layer_fx, axis=UP, collapsed_gap=0.14)
        stack.move_to([0.0, -0.35, 0.0])

        self.play(
            FadeIn(stack, scale=0.94, rate_func=cinema_spring_smooth),
            run_time=0.7,
        )
        self.add_sound(SFX_WHOOSH, gain=-3.0)
        self.play(stack.explode(spread=0.62, run_time=0.85))
        self.add_sound(SFX_GLASS_CHIME, gain=-4.0, mobject=layer_fx)

        callout_top = self.callout(
            layer_fx,
            "CUDA PASS",
            "GPU Post-FX + Defocus",
            offset=(3.65, 0.35, 0.0),
            target_anchor=RIGHT,
            accent=CINEMA_ICE,
        ).set_z_index(14)
        callout_bot = self.callout(
            layer_audio,
            "SYNC CLOCK",
            "Word & Beat Markers",
            offset=(-3.65, -0.25, 0.0),
            target_anchor=LEFT,
            accent=CINEMA_CHAMPAGNE,
        ).set_z_index(14)

        self.play(
            FadeIn(callout_top, shift=LEFT * 0.2, rate_func=cinema_spring_snappy),
            FadeIn(callout_bot, shift=RIGHT * 0.2, rate_func=cinema_spring_snappy),
            run_time=0.55,
        )

        # Focus spotlight + camera zoom onto optical Post-FX layer
        self.play(
            stack.focus_layer(2, dim_opacity=0.22),
            self.camera_focus(
                VGroup(layer_fx, callout_top),
                margin=1.6,
                dim_mobjects=[header, header_txt],
                dim_opacity=0.18,
                sound=SFX_GLASS_TAP,
            ),
            run_time=0.8,
        )
        self.wait(0.35, frozen_frame=False)
        self.play(
            self.camera_reset(restore_mobjects=[header, header_txt]),
            stack.restore_layers(),
            FadeOut(callout_top),
            FadeOut(callout_bot),
            run_time=0.7,
        )
        self.play(stack.collapse(run_time=0.65))

        # 4. Optical GPU Blur Transition -> Phase 2: Reactive Signals + GlassCode Diff (Motion Canvas)
        pct_sig = self.signal(0.0)
        card_title = Text("LIVE SIGNALS", font_size=21, weight=BOLD)
        card_title.set_color_by_gradient("#A3A3A3", "#FFFFFF")
        meter_readout = ReactiveText(
            lambda: f"{pct_sig():.0f}%",
            font_size=38,
            weight=BOLD,
            gradient=["#B8B8B8", "#FFFFFF"],
        )
        bar_track = RoundedRectangle(
            corner_radius=0.07,
            width=3.0,
            height=0.14,
            fill_color="#161616",
            fill_opacity=0.92,
            stroke_color="#333333",
            stroke_width=0.8,
        )
        bar_fill = RoundedRectangle(corner_radius=0.07, width=0.06, height=0.14, stroke_width=0)
        bar_fill.set_sheen_direction(RIGHT)
        bar_fill.set_fill(color=["#242424", "#A1A1A1", "#FFFFFF"], opacity=1.0)
        bar_fill.align_to(bar_track, LEFT).set_y(bar_track.get_y())
        bar_group = VGroup(bar_track, bar_fill)

        left_card = self.glass_stack(
            card_title,
            meter_readout,
            bar_group,
            gap=0.26,
            padding=(0.45, 0.40),
        ).move_to([-4.05, -0.25, 0.0])
        left_card.set_z_index(10)

        code_v1 = "\n".join(
            [
                "pct = scene.signal(0)",
                "scene.play(",
                "    pct.tween(100),",
                "    run_time=1.0,",
                ")",
            ]
        )
        code_card = self.glass_code(
            code_v1,
            title="signals_demo.py",
            font_size=17,
            padding=(0.42, 0.36),
        ).move_to([2.15, -0.25, 0.0])
        code_card.set_z_index(10)

        def _swap_to_phase2() -> None:
            self.remove(stack, *stack.get_family())
            self.add(left_card, code_card)
            bind_progress_bar(bar_fill, bar_track, pct_sig, min_value=0.0, max_value=100.0)
            bar_fill.set_z_index(12)

        self.blur_transition(_swap_to_phase2, max_defocus=16.0, dip_exposure=0.70, run_time=0.7)

        tick_handle = self.bind_value_tick(
            pct_sig.tracker,
            SFX_SOFT_TICK,
            step=15.0,
            cooldown=0.05,
            gain=-6.0,
            mobject=left_card,
        )
        self.play(pct_sig.tween(100.0, spring=SmoothSpring, run_time=1.1))
        self.remove_updater(tick_handle)

        # Dynamic flexbox push in GlassStack + live code diff in GlassCode
        status_chip = VGroup(
            Dot(radius=0.05, color=CINEMA_EMERALD),
            Text("NVENC · RTX 3060 ACTIVE", font_size=14, color=CINEMA_PLATINUM),
        ).arrange(RIGHT, buff=0.12)
        self.play(
            left_card.animate_push(status_chip, run_time=0.55),
            code_card.focus_lines(2, 3, run_time=0.45),
        )
        self.add_sound(SFX_UI_POP, gain=-3.0, mobject=left_card)

        code_v2 = "\n".join(
            [
                "pct = scene.signal(0)",
                "scene.play(",
                "    pct.tween(100, spring=SmoothSpring),",
                "    rate_func=cinema_spring_plop,",
                ")",
            ]
        )
        code_card_v2 = code_card.animate_diff(self, code_v2, run_time=0.8)
        self.wait(0.65, frozen_frame=False)

        self.play(
            FadeOut(left_card, rate_func=cinema_spring_smooth),
            FadeOut(code_card_v2, rate_func=cinema_spring_smooth),
            FadeOut(header_txt, rate_func=cinema_spring_smooth),
            FadeOut(header, rate_func=cinema_spring_smooth),
            run_time=0.65,
        )
