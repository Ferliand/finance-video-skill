# Full-Screen AI Image Assets & Custom Style Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add configurable visual styles, a pre-render `generate-images` step backed by Pollinations (Flux), and a full-screen cinematic RGBA compositor that replaces the boxy HTML-like layout across all scenes.

**Architecture:** We introduce `vengine/image_gen.py` to resolve style presets or custom style strings, synthesize full-screen prompts for all scenes (including card scenes whose `image_prompt` is `None`), and fetch/cache images from Pollinations (`model=flux`) into `out/images/scene_XXX.png` with automatic fallback canvases. `vengine/render.py` is refactored to composite full-bleed Ken Burns backgrounds with RGBA alpha-blended vignettes, glassmorphism overlays for numbers/punchlines, and borderless karaoke subtitles.

**Tech Stack:** Python 3.10+, Pydantic, PyYAML, Pillow (`RGBA` compositing), `urllib.request`, `edge-tts`, `imageio-ffmpeg`, `pytest`.

**Spec:** `docs/superpowers/specs/2026-11-12-fullscreen-image-assets-design.md`

## Global Constraints

- Only use existing Python dependencies (`pydantic`, `pyyaml`, `pillow`, `edge-tts`, `imageio-ffmpeg`, and standard library `urllib`).
- Output dimensions must be `1920x1080` for formats `A` and `B`, and `1080x1920` for format `S`.
- Every generated prompt must end with `"no text, no letters, no numbers, no watermark, clean composition"`.
- Existing 49 `pytest` tests must continue to pass without regression.
- Sync updated skill files to all agent directories (`~/.pi/agent/skills/finance-video-script`, `~/.gemini/config/skills/finance-video-script`, `~/.claude/skills/finance-video-script`).

## Review Focus

1. **Empty or whitespace-only `style` in `brief.yaml`:** `resolve_style_prefix("")` must fall back to `STYLE_PRESETS["flat-vector"]` rather than producing a leading comma or empty style.
2. **Scenes with `image_prompt=None` (e.g., `calc_step`, `punchline_card`, or legacy projects):** `build_scene_prompt` and `export_prompts` must still produce a valid, non-empty visual prompt for every scene so all scenes get full-screen assets.
3. **Network failure or invalid image bytes from Pollinations:** `generate_scene_image` must catch network/decode errors and save a full-screen fallback canvas so `generate-images` and `render` never crash offline.
4. **Re-running `generate-images` when images already exist:** Cached images in `out/images/scene_XXX.png` must not be overwritten unless `force=True` or `scene_id` targets that specific scene.
5. **Passing `--scene 999` (non-existent scene ID) to `generate-images`:** Must raise a clear `ValueError` listing valid scene IDs instead of silently succeeding with 0 images.

---

### Task 1: Style Configuration & Full-Storyboard Prompt Builder

**Files:**
- Modify: `skills/finance-video-script/assets/brief.template.yaml`
- Modify: `skills/finance-video-script/scripts/vengine/brief.py`
- Modify: `skills/finance-video-script/scripts/vengine/project.py`
- Create: `skills/finance-video-script/scripts/vengine/image_gen.py`
- Modify: `skills/finance-video-script/scripts/vengine/workflow.py`
- Test: `tests/test_image_gen.py`

**Interfaces:**
- Produces:
  - `Brief.style: str = "flat-vector"` in `vengine.brief`
  - `Project.create(cls, slug: str, topic: str, fmt: str = "B", minutes: float = 10, base: Path | None = None, style: str = "flat-vector") -> Project` in `vengine.project`
  - `STYLE_PRESETS: dict[str, str]` in `vengine.image_gen`
  - `NEGATIVE_SUFFIX: str = "no text, no letters, no numbers, no watermark, clean composition"` in `vengine.image_gen`
  - `resolve_style_prefix(style: str | None) -> str` in `vengine.image_gen`
  - `build_scene_prompt(scene: Scene, brief: Brief, bible: StoryBible, style_override: str | None = None) -> str` in `vengine.image_gen`
  - `workflow.export_prompts(project: Project, style_override: str | None = None) -> list[dict]`

- [ ] **Step 1: Write the failing tests for style resolution and all-scene prompt generation**

