import json
import subprocess
import sys

import pytest
from helpers import scenes_for_beat

from vengine import workflow
from vengine.project import SKILL_ROOT, Project
from vengine.schema import Beat

CLI = SKILL_ROOT / "scripts" / "vengine_cli.py"


def _built(tmp_path, fmt="B", minutes=3):
    p = Project.create("uji", "Rp20.000 per hari", fmt=fmt, minutes=minutes, base=tmp_path)
    workflow.build(p)
    return p


def _items(p, beat_id):
    beat = next(b for b in p.load_beats().beats if b.id == beat_id)
    return scenes_for_beat(beat)


def test_template_is_valid_and_slug_checked(tmp_path):
    p = Project.create("a-1", "topik: dengan titik dua # dan tanda", base=tmp_path)
    assert p.load_brief().topik == "topik: dengan titik dua # dan tanda"
    with pytest.raises(ValueError):
        Project("../x")
    with pytest.raises(ValueError):
        Project.create("bad", "x", fmt="Z", base=tmp_path)
    assert not Project("bad", tmp_path).exists()        # tidak meninggalkan folder setengah jadi


def test_add_all_beats_in_any_order_renumbers(tmp_path):
    p = _built(tmp_path)
    ids = [b.id for b in p.load_beats().beats]
    for bid in reversed(ids):                              # tulis terbalik
        saved, issues = workflow.add_scenes(p, bid, _items(p, bid))
        assert saved, [str(i) for i in issues]
    sb = p.load_storyboard()
    assert [s.id for s in sb.scenes] == list(range(1, len(sb.scenes) + 1))
    assert [s.beat for s in sb.scenes][0] == ids[0] and sb.scenes[-1].beat == ids[-1]
    assert workflow.beat_brief(p) is None
    assert all(r["done"] for r in workflow.status_rows(p))


def test_add_rejects_errors_and_requires_replace(tmp_path):
    p = _built(tmp_path)
    items = _items(p, "hook")
    items[-1]["tags"] = []                                  # langgar BRIDGE
    saved, issues = workflow.add_scenes(p, "hook", items)
    assert not saved and any(i.code == "tag_akhir" for i in issues)
    assert p.load_storyboard().scenes == []
    items[-1]["tags"] = ["BRIDGE"]
    assert workflow.add_scenes(p, "hook", items)[0]
    with pytest.raises(ValueError):
        workflow.add_scenes(p, "hook", items)               # sudah ada
    assert workflow.add_scenes(p, "hook", items, replace=True)[0]
    assert len([s for s in p.load_storyboard().scenes if s.beat == "hook"]) == len(items)


def test_unknown_character_warns_and_is_dropped(tmp_path):
    p = _built(tmp_path)
    items = _items(p, "hook")
    items[0]["characters"] = ["Andi"]
    saved, issues = workflow.add_scenes(p, "hook", items)
    assert saved and any(i.code == "tokoh_tidak_dikenal" for i in issues)
    assert p.load_storyboard().scenes[0].characters == []


def test_load_payload_accepts_fences_and_lists():
    assert len(workflow.load_payload('```json\n{"scenes":[{"narration":"a"}]}\n```')) == 1
    assert len(workflow.load_payload('[{"narration":"a"},{"narration":"b"}]')) == 2
    with pytest.raises(ValueError):
        workflow.load_payload("bukan json")


def test_beat_brief_next_and_context(tmp_path):
    p = _built(tmp_path)
    first = workflow.beat_brief(p)
    assert "tulis beat 'hook'" in first and "belum ada; ini beat pertama" in first
    workflow.add_scenes(p, "hook", _items(p, "hook"))
    second = workflow.beat_brief(p)
    assert "tulis beat 'mitos'" in second and "(hook)" in second       # konteks scene sebelumnya
    with pytest.raises(ValueError):
        workflow.beat_brief(p, "tidak-ada")


def test_export_markdown(tmp_path):
    p = _built(tmp_path)
    workflow.add_scenes(p, "hook", _items(p, "hook"))
    md = workflow.export_markdown(p)
    assert md.startswith("# Rp20.000 per hari") and "## Hook" in md and "`BRIDGE`" in md


def test_export_prompts_and_srt(tmp_path):
    p = _built(tmp_path)
    workflow.add_scenes(p, "hook", _items(p, "hook"))
    prompts = workflow.export_prompts(p)
    assert isinstance(prompts, list)
    assert len(prompts) > 0
    assert "prompt" in prompts[0] and "scene_id" in prompts[0]

    srt = workflow.export_srt(p)
    assert "00:00:00,000 -->" in srt
    assert "1\n" in srt



def run_cli(cwd, *args, stdin=None):
    return subprocess.run([sys.executable, str(CLI), *args], cwd=cwd, input=stdin,
                          capture_output=True, text=True, encoding="utf-8")


def test_cli_end_to_end(tmp_path):
    r = run_cli(tmp_path, "init", "uji", "--topic", "Uang harian", "--minutes", "3")
    assert r.returncode == 0, r.stderr
    assert (tmp_path / "video-projects" / "uji" / "brief.yaml").exists()
    assert run_cli(tmp_path, "build", "uji").returncode == 0
    p = Project("uji", tmp_path / "video-projects")
    bad = _items(p, "hook")
    bad[-1]["tags"] = []
    r = run_cli(tmp_path, "add", "uji", "--beat", "hook", "--file", "-", stdin=json.dumps({"scenes": bad}))
    assert r.returncode == 1 and "TIDAK disimpan" in r.stdout
    ok = _items(p, "hook")
    r = run_cli(tmp_path, "add", "uji", "--beat", "hook", "--file", "-", stdin=json.dumps({"scenes": ok}))
    assert r.returncode == 0 and "Disimpan" in r.stdout
    r = run_cli(tmp_path, "status", "uji")
    assert "[x] hook" in r.stdout and "Belum ditulis" in r.stdout
    assert run_cli(tmp_path, "lint", "uji").returncode == 1          # beat lain belum ada
    assert run_cli(tmp_path, "export", "uji").returncode == 0
    assert run_cli(tmp_path, "status", "tidak-ada").returncode != 0
