# 3D Claymation Style & 12 FPS Stop-Motion Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a locked `claymation` visual style preset, dual-keyframe (`end_image_prompt`) + `motion_prompt` scene support, a 12 FPS stop-motion animation engine in Python (`zoom_flicker`, `bob_and_sigh`, `switch_light`), and render the 3-scene (9-second) vertical Claymation hook simulation.

**Architecture:** We extend `Scene` in `vengine/schema.py` with `motion_prompt`, `end_image_prompt`, and `end_image_file`. `vengine/image_gen.py` adds the locked `claymation` preset (matte plasticine with subtle fingerprints, 15cm miniature diorama, tilt-shift macro, soft diffused studio lighting, chunky rounded silhouettes), strips Midjourney flags like `--ar 9:16` from user prompts so Flux receives clean text, and generates `scene_XXX_end.png` with the same seed when `end_image_prompt` is present. `vengine/render.py` adds a 12 FPS stop-motion animation operator supporting stepped frame cadence, tilt-shift macro depth-of-field blur, blue screen light flicker (`zoom_flicker`), top-prop bobbing + shoulder slump (`bob_and_sigh`), and start-to-end frame switch transition with warm studio light bloom (`switch_light`).

**Tech Stack:** Python 3.10+, Pydantic, Pillow (`ImageFilter.GaussianBlur`, `ImageEnhance`, `RGBA` compositing), Pollinations Flux, `edge-tts`, `imageio-ffmpeg`, `pytest`.

**Spec:** `docs/superpowers/specs/2026-11-12-claymation-stopmotion-design.md`

## Global Constraints

- Default FPS for `claymation` style renders is `12` FPS (configurable via `--fps` on `render`).
- Prompts containing Midjourney flags (e.g., `--ar 9:16`) must have those flags stripped before sending to Pollinations Flux.
- All existing 55 `pytest` tests must continue to pass without regression.
- Sync updated skill files to all agent directories (`~/.pi/agent/skills/finance-video-script`, `~/.gemini/config/skills/finance-video-script`, `~/.claude/skills/finance-video-script`).

## Review Focus

1. **Prompts containing `--ar 9:16` or `--v 6`:** `build_scene_prompt` must strip CLI-style flags (`--ar 9:16`) so Flux does not attempt to render literal text `"9:16"` inside the claymation scene.
2. **Scenes with `end_image_prompt` set (e.g., Scene 3 light switch):** `generate_project_images` must generate both `scene_XXX.png` and `scene_XXX_end.png` using the exact same seed so the miniature room layout matches between Start and End frames.
3. **Detecting motion mode from `motion_prompt`:** `_detect_clay_motion_mode` must accurately classify Scene 1 (`zoom_flicker`), Scene 2 (`bob_and_sigh`), and Scene 3 (`switch_light`) from the English `motion_prompt` strings in the spec.
4. **Stop-motion stepped cadence at 12 FPS:** Consecutive frames across a 3-second clip must differ over time (`ImageChops.difference` non-empty) for all three claymation motion modes.
5. **Custom fixed scene duration when rendering a simulation:** `render_project` must support preserving a pre-set `scene.duration` (e.g., `3.0` seconds per scene for the 9-second hook test) when `--keep-duration` or `tts_fn` is used.

---

### Task 1: Claymation Preset, Dual-Keyframe Schema, and End-Frame Generator

**Files:**
- Modify: `skills/finance-video-script/scripts/vengine/schema.py`
- Modify: `skills/finance-video-script/scripts/vengine/workflow.py`
- Modify: `skills/finance-video-script/scripts/vengine/image_gen.py`
- Test: `tests/test_image_gen.py`

**Interfaces:**
- Produces:
  - `Scene.motion_prompt: str | None = None` in `vengine.schema`
  - `Scene.end_image_prompt: str | None = None` in `vengine.schema`
  - `Scene.end_image_file: str | None = None` in `vengine.schema`
  - `STYLE_PRESETS["claymation"]` in `vengine.image_gen`
  - `clean_prompt_flags(text: str) -> str` in `vengine.image_gen`

- [ ] **Step 1: Write the failing test for `claymation` preset, `--ar 9:16` stripping, and `end_image_prompt` generation**

