<!-- manim-cinema:start -->
## Mandatory Video Standard (`manim.cinema`)

All animations, STEM/physics explainers, and video scenes generated in this workspace **MUST** use `manim.cinema` via `CinemaScene` (never plain `Scene`, flat solid backgrounds, bullet-point slides, stick figures / `người que`, multi-color PowerPoint rainbow fills, or uninspected `-ql` outputs):

1. Subclass `CinemaScene` and follow `.agents/skills/cinema-director/SKILL.md`.
2. Preserve the **85–90% Monochrome Black-to-White Gradient** aesthetic (`apply_mono_gradient`, shadowless `GlassPanel` / `GlassBadge`) paired with **10–15% restrained semantic mineral accents** (`CINEMA_ICE`, `CINEMA_EMERALD`, `CINEMA_CHAMPAGNE`, `CINEMA_AMBER`, `CINEMA_ROSE`, `harmonize_color`).
3. Follow **Visual Essay Anti-Slide storytelling** (**1 visual model + ≤ 5 words**, Phenomenon → Paradox → Geometry → Formula-last) using sleek geometric bodies (`RoundedRectangle`, `Circle` — **never stick figures**) with `chapter_card`, `stage_ground`, `physics_vector`, `strobe_trail`, `streamlines`, `speed_lines`, `typewriter`, `sketch_highlight`, `spotlight`, `split_viewport`, and `diagonal_wipe`.
4. Use `GlassStack`, `GlassCallout`, `ExplodeStack`, `GlassCode`, `Signal`/`ReactiveText`, spring easings (`cinema_spring_smooth`), spatial Foley/UI SFX (`SFX_*`), and GPU transitions (`blur_transition`, `camera_focus`).
5. Validate layout bounds (`assert not self.check_layout()`), render at 1080p CUDA/NVENC (`--fps 60` for physics essays, `--fps 24` for UI teardowns), and inspect `render_contact_sheet(mp4_path)` before shipping.
<!-- manim-cinema:end -->
