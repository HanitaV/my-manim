---
name: cinema-director
description: >-
  MANDATORY workflow and visual standard for ALL Manim videos, STEM/physics/math/code
  explainers, product teardowns, glass UI scenes, and vertical Shorts built with my-manim.
  Activate whenever creating, editing, refactoring, or rendering any Scene in this project.
---

# Cinema Director Standard (`manim.cinema`)

Every video scene in this repository or any project powered by `my-manim` **MUST** use the `manim.cinema` stack. Do not write plain vanilla Manim `Scene`s with flat colored backgrounds or rainbow shapes.

## Hard Enforcement Rules (Forbidden vs Mandatory)

| Area | Forbidden (Do NOT Do) | Mandatory (`manim.cinema`) |
| :--- | :--- | :--- |
| **Scene base** | `class Foo(Scene):` or `MovingCameraScene` | `class Foo(CinemaScene):` (enables ambient studio backdrop, `CinemaPostFX`, CUDA, NVENC). |
| **Color hierarchy** | Multi-color rainbow fills (`RED`, `YELLOW`, `GREEN`, `BLUE` solid PowerPoint circles/boxes). | **85–90% Monochrome Black → White Gradient** (`CINEMA_OBSIDIAN`..`CINEMA_IVORY`, `apply_mono_gradient`) + **10–15% semantic mineral accents** (`CINEMA_ICE`, `CINEMA_EMERALD`, `CINEMA_CHAMPAGNE`, `CINEMA_ROSE`, `harmonize_color`, `apply_accent_gradient`). |
| **UI containment** | Naked corner text, floating tags, bare mini-charts, or naked formulas on empty background. | Wrap HUD tags in `self.glass_badge()`, cards/charts/formulas in `self.glass_panel()` or `self.glass_stack()`, pointers in `self.callout()`, layered architectures in `self.explode_stack()`, and code in `self.glass_code()`. |
| **Glass optics** | Liquid distortion (`refraction > 0`), drop shadows, or hard sheen cut bands. | Keep clean shadowless dark glass (`refraction=0.0`, subtle smooth tint & white-to-charcoal rim). |
| **Motion & state** | Manual `ValueTracker` + `.become()` boilerplate; stiff `linear` timing; leftover mobjects after transitions. | Use `self.signal()`, `ReactiveText`, `bind_progress_bar`, spring presets (`cinema_spring_smooth`, `cinema_spring_snappy`, `cinema_spring_plop`), `camera_focus`, and `blur_transition`. On swaps, remove `*old.get_family()` so zero ghost mobjects remain. |
| **Audio & pacing** | Silent UI animations or fragile hardcoded waits when voiceover exists. | Attach spatial SFX (`SFX_GLASS_CHIME`, `SFX_GLASS_TAP`, `SFX_WHOOSH`, `SFX_SOFT_TICK`, `SFX_SUB_IMPACT`) via `.with_sound()`, `bind_value_tick`, `on_proximity_sound`, and sync narration via `self.set_narration(...)` + `self.wait_until(...)`. |
| **Resolution & QA** | Delivering `-ql` (`854x480`) previews without visual QA. | Set `aspect = "16:9" | "9:16" | "1:1"`, stay inside `self.safe_rect()`, assert `not self.check_layout()`, render `1920x1080` (or `1080x1920`), and inspect `render_contact_sheet(mp4_path)`. |

## Production Workflow

1. **Plan Beats & Narration**: Draft continuous spoken narration (or beat timestamps) and load with `self.set_narration(...)` / `self.load_beats(...)` so visual cuts stay locked to `self.wait_until(...)`.
2. **Compose Inside Glass Containers**: Group formulas, plots, and callouts cleanly inside `GlassPanel`, `GlassStack`, `GlassCallout`, `ExplodeStack`, or `GlassCode`. Look up exact signatures in [api-cheatsheet.md](./references/api-cheatsheet.md) and a complete STEM physics pattern in [kinematics_cinema_example.py](./examples/kinematics_cinema_example.py).
3. **Animate With Springs & Camera**: Use `cinema_spring_smooth` for cards/camera glides, `cinema_spring_plop` sparingly for badge pops, `camera_focus` to spotlight details, and `blur_transition` between chapters (`self.remove(old, *old.get_family())`).
4. **Render & Inspect QA Contact Sheet**:
   - Fast layout check (`-ql`): verify timing and `assert not self.check_layout()`.
   - Final CUDA + NVENC render: `manim render -r 1920,1080 --fps 24 --format mp4 <file.py> <Scene>` (or `1080,1920` for `"9:16"`).
   - Export and inspect `render_contact_sheet(mp4_path, cols=4, rows=3)` for overlap, clipping, banding, or orphan glyphs before shipping.
