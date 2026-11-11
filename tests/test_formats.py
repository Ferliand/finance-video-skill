import pytest

from vengine.brief import Brief
from vengine.formats import build_beats


@pytest.mark.parametrize("fmt,n", [("A", 3), ("A", 4), ("B", 3), ("B", 5)])
def test_beats_cover_duration(fmt, n):
    brief = Brief(topik="x", format=fmt, durasi_menit=10, jumlah_bagian=n)
    beats = build_beats(brief).beats
    ids = [b.id for b in beats]
    assert len(ids) == len(set(ids))
    assert abs(sum(b.target_seconds for b in beats) - 600) <= len(beats)
    assert beats[-1].id == "penutup" and beats[-1].last_tag is None
    assert all(b.last_tag == "BRIDGE" for b in beats[:-1])


def test_format_b_sections_have_requirements():
    beats = build_beats(Brief(topik="x", format="B", jumlah_bagian=4)).beats
    s = [b for b in beats if b.kind == "strategi"]
    assert [b.id for b in s] == ["s1", "s2", "s3", "s4"]
    assert all(b.first_tag == "SECTION" and b.min_tags == {"PUNCH": 1} for b in s)


def test_cta_only_when_requested():
    with_cta = build_beats(Brief(topik="x", format="B", cta={"komentar": "Hari ke-1"})).beats
    without = build_beats(Brief(topik="x", format="B")).beats
    assert with_cta[0].min_tags.get("CTA") == 1 and "CTA" not in without[0].min_tags


def test_format_s_short_form():
    brief = Brief(topik="Menabung 5000", format="S", durasi_menit=1)
    beats = build_beats(brief).beats
    assert [b.id for b in beats] == ["hook", "inti", "penutup"]
    assert sum(b.target_seconds for b in beats) == 60
    assert beats[0].last_tag == "BRIDGE"
    assert beats[1].min_tags.get("PUNCH") == 1
    assert beats[2].id == "penutup"