Create `tests/test_image_gen.py`:
```python
import pytest
from vengine import workflow
from vengine.brief import Brief
from vengine.image_gen import (
    NEGATIVE_SUFFIX,
    STYLE_PRESETS,
    build_scene_prompt,
    resolve_style_prefix,
)
from vengine.project import Project
from vengine.schema import Character, Scene, StoryBible


def test_resolve_style_presets_and_custom_and_empty():
    assert resolve_style_prefix("3d-pixar") == STYLE_PRESETS["3d-pixar"]
    assert resolve_style_prefix("  ANIME-GHIBLI ") == STYLE_PRESETS["anime-ghibli"]
    assert resolve_style_prefix("") == STYLE_PRESETS["flat-vector"]
    assert resolve_style_prefix(None) == STYLE_PRESETS["flat-vector"]
    custom = resolve_style_prefix("isometric neon cyberpunk city")
    assert "isometric neon cyberpunk city" in custom


def test_build_scene_prompt_covers_explicit_and_null_image_prompt():
    brief = Brief(topik="Menabung Rp20.000", format="S", durasi_menit=1.0, style="3d-pixar")
    bible = StoryBible(
        topic="Menabung Rp20.000",
        characters=[Character(id="protagonis", name="Raka", role="protagonis", descriptor="young man in green jacket")],
    )
    s_explicit = Scene(
        id=1, beat="hook", narration="Dompet kosong di akhir bulan.",
        image_prompt="empty leather wallet on wooden desk", characters=["protagonis"], mood="tense",
    )
    p1 = build_scene_prompt(s_explicit, brief, bible)
    assert STYLE_PRESETS["3d-pixar"] in p1
    assert "young man in green jacket" in p1
    assert "empty leather wallet on wooden desk" in p1
    assert p1.endswith(NEGATIVE_SUFFIX)

    s_null = Scene(
        id=2, beat="inti", narration="Dua puluh ribu dikali tiga puluh hari.",
        tags=["CALC"], page_type="calc_step", image_prompt=None, mood="uplift",
    )
    p2 = build_scene_prompt(s_null, brief, bible, style_override="watercolor")
    assert STYLE_PRESETS["watercolor"] in p2
    assert p2.endswith(NEGATIVE_SUFFIX)


def test_export_prompts_includes_all_scenes(tmp_path):
    p = Project.create("uji-style", "Dana Darurat", fmt="S", minutes=1.0, base=tmp_path, style="anime-ghibli")
    workflow.build(p)
    items = [
        {"narration": "Jangan tunggu sisa gaji untuk menabung.", "tags": ["PUNCH"], "image_prompt": None},
        {"narration": "Sisihkan dua puluh ribu rupiah setiap pagi.", "tags": ["BRIDGE"], "image_prompt": "glass jar with coins"},
    ]
    workflow.add_scenes(p, "hook", items, force=True)
    prompts = workflow.export_prompts(p)
    assert len(prompts) == 2
    assert all(STYLE_PRESETS["anime-ghibli"] in item["prompt"] for item in prompts)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_image_gen.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'vengine.image_gen'`

- [ ] **Step 3: Implement `Brief.style`, `Project.create(..., style=...)`, `image_gen.py` prompt helpers, and `workflow.export_prompts`**

