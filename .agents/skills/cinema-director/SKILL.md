---
name: cinema-director
description: >-
  MANDATORY workflow and visual standard for ALL Manim videos, STEM/physics/math/code
  explainers, visual essays, product teardowns, glass UI scenes, and vertical Shorts built
  with my-manim. Activate whenever creating, editing, refactoring, or rendering any Scene.
---

# Cinema Director Standard (`manim.cinema`)

Every video scene in this repository or any project powered by `my-manim` **MUST** subclass `CinemaScene` and follow the `manim.cinema` visual-essay & dark-glass standard. Never write vanilla `Scene` slides with flat backgrounds, PowerPoint bullet lists, stick figures, or multi-color rainbow shapes.

## Hard Enforcement Rules (Forbidden vs Mandatory)

| Area | Forbidden (Do NOT Do) | Mandatory (`manim.cinema`) |
| :--- | :--- | :--- |
| **Scene base** | `class Foo(Scene):` or `MovingCameraScene` | `class Foo(CinemaScene):` (ambient studio backdrop, Unicode font, `CinemaPostFX`, CUDA, NVENC). |
| **Anti-Slide density** | Bullet-point slides, paragraphs of text, or > 2 simultaneous panels on screen. | **Visual Essay rule**: **1 physical/conceptual model + ≤ 5 words per label**, ~70% negative space. Let voiceover carry prose. |
| **Physical actors** | **Stick figures (`người que`), cartoon clip-art, or toyish icons.** | Represent physical bodies strictly with **sleek geometric forms**: monochrome spheres (`Circle`), brushed blocks (`RoundedRectangle`), capsules, springs, and clean trajectories. |
| **Storytelling order** | Dumping equations first before showing what happens physically. | **Phenomenon → Question/Paradox → Vectors/Geometry → Formula-Last** (`self.typewriter(...)` or compact `self.glass_stack(...)`). |
| **Color hierarchy** | Rainbow fills (`RED`, `YELLOW`, `GREEN`, `BLUE` solid PowerPoint circles/boxes). | **85–90% Monochrome Black → White Gradient** (`CINEMA_OBSIDIAN`..`CINEMA_IVORY`, `apply_mono_gradient`) + **10–15% semantic mineral accents** (`CINEMA_ICE`, `CINEMA_EMERALD`, `CINEMA_CHAMPAGNE`, `CINEMA_AMBER`, `CINEMA_ROSE`, `harmonize_color`). |
| **Semantic vectors** | Arbitrary random arrow colors per scene. | Use `self.physics_vector(..., role=...)`: `"velocity"` → `CINEMA_IVORY`, `"accel"`/`"force"` → `CINEMA_EMERALD`, `"friction"`/`"drag"`/`"reaction"` → `CINEMA_ROSE`, `"displacement"`/`"energy"` → `CINEMA_CHAMPAGNE`. |
| **Transient focus** | Permanent clutter of red circles, boxes, and callout arrows left on screen. | Use transient focus tools that auto-clean: `self.sketch_highlight(target)` (`SFX_PEN_STROKE`), `self.spotlight(target)`, or temporary `self.callout(...)`. |
| **Glass & UI optics** | Naked floating HUD text, liquid distortion (`refraction > 0`), or drop shadows. | Clean shadowless dark glass (`refraction=0.0`): `self.glass_badge()`, `self.glass_panel()`, `self.glass_stack()`, `self.explode_stack()`, `self.glass_code()`. |
| **Transitions & cleanup** | Abrupt cuts or orphan child mobjects left behind after `self.remove(parent)`. | Open sections with `self.chapter_card(...)` (`SFX_CHAPTER_CHORD`); cut via `self.diagonal_wipe(swap_fn)` or `self.blur_transition(swap_fn)` and always `self.remove(old, *old.get_family())`. |
| **Audio & pacing** | Silent animations or hardcoded sleeps fighting voiceover. | Pair motion with spatial Foley/UI synth (`SFX_KEY_TICK`, `SFX_PEN_STROKE`, `SFX_SOFT_THUD`, `SFX_CHAPTER_CHORD`, `SFX_WHOOSH`, `SFX_SOFT_TICK`, `SFX_GLASS_CHIME`) and `self.set_narration(...)` + `self.wait_until(...)`. |
| **Resolution & QA** | Shipping uninspected `-ql` (`854x480`) previews. | Set `aspect = "16:9" | "9:16" | "1:1"`, assert `not self.check_layout()`, render `1920x1080` (`--fps 60` for physics essays, `--fps 24` for teardowns), and inspect `render_contact_sheet(mp4_path)`. |

## Choosing Your Visual Mode

1. **Visual Essay / STEM Physics Mode** (Default for physics, math, intuition explainers):
   - Stage clean 2D experiments on `self.stage_ground(surface_type="matte" | "ice")` using sleek monochrome geometric masses (`RoundedRectangle`, `Circle`) — **never stick figures**.
   - Show motion & fields visually via `self.strobe_trail(body)` (`0s, 1s, 2s` ghost snapshots), `self.speed_lines()`, `self.streamlines(body)`, and `self.physics_vector(...)`.
   - Compare reference frames side-by-side with `self.split_viewport("2x1" | "1x2" | "3x1", labels=[...])`.
   - Punch key insights with `self.typewriter(eq_text)`, `self.sketch_highlight(term)`, and `self.spotlight(target)`.
2. **HUD / Architecture Teardown Mode** (Default for systems, code, product breakdowns):
   - Compose inside `self.glass_stack()`, `self.explode_stack()`, `self.callout()`, and `self.glass_code()` (`.focus_lines()`, `.animate_diff()`), driven by `self.signal()` + `ReactiveText` + spring easings (`cinema_spring_smooth`).

## Production Workflow

1. **Script Beats First**: Map spoken beats via `self.set_narration(...)` / `self.load_beats(...)` and sync cuts to `self.wait_until(...)`.
2. **Stage Minimalist Visuals**: Check exact signatures in [api-cheatsheet.md](./references/api-cheatsheet.md) and the complete reference scene in [kinematics_cinema_example.py](./examples/kinematics_cinema_example.py).
3. **Render & Inspect QA Contact Sheet**:
   - Fast layout check (`-ql`): verify timing and `assert not self.check_layout()`.
   - Final CUDA + NVENC render: `manim render -r 1920,1080 --fps 60 --format mp4 <file.py> <Scene>`.
   - Inspect `render_contact_sheet(mp4_path, cols=4, rows=3)` for clipping, overlap, or orphan mobjects before shipping.
