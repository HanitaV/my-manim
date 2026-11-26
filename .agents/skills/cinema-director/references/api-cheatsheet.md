# `manim.cinema` Quick API Cheatsheet

Import everything with `from manim import *`.

## 1. Scene Setup & Aspect Ratios

```python
class MyScene(CinemaScene):
    aspect = "16:9"  # "16:9" (1920x1080), "9:16" (1080x1920), or "1:1" (1080x1080)
```

* `self.safe_rect()` -> `RoundedRectangle` layout safe boundary for current `aspect`.
* `self.check_layout(safe_rect=...)` -> returns `list[str]` of clipping or overlap issues (`[]` when clean).

## 2. Monochrome Palette & Mineral Accent Helpers

* **Monochrome stops**: `CINEMA_BLACK` (`#040404`), `CINEMA_OBSIDIAN` (`#080808`), `CINEMA_MIDNIGHT` (`#121212`), `CINEMA_SLATE` (`#1E1E1E`), `CINEMA_GRAPHITE` (`#333333`), `CINEMA_MUTED` (`#737373`), `CINEMA_SILVER` (`#B8B8B8`), `CINEMA_PLATINUM` (`#E5E5E5`), `CINEMA_IVORY` (`#FAFAFA`), `CINEMA_MONO_GRADIENT`.
* **Restrained mineral accents**: `CINEMA_ICE`, `CINEMA_CYAN`, `CINEMA_VIOLET`, `CINEMA_EMERALD`, `CINEMA_CHAMPAGNE`, `CINEMA_AMBER`, `CINEMA_ROSE`.
* **Helpers**:
  * `apply_mono_gradient(mob, colors=[CINEMA_SILVER, CINEMA_IVORY], direction=RIGHT)`
  * `apply_accent_gradient(mob, CINEMA_ICE, anchor="both", direction=RIGHT)` (`anchor` = `"dark" | "light" | "both"`)
  * `harmonize_color("#00FF88")` -> softens vivid hexes to dark-luxury chroma.

## 3. Clean Glass & Teardown Components

* `self.glass_panel(width=4.5, height=2.6, corner_radius=0.28, sheen_opacity=0.04)` -> shadow-free dark glass card.
* `self.glass_badge(width=2.4, height=0.62)` -> pill HUD tag.
* `self.glass_stack(*items, direction=DOWN, gap=0.22, padding=(0.45, 0.38))` -> auto-sizing flex card; `.animate_push(item)` reflows children + backing panel smoothly.
* `self.callout(target, title, subtitle=None, offset=(1.8, 0.9, 0.0), target_anchor=ORIGIN, accent=CINEMA_ICE, follow=True)` -> live pinned HUD label + elbow leader line.
* `self.explode_stack(*layers, axis=UP, collapsed_gap=0.14)` -> `.explode(spread=0.8)`, `.focus_layer(idx, dim_opacity=0.22)`, `.restore_layers()`, `.collapse()`.
* `self.glass_code(code_str, title="app.py", font_size=18)` -> `.focus_lines(1, (3, 4))`, `.focus_token(2, "name")`, `.reset_focus()`, `.animate_diff(scene, new_code_str)`.
* `GlassCaption("...")` -> `.set_caption("...")`.

## 4. Signals, Springs & Followers

* **Springs**: `SmoothSpring`, `SnappySpring`, `PlopSpring`, `GentleSpring`, `spring_rate(spec)`, `spring_duration(spec)`, `cinema_spring_smooth`, `cinema_spring_snappy`, `cinema_spring_plop`.
* `sig = self.signal(0.0)` -> `sig.tween(100.0, spring=SmoothSpring, run_time=1.0)`.
* `ReactiveText(lambda: f"{sig():.0f}%", font_size=36, gradient=[CINEMA_SILVER, CINEMA_IVORY])`
* `bind_progress_bar(bar_fill, bar_track, sig, min_value=0.0, max_value=100.0)`
* `attach_spring_follower(follower, leader, offset=(0.4, 0, 0), stiffness=180.0, damping=24.0)`

## 5. Camera, Transitions, Audio & Narration QA

* `self.camera_focus(target, margin=1.4, dim_mobjects=[...], sound=SFX_GLASS_TAP)` & `self.camera_reset(restore_mobjects=[...])`
* `self.camera_impulse(strength=0.08, duration=0.25, sound=SFX_SUB_IMPACT)`
* `self.blur_transition(swap_fn, max_defocus=16.0, dip_exposure=0.70, run_time=0.75)` (GPU optical defocus; always `self.remove(old, *old.get_family())` inside `swap_fn`).
* `self.slide_transition(outgoing, incoming, direction=LEFT)`
* **Procedural 48kHz Stereo Synth Presets**: `SFX_GLASS_TAP`, `SFX_GLASS_CHIME`, `SFX_SOFT_TICK`, `SFX_UI_POP`, `SFX_WHOOSH`, `SFX_SUB_IMPACT`, `SFX_SHIMMER`.
* **Synchronization**: `anim.with_sound(SFX_WHOOSH, gain=-3.0)`, `group_anim.with_staggered_sound(SFX_GLASS_CHIME, pitch_step=2.5)`, `self.bind_value_tick(sig.tracker, SFX_SOFT_TICK, step=10.0)`, `self.on_proximity_sound(probe, targets, SFX_GLASS_TAP)`.
* **One-take narration**: `self.set_narration("voice.json", audio_file="voice.mp3", bgm="bgm.mp3", bgm_duck=-8.0)` + `self.wait_until("marker_or_word")`.
* **Contact Sheet QA**: `render_contact_sheet(mp4_path, cols=4, rows=3)`.