1. In `skills/finance-video-script/assets/brief.template.yaml`, add `style: {{style}}` after `durasi_menit`.
2. In `skills/finance-video-script/scripts/vengine/brief.py`, add `style: str = "flat-vector"` to `Brief`.
3. In `skills/finance-video-script/scripts/vengine/project.py`, update `Project.create` to accept `style: str = "flat-vector"` and replace `{{style}}` with `json.dumps(style, ensure_ascii=False)`.
4. In `skills/finance-video-script/scripts/vengine/image_gen.py`, define `STYLE_PRESETS` (`flat-vector`, `3d-pixar`, `anime-ghibli`, `cinematic-realistic`, `watercolor`, `comic-book`, `dark-moody`), `NEGATIVE_SUFFIX`, `resolve_style_prefix`, and `build_scene_prompt`. When `scene.image_prompt` is `None`, synthesize an atmospheric scene description based on `scene.page_type` / `scene.tags` and `scene.mood` so calculation/punchline cards get clean, moody financial background art.
5. In `skills/finance-video-script/scripts/vengine/workflow.py`, update `export_prompts(project: Project, style_override: str | None = None) -> list[dict]` to iterate over **all** `s in sb.scenes` and build each entry using `build_scene_prompt(s, brief, bible, style_override=style_override)`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_image_gen.py tests/test_workflow.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add skills/finance-video-script/assets/brief.template.yaml skills/finance-video-script/scripts/vengine/brief.py skills/finance-video-script/scripts/vengine/project.py skills/finance-video-script/scripts/vengine/image_gen.py skills/finance-video-script/scripts/vengine/workflow.py tests/test_image_gen.py
git commit -m "feat: add visual style presets and full-storyboard prompt builder"
```

---

### Task 2: Pollinations Flux Image Asset Generator & CLI `generate-images`

**Files:**
- Modify: `skills/finance-video-script/scripts/vengine/image_gen.py`
- Modify: `skills/finance-video-script/scripts/vengine/cli.py`
- Modify: `tests/test_image_gen.py`

**Interfaces:**
- Consumes: `resolve_style_prefix`, `build_scene_prompt` from Task 1
- Produces:
  - `build_pollinations_url(prompt: str, width: int, height: int, seed: int, model: str = "flux") -> str`
  - `render_fallback_canvas(scene: Scene, width: int, height: int) -> Image.Image`
  - `generate_scene_image(scene: Scene, prompt: str, out_path: Path, width: int, height: int, seed: int, fetcher: Callable[[str], bytes] | None = None) -> Path`
  - `generate_project_images(project: Project, style_override: str | None = None, scene_id: int | None = None, force: bool = False, fetcher: Callable[[str], bytes] | None = None) -> list[Path]`
  - CLI subcommand: `vengine_cli.py generate-images <slug> [--style STYLE] [--scene ID] [--force]`

- [ ] **Step 1: Write failing tests for URL building, caching, `--scene` filtering, and offline fallback**

Append to `tests/test_image_gen.py`:
```python
import io
from PIL import Image
from vengine.image_gen import (
    build_pollinations_url,
    generate_project_images,
    generate_scene_image,
)
from tests.test_workflow import run_cli


def _fake_png_bytes(color=(40, 90, 140)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (320, 180), color=color).save(buf, format="PNG")
    return buf.getvalue()


def test_build_pollinations_url_encodes_parameters():
    url = build_pollinations_url("warm flat vector, jar of coins", 1080, 1920, seed=4242)
    assert "image.pollinations.ai/prompt/" in url
    assert "width=1080" in url and "height=1920" in url
    assert "seed=4242" in url and "model=flux" in url and "nologo=true" in url


