import wave
from pathlib import Path

from PIL import Image, ImageChops
import pytest

from vengine import workflow
from vengine.project import Project
from vengine.render import (
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


