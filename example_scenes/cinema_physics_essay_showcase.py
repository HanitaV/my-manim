"""Showcase of Visual-Essay Physics Storytelling + Monochrome Dark Luxury Cinema.

Render 1080p60 with CUDA + NVENC:
    manim render -r 1920,1080 --fps 60 --format mp4 example_scenes/cinema_physics_essay_showcase.py CinemaPhysicsEssayShowcase
"""

from __future__ import annotations

from manim import *


class CinemaPhysicsEssayShowcase(CinemaScene):
    """Demonstrates chapter card, geometric bodies, PhysicsVector, StrobeTrail, Streamlines, Typewriter, Sketch & Spotlight."""

    aspect = "16:9"

    def construct(self) -> None:
        # Beat 1: Minimalist breathing chapter card + felt-piano chime
        self.chapter_card("PHẦN 2", "Cơ học Newton & Lực cản", hold_time=0.85)

        # Beat 2: Phenomenon on StageGround — sleek brushed block with StrobeTrail & semantic vectors
        ground = self.stage_ground(y_level=-2.40, surface_type="matte")
        block = RoundedRectangle(
            width=1.15,
            height=0.68,
            corner_radius=0.12,
            fill_color=CINEMA_SLATE,
            fill_opacity=0.95,
            stroke_color=CINEMA_PLATINUM,
            stroke_width=2.0,
        ).move_to([-4.2, ground.surface_y + 0.34, 0.0])

        x_pos = self.signal(-4.2)
        block.add_updater(lambda m: m.set_x(x_pos()))

        v_vec = always_redraw(
            lambda: self.physics_vector(
                block.get_right() + RIGHT * 0.06,
                RIGHT * max(0.25, 1.95 - 0.19 * (x_pos() + 4.2)),
                "v",
                role="velocity",
            )
        )
        f_drag = always_redraw(
            lambda: self.physics_vector(
                block.get_bottom() + UP * 0.06,
                LEFT * 1.10,
                "F_ms",
                role="friction",
            )
        )
        trail = self.strobe_trail(block, interval=0.40, show_time_labels=True)

        self.play(FadeIn(ground), FadeIn(block), run_time=0.40)
        self.add(trail, v_vec, f_drag)

        self.play(x_pos.tween(2.4, spring=SmoothSpring, run_time=1.55))
        block.clear_updaters()
        trail.clear_updaters()
        self.add_sound(SFX_SOFT_THUD, gain=-5.0, mobject=block)

        # Question / Formula-last reveal via block-cursor typewriter + transient hand-sketched loop
        headline = Text("Tại sao vật dừng lại?", font_size=34, weight=BOLD).move_to(
            [0.0, 2.25, 0.0]
        )
        apply_mono_gradient(headline, colors=[CINEMA_SILVER, CINEMA_IVORY])
        self.typewriter(headline, run_time=0.65)
        self.sketch_highlight(f_drag, color=CINEMA_AMBER, pad=0.24, hold_time=0.35)

        act1_mobs = [ground, block, trail, v_vec, f_drag, headline]

        # Beat 3: Diagonal shutter wipe into SplitViewport (Freefall Sphere Airflow vs Newton II Glass Readout)
        split = self.split_viewport(
            "2x1",
            labels=["RƠI TỰ DO & LỰC CẢN KHÍ", "ĐỊNH LUẬT II NEWTON"],
            accent=CINEMA_SILVER,
        )
        left_c = split.pane_center(0)
        right_c = split.pane_center(1)

        sphere = Circle(
            radius=0.42,
            fill_color=CINEMA_SLATE,
            fill_opacity=0.95,
            stroke_color=CINEMA_IVORY,
            stroke_width=2.2,
        ).move_to(left_c + DOWN * 0.10)
        mass_label = Text("m", font_size=20, weight=SEMIBOLD, color=CINEMA_PLATINUM).move_to(
            sphere
        )
        airflow = self.streamlines(
            sphere,
            length=4.0,
            spread=2.3,
            lines_count=6,
            flow_direction=UP,
            color=CINEMA_ICE,
            speed=2.6,
        )
        fg_vec = self.physics_vector(
            sphere.get_bottom() + DOWN * 0.04,
            DOWN * 1.10,
            "P = m·g",
            role="force",
        )
        fd_vec = self.physics_vector(
            sphere.get_top() + UP * 0.04,
            UP * 1.10,
            "F_cản",
            role="drag",
        )
        freefall_diagram = VGroup(sphere, mass_label, fg_vec, fd_vec)

        law_kicker = Text("CÂN BẰNG LỰC TỚI HẠN", font_size=16, weight=SEMIBOLD, color=CINEMA_SILVER)
        law_formula = Text("∑F = m · a = 0", font_size=36, weight=BOLD)
        apply_mono_gradient(law_formula, colors=[CINEMA_SILVER, CINEMA_IVORY])
        term_note = Text("v → v_gh  (vận tốc giới hạn)", font_size=19, color=CINEMA_EMERALD)
        law_card = self.glass_stack(
            law_kicker,
            law_formula,
            term_note,
            gap=0.26,
            padding=(0.52, 0.46),
        ).move_to(right_c + DOWN * 0.1)

        def _swap_to_split() -> None:
            for mob in act1_mobs:
                self.remove(mob, *mob.get_family())
            self.add(split, airflow, freefall_diagram, law_card)

        self.diagonal_wipe(_swap_to_split, run_time=0.65)
        self.wait(0.75, frozen_frame=False)
        airflow.clear_updaters()

        # Radial spotlight focus on ∑F = m · a = 0
        self.spotlight(law_card, radius=2.35, hold_time=0.50)
        assert not self.check_layout(safe_rect=self.safe_rect())
        self.wait(0.35, frozen_frame=False)
