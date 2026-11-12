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
