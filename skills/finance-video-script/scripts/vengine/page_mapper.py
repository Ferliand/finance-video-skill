"""Pemetaan otomatis Scene naskah ke katalog halaman (PageType) berdasarkan design-video.md."""
from __future__ import annotations

import re

from .schema import PageType, Scene, Storyboard

SECTION_START_RE = re.compile(
    r"^(Strategi|Transformasi|Langkah|Pelajaran)\s+(pertama|kedua|ketiga|keempat|kelima|kesatu|\d+)",
    re.IGNORECASE,
)
MYTH_RE = re.compile(r"\b(kebohongan|mitos|anggapan bahwa)\b", re.IGNORECASE)
BEFORE_AFTER_RE = re.compile(r"\b(dulu|tahun lalu|tiga tahun lalu)\b.{1,80}?\b(sekarang|hari ini)\b", re.IGNORECASE)
PHASE_RE = re.compile(r"\bfase\s+(pertama|kedua|ketiga|keempat)\b", re.IGNORECASE)
DIAGRAM_RE = re.compile(r"\b(kantong|pos)\s+(pertama|kedua|ketiga)\b", re.IGNORECASE)
BANK_RE = re.compile(r"\b(saldo|aplikasi bank|mobile banking|layar ponsel)\b", re.IGNORECASE)
CHAT_RE = re.compile(r'["“][^"”]{3,}["”]')


def map_scene_page(scene: Scene) -> tuple[PageType, dict]:
    """Tentukan PageType dan props dasar untuk satu scene sesuai prioritas di design-video.md."""
    tags = set(scene.tags)
    narration = scene.narration.strip()

    if "SECTION" in tags or SECTION_START_RE.search(narration):
        return "section_title", {"title": narration}

    if "PUNCH" in tags:
        return "punchline_card", {"text": narration}

    if "CALC" in tags or (scene.notes and any(op in scene.notes for op in "x*+÷/-")):
        return "calc_step", {"formula": scene.notes}

    if "NUMBER" in tags:
        return "number_callout", {}

    if BEFORE_AFTER_RE.search(narration):
        return "before_after", {}

    if PHASE_RE.search(narration):
        return "phase_cards", {}

    if DIAGRAM_RE.search(narration):
        return "diagram", {}

    if MYTH_RE.search(narration):
        return "myth_card", {}

    if "CTA" in tags:
        return "cta_comment", {}

    if CHAT_RE.search(narration):
        return "chat_bubble", {}

    if BANK_RE.search(narration):
        return "bank_screen", {}

    return "illustration", {}


def map_storyboard_pages(sb: Storyboard) -> Storyboard:
    """Petakan semua scene dalam storyboard ke page_type dan props yang sesuai."""
    for s in sb.scenes:
        ptype, props = map_scene_page(s)
        s.page_type = ptype
        if props:
            s.props = {**s.props, **props}
    return sb
