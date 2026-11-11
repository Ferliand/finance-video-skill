"""Kontrak data antar tahap. Semua tahap membaca/menulis model-model ini.

File di folder proyek:
  brief.yaml       -> Brief        (input kamu; lihat brief.py)
  story_bible.json -> StoryBible   (tokoh, variabel angka, disclaimer)
  beats.json       -> BeatSheet    (kerangka cerita + syarat tag per beat)
  scenes.json      -> Storyboard   (scene: narasi, tag, prompt, audio, gambar, timing)
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Tag = Literal["PUNCH", "BRIDGE", "SECTION", "CTA", "NUMBER", "CALC"]
TAGS: tuple[str, ...] = ("PUNCH", "BRIDGE", "SECTION", "CTA", "NUMBER", "CALC")

Mood = Literal["tense", "neutral", "warm", "uplift", "melancholy"]
MOODS: tuple[str, ...] = ("tense", "neutral", "warm", "uplift", "melancholy")

PageType = Literal[
    "illustration", "section_title", "number_callout", "calc_step", "before_after",
    "diagram", "phase_cards", "myth_card", "punchline_card", "timeline",
    "chat_bubble", "bank_screen", "cta_comment", "disclaimer_card", "outro",
]


# ---------- Story bible ----------
class Character(BaseModel):
    id: str
    name: str
    role: str                      # protagonis | pembanding | figuran
    descriptor: str = ""           # deskripsi visual TETAP, disisipkan ke prompt gambar


class StoryBible(BaseModel):
    topic: str
    angle: str = ""
    language: str = "id"
    characters: list[Character] = Field(default_factory=list)
    # angka kunci sebagai variabel agar konsisten di seluruh naskah,
    # mis. {"setoran_harian": "20000", "target": "100000000"}
    variables: dict[str, str] = Field(default_factory=dict)
    disclaimers: list[str] = Field(default_factory=list)
    is_fiction: bool = True        # untuk label "cerita ilustrasi"
    built: bool = False            # True setelah tahap 'bible' berjalan


# ---------- Beat sheet ----------
class Beat(BaseModel):
    id: str                        # hook | t1.. | s1.. | mitos | angka | ... | penutup
    kind: str = ""                 # hook | transformasi | strategi | mitos | angka | ...
    title: str
    goal: str
    key_points: list[str] = Field(default_factory=list)
    metaphor: str | None = None
    target_seconds: int = 60
    target_words: int = 0
    target_scenes: int = 0
    mood: str = "neutral"
    # syarat struktur (sumber tunggal: dipakai prompt LLM DAN lint)
    first_tag: str | None = None   # scene pertama beat wajib bertag ini
    last_tag: str | None = None    # scene terakhir beat wajib bertag ini
    min_tags: dict[str, int] = Field(default_factory=dict)
    max_tags: dict[str, int] = Field(default_factory=dict)


class BeatSheet(BaseModel):
    beats: list[Beat] = Field(default_factory=list)


# ---------- Storyboard ----------
class WordTiming(BaseModel):
    word: str
    start: float
    end: float


class Scene(BaseModel):
    id: int
    beat: str
    narration: str                       # teks kanonik (juga untuk subtitle)
    tts_text: str | None = None          # versi lisan hasil normalisasi
    tags: list[Tag] = Field(default_factory=list)
    notes: str = ""                      # rumus hitungan & sumber klaim
    image_prompt: str | None = None      # bahasa Inggris, tanpa teks di dalam gambar
    characters: list[str] = Field(default_factory=list)
    mood: Mood = "neutral"
    # diisi page mapper (lihat docs/design-video.md)
    page_type: PageType | None = None
    props: dict = Field(default_factory=dict)
    anchor_word: int | None = None
    sfx: list[str] = Field(default_factory=list)
    hold_after: float = 0.0
    # diisi tahap berikutnya
    audio_file: str | None = None
    image_file: str | None = None
    duration: float | None = None
    words: list[WordTiming] = Field(default_factory=list)


class Storyboard(BaseModel):
    title: str = ""
    style_prefix: str = ""
    scenes: list[Scene] = Field(default_factory=list)
