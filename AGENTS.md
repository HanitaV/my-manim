<!-- manim-cinema:start -->
## Mandatory Video Standard (`manim.cinema`)

All animations, explainers, and video scenes generated in this workspace **MUST** use `manim.cinema` via `CinemaScene` (never plain `Scene`, flat solid backgrounds, multi-color PowerPoint rainbow fills, or uninspected `-ql` outputs):

1. Subclass `CinemaScene` and follow `.agents/skills/cinema-director/SKILL.md`.
2. Preserve the **85–90% Monochrome Black-to-White Gradient** aesthetic (`apply_mono_gradient`, clean shadowless `GlassPanel` / `GlassBadge`) paired with **10–15% restrained semantic mineral accents** (`CINEMA_ICE`, `CINEMA_EMERALD`, `CINEMA_CHAMPAGNE`, `harmonize_color`).
3. Use `GlassStack`, `GlassCallout`, `ExplodeStack`, `GlassCode`, `Signal`/`ReactiveText`, spring easings (`cinema_spring_smooth`), spatial SFX (`SFX_*`), and GPU transitions (`blur_transition`, `camera_focus`).
4. Validate layout bounds (`assert not self.check_layout()`), render at 1080p CUDA/NVENC, and inspect `render_contact_sheet(mp4_path)` before shipping.
<!-- manim-cinema:end -->
