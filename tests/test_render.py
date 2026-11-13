import wave
from pathlib import Path

from PIL import Image, ImageChops
import pytest

from vengine import workflow
from vengine.project import Project
from vengine.render import (
    _detect_clay_motion_mode,
    active_word_index,
    compute_word_timings,
    render_project,
    render_scene_frame,
    render_scene_frame_at,
)
from vengine.schema import Scene


def _dummy_tts(text: str, out_path: Path, voice: str = "id-ID-ArdiNeural") -> float:
    """Buat file audio WAV pendek yang valid untuk pengujian cepat."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sr = 22050
    duration = 1.0
    n_samples = int(sr * duration)
    with wave.open(str(out_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(b"\x00\x00" * n_samples)
    return duration


def test_render_scene_frame_dimensions_and_types(tmp_path):
    s_punch = Scene(
        id=1,
        beat="inti",
        narration="Kalau menunggu sisa tidak akan ada sisa.",
        tags=["PUNCH"],
        page_type="punchline_card",
    )
    out_vertical = tmp_path / "punch_s.png"
    render_scene_frame(s_punch, out_vertical, fmt="S", topic="Menabung 20 Ribu")
    assert out_vertical.exists()
    with Image.open(out_vertical) as img:
        assert img.size == (1080, 1920)

    s_calc = Scene(
        id=2,
        beat="angka",
        narration="Dua puluh ribu dikali tiga puluh hari sama dengan enam ratus ribu.",
        tags=["CALC"],
        notes="20.000 x 30 = 600.000",
        page_type="calc_step",
    )
    out_horiz = tmp_path / "calc_b.png"
    render_scene_frame(s_calc, out_horiz, fmt="B", topic="Menabung 20 Ribu")
    assert out_horiz.exists()
    with Image.open(out_horiz) as img:
        assert img.size == (1920, 1080)


def test_render_project_creates_mp4(tmp_path):
    p = Project.create("uji-video", "Trik Menabung", fmt="S", minutes=0.5, base=tmp_path)
    workflow.build(p)
    items = [
        {"narration": "Jangan menabung dari sisa belanja bulananmu.", "tags": ["BRIDGE"]},
    ]
    workflow.add_scenes(p, "hook", items, force=True)
    video_path = render_project(p, tts_fn=_dummy_tts)
    assert video_path.exists()
    assert video_path.stat().st_size > 1000
    sb = p.load_storyboard()
    assert sb.scenes[0].duration is not None and sb.scenes[0].duration > 0
    assert sb.scenes[0].image_file is not None
    assert sb.scenes[0].audio_file is not None
    assert len(sb.scenes[0].words) > 0


def test_compute_word_timings_and_active_word():
    words = compute_word_timings("Satu langkah kecil setiap hari.", 2.5)
    assert len(words) == 5
    assert words[0].start == 0.0
    assert abs(words[-1].end - 2.5) < 1e-3
    assert active_word_index(words, 0.05) == 0
    assert active_word_index(words, 2.4) == 4


@pytest.mark.parametrize(
    "ptype,narration,notes,prompt",
    [
        ("punchline_card", "Kalau menunggu sisa tidak akan ada sisa.", "", None),
        ("calc_step", "Dua puluh ribu dikali tiga puluh hari menjadi enam ratus ribu.", "20.000 x 30 = 600.000", None),
        ("cta_comment", "Tulis di kolom komentar: Hari ke-1.", "", None),
        ("section_title", "Strategi kesatu, pisahkan uang sejak awal.", "", None),
        ("myth_card", "Kebohongan pertama adalah investasi butuh modal besar.", "", None),
        ("before_after", "Dulu dompet selalu kosong, sekarang tabungan mulai terisi.", "", None),
        ("illustration", "Setiap malam dia menyisihkan uang hasil kerja ke dalam toples.", "", "two glass jars on wooden table"),
    ],
)
def test_motion_frames_differ_over_time(ptype, narration, notes, prompt):
    scene = Scene(
        id=1,
        beat="inti",
        narration=narration,
        notes=notes,
        image_prompt=prompt,
        page_type=ptype,
        words=compute_word_timings(narration, 3.0),
    )
    frame_early = render_scene_frame_at(scene, t=0.1, duration=3.0, fmt="S", topic="Menabung")
    frame_late = render_scene_frame_at(scene, t=2.6, duration=3.0, fmt="S", topic="Menabung")
    diff = ImageChops.difference(frame_early, frame_late)
    assert diff.getbbox() is not None, f"Frame statis / tidak ada animasi pada page_type={ptype}"


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
    px = frame.getpixel((20, 40))
    assert px[2] > px[0], f"Expected blue-dominant full-bleed background at edge, got {px}"


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


def test_semantic_chunking_keeps_prepositions_and_compounds_together():
    from vengine.render import _chunk_words_semantic, compute_word_timings

    text = "Layar ponsel yang menyala terang di malam hari menguras energimu."
    words = compute_word_timings(text, 4.0)
    chunks = _chunk_words_semantic(words, max_words=5)
    joined_chunks = [" ".join(w.word for w in ch) for ch in chunks]
    assert any("di malam hari" in jc for jc in joined_chunks), f"Expected 'di malam hari' intact, got {joined_chunks}"


def test_split_sprite_sheet_2x2_removes_background(tmp_path):
    from PIL import Image, ImageDraw
    from vengine.sprites import split_sprite_sheet_2x2

    sheet = Image.new("RGB", (400, 400), (245, 245, 245))
    draw = ImageDraw.Draw(sheet)
    centers = [(100, 100, (220, 60, 60)), (300, 100, (60, 180, 90)), (100, 300, (60, 110, 220)), (300, 300, (220, 170, 40))]
    for cx, cy, col in centers:
        draw.ellipse((cx - 45, cy - 45, cx + 45, cy + 45), fill=col)

    sheet_path = tmp_path / "sheet.png"
    sheet.save(sheet_path)

    out_dir = tmp_path / "sprites"
    paths = split_sprite_sheet_2x2(
        sheet_path,
        out_dir,
        pose_names=("idle", "angry", "shocked", "sad"),
        remove_bg=True,
    )
    assert len(paths) == 4
    for p, expected_name in zip(paths, ("idle.png", "angry.png", "shocked.png", "sad.png")):
        assert p.name == expected_name
        assert p.exists()
        with Image.open(p) as sp:
            assert sp.mode == "RGBA"
            # Corner must be transparent, center must be opaque
            assert sp.getpixel((0, 0))[3] == 0
            assert sp.getpixel((sp.width // 2, sp.height // 2))[3] > 200


def test_layered_puppet_scene_renders_motion(tmp_path):
    from PIL import Image, ImageChops, ImageDraw
    from vengine.schema import PuppetLayer, Scene
    from vengine.render import render_scene_frame_at

    bg = Image.new("RGB", (540, 960), (45, 38, 32))
    sprite = Image.new("RGBA", (200, 300), (0, 0, 0, 0))
    ImageDraw.Draw(sprite).ellipse((40, 20, 160, 280), fill=(240, 235, 225, 255))
    sprite_path = tmp_path / "poci.png"
    sprite.save(sprite_path)

    for motion in ("hop", "shake"):
        sc = Scene(
            id=1,
            beat="hook",
            narration="Hihihi penghuni baru.",
            puppet_layers=[
                PuppetLayer(sprite="poci.png", x=0.5, y=0.65, scale=0.65, motion=motion),
            ],
        )
        f1 = render_scene_frame_at(sc, t=0.1, duration=2.0, fmt="S", bg_image=bg, project_root=tmp_path)
        f2 = render_scene_frame_at(sc, t=0.55, duration=2.0, fmt="S", bg_image=bg, project_root=tmp_path)
        assert f1.size == (1080, 1920)
        assert f2.size == (1080, 1920)
        assert ImageChops.difference(f1, f2).getbbox() is not None





