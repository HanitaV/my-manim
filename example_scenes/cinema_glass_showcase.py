"""Showcase scene for Monochrome Black-to-White Cinema Theme with Harmonized Accents.

Render with:
    manim render -r 1920,1080 --fps 24 --format mp4 example_scenes/cinema_glass_showcase.py CinemaGlassShowcase
"""

from __future__ import annotations

import math

from manim import *


class CinemaGlassShowcase(CinemaScene):
    """Demonstrates monochrome black-to-white luxury theme, subtle mineral accents, clean glass, and spatial audio."""

    def construct(self) -> None:
        # 1. Monochrome architectural hairlines & subtle cool-to-warm mineral ring behind dark glass
        glow_line_top = Line([-7.2, 1.55, 0.0], [7.2, 0.25, 0.0]).set_z_index(-20)
        glow_line_top.set_sheen_direction(RIGHT)
        glow_line_top.set_stroke(
            color=["#0A0A0A", "#FFFFFF", "#141414"],
            width=2.2,
            opacity=0.34,
        )

        glow_line_bot = Line([-7.2, -1.75, 0.0], [7.2, -0.45, 0.0]).set_z_index(-20)
        glow_line_bot.set_sheen_direction(RIGHT)
        glow_line_bot.set_stroke(
            color=["#141414", "#D4D4D4", "#0A0A0A"],
            width=2.2,
            opacity=0.28,
        )

        soft_sweep = Circle(radius=1.8).move_to([-3.6, 0.4, 0.0]).set_z_index(-18)
        soft_sweep.set_sheen_direction(UL)
        soft_sweep.set_fill(color=[CINEMA_ICE, "#141414", CINEMA_CHAMPAGNE], opacity=0.09)
        soft_sweep.set_stroke(
            color=[CINEMA_ICE, "#141414", CINEMA_CHAMPAGNE],
            width=1.3,
            opacity=0.24,
        )

        self.add(glow_line_top, glow_line_bot, soft_sweep)
        soft_sweep.add_updater(
            lambda m, dt: m.move_to(
                [
                    3.8 * math.sin(self.time * 0.55),
                    0.35 * math.cos(self.time * 0.45),
                    0.0,
                ]
            )
        )

        # 2. Top neutral dark-glass badge + metallic silver-to-white title
        badge = self.glass_badge(width=5.6, height=0.62, sheen_opacity=0.04).to_edge(
            UP, buff=0.55
        )
        badge_text = Text(
            "CINEMA GLASS & SPATIAL AUDIO",
            font_size=20,
            weight=SEMIBOLD,
        ).move_to(badge)
        apply_mono_gradient(badge_text, colors=["#A3A3A3", "#FFFFFF", "#B8B8B8"])
        badge.set_z_index(10)
        badge_text.set_z_index(11)

        self.add_sound(SFX_SUB_IMPACT, gain=-2.0)
        self.play(
            FadeIn(badge, shift=DOWN * 0.25, rate_func=cinema_smooth_out).with_sound(
                SFX_WHOOSH, at_alpha=0.05, gain=-4.0
            ),
            FadeIn(badge_text, shift=DOWN * 0.2, rate_func=cinema_smooth_out),
            run_time=1.0,
        )

        # 3. Three neutral smoked-glass cards with subtle element-matched accents
        card_left = self.glass_panel(
            width=3.6,
            height=3.4,
            corner_radius=0.28,
            sheen_opacity=0.04,
        ).shift(LEFT * 4.1 + DOWN * 0.35)

        card_center = self.glass_panel(
            width=3.8,
            height=3.6,
            corner_radius=0.30,
            sheen_opacity=0.04,
        ).shift(DOWN * 0.35)

        card_right = self.glass_panel(
            width=3.6,
            height=3.4,
            corner_radius=0.28,
            sheen_opacity=0.04,
        ).shift(RIGHT * 4.1 + DOWN * 0.35)

        cards = [card_left, card_center, card_right]
        for card in cards:
            card.set_z_index(10)

        title_left = Text("OBSIDIAN GLASS", font_size=22, weight=BOLD)
        title_left.set_color_by_gradient("#8A8A8A", "#FFFFFF")
        rule_left = Line([-0.75, 0.0, 0.0], [0.75, 0.0, 0.0], stroke_width=1.6)
        apply_accent_gradient(rule_left, CINEMA_ICE, anchor="both", direction=RIGHT)

        live_dot = VGroup(
            Circle(
                radius=0.13,
                fill_color=CINEMA_EMERALD,
                fill_opacity=0.22,
                stroke_width=0,
            ),
            Dot(radius=0.055, color=CINEMA_EMERALD),
        )
        title_center_text = Text("LIVE TELEMETRY", font_size=22, weight=BOLD)
        title_center_text.set_color_by_gradient("#A3A3A3", "#FFFFFF")
        title_center = VGroup(live_dot, title_center_text).arrange(RIGHT, buff=0.14)

        title_right = Text("SPATIAL AUDIO", font_size=22, weight=BOLD)
        title_right.set_color_by_gradient("#FFFFFF", "#8A8A8A")
        rule_right = Line([-0.75, 0.0, 0.0], [0.75, 0.0, 0.0], stroke_width=1.6)
        apply_accent_gradient(rule_right, CINEMA_CHAMPAGNE, anchor="both", direction=LEFT)

        card_labels = [
            VGroup(
                title_left,
                Text("Optical Blur & Rim", font_size=18, color=CINEMA_SILVER),
                rule_left,
            )
            .arrange(DOWN, buff=0.18)
            .move_to(card_left)
            .set_z_index(12),
            VGroup(
                title_center,
                Text("Frame-Synced Ticks", font_size=18, color=CINEMA_SILVER),
            )
            .arrange(DOWN, buff=0.18)
            .move_to(card_center.get_top() + DOWN * 0.85)
            .set_z_index(12),
            VGroup(
                title_right,
                Text("Stereo Pan & Pitch", font_size=18, color=CINEMA_SILVER),
                rule_right,
            )
            .arrange(DOWN, buff=0.18)
            .move_to(card_right)
            .set_z_index(12),
        ]

        self.play(
            LaggedStart(
                *(
                    AnimationGroup(
                        FadeIn(card, shift=UP * 0.35, rate_func=cinema_smooth_out),
                        FadeIn(lbl, shift=UP * 0.25, rate_func=cinema_smooth_out),
                    )
                    for card, lbl in zip(cards, card_labels, strict=True)
                ),
                lag_ratio=0.22,
            ).with_staggered_sound(
                SFX_GLASS_CHIME,
                at_alpha=0.05,
                gain=-3.0,
                pitch_start=-2.0,
                pitch_step=3.0,
            ),
            run_time=1.8,
        )

        # 4. Interactive ValueTracker meter inside center card with black-to-white gradient bar
        progress = ValueTracker(0.0)
        self.add(progress)
        meter_num = (
            Text("0%", font_size=44, weight=BOLD, color=CINEMA_IVORY)
            .set_color_by_gradient("#B8B8B8", "#FFFFFF")
            .move_to(card_center.get_center() + DOWN * 0.05)
            .set_z_index(12)
        )
        last_pct = [-1]

        def _update_meter(mob: Text) -> None:
            pct = round(progress.get_value())
            if pct != last_pct[0]:
                last_pct[0] = pct
                new_txt = (
                    Text(f"{pct}%", font_size=44, weight=BOLD, color=CINEMA_IVORY)
                    .set_color_by_gradient("#B8B8B8", "#FFFFFF")
                    .move_to(card_center.get_center() + DOWN * 0.05)
                    .set_z_index(12)
                )
                mob.become(new_txt)

        meter_num.add_updater(_update_meter)

        bar_bg = (
            RoundedRectangle(
                corner_radius=0.08,
                width=2.8,
                height=0.16,
                fill_color="#161616",
                fill_opacity=0.92,
                stroke_color="#333333",
                stroke_width=0.8,
                stroke_opacity=0.7,
            )
            .move_to(card_center.get_bottom() + UP * 0.72)
            .set_z_index(12)
        )
        bar_fill = RoundedRectangle(
            corner_radius=0.08,
            width=0.05,
            height=0.16,
            stroke_width=0,
        ).set_z_index(13)
        bar_fill.set_sheen_direction(RIGHT)
        bar_fill.set_fill(color=["#202020", "#9E9E9E", "#FFFFFF"], opacity=1.0)

        def _update_bar(mob: RoundedRectangle) -> None:
            frac = max(0.02, min(1.0, progress.get_value() / 100.0))
            mob.stretch_to_fit_width(2.8 * frac)
            mob.align_to(bar_bg, LEFT)
            mob.set_y(bar_bg.get_y())

        bar_fill.add_updater(_update_bar)
        self.play(FadeIn(meter_num), FadeIn(bar_bg), FadeIn(bar_fill), run_time=0.4)

        tick_handle = self.bind_value_tick(
            progress,
            SFX_SOFT_TICK,
            step=10.0,
            cooldown=0.04,
            gain=-7.0,
            pitch_base=-3.0,
            pitch_per_unit=0.06,
            mobject=card_center,
        )
        self.play(progress.animate(rate_func=cinema_ease).set_value(100.0), run_time=1.8)
        self.remove_updater(tick_handle)
        self.add_sound(SFX_UI_POP, gain=-2.0, mobject=card_center)

        # 5. Sweeping champagne-white audio probe triggering proximity glass taps across stereo field
        probe_halo = Circle(radius=0.34, stroke_width=0)
        probe_halo.set_sheen_direction(UP)
        probe_halo.set_fill(color=[CINEMA_CHAMPAGNE, "#141414"], opacity=0.26)
        probe = (
            Group(
                probe_halo,
                Dot(radius=0.10, color=WHITE),
            )
            .move_to([-6.4, -2.55, 0])
            .set_z_index(20)
        )
        self.play(FadeIn(probe, scale=0.6), run_time=0.35)

        prox_targets = [
            card_left.copy().set_opacity(0).move_to([card_left.get_x(), -2.55, 0]),
            card_center.copy().set_opacity(0).move_to([card_center.get_x(), -2.55, 0]),
            card_right.copy().set_opacity(0).move_to([card_right.get_x(), -2.55, 0]),
        ]
        prox_handle = self.on_proximity_sound(
            probe,
            prox_targets,
            SFX_GLASS_TAP,
            radius=0.9,
            cooldown=0.1,
            gain=-1.5,
            pitch_base=-1.0,
            pitch_step=3.5,
        )
        self.play(
            probe.animate(rate_func=cinema_snappy).move_to([6.4, -2.55, 0]),
            run_time=1.8,
        )
        self.remove_updater(prox_handle)

        # 6. Hold cleanly then fade out
        self.wait(0.8, frozen_frame=False)
        self.play(
            FadeOut(probe),
            FadeOut(meter_num),
            FadeOut(bar_bg),
            FadeOut(bar_fill),
            *(FadeOut(lbl) for lbl in card_labels),
            *(FadeOut(card) for card in cards),
            FadeOut(badge_text),
            FadeOut(badge),
            run_time=0.9,
        )
