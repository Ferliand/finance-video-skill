import io
from PIL import Image
import pytest
from vengine import workflow
from vengine.brief import Brief
from vengine.image_gen import (
    NEGATIVE_SUFFIX,
    STYLE_PRESETS,
    build_pollinations_url,
    build_scene_prompt,
    generate_project_images,
    generate_scene_image,
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


def _fake_png_bytes(color=(40, 90, 140)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (320, 180), color=color).save(buf, format="PNG")
    return buf.getvalue()


def test_build_pollinations_url_encodes_parameters():
    url = build_pollinations_url("warm flat vector, jar of coins", 1080, 1920, seed=4242)
    assert "image.pollinations.ai/prompt/" in url
    assert "width=1080" in url and "height=1920" in url
    assert "seed=4242" in url and "model=flux" in url and "nologo=true" in url and "enhance=false" in url


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

    generate_project_images(p, fetcher=fake_fetcher)
    assert len(calls) == 2  # Start frame + End frame
    sb_after = p.load_storyboard()
    assert sb_after.scenes[0].image_file is not None
    assert sb_after.scenes[0].end_image_file is not None
    assert (p.root / sb_after.scenes[0].end_image_file).exists()


