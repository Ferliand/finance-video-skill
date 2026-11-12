"""Folder proyek: path, baca/tulis JSON (atomik). Lokasi proyek: $VENGINE_HOME atau ./video-projects."""
from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path

from .brief import Brief, load_brief
from .schema import BeatSheet, StoryBible, Storyboard

SKILL_ROOT = Path(__file__).resolve().parents[2]       # folder yang berisi SKILL.md
TEMPLATE = SKILL_ROOT / "assets" / "brief.template.yaml"
_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9\-]*$")


def projects_dir() -> Path:
    return Path(os.environ.get("VENGINE_HOME") or Path.cwd() / "video-projects")


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


class Project:
    def __init__(self, slug: str, base: Path | None = None):
        if not _SLUG_RE.match(slug):
            raise ValueError("slug hanya boleh huruf kecil, angka, dan tanda minus")
        self.slug = slug
        self.root = (base or projects_dir()) / slug

    brief_path = property(lambda s: s.root / "brief.yaml")
    bible_path = property(lambda s: s.root / "story_bible.json")
    beats_path = property(lambda s: s.root / "beats.json")
    scenes_path = property(lambda s: s.root / "scenes.json")
    draft_dir = property(lambda s: s.root / "draft")
    out_dir = property(lambda s: s.root / "out")

    def exists(self) -> bool:
        return self.root.exists()

    @classmethod
    def create(cls, slug: str, topic: str, fmt: str = "B", minutes: float = 10,
               base: Path | None = None, style: str = "flat-vector") -> "Project":
        p = cls(slug, base)
        if p.exists():
            raise FileExistsError(f"Proyek '{slug}' sudah ada: {p.root}")
        text = TEMPLATE.read_text(encoding="utf-8")
        text = (text.replace("{{topik}}", json.dumps(topic, ensure_ascii=False))
                    .replace("{{format}}", fmt)
                    .replace("{{durasi}}", str(minutes))
                    .replace("{{style}}", json.dumps(style or "flat-vector", ensure_ascii=False)))
        atomic_write(p.brief_path, text)
        try:
            load_brief(p.brief_path)                  # validasi dini (format/durasi salah)
        except Exception:
            p.brief_path.unlink()
            p.root.rmdir()
            raise
        for d in (p.draft_dir, p.out_dir):
            d.mkdir(parents=True, exist_ok=True)
        p.save_bible(StoryBible(topic=topic))
        p.save_beats(BeatSheet())
        p.save_storyboard(Storyboard())
        return p

    def load_brief(self) -> Brief:
        return load_brief(self.brief_path)

    def load_bible(self) -> StoryBible:
        return StoryBible.model_validate_json(self.bible_path.read_text(encoding="utf-8"))

    def save_bible(self, b: StoryBible) -> None:
        atomic_write(self.bible_path, b.model_dump_json(indent=2))

    def load_beats(self) -> BeatSheet:
        return BeatSheet.model_validate_json(self.beats_path.read_text(encoding="utf-8"))

    def save_beats(self, b: BeatSheet) -> None:
        atomic_write(self.beats_path, b.model_dump_json(indent=2))

    def load_storyboard(self) -> Storyboard:
        return Storyboard.model_validate_json(self.scenes_path.read_text(encoding="utf-8"))

    def save_storyboard(self, sb: Storyboard) -> None:
        atomic_write(self.scenes_path, sb.model_dump_json(indent=2))