def test_generate_project_images_caches_and_supports_scene_filter_and_fallback(tmp_path):
    p = Project.create("uji-img", "Menabung Harian", fmt="S", minutes=1.0, base=tmp_path, style="3d-pixar")
    workflow.build(p)
    items = [
        {"narration": "Jangan menabung dari uang sisa.", "tags": ["PUNCH"]},
        {"narration": "Sisihkan dua puluh ribu di awal hari.", "tags": ["BRIDGE"], "image_prompt": "coins in jar"},
    ]
    workflow.add_scenes(p, "hook", items, force=True)

    calls = []
    def fake_fetcher(url: str) -> bytes:
        calls.append(url)
        return _fake_png_bytes()

    paths = generate_project_images(p, fetcher=fake_fetcher)
    assert len(paths) == 2
    assert len(calls) == 2
    for img_path in paths:
        assert img_path.exists()
        with Image.open(img_path) as im:
            assert im.size == (1080, 1920)

    # Second run without force uses cache
    generate_project_images(p, fetcher=fake_fetcher)
    assert len(calls) == 2

    # Regenerate only scene 2
    generate_project_images(p, scene_id=2, fetcher=fake_fetcher)
    assert len(calls) == 3

    # Invalid scene_id raises ValueError
    with pytest.raises(ValueError, match="Scene 999"):
        generate_project_images(p, scene_id=999, fetcher=fake_fetcher)

    # Network error falls back to procedural atmospheric canvas without crashing
    def failing_fetcher(url: str) -> bytes:
        raise OSError("network down")

    fallback_out = tmp_path / "fallback.png"
    s1 = p.load_storyboard().scenes[0]
    generate_scene_image(s1, "test prompt", fallback_out, 1080, 1920, seed=1, fetcher=failing_fetcher)
    assert fallback_out.exists()
    with Image.open(fallback_out) as im:
        assert im.size == (1080, 1920)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_image_gen.py -v`
Expected: FAIL with `ImportError: cannot import name 'build_pollinations_url'`

- [ ] **Step 3: Implement Pollinations Flux fetcher, fallback canvas, project image generator, and CLI command**

1. In `skills/finance-video-script/scripts/vengine/image_gen.py`:
   - `build_pollinations_url`: `urllib.parse.quote(prompt)` into `https://image.pollinations.ai/prompt/{encoded}?width={width}&height={height}&seed={seed}&model={model}&nologo=true`.
   - `render_fallback_canvas(scene, width, height)`: renders a full-screen smooth vertical gradient with soft glowing bokeh circles and contextual vector silhouette so offline renders look atmospheric rather than boxed HTML.
   - `generate_scene_image`: calls `fetcher(url)` (defaulting to `urllib.request.urlopen` with User-Agent and 2 retries), opens with `Image.open(io.BytesIO(data)).convert("RGB")`, resizes with `Image.Resampling.LANCZOS` to `(width, height)`, or falls back to `render_fallback_canvas` on exception.
   - `generate_project_images`: maps pages if unmapped, validates `scene_id` if provided, generates images into `project.out_dir / "images" / f"scene_{s.id:03d}.png"`, updates `s.image_file = str(img_path.relative_to(project.root))`, writes `out/prompts.json`, and saves storyboard.
2. In `skills/finance-video-script/scripts/vengine/cli.py`:
   - Add `--style` to `init` (default `"flat-vector"`), `export` (default `None`), and `render` (default `None`).
   - Add `generate-images` subcommand with `slug`, `--style`, `--scene` (`type=int`), and `--force`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_image_gen.py tests/test_workflow.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add skills/finance-video-script/scripts/vengine/image_gen.py skills/finance-video-script/scripts/vengine/cli.py tests/test_image_gen.py
git commit -m "feat: add Pollinations Flux image generator and generate-images CLI"
```

---

### Task 3: Full-Screen Cinematic RGBA Compositor in `render.py`

**Files:**
- Modify: `skills/finance-video-script/scripts/vengine/render.py`
- Modify: `tests/test_render.py`

**Interfaces:**
- Consumes: `generate_project_images`, `render_fallback_canvas` from `vengine.image_gen`
- Produces:
  - `render_scene_frame_at(scene: Scene, t: float, duration: float, fmt: str = "B", topic: str = "", bg_image: Image.Image | None = None) -> Image.Image`
  - `render_scene_frame(scene: Scene, out_path: Path, fmt: str = "B", topic: str = "", t: float = 1.0, duration: float = 3.0, bg_image: Image.Image | None = None) -> Path`
  - `render_project(project: Project, voice: str = DEFAULT_VOICE, tts_fn: Callable[[str, Path, str], float] | None = None, fps: int = 15, style_override: str | None = None, image_fetcher: Callable[[str], bytes] | None = None) -> Path`

- [ ] **Step 1: Write failing tests for full-screen background compositing and Ken Burns motion**

Update `tests/test_render.py` to add `test_fullscreen_background_image_is_composited_edge_to_edge`:
```python
def test_fullscreen_background_image_is_composited_edge_to_edge(tmp_path):
    bg = Image.new("RGB", (1080, 1920), color=(25, 110, 160))
    scene = Scene(
        id=1,
        beat="hook",
        narration="Menabung dua puluh ribu setiap pagi mengubah masa depanmu.",
        page_type="illustration",
        words=compute_word_timings("Menabung dua puluh ribu setiap pagi mengubah masa depanmu.", 3.0),
    )
    frame = render_scene_frame_at(scene, t=0.5, duration=3.0, fmt="S", topic="Menabung", bg_image=bg)
    assert frame.size == (1080, 1920)
    # Top-left safe area (below thin progress bar) reflects the full-bleed background image, not a fixed cream/dark margin
    px = frame.getpixel((20, 40))
    assert px[2] > px[0], f"Expected blue-dominant full-bleed background at edge, got {px}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_render.py::test_fullscreen_background_image_is_composited_edge_to_edge -v`