Append to `tests/test_image_gen.py`:
```python
def test_claymation_preset_strips_ar_flags_and_generates_end_frame(tmp_path):
    assert "claymation" in STYLE_PRESETS
    assert "plasticine" in STYLE_PRESETS["claymation"]
    assert "tilt-shift" in STYLE_PRESETS["claymation"]

    p = Project.create("uji-clay", "Hook Claymation", fmt="S", minutes=0.5, base=tmp_path, style="claymation")
    workflow.build(p)
    items = [
        {
            "narration": "Tangan tanah liat menekan sakelar lampu hingga ruangan menjadi cerah.",
            "tags": ["BRIDGE"],
            "image_prompt": "Macro shot of a chunky clay hand flipping a miniature yellow light switch on a wall --ar 9:16",
            "end_image_prompt": "Macro shot of a chunky clay hand on a flipped yellow light switch, warm bright light illuminating the miniature room --ar 9:16",
            "motion_prompt": "Stop-motion claymation, clay hand flips the switch upward, sudden warm studio light fills the miniature room",
        }
    ]
    workflow.add_scenes(p, "hook", items, force=True)
    sb = p.load_storyboard()
    s1 = sb.scenes[0]
    assert s1.motion_prompt is not None
    assert s1.end_image_prompt is not None

    built_prompt = build_scene_prompt(s1, p.load_brief(), p.load_bible())
    assert "--ar 9:16" not in built_prompt
    assert "plasticine" in built_prompt

    calls = []
    def fake_fetcher(url: str) -> bytes:
        calls.append(url)
        return _fake_png_bytes()

    paths = generate_project_images(p, fetcher=fake_fetcher)
    assert len(calls) == 2  # Start frame + End frame
    sb_after = p.load_storyboard()
    assert sb_after.scenes[0].image_file is not None
    assert sb_after.scenes[0].end_image_file is not None
    assert (p.root / sb_after.scenes[0].end_image_file).exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -m pytest tests/test_image_gen.py::test_claymation_preset_strips_ar_flags_and_generates_end_frame -v`
Expected: FAIL (`AssertionError: assert 'claymation' in STYLE_PRESETS`)

- [ ] **Step 3: Implement `claymation` preset, `Scene` fields, `--ar` flag cleaner, and `end_image_prompt` generation**

1. In `skills/finance-video-script/scripts/vengine/schema.py`, add `end_image_prompt: str | None = None`, `motion_prompt: str | None = None`, and `end_image_file: str | None = None` to `Scene`.
2. In `skills/finance-video-script/scripts/vengine/workflow.py`:
   - In `parse_scenes`, pass `end_image_prompt=it.get("end_image_prompt") or None` and `motion_prompt=it.get("motion_prompt") or None` into `Scene(...)`.
   - In `export_prompts`, include `motion_prompt` and `end_prompt` in the exported dictionary when present.
3. In `skills/finance-video-script/scripts/vengine/image_gen.py`:
   - Add `"claymation": "3D claymation style, handmade plasticine polymer clay texture with subtle fingerprints and sculpt tool marks, matte finish, miniature 15cm diorama set, soft diffused studio softbox lighting, gentle contact shadows, tilt-shift macro photography, shallow depth of field, chunky rounded silhouettes, pastel matte color palette, clean solid background"` to `STYLE_PRESETS`.
   - Strip `--ar \S+` and `--v \S+` flags in `build_scene_prompt` via `re.sub(r"--[a-zA-Z]+\s+\S+", "", text).strip()`.
   - In `generate_project_images`, if `s.end_image_prompt` is present, also generate `images_dir / f"scene_{s.id:03d}_end.png"` with the **same `seed`** and store `s.end_image_file = str(end_path.relative_to(project.root))`.

- [ ] **Step 4: Run test to verify it passes**

Run: `py -m pytest tests/test_image_gen.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add skills/finance-video-script/scripts/vengine/schema.py skills/finance-video-script/scripts/vengine/workflow.py skills/finance-video-script/scripts/vengine/image_gen.py tests/test_image_gen.py
git commit -m "feat: add claymation preset, motion_prompt, and dual-keyframe end_image_prompt"
```

---

### Task 2: 12 FPS Stop-Motion Animator (`zoom_flicker`, `bob_and_sigh`, `switch_light`) in `render.py`

**Files:**
- Modify: `skills/finance-video-script/scripts/vengine/render.py`
- Modify: `skills/finance-video-script/scripts/vengine/cli.py`
- Test: `tests/test_render.py`

**Interfaces:**
- Consumes: `Scene.motion_prompt`, `Scene.end_image_file` from Task 1
- Produces:
  - `_detect_clay_motion_mode(scene: Scene) -> str` in `vengine.render`
  - `render_scene_frame_at(..., end_bg_image: Image.Image | None = None) -> Image.Image` in `vengine.render`
  - CLI `--fps` option on `render` (defaults to `12` when `brief.style == "claymation"`, else `15`)

- [ ] **Step 1: Write failing tests for `_detect_clay_motion_mode` and the 3 claymation motion modes**

Append to `tests/test_render.py`:
```python
from vengine.render import _detect_clay_motion_mode


def test_claymation_motion_modes_detect_and_animate():
    bg_start = Image.new("RGB", (1080, 1920), color=(40, 50, 75))
    bg_end = Image.new("RGB", (1080, 1920), color=(220, 185, 110))

    s1 = Scene(
        id=1, beat="hook", narration="Menatap layar HP di kamar redup.",
        motion_prompt="Stop-motion claymation, slow zoom in toward character's face, soft blue screen light flickering on clay skin, subtle breathing motion",
    )
    s2 = Scene(
        id=2, beat="hook", narration="Baterai merah raksasa melayang di atas kepala.",
        motion_prompt="Stop-motion claymation, static camera, red battery icon gently bobbing up and down, character sighs and slumps shoulders slightly",
    )
    s3 = Scene(
        id=3, beat="hook", narration="Tangan menekan sakelar lampu hingga ruangan cerah.",
        motion_prompt="Stop-motion claymation, clay hand flips the switch upward, sudden warm studio light fills the miniature room, crisp tactile motion",
    )

    assert _detect_clay_motion_mode(s1) == "zoom_flicker"
    assert _detect_clay_motion_mode(s2) == "bob_and_sigh"
    assert _detect_clay_motion_mode(s3) == "switch_light"

    for sc, end_img in ((s1, None), (s2, None), (s3, bg_end)):
        f_early = render_scene_frame_at(sc, t=0.2, duration=3.0, fmt="S", bg_image=bg_start, end_bg_image=end_img)
        f_late = render_scene_frame_at(sc, t=2.4, duration=3.0, fmt="S", bg_image=bg_start, end_bg_image=end_img)
        diff = ImageChops.difference(f_early, f_late)
        assert diff.getbbox() is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -m pytest tests/test_render.py::test_claymation_motion_modes_detect_and_animate -v`
