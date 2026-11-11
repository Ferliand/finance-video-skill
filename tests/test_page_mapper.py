import pytest

from vengine.page_mapper import map_scene_page, map_storyboard_pages
from vengine.schema import Scene, Storyboard


def test_map_punch_tag_to_punchline_card():
    s = Scene(id=1, beat="s1", narration="Ingat, kalau menunggu sisa tidak akan ada sisa.", tags=["PUNCH"])
    ptype, props = map_scene_page(s)
    assert ptype == "punchline_card"


def test_map_section_tag_to_section_title():
    s = Scene(id=1, beat="s1", narration="Strategi kesatu, pisahkan uang sejak hari pertama.", tags=["SECTION"])
    ptype, props = map_scene_page(s)
    assert ptype == "section_title"


def test_map_calc_tag_to_calc_step():
    s = Scene(id=2, beat="angka", narration="Dua puluh ribu dikali tiga puluh hari menghasilkan enam ratus ribu rupiah.",
              tags=["CALC"], notes="20.000 x 30 = 600.000")
    ptype, props = map_scene_page(s)
    assert ptype == "calc_step"


def test_map_number_tag_to_number_callout():
    s = Scene(id=3, beat="hook", narration="Target kita adalah seratus juta rupiah pertama.", tags=["NUMBER"])
    ptype, props = map_scene_page(s)
    assert ptype == "number_callout"


def test_map_cta_tag_to_cta_comment():
    s = Scene(id=4, beat="hook", narration="Tulis di kolom komentar: Hari ke-1.", tags=["CTA"])
    ptype, props = map_scene_page(s)
    assert ptype == "cta_comment"


def test_map_myth_phrase_to_myth_card():
    s = Scene(id=5, beat="mitos", narration="Kebohongan pertama yang sering kita dengar adalah investasi butuh modal besar.")
    ptype, props = map_scene_page(s)
    assert ptype == "myth_card"


def test_map_before_after_phrase():
    s = Scene(id=6, beat="t1", narration="Tiga tahun lalu dompetnya selalu kosong, tapi hari ini dia punya tabungan.")
    ptype, props = map_scene_page(s)
    assert ptype == "before_after"


def test_map_bank_screen():
    s = Scene(id=7, beat="t1", narration="Dia membuka aplikasi dan melihat saldo tabungan yang mulai bertambah.")
    ptype, props = map_scene_page(s)
    assert ptype == "bank_screen"


def test_map_default_illustration():
    s = Scene(id=8, beat="t1", narration="Malam itu dia duduk memandangi jalan raya yang mulai sepi.")
    ptype, props = map_scene_page(s)
    assert ptype == "illustration"


def test_map_storyboard_pages():
    scenes = [
        Scene(id=1, beat="s1", narration="Strategi kesatu, pisahkan uang.", tags=["SECTION"]),
        Scene(id=2, beat="s1", narration="Fokus pada langkah kecil."),
        Scene(id=3, beat="s1", narration="Kalau menunggu sisa tidak ada sisa.", tags=["PUNCH"]),
    ]
    sb = Storyboard(title="Test", scenes=scenes)
    mapped = map_storyboard_pages(sb)
    assert mapped.scenes[0].page_type == "section_title"
    assert mapped.scenes[1].page_type == "illustration"
    assert mapped.scenes[2].page_type == "punchline_card"


def test_workflow_map_pages(tmp_path):
    from vengine.project import Project
    from vengine import workflow
    from helpers import scenes_for_beat

    p = Project.create("uji-page", "Menabung harian", fmt="B", minutes=3, base=tmp_path)
    workflow.build(p)
    beat_s1 = next(b for b in p.load_beats().beats if b.id == "s1")
    items = scenes_for_beat(beat_s1)
    saved, issues = workflow.add_scenes(p, "s1", items)
    assert saved, [str(i) for i in issues]
    mapped_sb = workflow.map_pages(p)
    assert mapped_sb.scenes[0].page_type == "section_title"
    # verify persisted
    persisted = p.load_storyboard()
    assert persisted.scenes[0].page_type == "section_title"

