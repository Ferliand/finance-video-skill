import copy

from helpers import scenes_for_beat
from vengine.brief import Brief
from vengine.formats import build_beats
from vengine.lint_script import _eval_formula, lint, parse_id_number
from vengine.schema import Scene, Storyboard


def _good(fmt="B", minutes=3):
    brief = Brief(topik="x", format=fmt, durasi_menit=minutes, jumlah_bagian=3,
                  angka_kunci={"setoran": 20000, "target": 100000000},
                  instrumen_boleh_disebut=["emas digital"], cta={"komentar": "Hari ke-1"})
    beats = build_beats(brief)
    scenes, i = [], 1
    for b in beats.beats:
        for d in scenes_for_beat(b):
            scenes.append(Scene(id=i, beat=b.id, **d))
            i += 1
    return Storyboard(title="x", scenes=scenes), beats, brief


def codes(issues, level="error"):
    return {i.code for i in issues if i.level == level}


def test_good_storyboard_has_no_errors():
    sb, beats, brief = _good()
    assert codes(lint(sb, beats, brief)) == set()


def test_parse_id_number():
    assert parse_id_number("20.000") == 20000
    assert parse_id_number("7.200.000") == 7200000
    assert parse_id_number("7,2") == 7.2


def test_wrong_formula_detected():
    sb, beats, brief = _good()
    for s in sb.scenes:
        if "CALC" in s.tags:
            s.notes = "20.000 x 30 = 650.000"
            break
    assert "rumus_salah" in codes(lint(sb, beats, brief))


def test_calc_without_formula_detected():
    sb, beats, brief = _good()
    next(s for s in sb.scenes if "CALC" in s.tags).notes = ""
    assert "rumus_hilang" in codes(lint(sb, beats, brief))


def test_unsourced_statistic_detected():
    sb, beats, brief = _good()
    sb.scenes[1].narration += " Sembilan puluh persen orang tidak pernah sampai. 90% orang menyerah."
    assert "statistik_tanpa_sumber" in codes(lint(sb, beats, brief))


def test_instrument_requires_disclaimer():
    sb, beats, brief = _good()
    sb.scenes[1].narration += " Kamu bisa mulai dari emas digital yang relatif stabil."
    assert "disclaimer_hilang" in codes(lint(sb, beats, brief))
    sb.scenes[-1].narration += " Ini bukan ajakan membeli produk tertentu."
    assert "disclaimer_hilang" not in codes(lint(sb, beats, brief))


def test_missing_bridge_and_beat():
    sb, beats, brief = _good()
    first_beat = sb.scenes[0].beat
    last_of_first = [s for s in sb.scenes if s.beat == first_beat][-1]
    last_of_first.tags = [t for t in last_of_first.tags if t != "BRIDGE"]
    removed = sb.scenes[-1].beat
    sb.scenes = [s for s in sb.scenes if s.beat != removed]
    c = codes(lint(sb, beats, brief))
    assert {"tag_akhir", "beat_hilang"} <= c


def test_too_many_cta():
    sb, beats, brief = _good()
    for s in sb.scenes[2:6]:
        s.tags.append("CTA")
    assert "cta_lebih" in codes(lint(sb, beats, brief))


def test_overlap_with_reference_detected():
    sb, beats, brief = _good()
    ref = sb.scenes[1].narration            # "referensi" yang kebetulan sama persis
    issues = lint(sb, beats, brief, references=[ref])
    assert "mirip_referensi" in codes(issues)
    assert "mirip_referensi" not in codes(lint(sb, beats, brief, references=["teks lain sama sekali berbeda isinya"]))


def test_total_words_out_of_range():
    sb, beats, brief = _good()
    sb.scenes = sb.scenes[: len(sb.scenes) // 2]
    assert "total_kata" in codes(lint(sb, beats, brief))


def test_formula_with_parentheses():
    val = _eval_formula("(20.000 + 10.000) x 30")
    assert val == 900000.0


def test_broader_unsourced_statistic_detected():
    sb, beats, brief = _good()
    sb.scenes[1].narration += " Sekitar 80% anak muda belum punya dana darurat."
    assert "statistik_tanpa_sumber" in codes(lint(sb, beats, brief))

