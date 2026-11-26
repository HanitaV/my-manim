"""Visual-Essay STEM physics pattern in Monochrome Dark Luxury + Mineral Accents.

Render with:
    manim render -r 1920,1080 --fps 60 --format mp4 kinematics_cinema_example.py KinematicsCinemaExample
"""

from __future__ import annotations

from manim import *


class KinematicsCinemaExample(CinemaScene):
    """Demonstrates Visual Essay physics storytelling (Phenomenon -> Geometry -> Formula-last)."""

    aspect = "16:9"

    def construct(self) -> None:
        # 1. Breathing chapter card with warm felt-piano chime
        self.chapter_card("PHẦN 1", "Quán tính & Vận tốc tức thời", hold_time=0.95)

        # 2. Phenomenon first: minimalist ground stage + sleek geometric puck + StrobeTrail
        ground = self.stage_ground(y_level=-2.35, surface_type="ice")
        puck = RoundedRectangle(
            width=1.05,
            height=0.46,
            corner_radius=0.12,
            fill_color=CINEMA_SLATE,
            fill_opacity=0.95,
            stroke_color=CINEMA_IVORY,
            stroke_width=2.0,
        ).move_to([-4.2, ground.surface_y + 0.23, 0.0])

        x_sig = self.signal(-4.2)
        puck.add_updater(lambda m: m.set_x(x_sig()))
        v_vec = always_redraw(
            lambda: self.physics_vector(
                puck.get_right() + RIGHT * 0.08,
                RIGHT * 1.45,
                "v = const",
                role="velocity",
            )
        )
        trail = self.strobe_trail(puck, interval=0.45, show_time_labels=True)

        stage_group = VGroup(ground, puck, v_vec, trail)
        self.play(FadeIn(ground), FadeIn(puck), run_time=0.45)
        self.add(trail, v_vec)

        self.play(x_sig.tween(3.2, spring=SmoothSpring, run_time=1.8))
        puck.clear_updaters()
        trail.clear_updaters()

        # Formula-last reveal via crisp block-cursor typewriter + transient sketch loop
        law_eq = Text("F = 0   ⇒   v = hằng số", font_size=34, weight=BOLD).move_to(
            [0.0, 1.85, 0.0]
        )
        apply_mono_gradient(law_eq, colors=[CINEMA_SILVER, CINEMA_IVORY])
        self.typewriter(law_eq, run_time=0.75)
        self.sketch_highlight(law_eq, color=CINEMA_AMBER, hold_time=0.35)

        # 3. Diagonal shutter wipe into x(t) tangent geometry + clean GlassStack readout
        t_sig = self.signal(1.2)
        axes = Axes(
            x_range=[0, 5, 1],
            y_range=[0, 4, 1],
            x_length=4.6,
            y_length=2.9,
            tips=True,
            axis_config={"color": CINEMA_MUTED, "stroke_width": 1.4},
        )
        curve = axes.plot(
            lambda x: 0.45 + 0.12 * x * x + 0.2 * x,
            x_range=[0.2, 4.6],
            stroke_width=2.6,
        )
        apply_accent_gradient(curve, CINEMA_ICE, anchor="light")

        left_panel = self.glass_panel(width=6.0, height=4.4).move_to([-3.3, -0.2, 0.0])
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
            lambda: Dot(axes.c2p(t_sig(), _val(t_sig())), radius=0.07, color=WHITE).set_z_index(
                13
            )
        )

        eq_title = Text("ĐỘ DỐC TIẾP TUYẾN", font_size=17, weight=BOLD, color=CINEMA_SILVER)
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
            gap=0.26,
            padding=(0.52, 0.48),
        ).move_to([3.55, -0.2, 0.0])

        def _swap_to_geometry() -> None:
            for mob in (stage_group, law_eq):
                self.remove(mob, *mob.get_family())
            self.add(left_panel, axes_grp, tangent, tangent_dot, right_card)

        self.diagonal_wipe(_swap_to_geometry, run_time=0.65)
        self.play(t_sig.tween(3.8, spring=SmoothSpring, run_time=1.4))
        self.spotlight(tangent_dot, radius=1.05, hold_time=0.45)

        assert not self.check_layout(safe_rect=self.safe_rect())
        self.wait(0.4, frozen_frame=False)
