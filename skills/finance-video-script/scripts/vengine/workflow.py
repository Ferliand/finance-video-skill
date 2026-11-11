"""Alur kerja: bible, prompt per beat, menerima scene dari agen, status, ekspor."""
from __future__ import annotations

import json
import re

import yaml

from .brief import Brief
from .formats import build_beats
from .lint_script import Issue, check_beat, words
from .project import Project
from .schema import MOODS, TAGS, Beat, Character, Scene, StoryBible

DISCLAIMER = "Ini bukan ajakan membeli produk tertentu. Pelajari risikonya dan sesuaikan dengan kondisimu."
FICTION_LABEL = "Cerita ilustrasi: tokoh dan kejadian dalam video ini fiktif."


# ---------- build: bible + beats (deterministik, tanpa LLM) ----------
def build_bible(brief: Brief) -> StoryBible:
    characters = []
    for role, info in brief.tokoh.items():
        name = info.get("nama") or role
        job = info.get("pekerjaan") or info.get("peran") or role
        descriptor = info.get("descriptor") or (
            f"{job} named {name}, simple flat-vector figure, minimal face, consistent outfit")
        characters.append(Character(id=role, name=name, role=role, descriptor=descriptor))
    return StoryBible(
        topic=brief.topik,
        angle=brief.audiens_spesifik,
        characters=characters,
        variables={k: str(v) for k, v in brief.angka_kunci.items()},
        disclaimers=[DISCLAIMER] + ([FICTION_LABEL] if brief.format == "A" else []),
        is_fiction=brief.format == "A",
        built=True,
    )


def build(project: Project) -> None:
    brief = project.load_brief()
    project.save_bible(build_bible(brief))
    project.save_beats(build_beats(brief))


# ---------- prompt/ringkasan beat untuk agen ----------
def _beat_requirements(beat: Beat) -> list[str]:
    req = []
    if beat.first_tag:
        req.append(f"Scene PERTAMA wajib bertag {beat.first_tag}.")
    if beat.last_tag:
        req.append(f"Scene TERAKHIR wajib bertag {beat.last_tag}.")
    for tag, n in beat.min_tags.items():
        req.append(f"Minimal {n} scene bertag {tag}.")
    for tag, n in beat.max_tags.items():
        req.append(f"Maksimal {n} scene bertag {tag}.")
    return req


def beat_brief(project: Project, beat_id: str | None = None) -> str | None:
    """Teks tugas untuk menulis satu beat. beat_id=None -> beat pertama yang belum ditulis."""
    beats = project.load_beats().beats
    sb = project.load_storyboard()
    written = {s.beat for s in sb.scenes}
    if beat_id is None:
        beat = next((b for b in beats if b.id not in written), None)
        if beat is None:
            return None
    else:
        beat = next((b for b in beats if b.id == beat_id), None)
        if beat is None:
            raise ValueError(f"Beat '{beat_id}' tidak ada. Pilihan: {', '.join(b.id for b in beats)}")
    brief, bible = project.load_brief(), project.load_bible()
    order = [b.id for b in beats]
    prev = [s for s in sb.scenes if order.index(s.beat) < order.index(beat.id)][-3:]
    brief_yaml = yaml.safe_dump(brief.model_dump(), sort_keys=False, allow_unicode=True)
    bible_json = json.dumps(
        {"characters": [c.model_dump() for c in bible.characters], "variables": bible.variables,
         "disclaimers": bible.disclaimers, "is_fiction": bible.is_fiction},
        ensure_ascii=False, indent=2)
    prev_txt = "\n".join(f"- ({s.beat}) {s.narration}" for s in prev) or "(belum ada; ini beat pertama)"
    reqs = "\n".join(f"- {r}" for r in _beat_requirements(beat)) or "- (tidak ada syarat tag khusus)"
    kp = "\n".join(f"- {k}" for k in beat.key_points)
    return (
        f"<BRIEF>\n{brief_yaml}</BRIEF>\n\n<BIBLE>\n{bible_json}\n</BIBLE>\n\n"
        f"<SEBELUMNYA>\n{prev_txt}\n</SEBELUMNYA>\n\n"
        f"=== TUGAS: tulis beat '{beat.id}' ({beat.title}) ===\n"
        f"Tujuan: {beat.goal}\nPoin isi:\n{kp}\n"
        f"- Sekitar {beat.target_scenes} scene (boleh ±2), total sekitar {beat.target_words} kata (±15%).\n"
        f"- Mood dasar: {beat.mood}.\nSyarat tag:\n{reqs}\n"
    )


# ---------- menerima scene dari agen ----------
def load_payload(text: str) -> list[dict]:
    text = re.sub(r"```(?:json)?", "", text).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        a, b = text.find("{"), text.rfind("}")
        if a < 0 or b <= a:
            raise ValueError("tidak ada JSON yang bisa dibaca")
        data = json.loads(text[a:b + 1])
    items = data if isinstance(data, list) else data.get("scenes")
    if not isinstance(items, list) or not items:
        raise ValueError("JSON harus berisi daftar 'scenes' yang tidak kosong")
    return items


