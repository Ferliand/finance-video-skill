"""Pembantu tes: responder LLM palsu yang patuh pada syarat beat."""
from __future__ import annotations

import json
import re

from vengine.schema import Beat

FILLER = ("uang harian perlu diberi tugas yang jelas sejak pertama kali diterima "
          "supaya hasilnya tidak habis tanpa bekas").split()


def _regular(words: int) -> str:
    out, i = [], 0
    while len(out) < words:
        out.append(FILLER[i % len(FILLER)])
        i += 1
    chunks = [" ".join(out[j:j + 15]) for j in range(0, len(out), 15)]
    return ". ".join(c.capitalize() for c in chunks) + "."


def scenes_for_beat(beat: Beat) -> list[dict]:
    specials: list[dict] = []
    first = last = None
    if beat.first_tag:
        first = {"narration": "Strategi kesatu uang dipisah di awal", "tags": [beat.first_tag]}
    if beat.last_tag:
        last = {"narration": "Di bagian berikutnya kita bahas langkah selanjutnya", "tags": [beat.last_tag]}
    for tag, n in beat.min_tags.items():
        for _ in range(n):
            if tag == "PUNCH":
                specials.append({"narration": "Kalau nunggu sisa tidak akan ada sisa", "tags": ["PUNCH"]})
            elif tag == "CALC":
                specials.append({"narration": _regular(20), "tags": ["CALC"], "notes": "20.000 x 30 = 600.000"})
            elif tag == "CTA":
                specials.append({"narration": _regular(20), "tags": ["CTA"]})
    fixed = ([first] if first else []) + specials + ([last] if last else [])
    fixed_words = sum(len(s["narration"].split()) for s in fixed)
    n_regular = max(1, beat.target_scenes - len(fixed))
    per = max(15, round((beat.target_words - fixed_words) / n_regular))
    regular = [{"narration": _regular(per), "tags": [], "image_prompt": "flat vector scene, daily worker at night"}
               for _ in range(n_regular)]
    body = regular[:1] + specials + regular[1:]
    scenes = ([first] if first else []) + body + ([last] if last else [])
    for s in scenes:
        s.setdefault("image_prompt", None)
        s.setdefault("characters", [])
        s.setdefault("mood", beat.mood)
        s.setdefault("notes", "")
    return scenes


def good_responder(system: str, user: str) -> str:
    m = re.search(r"<BEAT>(.*?)</BEAT>", user, re.S)
    beat = Beat.model_validate_json(m.group(1))
    return json.dumps({"scenes": scenes_for_beat(beat)}, ensure_ascii=False)
