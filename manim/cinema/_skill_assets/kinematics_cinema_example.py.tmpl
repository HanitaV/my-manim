"""STEM explainer pattern in strict Monochrome Dark Glass + Restrained Mineral Accents.

Render with:
    manim render -r 1920,1080 --fps 24 --format mp4 kinematics_cinema_example.py KinematicsCinemaExample
"""

from __future__ import annotations

from manim import *


class KinematicsCinemaExample(CinemaScene):
    """Demonstrates how to upgrade a physics/STEM slide into Cinema Monochrome Glass."""

    aspect = "16:9"

    def construct(self) -> None:
        # 1. Subtle HUD tag in corner GlassBadge (never float naked colored dots/text)
        ctx_dot = Dot(radius=0.05, color=CINEMA_ICE)
        ctx_label = Text("BỐI CẢNH", font_size=15, weight=SEMIBOLD, color=CINEMA_PLATINUM)
        ctx_row = VGroup(ctx_dot, ctx_label).arrange(RIGHT, buff=0.12)
        ctx_badge = self.glass_badge(width=2.1, height=0.46, sheen_opacity=0.04).to_corner(
            UR, buff=0.45
        )
        ctx_row.move_to(ctx_badge)
        ctx_badge.set_z_index(12)
        ctx_row.set_z_index(13)

        # 2. Title hero in monochrome gradient + restrained champagne accent
        title = Text("Động học chất điểm", font_size=44, weight=BOLD)
        apply_mono_gradient(title, colors=[CINEMA_SILVER, CINEMA_IVORY])
        subtitle = Text("Bài 2.1 – 2.7  ·  Chuyển động & Độ dốc", font_size=22, color=CINEMA_CHAMPAGNE)
        title_group = VGroup(title, subtitle).arrange(DOWN, buff=0.22).set_z_index(10)

        self.play(
            FadeIn(ctx_badge, shift=DOWN * 0.15, rate_func=cinema_spring_smooth),
            FadeIn(ctx_row, shift=DOWN * 0.12, rate_func=cinema_spring_smooth),
            FadeIn(title_group, shift=UP * 0.25, rate_func=cinema_spring_smooth).with_sound(
                SFX_WHOOSH, gain=-3.0
            ),
            run_time=0.85,
        )
        self.wait(0.45, frozen_frame=False)

        # 3. Optical blur transition to interactive x(t) graph + v = dx/dt GlassCard
        t_sig = self.signal(1.2)
        axes = Axes(
            x_range=[0, 5, 1],
            y_range=[0, 4, 1],
            x_length=4.6,
            y_length=2.9,
            tips=True,
            axis_config={"color": CINEMA_MUTED, "stroke_width": 1.4},
        )
        curve = axes.plot(lambda x: 0.45 + 0.12 * x * x + 0.2 * x, x_range=[0.2, 4.6], stroke_width=2.6)
        apply_accent_gradient(curve, CINEMA_ICE, anchor="light")

        left_panel = self.glass_panel(width=6.0, height=4.5, sheen_opacity=0.04).move_to(
            [-3.3, -0.25, 0.0]
        )
        axes_grp = VGroup(axes, curve).move_to(left_panel).set_z_index(11)
        left_panel.set_z_index(10)

        def _slope(t: float) -> float:
            return 0.24 * t + 0.2

        def _val(t: float) -> float:
            return 0.45 + 0.12 * t * t + 0.2 * t

        tangent = always_redraw(
            lambda: Line(
                axes.c2p(t_sig() - 0.85, _val(t_sig()) - 0.85 * _slope(t_sig())),
                axes.c2p(t_sig() + 0.85, _val(t_sig()) + 0.85 * _slope(t_sig())),
                stroke_width=2.4,
                color=CINEMA_CHAMPAGNE,
            ).set_z_index(12)
        )
        tangent_dot = always_redraw(
            lambda: Dot(
                axes.c2p(t_sig(), _val(t_sig())),
                radius=0.07,
                color=WHITE,
            ).set_z_index(13)
        )

        # Clean glass formula card via GlassStack + Reactive readout
        eq_title = Text("VẬN TỐC TỨC THỜI", font_size=18, weight=BOLD, color=CINEMA_SILVER)
        eq_main = Text("v(t) = dx / dt", font_size=34, weight=BOLD)
        apply_mono_gradient(eq_main, colors=[CINEMA_SILVER, CINEMA_IVORY])
        v_readout = ReactiveText(
            lambda: f"t = {t_sig():.1f} s   |   v = {_slope(t_sig()):.2f} m/s",
            font_size=18,
            color=CINEMA_ICE,
        )
        right_card = self.glass_stack(
            eq_title,
            eq_main,
            v_readout,
            gap=0.28,
            padding=(0.55, 0.50),
        ).move_to([3.55, -0.25, 0.0])
        right_card.set_z_index(10)

        slope_pin = self.callout(
            tangent_dot,
            "ĐỘ DỐC TIẾP TUYẾN",
            "Bằng vận tốc v(t)",
            offset=(-2.2, 1.05, 0.0),
            accent=CINEMA_CHAMPAGNE,
        ).set_z_index(14)

        def _swap_to_graph() -> None:
            self.remove(title_group, *title_group.get_family())
            self.add(left_panel, axes_grp, tangent, tangent_dot, right_card, slope_pin)

        self.blur_transition(_swap_to_graph, max_defocus=16.0, run_time=0.7)

        tick_handle = self.bind_value_tick(
            t_sig.tracker,
            SFX_SOFT_TICK,
            step=0.6,
            cooldown=0.06,
            gain=-7.0,
            mobject=tangent_dot,
        )
        self.play(t_sig.tween(3.8, spring=SmoothSpring, run_time=1.8))
        self.remove_updater(tick_handle)
        self.add_sound(SFX_UI_POP, gain=-3.0, mobject=right_card)

        assert not self.check_layout(safe_rect=self.safe_rect())
        self.wait(0.6, frozen_frame=False)