def parse_scenes(items: list[dict], beat: Beat, bible: StoryBible) -> tuple[list[Scene], list[Issue]]:
    known = {c.id for c in bible.characters}
    scenes, issues = [], []
    for i, it in enumerate(items, 1):
        tags = [t for t in it.get("tags", []) if t in TAGS]
        bad_tags = [t for t in it.get("tags", []) if t not in TAGS]
        if bad_tags:
            issues.append(Issue("warn", "tag_tidak_dikenal", f"diabaikan: {bad_tags}", i, beat.id))
        chars = [c for c in it.get("characters", []) if c in known]
        if len(chars) != len(it.get("characters", [])):
            issues.append(Issue("warn", "tokoh_tidak_dikenal",
                                f"id tokoh harus salah satu dari {sorted(known) or '(kosong)'}", i, beat.id))
        scenes.append(Scene(
            id=0, beat=beat.id,
            narration=str(it.get("narration", "")).strip(),
            tags=tags, notes=str(it.get("notes") or ""),
            image_prompt=it.get("image_prompt") or None,
            characters=chars,
            mood=it.get("mood") if it.get("mood") in MOODS else beat.mood,
        ))
    return scenes, issues


def add_scenes(project: Project, beat_id: str, items: list[dict], replace: bool = False,
               force: bool = False) -> tuple[bool, list[Issue]]:
    beats = project.load_beats().beats
    if not beats or not project.load_bible().built:
        raise ValueError("Jalankan `build` dulu.")
    beat = next((b for b in beats if b.id == beat_id), None)
    if beat is None:
        raise ValueError(f"Beat '{beat_id}' tidak ada. Pilihan: {', '.join(b.id for b in beats)}")
    sb = project.load_storyboard()
    if any(s.beat == beat_id for s in sb.scenes) and not replace:
        raise ValueError(f"Beat '{beat_id}' sudah ditulis. Pakai --replace untuk menimpa.")
    new, issues = parse_scenes(items, beat, project.load_bible())
    issues += check_beat(new, beat)
    if any(i.level == "error" for i in issues) and not force:
        return False, issues
    order = {b.id: i for i, b in enumerate(beats)}
    merged = sorted([s for s in sb.scenes if s.beat != beat_id] + new, key=lambda s: order[s.beat])
    for n, s in enumerate(merged, 1):
        s.id = n
    sb.scenes = merged
    sb.title = sb.title or project.load_brief().topik
    project.save_storyboard(sb)
    return True, issues


# ---------- status & ekspor ----------
def map_pages(project: Project) -> Storyboard:
    from .page_mapper import map_storyboard_pages
    sb = project.load_storyboard()
    mapped = map_storyboard_pages(sb)
    project.save_storyboard(mapped)
    return mapped


def status_rows(project: Project) -> list[dict]:
    sb = project.load_storyboard()
    rows = []
    for b in project.load_beats().beats:
        sc = [s for s in sb.scenes if s.beat == b.id]
        rows.append(dict(id=b.id, title=b.title, done=bool(sc), scenes=len(sc),
                         words=sum(words(s.narration) for s in sc), target_words=b.target_words))
    return rows


def export_markdown(project: Project) -> str:
    sb = project.load_storyboard()
    brief = project.load_brief()
    lines = [f"# {sb.title or brief.topik}", "",
             f"Format {brief.format} · target {brief.durasi_menit:g} menit", ""]
    for b in project.load_beats().beats:
        sc = [s for s in sb.scenes if s.beat == b.id]
        if not sc:
            continue
        lines += [f"## {b.title} ({b.id})", ""]
        for s in sc:
            tag = f" `{'/'.join(s.tags)}`" if s.tags else ""
            lines.append(f"{s.id}.{tag} {s.narration}")
        lines.append("")
    return "\n".join(lines)


STYLE_PREFIX = "flat vector illustration, warm palette, soft shadows, minimal detail, no text"


def export_prompts(project: Project) -> list[dict]:
    sb = project.load_storyboard()
    bible = project.load_bible()
    char_desc = {c.id: c.descriptor for c in bible.characters}
    out = []
    for s in sb.scenes:
        if s.image_prompt:
            parts = [STYLE_PREFIX]
            for cid in s.characters:
                if cid in char_desc and char_desc[cid]:
                    parts.append(char_desc[cid])
            parts.append(s.image_prompt)
            full_prompt = ", ".join(parts)
            out.append({
                "scene_id": s.id,
                "beat": s.beat,
                "prompt": full_prompt,
                "characters": s.characters,
            })
    return out


def _format_srt_timestamp(seconds: float) -> str:
    millis = int(round(seconds * 1000))
    hours = millis // 3_600_000
    millis %= 3_600_000
    minutes = millis // 60_000
    millis %= 60_000
    secs = millis // 1000
    millis %= 1000
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def export_srt(project: Project) -> str:
    sb = project.load_storyboard()
    brief = project.load_brief()
    from .formats import WPM
    wpm = WPM.get(brief.format, 155)
    current_time = 0.0
    entries = []
    for s in sb.scenes:
        dur = s.duration if s.duration else max(1.5, (words(s.narration) / (wpm / 60.0)))
        start_ts = _format_srt_timestamp(current_time)
        end_ts = _format_srt_timestamp(current_time + dur)
        current_time += dur + s.hold_after
        entries.append(f"{s.id}\n{start_ts} --> {end_ts}\n{s.narration}\n")
    return "\n".join(entries)
