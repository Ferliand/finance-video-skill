"""Lint naskah: cek struktur, angka, klaim, dan gaya berdasarkan panduan-naskah.md.

error = pelanggaran struktur/angka/klaim (menahan pipeline)
warn  = pelanggaran gaya (dibaca manusia)
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass

from .brief import Brief
from .formats import WPM
from .schema import Beat, BeatSheet, Scene, Storyboard

SHORT_TAGS = {"PUNCH", "SECTION"}       # scene pendek (maks. 14 kata)
INSTRUMENT_RE = re.compile(
    r"\b(emas digital|emas|reksa dana|saham|kripto|crypto|deposito|obligasi|sbn|p2p)\b", re.I)
DISCLAIMER_RE = re.compile(r"bukan ajakan", re.I)
STAT_RE = re.compile(
    r"(\d+\s?%|\d+\s+persen)\s+(orang|pekerja|karyawan|masyarakat|pengusaha|anak muda|generasi muda|generasi|keluarga|penduduk|warga)", re.I)
PROMISE_RE = re.compile(r"\b(pasti untung|dijamin|garansi|bebas risiko|tanpa risiko)\b", re.I)
CONTRAST_RE = re.compile(r"\bbukan\b[^.!?]{0,80}?\b(tapi|tetapi|melainkan)\b", re.I)
FORMULA_RE = re.compile(
    r"((?:\d[\d.,]*)(?:\s*[×x*÷/+\-−]\s*\d[\d.,]*)+)\s*=\s*(\d[\d.,]*)")
RUPIAH_RE = re.compile(r"Rp\s?(\d[\d.,]*)(?:\s*(juta|ribu|miliar|m|rb))?", re.I)
_UNIT = {"juta": 1e6, "ribu": 1e3, "rb": 1e3, "miliar": 1e9, "m": 1e9}


@dataclass
class Issue:
    level: str            # "error" | "warn"
    code: str
    message: str
    scene: int | None = None
    beat: str | None = None

    def __str__(self) -> str:
        where = f" [scene {self.scene}]" if self.scene is not None else (
            f" [beat {self.beat}]" if self.beat else "")
        return f"{self.level.upper():5} {self.code}{where}: {self.message}"


# ---------- util ----------
def words(text: str) -> int:
    return len(text.split())


def sentences(text: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s]


def parse_id_number(s: str) -> float:
    """'20.000' -> 20000 ; '7,2' -> 7.2 (titik = pemisah ribuan, koma = desimal)."""
    s = s.strip().rstrip(".,")
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(".", "")
    return float(s)


def _eval_formula(expr: str) -> float | None:
    parts = re.split(r"(\s*[()×x*÷/+\-−]\s*)", expr)
    out = []
    for p in parts:
        q = p.strip()
        if not q:
            continue
        if q in "×x*":
            out.append("*")
        elif q in "÷/":
            out.append("/")
        elif q in "+":
            out.append("+")
        elif q in "-−":
            out.append("-")
        elif q in "()":
            out.append(q)
        else:
            out.append(repr(parse_id_number(q)))
    safe = " ".join(out)
    if not re.fullmatch(r"[0-9.+\-*/ e()]+", safe):
        return None
    try:
        return float(eval(safe, {"__builtins__": {}}, {}))   # noqa: S307 (whitelist di atas)
    except Exception:
        return None


def _norm_tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def ngrams(text: str, n: int) -> set[tuple[str, ...]]:
    t = _norm_tokens(text)
    return {tuple(t[i:i + n]) for i in range(len(t) - n + 1)}


# ---------- cek per beat (dipakai juga oleh tahap script untuk retry) ----------
def check_beat(scenes: list[Scene], beat: Beat) -> list[Issue]:
    issues: list[Issue] = []
    bid = beat.id
    if not scenes:
        return [Issue("error", "beat_kosong", "tidak ada scene", beat=bid)]
    if beat.first_tag and beat.first_tag not in scenes[0].tags:
        issues.append(Issue("error", "tag_awal", f"scene pertama harus bertag {beat.first_tag}", scenes[0].id, bid))
    if beat.last_tag and beat.last_tag not in scenes[-1].tags:
        issues.append(Issue("error", "tag_akhir", f"scene terakhir harus bertag {beat.last_tag}", scenes[-1].id, bid))
    for tag, n in beat.min_tags.items():
        c = sum(tag in s.tags for s in scenes)
        if c < n:
            issues.append(Issue("error", "tag_kurang", f"tag {tag}: {c} (minimal {n})", beat=bid))
    for tag, n in beat.max_tags.items():
        c = sum(tag in s.tags for s in scenes)
        if c > n:
            issues.append(Issue("error", "tag_lebih", f"tag {tag}: {c} (maksimal {n})", beat=bid))
    if beat.target_words:
        w = sum(words(s.narration) for s in scenes)
        dev = (w - beat.target_words) / beat.target_words
        if abs(dev) > 0.35:
            issues.append(Issue("error", "kata_beat", f"{w} kata vs target {beat.target_words} ({dev:+.0%})", beat=bid))
        elif abs(dev) > 0.20:
            issues.append(Issue("warn", "kata_beat", f"{w} kata vs target {beat.target_words} ({dev:+.0%})", beat=bid))
    for s in scenes:
        if not s.narration.strip():
            issues.append(Issue("error", "narasi_kosong", "narasi kosong", s.id, bid))
            continue
        w = words(s.narration)
        if SHORT_TAGS & set(s.tags):
            if w > 14:
                issues.append(Issue("warn", "scene_pendek", f"{w} kata (maks. 14 untuk PUNCH/SECTION)", s.id, bid))
        elif w < 15 or w > 35:
            issues.append(Issue("warn", "panjang_scene", f"{w} kata (target 15-35)", s.id, bid))
        for sent in sentences(s.narration):
            if words(sent) > 30:
                issues.append(Issue("error", "kalimat_panjang", f"kalimat {words(sent)} kata (maks. 30)", s.id, bid))
        if ({"CALC", "NUMBER"} & set(s.tags)) and not FORMULA_RE.search(s.notes):
            issues.append(Issue("error", "rumus_hilang", "scene CALC/NUMBER tanpa rumus 'A x B = C' di notes", s.id, bid))
        for m in FORMULA_RE.finditer(s.notes):
            val = _eval_formula(m.group(1))
            try:
                claimed = parse_id_number(m.group(2))
            except ValueError:
                continue
            if val is None or not math.isclose(val, claimed, rel_tol=1e-6):
                issues.append(Issue("error", "rumus_salah", f"'{m.group(0)}' tidak cocok (hasil {val})", s.id, bid))
        if STAT_RE.search(s.narration):
            issues.append(Issue("error", "statistik_tanpa_sumber", "persentase 'orang' tanpa sumber", s.id, bid))
        if PROMISE_RE.search(s.narration):
            issues.append(Issue("warn", "janji_hasil", "kemungkinan janji hasil/tanpa risiko", s.id, bid))
    return issues


# ---------- lint penuh ----------
def _known_values(sb: Storyboard, brief: Brief) -> set[float]:
    vals: set[float] = set()
    for v in brief.angka_kunci.values():
        try:
            vals.add(float(v))
        except (TypeError, ValueError):
            pass
    for s in sb.scenes:
        for tok in re.findall(r"\d[\d.,]*", s.notes):
            try:
                vals.add(parse_id_number(tok))
            except ValueError:
                pass
    return vals


def lint(
    sb: Storyboard,
    beats: BeatSheet,
    brief: Brief,
    references: list[str] | None = None,
    overlap_n: int = 8,
) -> list[Issue]:
    issues: list[Issue] = []
    if not sb.scenes:
        return [Issue("error", "naskah_kosong", "belum ada scene")]

    by_beat: dict[str, list[Scene]] = {}
    for s in sb.scenes:
        by_beat.setdefault(s.beat, []).append(s)

    for beat in beats.beats:
        if beat.id not in by_beat:
            issues.append(Issue("error", "beat_hilang", "beat belum ditulis", beat=beat.id))
            continue
        issues.extend(check_beat(by_beat[beat.id], beat))

    # total kata
    total = sum(words(s.narration) for s in sb.scenes)
    target = round(brief.durasi_menit * WPM[brief.format])
    dev = (total - target) / target
    if abs(dev) > 0.08:
        issues.append(Issue("error", "total_kata", f"{total} kata vs target {target} ({dev:+.0%}, batas ±8%)"))

    # panjang kalimat rata-rata (scene biasa saja)
    sent_lens = [words(x) for s in sb.scenes if not (SHORT_TAGS & set(s.tags)) for x in sentences(s.narration)]
    if sent_lens:
        avg = sum(sent_lens) / len(sent_lens)
        if not 12 <= avg <= 18:
            issues.append(Issue("warn", "rata_kalimat", f"rata-rata {avg:.1f} kata/kalimat (target 12-18)"))

    # kontras "bukan X, tapi Y"
    contrast = sum(len(CONTRAST_RE.findall(s.narration)) for s in sb.scenes)
    need = max(1, math.floor(0.6 * brief.durasi_menit))
    if contrast < need:
        issues.append(Issue("warn", "kontras_kurang", f"{contrast} kontras 'bukan..tapi' (minimal {need})"))

    # CTA total
    cta = sum("CTA" in s.tags for s in sb.scenes)
    cta_max = 1 if brief.format == "A" else 2
    if cta > cta_max:
        issues.append(Issue("error", "cta_lebih", f"{cta} ajakan komentar (maksimal {cta_max})"))

    # disclaimer jika instrumen keuangan disebut
    text_all = " ".join(s.narration for s in sb.scenes)
    inst = list(brief.instrumen_boleh_disebut)
    mentioned = bool(INSTRUMENT_RE.search(text_all)) or any(i.lower() in text_all.lower() for i in inst)
    if mentioned and not DISCLAIMER_RE.search(text_all):
        issues.append(Issue("error", "disclaimer_hilang", "instrumen keuangan disebut tanpa kalimat disclaimer ('bukan ajakan ...')"))

    # nilai rupiah di narasi yang tidak punya dasar
    known = _known_values(sb, brief)
    for s in sb.scenes:
        for m in RUPIAH_RE.finditer(s.narration):
            try:
                v = parse_id_number(m.group(1)) * _UNIT.get((m.group(2) or "").lower(), 1)
            except ValueError:
                continue
            if not any(math.isclose(v, k, rel_tol=1e-6) for k in known):
                issues.append(Issue("warn", "rupiah_tanpa_dasar",
                                    f"'{m.group(0)}' tidak ada di angka_kunci/notes", s.id, s.beat))

    # tumpang tindih dengan teks referensi
    if references:
        mine = ngrams(text_all, overlap_n)
        for i, ref in enumerate(references):
            hit = mine & ngrams(ref, overlap_n)
            if hit:
                example = " ".join(sorted(hit)[0])
                issues.append(Issue("error", "mirip_referensi",
                                    f"{len(hit)} rangkaian {overlap_n}-kata sama dengan referensi #{i + 1}, mis. '{example}'"))
    return issues


def format_report(issues: list[Issue]) -> str:
    if not issues:
        return "Lint: bersih (0 error, 0 warn)."
    e = sum(i.level == "error" for i in issues)
    w = len(issues) - e
    lines = [f"Lint: {e} error, {w} warn"]
    lines += [f"  {i}" for i in sorted(issues, key=lambda x: (x.level != "error", x.scene or 0))]
    return "\n".join(lines)