Expected: FAIL (`ImportError: cannot import name '_detect_clay_motion_mode'`)

- [ ] **Step 3: Implement `_detect_clay_motion_mode`, stop-motion operators, Tilt-Shift DoF, and `--fps` in `render.py` & `cli.py`**

1. In `skills/finance-video-script/scripts/vengine/render.py`:
   - `_detect_clay_motion_mode(scene: Scene) -> str`: inspects `(scene.motion_prompt or "").lower()`; returns `"switch_light"` if `"switch"` / `"flip"` / `"illuminat"` or `scene.end_image_file` is set; returns `"bob_and_sigh"` if `"bobbing"` / `"battery"` / `"slump"` / `"sigh"`; returns `"zoom_flicker"` if `"flicker"` / `"screen"` / `"breathing"`; otherwise `"ken_burns"`.
   - `_apply_clay_stop_motion(...)`:
     - Quantizes `t` into stepped stop-motion poses (`pose_idx = int(t * 6)` — 6 poses/sec, i.e., "on twos" at 12 FPS) with subtle tactile micro-jitter (`±1 px`).
     - **`zoom_flicker` (Scene 1):** Stepped slow push-in (`1.0 -> 1.12`) toward center-top, subtle vertical breathing stretch (`1.0 + 0.012 * sin`), and an oscillating soft cyan-blue screen-glow radial light (`RGBA(80, 175, 255, alpha)`) flickering on the center subject.
     - **`bob_and_sigh` (Scene 2):** Static camera frame where the upper icon zone (`y: 0.08..0.42`) bobs vertically (`±18 px` stepped sinusoidal offset) and the lower character shoulder zone (`y: 0.45..0.85`) gently slumps downward (`0 -> +14 px` over the second half of the clip) with seamless feathered blending.
     - **`switch_light` (Scene 3):** Holds/slightly moves the Start Frame for `p < 0.48`, then at the switch flip (`p >= 0.48`) transitions across 3 stop-motion steps into `end_bg_image` (or warmly illuminated version of `bg_image`) accompanied by a warm golden studio softbox light bloom (`RGBA(255, 215, 130, alpha)`).
     - Applies subtle macro tilt-shift blur at the top 7% and bottom 7% edges to reinforce the 15cm miniature diorama look.
2. In `skills/finance-video-script/scripts/vengine/cli.py`:
   - Add `--fps` (`type=int, default=None`) to `render`, defaulting to `12` when `brief.style == "claymation"` else `15`.

- [ ] **Step 4: Run all tests to verify they pass**

Run: `py -m pytest -v`
Expected: All 57 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add skills/finance-video-script/scripts/vengine/render.py skills/finance-video-script/scripts/vengine/cli.py tests/test_render.py
git commit -m "feat: add 12fps claymation stop-motion animation modes in render.py"
```

---

### Task 3: Sync Skill & Render the 9-Second 3-Scene Claymation Hook Simulation (`clay-hook`)

**Files:**
- Modify: `skills/finance-video-script/SKILL.md`
- Create project: `video-projects/clay-hook/` (3 scenes × ~3s, 9:16, 12 FPS, `style: claymation`)

- [ ] **Step 1: Update `SKILL.md` to document `claymation` preset, `motion_prompt`, `end_image_prompt`, and `--fps 12`, then sync via `install.ps1 -All`**

Run: `.\scripts\install.ps1 -All`
Run: `py -m pytest -v`
Expected: All 57 tests PASS.

- [ ] **Step 2: Initialize, populate, generate images, and render `clay-hook` (3 scenes from spec, 12 FPS)**

Run `vengine_cli.py` to build `clay-hook` with the exact 3 scenes from the user's specification (Scene 1: glowing smartphone in dark room; Scene 2: giant red low-battery clay icon bobbing above head; Scene 3: chunky clay hand flipping yellow light switch from dim to bright warm room), generate the Flux claymation assets, and render `video-projects/clay-hook/out/video.mp4` at 12 FPS.

- [ ] **Step 3: Commit documentation updates**

```bash
git add skills/finance-video-script/SKILL.md
git commit -m "docs: add claymation stop-motion workflow and motion_prompt to SKILL.md"
```
