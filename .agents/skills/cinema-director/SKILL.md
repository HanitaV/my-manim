---
name: cinema-director
description: Storyboard-first production workflow for dark monochrome-luxury Cinema videos, product teardowns, glass UI, code walkthroughs, spatial audio, and contact-sheet QA in my-manim.
---

# Cinema Director Workflow (`my-manim`)

Follow this end-to-end production pipeline whenever creating explainer, architecture, or teardown videos with `manim.cinema`.

## 1. Storyboard & One-Take Audio First
1. Draft the narration as natural spoken prose (never choppy per-line snippets).
2. If you have voiceover + word timestamps JSON (`{"beats": ..., "words": [...]}`), load it via `self.set_narration(json_path, audio_file="voice.mp3", bgm="bgm.mp3", bgm_gain=-14.0, bgm_duck=-8.0)`.
3. Map every visual cut to `self.wait_until("word or beat")` so pacing follows the spoken clock rather than fragile hardcoded waits.
4. Choose target aspect ratio on `CinemaScene`:
   - `aspect = "16:9"` (landscape explainers, 1920x1080)
   - `aspect = "9:16"` (Shorts / Reels, 1080x1920 — keep HUD inside `self.safe_rect()`)
   - `aspect = "1:1"` (square social cards, 1080x1080)

## 2. Visual Grammar: Monochrome Luxury + Restrained Accents
- **85–90% Monochrome Base**: Deep obsidian backdrop (`CINEMA_OBSIDIAN`), shadow-free clean dark glass (`GlassPanel`, `GlassBadge`), white-to-charcoal rims, and black-to-white gradients (`apply_mono_gradient`). Never add liquid distortion (`refraction=0`) or drop shadows on glass.
- **10–15% Semantic Mineral Accents**: Pair element roles cleanly via `harmonize_color()` or `apply_accent_gradient()`:
  - Optical / system geometry: `CINEMA_ICE`
  - Live telemetry / active pass: `CINEMA_EMERALD`
  - Audio / warm emphasis: `CINEMA_CHAMPAGNE`
  - Caution / error cue: `CINEMA_ROSE`

## 3. Motion, Teardown & Code Primitives
- **Physics Springs**: Prefer `cinema_spring_smooth`, `cinema_spring_snappy`, `cinema_spring_plop`, or `spring_rate(SpringSpec(...))` over mechanical linear fades. Use `attach_spring_follower()` for tracking HUD pointers.
- **Reactive State**: Drive counters and meters with `sig = self.signal(0.0)`, `ReactiveText`, and `bind_progress_bar` instead of manual per-frame `add_updater` boilerplate.
- **Product Teardowns**: Stack subsystems in `ExplodeStack` (`explode`, `focus_layer`, `restore_layers`, `collapse`) and attach live leader-line labels with `GlassCallout`.
- **Flex Cards**: Group growing/shrinking UI lists in `GlassStack` (`animate_push`).
- **Code Walkthroughs**: Use `GlassCode` (`focus_lines`, `focus_token`, `animate_diff`) for live diffing and spotlighting.
- **Camera & Transitions**: Use `camera_focus`, `camera_reset`, `camera_impulse`, `blur_transition` (GPU optical defocus), and `slide_transition`. Pair motion cues with spatial SFX (`SFX_GLASS_CHIME`, `SFX_GLASS_TAP`, `SFX_WHOOSH`, `SFX_SOFT_TICK`, `SFX_SUB_IMPACT`).

## 4. CUDA Render & QA Gate (Mandatory Before Shipping)
1. Validate layout bounds & overlaps: assert `not self.check_layout()` before finishing animated sections.
2. Render with `.venv\Scripts\python.exe -m manim render -r 1920,1080 --fps 24 --format mp4 <scene_file.py> <SceneClass>` (CUDA post-FX and `h264_nvenc` activate automatically).
3. Generate a contact sheet via `render_contact_sheet(mp4_path, cols=4, rows=3)` and visually inspect it for text clipping, overlaps, dark banding, or stale labels before finalizing.
