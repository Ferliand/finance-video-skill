"""CLI vengine: init | build | beat | add | status | lint | export."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from . import workflow
from .lint_script import format_report, lint
from .project import Project


def _project(slug: str) -> Project:
    p = Project(slug)
    if not p.exists():
        raise SystemExit(f"Proyek '{slug}' tidak ditemukan di {p.root.parent}. Jalankan `init` dulu.")
    return p


def cmd_init(a) -> int:
    p = Project.create(a.slug, a.topic, fmt=a.format, minutes=a.minutes, style=a.style)
    print(f"Proyek dibuat: {p.root} (style: {a.style})")
    print(f"Isi {p.brief_path} (angka_kunci, tokoh, cta, style, ...) lalu jalankan: build {a.slug}")
    return 0


def cmd_build(a) -> int:
    p = _project(a.slug)
    workflow.build(p)
    print("Beat sheet:")
    for r in workflow.status_rows(p):
        print(f"  {r['id']:<10} ~{r['target_words']:>4} kata   {r['title']}")
    return 0


def cmd_beat(a) -> int:
    p = _project(a.slug)
    txt = workflow.beat_brief(p, a.beat)
    if txt is None:
        print("Semua beat sudah ditulis. Jalankan `lint`.")
        return 0
    print(txt)
    return 0


def cmd_add(a) -> int:
    p = _project(a.slug)
    text = sys.stdin.read() if a.file == "-" else Path(a.file).read_text(encoding="utf-8")
    try:
        saved, issues = workflow.add_scenes(p, a.beat, workflow.load_payload(text), a.replace, a.force)
    except ValueError as e:
        print(f"Gagal: {e}")
        return 2
    print(format_report(issues))
    if not saved:
        print("TIDAK disimpan. Perbaiki error di atas lalu jalankan `add` lagi (atau --force).")
        return 1
    n = sum(s.beat == a.beat for s in p.load_storyboard().scenes)
    print(f"Disimpan: beat '{a.beat}' ({n} scene).")
    return 0


def cmd_status(a) -> int:
    p = _project(a.slug)
    rows = workflow.status_rows(p)
    for r in rows:
        mark = "[x]" if r["done"] else "[ ]"
        print(f"{mark} {r['id']:<10} {r['scenes']:>2} scene  {r['words']:>4}/{r['target_words']:<4} kata  {r['title']}")
    tw, tt = sum(r["words"] for r in rows), sum(r["target_words"] for r in rows)
    pending = [r["id"] for r in rows if not r["done"]]
    print(f"Total: {tw}/{tt} kata. " + (f"Belum ditulis: {', '.join(pending)}" if pending else "Semua beat sudah ditulis."))
    return 0


def cmd_lint(a) -> int:
    p = _project(a.slug)
    refs_dir = Path(a.refs)
    refs = [f.read_text(encoding="utf-8") for f in sorted(refs_dir.glob("*.txt"))] if refs_dir.exists() else []
    issues = lint(p.load_storyboard(), p.load_beats(), p.load_brief(), refs)
    print(format_report(issues))
    print(f"(referensi dicek: {len(refs)} file dari {refs_dir})")
    return 1 if any(i.level == "error" for i in issues) else 0


def cmd_map_pages(a) -> int:
    p = _project(a.slug)
    sb = workflow.map_pages(p)
    counts: dict[str, int] = {}
    for s in sb.scenes:
        pt = s.page_type or "illustration"
        counts[pt] = counts.get(pt, 0) + 1
    print(f"Pemetaan halaman ({len(sb.scenes)} scene):")
    for pt, count in sorted(counts.items(), key=lambda x: -x[1]):
        print(f"  {pt:<16} {count:>2} scene")
    return 0


def cmd_export(a) -> int:
    p = _project(a.slug)
    p.out_dir.mkdir(parents=True, exist_ok=True)
    out_md = p.out_dir / "naskah.md"
    out_md.write_text(workflow.export_markdown(p), encoding="utf-8", newline="\n")
    print(f"Ditulis: {out_md}")

    prompts = workflow.export_prompts(p, style_override=getattr(a, "style", None))
    out_prompts = p.out_dir / "prompts.json"
    import json
    out_prompts.write_text(json.dumps(prompts, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Ditulis: {out_prompts} ({len(prompts)} prompts)")

    out_srt = p.out_dir / "naskah.srt"
    out_srt.write_text(workflow.export_srt(p), encoding="utf-8", newline="\n")
    print(f"Ditulis: {out_srt}")

    out_el_md = p.out_dir / "naskah_elevenlabs.md"
    out_el_md.write_text(workflow.export_elevenlabs(p), encoding="utf-8", newline="\n")
    print(f"Ditulis: {out_el_md}")

    out_el_txt = p.out_dir / "naskah_elevenlabs.txt"
    out_el_txt.write_text(workflow.export_elevenlabs_plain(p), encoding="utf-8", newline="\n")
    print(f"Ditulis: {out_el_txt}")
    return 0


def cmd_generate_images(a) -> int:
    from .image_gen import generate_project_images
    p = _project(a.slug)
    style = a.style or p.load_brief().style
    print(f"Men-generate aset gambar full-screen untuk '{a.slug}' (style: {style})...")
    paths = generate_project_images(p, style_override=a.style, scene_id=a.scene, force=a.force)
    print(f"Selesai! {len(paths)} aset gambar siap di: {p.out_dir / 'images'}")
    return 0


def cmd_render(a) -> int:
    from .render import render_project
    p = _project(a.slug)
    brief = p.load_brief()
    style = getattr(a, "style", None) or brief.style
    fps = getattr(a, "fps", None) or 24
    keep_audio = bool(getattr(a, "keep_audio", False))
    audio_file_arg = getattr(a, "audio_file", None)
    full_audio = Path(audio_file_arg) if audio_file_arg else None
    voice_label = f"file:{full_audio.name}" if full_audio else ("existing-audio" if keep_audio else a.voice)
    print(f"Me-render video untuk proyek '{a.slug}' (suara: {voice_label}, fps: {fps})...")
    video_path = render_project(
        p,
        voice=a.voice,
        fps=fps,
        style_override=getattr(a, "style", None),
        keep_audio=keep_audio,
        full_audio_path=full_audio,
    )
    total_dur = sum((s.duration or 0.0) for s in p.load_storyboard().scenes)
    print(f"Selesai! Video dibuat: {video_path} (durasi: {total_dur:.1f} detik, {fps} FPS)")
    return 0


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):          # konsol Windows sering bukan UTF-8
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass
    ap = argparse.ArgumentParser(prog="vengine_cli.py", description=__doc__)
    ap.add_argument("--home", help="folder induk proyek (default: $VENGINE_HOME atau ./video-projects)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("init"); s.add_argument("slug"); s.add_argument("--topic", required=True)
    s.add_argument("--format", choices=["A", "B", "S"], default="B"); s.add_argument("--minutes", type=float, default=10)
    s.add_argument("--style", default="flat-vector", help="preset atau custom style visual (default: flat-vector)")
    s.set_defaults(fn=cmd_init)
    s = sub.add_parser("build"); s.add_argument("slug"); s.set_defaults(fn=cmd_build)
    s = sub.add_parser("beat"); s.add_argument("slug"); s.add_argument("--beat"); s.set_defaults(fn=cmd_beat)
    s = sub.add_parser("add"); s.add_argument("slug"); s.add_argument("--beat", required=True)
    s.add_argument("--file", required=True, help="JSON scene untuk beat ini ('-' = stdin)")
    s.add_argument("--replace", action="store_true"); s.add_argument("--force", action="store_true")
    s.set_defaults(fn=cmd_add)
    s = sub.add_parser("status"); s.add_argument("slug"); s.set_defaults(fn=cmd_status)
    s = sub.add_parser("lint"); s.add_argument("slug")
    s.add_argument("--refs", default="references", help="folder transkrip referensi (*.txt) untuk cek kemiripan")
    s.set_defaults(fn=cmd_lint)
    s = sub.add_parser("map-pages"); s.add_argument("slug"); s.set_defaults(fn=cmd_map_pages)
    s = sub.add_parser("export"); s.add_argument("slug")
    s.add_argument("--style", default=None, help="override visual style untuk prompts.json")
    s.set_defaults(fn=cmd_export)
    s = sub.add_parser("generate-images"); s.add_argument("slug")
    s.add_argument("--style", default=None, help="preset atau custom style visual")
    s.add_argument("--scene", type=int, default=None, help="hanya generate ulang nomor scene tertentu")
    s.add_argument("--force", action="store_true", help="timpa file gambar yang sudah ada")
    s.set_defaults(fn=cmd_generate_images)
    s = sub.add_parser("render"); s.add_argument("slug")
    s.add_argument("--voice", default="id-ID-ArdiNeural", help="suara edge-tts atau 'elevenlabs:<voice_id>' (default: id-ID-ArdiNeural)")
    s.add_argument("--style", default=None, help="preset atau custom style visual jika gambar belum dibuat")
    s.add_argument("--fps", type=int, default=None, help="frame rate render (default: 12 untuk claymation, 15 untuk lainnya)")
    s.add_argument("--keep-audio", action="store_true", help="gunakan file audio yang sudah ada di out/audio/ (mis. hasil ElevenLabs) tanpa menimpa")
    s.add_argument("--audio-file", default=None, help="path ke 1 file MP3 utuh (mis. hasil ElevenLabs) untuk dipotong otomatis per scene")
    s.set_defaults(fn=cmd_render)

    a = ap.parse_args(argv)
    if a.home:
        os.environ["VENGINE_HOME"] = a.home
    try:
        return a.fn(a)
    except (FileExistsError, ValueError) as e:
        print(f"Gagal: {e}")
        return 2