Expected: FAIL (`TypeError: render_scene_frame_at() got an unexpected keyword argument 'bg_image'`)

- [ ] **Step 3: Refactor `render.py` to use full-screen Ken Burns + RGBA glass overlays + borderless karaoke subtitle**

In `skills/finance-video-script/scripts/vengine/render.py`:
1. Add `_apply_fullscreen_ken_burns(bg: Image.Image, width: int, height: int, p: float, scene_id: int) -> Image.Image` that crops & resizes `bg` across the entire `(width, height)` canvas (`zoom = 1.0 + 0.08 * p`, alternating pan direction by `scene_id % 2`).
2. Add `_apply_cinematic_vignette(base_rgb: Image.Image, darken_center: bool) -> Image.Image` using `RGBA` alpha compositing: smooth dark gradient in the bottom 35% of the screen (`alpha` 0 → 215) for subtitle legibility, top 12% (`alpha` 130 → 0) for the minimal pill badge, and optional center dimming (`alpha` 115) when rendering overlay cards (`calc_step`, `punchline_card`, `myth_card`, `before_after`, `cta_comment`, `section_title`).
3. Replace opaque white/dark HTML-like rectangles on `calc_step`, `myth_card`, `before_after`, `cta_comment` with semi-transparent dark glass panels (`RGBA(15, 23, 42, 185)`) with a subtle 2px accent border on an `RGBA` overlay layer composited onto the full-screen background.
4. Update `_draw_karaoke_subtitle` to remove the large bordered container box; instead draw clean centered text over the bottom vignette with a soft dark text shadow `(0, 0, 0)` and a rounded accent pill (`#E8A33D`) behind the currently spoken word.
5. In `render_project`, call `generate_project_images(project, style_override=style_override, fetcher=image_fetcher)` first so any missing `out/images/scene_XXX.png` is created before rendering frames, load each scene's `bg_image` once per scene, and pass `bg_image` to `render_scene_frame` and `_render_animated_segment`.

- [ ] **Step 4: Run all tests to verify they pass**

Run: `python -m pytest -v`
Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add skills/finance-video-script/scripts/vengine/render.py tests/test_render.py
git commit -m "feat: replace boxed HTML-like cards with full-screen RGBA compositor"
```

---

### Task 4: Skill Documentation & Multi-Agent Installation Sync

**Files:**
- Modify: `skills/finance-video-script/SKILL.md`
- Modify: `README.md`
- Modify: `PROJECT.md`

**Interfaces:**
- Consumes: CLI `generate-images` and `--style` options from Tasks 1–3
- Produces: Updated `SKILL.md` synced to `C:\Users\Ferli\.pi\agent\skills\finance-video-script`, `C:\Users\Ferli\.gemini\config\skills\finance-video-script`, and `C:\Users\Ferli\.claude\skills\finance-video-script`.

- [ ] **Step 1: Update `SKILL.md`, `README.md`, and `PROJECT.md`**

1. In `skills/finance-video-script/SKILL.md`:
   - Document `style` selection in Step 1 & Step 3 (`--style flat-vector|3d-pixar|anime-ghibli|cinematic-realistic|watercolor|comic-book|dark-moody` or custom style string).
   - Instruct the agent in Step 4 & "Format JSON scene" to provide an English `image_prompt` for **every** scene so every scene gets a tailored full-screen visual.
   - Add Step 8: `generate-images <slug> [--style ...]` to generate full-screen assets into `out/images/` before running `render <slug>`.
2. Update `README.md` and `PROJECT.md` to reflect the `generate-images` command and full-screen Pollinations Flux pipeline.

- [ ] **Step 2: Sync skill installation across all agents and verify**

Run: `.\scripts\install.ps1 -All`
Run: `python -m pytest -v`
Expected: `install.ps1` copies updated files to Claude, Antigravity, and Pi (`C:\Users\Ferli\.pi\agent\skills\finance-video-script`), and all `pytest` tests pass.

- [ ] **Step 3: Commit**

```bash
git add skills/finance-video-script/SKILL.md README.md PROJECT.md
git commit -m "docs: document generate-images workflow and style presets in SKILL.md"
```
