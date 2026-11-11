"""Render storyboard (scenes.json) dengan animasi per-frame (kinetic text, count-up, Ken Burns, karaoke subtitle), audio TTS, dan MP4."""
from __future__ import annotations

import asyncio
import math
import re
import subprocess
import textwrap
from pathlib import Path
from typing import Callable

from PIL import Image, ImageDraw, ImageFont

from .page_mapper import map_storyboard_pages
from .project import Project
from .schema import Scene, WordTiming

# Palet warna dari references/design-video.md
BG_CREAM = (246, 241, 231)     # #F6F1E7
BG_DARK = (20, 24, 31)         # #14181F
CARD_DARK = (30, 41, 59)       # #1E293B
INK = (31, 41, 55)             # #1F2937
ACCENT = (232, 163, 61)        # #E8A33D
POSITIVE = (46, 125, 91)       # #2E7D5B
NEGATIVE = (184, 67, 47)       # #B8432F
WHITE = (255, 255, 255)
MUTED = (148, 163, 184)

DEFAULT_VOICE = "id-ID-ArdiNeural"
_FONT_CACHE: dict[tuple[int, bool], ImageFont.FreeTypeFont | ImageFont.ImageFont] = {}


def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    key = (size, bold)
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]
    candidates = (
        ["segoeuib.ttf", "arialbd.ttf", "calibrib.ttf", "DejaVuSans-Bold.ttf"]
        if bold
        else ["segoeui.ttf", "arial.ttf", "calibri.ttf", "DejaVuSans.ttf"]
    )
    for name in candidates:
        try:
            font = ImageFont.truetype(name, size)
            _FONT_CACHE[key] = font
            return font
        except OSError:
            continue
    font = ImageFont.load_default(size=size)
    _FONT_CACHE[key] = font
    return font


def _clamp(val: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, val))


def _ease_out_cubic(x: float) -> float:
    x = _clamp(x)
    return 1.0 - (1.0 - x) ** 3


def _ease_out_back(x: float) -> float:
    x = _clamp(x)
    c1 = 1.70158
    c3 = c1 + 1.0
    return 1.0 + c3 * ((x - 1.0) ** 3) + c1 * ((x - 1.0) ** 2)


def _format_id_int(val: float) -> str:
    n = int(round(val))
    return f"{n:,}".replace(",", ".")


# ---------- Word Timing & Karaoke Helpers ----------
def compute_word_timings(text: str, duration: float) -> list[WordTiming]:
    """Hitung estimasi timestamp mulai & selesai per kata secara proporsional terhadap panjang kata & tanda baca."""
    tokens = [w for w in text.strip().split() if w]
    if not tokens:
        return []
    weights = []
    for tok in tokens:
        base = max(2, len(tok.rstrip(".,!?;:")))
        pause = 2.5 if tok.endswith((".", "!", "?")) else (1.4 if tok.endswith((",", ";", ":")) else 0.0)
        weights.append(base + pause)
    total_w = sum(weights) or 1.0
    out: list[WordTiming] = []
    cursor = 0.0
    for i, (tok, w) in enumerate(zip(tokens, weights)):
        span = duration * (w / total_w)
        end = duration if i == len(tokens) - 1 else round(cursor + span, 3)
        out.append(WordTiming(word=tok, start=round(cursor, 3), end=end))
        cursor = end
    return out


def active_word_index(words: list[WordTiming], t: float) -> int:
    """Kembalikan indeks kata yang sedang aktif diucapkan pada detik t."""
    if not words:
        return 0
    for i, w in enumerate(words):
        if w.start <= t <= w.end:
            return i
    if t < words[0].start:
        return 0
    return len(words) - 1


def _draw_wrapped_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    fill: tuple[int, int, int],
    center_x: int,
    start_y: int,
    max_chars: int,
    line_spacing: int = 14,
) -> int:
    lines = textwrap.wrap(text, width=max_chars) or [text]
    y = start_y
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        draw.text((center_x - w // 2, y), line, font=font, fill=fill)
        y += h + line_spacing
    return y


def _draw_karaoke_subtitle(
    draw: ImageDraw.ImageDraw,
    scene: Scene,
    t: float,
    duration: float,
    width: int,
    height: int,
    is_vertical: bool,
) -> None:
    """Gambar subtitle dengan highlight warna ACCENT pada kata yang sedang aktif diucapkan."""
    words = scene.words or compute_word_timings(scene.narration, duration)
    if not words:
        return
    act_idx = active_word_index(words, t)
    chunk_size = 7 if is_vertical else 11
    page_idx = act_idx // chunk_size
    chunk = words[page_idx * chunk_size : (page_idx + 1) * chunk_size]
    local_act = act_idx - page_idx * chunk_size

    margin_x = int(width * 0.06)
    sub_box_top = int(height * 0.72) if is_vertical else int(height * 0.74)
    sub_box_bot = int(height * 0.89) if is_vertical else int(height * 0.90)

    draw.rounded_rectangle(
        [margin_x, sub_box_top, width - margin_x, sub_box_bot],
        radius=26,
        fill=(18, 23, 33),
        outline=ACCENT,
        width=2,
    )

    font = _load_font(42 if is_vertical else 38, bold=True)
    max_line_w = (width - 2 * margin_x) - 70

    # Susun kata dalam baris
    lines: list[list[tuple[int, str, int]]] = []
    cur_line: list[tuple[int, str, int]] = []
    cur_w = 0
    space_w = draw.textbbox((0, 0), " ", font=font)[2]

    for idx, wt in enumerate(chunk):
        wb = draw.textbbox((0, 0), wt.word, font=font)
        ww = wb[2] - wb[0]
        if cur_line and cur_w + space_w + ww > max_line_w:
            lines.append(cur_line)
            cur_line = [(idx, wt.word, ww)]
            cur_w = ww
        else:
            cur_w += (space_w if cur_line else 0) + ww
            cur_line.append((idx, wt.word, ww))
    if cur_line:
        lines.append(cur_line)

    line_h = 54 if is_vertical else 48
    total_h = len(lines) * line_h
    start_y = (sub_box_top + sub_box_bot - total_h) // 2

    for r_i, line in enumerate(lines):
        row_w = sum(x[2] for x in line) + space_w * max(0, len(line) - 1)
        x = width // 2 - row_w // 2
        y = start_y + r_i * line_h
        for idx, word_str, ww in line:
            if idx == local_act:
                pad_x, pad_y = 10, 6
                draw.rounded_rectangle(
                    [x - pad_x, y - pad_y, x + ww + pad_x, y + line_h - 8],
                    radius=12,
                    fill=ACCENT,
                )
                draw.text((x, y), word_str, font=font, fill=BG_DARK)
            elif idx < local_act:
                draw.text((x, y), word_str, font=font, fill=WHITE)
            else:
                draw.text((x, y), word_str, font=font, fill=(175, 185, 200))
            x += ww + space_w


# ---------- Procedural Animated Flat-Vector Illustration ----------
def _draw_animated_vector_art(
    draw: ImageDraw.ImageDraw,
    scene: Scene,
    t: float,
    duration: float,
    box: tuple[int, int, int, int],
    is_dark: bool,
) -> None:
    """Gambar ilustrasi flat-vector kontekstual dengan animasi bergerak (floating, rising bars, coin drop)."""
    x1, y1, x2, y2 = box
    w, h = x2 - x1, y2 - y1
    cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
    p = _clamp(t / max(0.1, duration))
    bob = int(math.sin(t * 3.2) * 12)
    pulse = int(math.cos(t * 2.5) * 8)

    text_key = f"{scene.image_prompt or ''} {scene.narration}".lower()

    # Latar belakang lingkaran cahaya lembut yang bernapas (breathing rings)
    ring_r = int(min(w, h) * 0.34) + pulse
    ring_col = (38, 52, 74) if is_dark else (236, 226, 208)
    draw.ellipse([cx - ring_r, cy - ring_r, cx + ring_r, cy + ring_r], fill=ring_col)

    if any(k in text_key for k in ("wallet", "dompet", "kosong", "habis", "menguap")):
        # Ilustrasi Dompet Terbuka + Koin Melayang
        ww, wh = 260, 170
        wx, wy = cx - ww // 2, cy - wh // 2 + bob
        draw.rounded_rectangle([wx, wy, wx + ww, wy + wh], radius=24, fill=NEGATIVE, outline=INK, width=4)
        draw.rounded_rectangle([wx + 20, wy - 22, wx + ww - 30, wy + 25], radius=12, fill=ACCENT, outline=INK, width=3)
        # Kancing dompet
        draw.rounded_rectangle([wx + ww - 65, wy + 55, wx + ww + 8, wy + 115], radius=14, fill=INK)
        draw.ellipse([wx + ww - 45, wy + 75, wx + ww - 25, wy + 95], fill=ACCENT)
        # Koin melayang keluar
        for i in range(3):
            offset_y = int(((p * 120 + i * 45) % 130))
            coin_x = cx - 70 + i * 70 + int(math.sin(t * 3 + i) * 14)
            coin_y = wy - 30 - offset_y
            draw.ellipse([coin_x - 24, coin_y - 24, coin_x + 24, coin_y + 24], fill=ACCENT, outline=INK, width=3)

    elif any(k in text_key for k in ("jar", "toples", "envelope", "amplop", "pisahkan", "rekening", "lembar")):
        # Ilustrasi Dua Toples / Pos Keuangan dengan Level Tabungan Naik & Koin Jatuh
        jar_w, jar_h = 150, 210
        for idx, (label, col, fill_ratio) in enumerate([("TABUNGAN", POSITIVE, _ease_out_cubic(p)), ("HARIAN", ACCENT, 0.45)]):
            jx = cx - 180 + idx * 210
            jy = cy - jar_h // 2 + 20
            # Badan toples
            draw.rounded_rectangle([jx, jy, jx + jar_w, jy + jar_h], radius=22, fill=WHITE, outline=INK, width=4)
            # Isi toples yang naik
            fill_h = int((jar_h - 24) * _clamp(fill_ratio, 0.15, 0.9))
            draw.rounded_rectangle(
                [jx + 10, jy + jar_h - 10 - fill_h, jx + jar_w - 10, jy + jar_h - 10],
                radius=14,
                fill=col,
            )
            # Tutup toples
            draw.rounded_rectangle([jx + 20, jy - 20, jx + jar_w - 20, jy + 6], radius=8, fill=INK)
            f_lbl = _load_font(22, bold=True)
            lb = draw.textbbox((0, 0), label, font=f_lbl)
            draw.text((jx + (jar_w - (lb[2] - lb[0])) // 2, jy + jar_h + 14), label, font=f_lbl, fill=WHITE if is_dark else INK)

        # Animasi koin jatuh ke toples Tabungan
        drop_y = int((t * 180) % 110)
        coin_cx = cx - 180 + jar_w // 2
        coin_cy = cy - jar_h // 2 - 90 + drop_y
        draw.ellipse([coin_cx - 26, coin_cy - 26, coin_cx + 26, coin_cy + 26], fill=ACCENT, outline=INK, width=3)

    else:
        # Ilustrasi Grafik Pertumbuhan Dinamis + Koin Rp Bersinar
        num_bars = 5
        bar_w = 48
        gap = 26
        total_bw = num_bars * bar_w + (num_bars - 1) * gap
        start_bx = cx - total_bw // 2
        base_by = cy + 120
        heights = [70, 115, 160, 215, 275]

        points: list[tuple[int, int]] = []
        for i, target_h in enumerate(heights):
            local_p = _ease_out_cubic(_clamp((p * 1.4) - i * 0.12))
            cur_h = max(18, int(target_h * local_p))
            bx = start_bx + i * (bar_w + gap)
            by = base_by - cur_h
            col = POSITIVE if i == num_bars - 1 else ACCENT
            draw.rounded_rectangle([bx, by, bx + bar_w, base_by], radius=10, fill=col, outline=INK, width=3)
            points.append((bx + bar_w // 2, by - 20))

        # Garis tren penghubung di atas batang
        if len(points) >= 2:
            draw.line(points, fill=POSITIVE if not is_dark else WHITE, width=5)
            for px, py in points:
                draw.ellipse([px - 8, py - 8, px + 8, py + 8], fill=ACCENT, outline=INK, width=2)

        # Lencana koin melayang di sudut atas grafik
        badge_r = 46
        bx_c, by_c = cx - 130, cy - 110 + bob
        draw.ellipse([bx_c - badge_r, by_c - badge_r, bx_c + badge_r, by_c + badge_r], fill=ACCENT, outline=INK, width=3)
        f_rp = _load_font(34, bold=True)
        rb = draw.textbbox((0, 0), "Rp", font=f_rp)
        draw.text((bx_c - (rb[2] - rb[0]) // 2, by_c - (rb[3] - rb[1]) // 2 - 4), "Rp", font=f_rp, fill=BG_DARK)


def _extract_formula_numbers(notes: str) -> tuple[str, float | None]:
    """Ekstrak ekspresi kiri dan nilai target kanan dari rumus 'A x B = C'."""
    m = re.search(r"([^=]+)=\s*(\d[\d.,]*)", notes or "")
    if not m:
        return notes or "20.000", None
    lhs = m.group(1).strip().replace("x", "×").replace("*", "×")
    raw_rhs = m.group(2).strip().rstrip(".,").replace(".", "").replace(",", ".")
    try:
        return lhs, float(raw_rhs)
    except ValueError:
        return lhs, None


# ---------- Core Animated Frame Renderer ----------
def render_scene_frame_at(
    scene: Scene,
    t: float,
    duration: float,
    fmt: str = "B",
    topic: str = "",
) -> Image.Image:
    """Render satu frame Image pada waktu t (detik) dengan animasi penuh."""
    duration = max(0.5, duration)
    t = _clamp(t, 0.0, duration)
    p = t / duration
    intro_p = _ease_out_cubic(_clamp(t / 0.45))

    is_vertical = fmt == "S"
    width, height = (1080, 1920) if is_vertical else (1920, 1080)
    ptype = scene.page_type or "illustration"

    is_dark = ptype in ("punchline_card", "section_title", "cta_comment") or scene.mood == "tense"
    bg_color = BG_DARK if is_dark else BG_CREAM
    img = Image.new("RGB", (width, height), color=bg_color)
    draw = ImageDraw.Draw(img)

    # 1. Animated Progress Bar di tepi atas layar
    bar_h = 14
    draw.rectangle([0, 0, width, bar_h], fill=(40, 48, 62) if is_dark else (222, 214, 200))
    prog_w = max(12, int(width * p))
    draw.rectangle([0, 0, prog_w, bar_h], fill=ACCENT)

    font_badge = _load_font(28 if is_vertical else 24, bold=True)
    font_title = _load_font(60 if is_vertical else 54, bold=True)
    font_formula = _load_font(72 if is_vertical else 66, bold=True)

    cx = width // 2
    margin_x = int(width * 0.07)

    # Header dengan efek slide-in halus
    header_y = int(height * 0.05) + int((1.0 - intro_p) * -25)
    badge_text = f"SCENE {scene.id:02d}  •  {scene.beat.upper()}"
    draw.text((margin_x, header_y), badge_text, font=font_badge, fill=ACCENT)
    if topic:
        t_bbox = draw.textbbox((0, 0), topic.upper(), font=font_badge)
        draw.text((width - margin_x - (t_bbox[2] - t_bbox[0]), header_y), topic.upper(), font=font_badge, fill=MUTED)

    words = scene.words or compute_word_timings(scene.narration, duration)
    act_idx = active_word_index(words, t)

    # 2. Render per page_type dengan animasi spesifik
    if ptype == "punchline_card":
        # Kinetic Typography: Kata muncul satu per satu sesuai pembicaraan + kata aktif disorot ACCENT
        pill_w, pill_h = 340, 56
        pill_y = int(height * 0.25) + int((1.0 - intro_p) * 40)
        draw.rounded_rectangle([cx - pill_w // 2, pill_y, cx + pill_w // 2, pill_y + pill_h], radius=28, fill=ACCENT)
        lbl = "PRINSIP UTAMA"
        lb = draw.textbbox((0, 0), lbl, font=font_badge)
        draw.text((cx - (lb[2] - lb[0]) // 2, pill_y + 12), lbl, font=font_badge, fill=BG_DARK)

        visible_words = [w.word for i, w in enumerate(words) if i <= act_idx] or [scene.narration]
        partial_text = " ".join(visible_words)
        text_y = int(height * 0.37)
        end_y = _draw_wrapped_text(
            draw,
            f'"{partial_text}"',
            font_title,
            WHITE,
            cx,
            text_y,
            max_chars=20 if is_vertical else 34,
            line_spacing=22,
        )
        # Garis bawah yang memanjang sesuai progres kalimat
        line_half = int(220 * _ease_out_cubic(p))
        draw.rounded_rectangle([cx - line_half, end_y + 36, cx + line_half, end_y + 46], radius=5, fill=ACCENT)

    elif ptype == "section_title":
        # Slide-up title + expanding ring
        slide_offset = int((1.0 - intro_p) * 110)
        ring_r = int(140 + 40 * math.sin(t * 2.0))
        draw.ellipse([cx - ring_r, height // 2 - ring_r, cx + ring_r, height // 2 + ring_r], outline=(45, 55, 72), width=4)

        pill_w, pill_h = 280, 54
        pill_y = int(height * 0.32) + slide_offset
        draw.rounded_rectangle([cx - pill_w // 2, pill_y, cx + pill_w // 2, pill_y + pill_h], radius=27, fill=ACCENT)
        lbl = "BAGIAN BARU"
        lb = draw.textbbox((0, 0), lbl, font=font_badge)
        draw.text((cx - (lb[2] - lb[0]) // 2, pill_y + 11), lbl, font=font_badge, fill=BG_DARK)

        _draw_wrapped_text(
            draw,
            scene.narration,
            font_title,
            WHITE,
            cx,
            int(height * 0.42) + slide_offset,
            max_chars=22 if is_vertical else 36,
            line_spacing=20,
        )

    elif ptype in ("calc_step", "number_callout"):
        # Count-up angka dinamis + progress bar akumulasi
        card_top = int(height * 0.16) + int((1.0 - intro_p) * 50)
        card_bot = int(height * 0.62)
        draw.rounded_rectangle([margin_x, card_top, width - margin_x, card_bot], radius=32, fill=WHITE, outline=ACCENT, width=5)

        draw.text((margin_x + 45, card_top + 38), "SIMULASI HITUNGAN OTOMATIS", font=font_badge, fill=POSITIVE)

        lhs, target_val = _extract_formula_numbers(scene.props.get("formula") or scene.notes)
        count_p = _ease_out_cubic(_clamp((p - 0.12) / 0.72))

        if target_val is not None:
            current_val = target_val * count_p
            lhs_y = card_top + 120
            _draw_wrapped_text(draw, f"Rp {lhs} =", _load_font(46, bold=True), MUTED, cx, lhs_y, max_chars=30)
            val_str = f"Rp {_format_id_int(current_val)}"
            _draw_wrapped_text(draw, val_str, font_formula, POSITIVE, cx, lhs_y + 85, max_chars=24)
        else:
            _draw_wrapped_text(draw, f"Rp {lhs}", font_formula, INK, cx, (card_top + card_bot) // 2 - 40, max_chars=24)

        # Progress meter di dalam kartu hitungan
        meter_x1, meter_x2 = margin_x + 60, width - margin_x - 60
        meter_y = card_bot - 70
        draw.rounded_rectangle([meter_x1, meter_y, meter_x2, meter_y + 24], radius=12, fill=(230, 234, 240))
        fill_x2 = meter_x1 + max(24, int((meter_x2 - meter_x1) * count_p))
        draw.rounded_rectangle([meter_x1, meter_y, fill_x2, meter_y + 24], radius=12, fill=POSITIVE)

        _draw_karaoke_subtitle(draw, scene, t, duration, width, height, is_vertical)

    elif ptype == "myth_card":
        # Kartu klaim mitos + animasi coretan merah menyapu (strikethrough sweep)
        card_top = int(height * 0.20)
        card_bot = int(height * 0.60)
        draw.rounded_rectangle([margin_x, card_top, width - margin_x, card_bot], radius=32, fill=WHITE, outline=NEGATIVE, width=5)
        draw.text((margin_x + 45, card_top + 36), "MITOS / ANGGAPAN KELIRU", font=font_badge, fill=NEGATIVE)

        text_y = card_top + 120
        end_y = _draw_wrapped_text(
            draw,
            scene.narration,
            _load_font(48 if is_vertical else 44, bold=True),
            INK,
            cx,
            text_y,
            max_chars=24 if is_vertical else 38,
            line_spacing=18,
        )
        # Animasi garis coret merah menyapu setelah p > 0.25
        strike_p = _ease_out_cubic(_clamp((p - 0.20) / 0.45))
        if strike_p > 0:
            sx1 = margin_x + 70
            sx2 = sx1 + int((width - 2 * margin_x - 140) * strike_p)
            sy_mid = (text_y + end_y) // 2
            draw.line([(sx1, sy_mid - 20), (sx2, sy_mid + 20)], fill=NEGATIVE, width=12)

        _draw_karaoke_subtitle(draw, scene, t, duration, width, height, is_vertical)

    elif ptype == "before_after":
        # Split screen DULU vs SEKARANG dengan garis pembelah menyapu
        top_box = (margin_x, int(height * 0.14), width - margin_x, int(height * 0.38))
        bot_box = (margin_x, int(height * 0.42), width - margin_x, int(height * 0.66))

        draw.rounded_rectangle(top_box, radius=26, fill=(252, 232, 228), outline=NEGATIVE, width=4)
        draw.text((top_box[0] + 35, top_box[1] + 24), "KONDISI LAMA (DULU)", font=font_badge, fill=NEGATIVE)

        reveal_p = _ease_out_cubic(_clamp((p - 0.25) / 0.45))
        if reveal_p > 0.05:
            offset = int((1.0 - reveal_p) * 80)
            b_box = (bot_box[0], bot_box[1] + offset, bot_box[2], bot_box[3] + offset)
            draw.rounded_rectangle(b_box, radius=26, fill=(225, 245, 235), outline=POSITIVE, width=4)
            draw.text((b_box[0] + 35, b_box[1] + 24), "KONDISI SEKARANG", font=font_badge, fill=POSITIVE)

        _draw_karaoke_subtitle(draw, scene, t, duration, width, height, is_vertical)

    elif ptype == "cta_comment":
        # Kartu komentar dengan animasi mengetik (typewriter) + kursor berkedip
        card_top = int(height * 0.18) + int((1.0 - intro_p) * 45)
        card_bot = int(height * 0.64)
        draw.rounded_rectangle([margin_x, card_top, width - margin_x, card_bot], radius=32, fill=CARD_DARK, outline=ACCENT, width=4)
        _draw_wrapped_text(draw, "TULIS KOMITMENMU DI KOMENTAR", font_badge, ACCENT, cx, card_top + 45, max_chars=34)

        # Mock kotak input komentar dengan efek ketikan
        input_y1 = card_top + 125
        input_y2 = input_y1 + 110
        draw.rounded_rectangle([margin_x + 50, input_y1, width - margin_x - 50, input_y2], radius=20, fill=BG_DARK, outline=WHITE, width=3)

        cta_sample = "Hari ke-1"
        typed_len = max(1, int(len(cta_sample) * _clamp(p * 1.6)))
        cursor_char = "|" if int(t * 4) % 2 == 0 else " "
        typed_str = f"💬  {cta_sample[:typed_len]}{cursor_char}"
        draw.text((margin_x + 85, input_y1 + 26), typed_str, font=_load_font(46, bold=True), fill=ACCENT)

        _draw_karaoke_subtitle(draw, scene, t, duration, width, height, is_vertical)

    else:
        # Illustration scene: Kanvas Flat-Vector dengan Ken Burns Zoom & Pan + Karaoke Subtitle
        art_top = int(height * 0.12)
        art_bot = int(height * 0.66)
        card_fill = CARD_DARK if is_dark else WHITE
        border_col = ACCENT if is_dark else (218, 208, 192)

        # Render art di layer tersendiri lalu terapkan Ken Burns zoom (1.0 -> 1.08)
        box_w = width - 2 * margin_x
        box_h = art_bot - art_top
        art_layer = Image.new("RGB", (box_w, box_h), color=card_fill)
        art_draw = ImageDraw.Draw(art_layer)
        _draw_animated_vector_art(art_draw, scene, t, duration, (0, 0, box_w, box_h), is_dark)

        zoom = 1.0 + 0.08 * p
        crop_w = int(box_w / zoom)
        crop_h = int(box_h / zoom)
        pan_x = int((box_w - crop_w) * (0.5 + 0.3 * math.sin(p * math.pi)))
        pan_y = int((box_h - crop_h) * 0.5)
        zoomed_art = art_layer.crop((pan_x, pan_y, pan_x + crop_w, pan_y + crop_h)).resize(
            (box_w, box_h), Image.Resampling.BILINEAR
        )
        img.paste(zoomed_art, (margin_x, art_top))
        draw.rounded_rectangle([margin_x, art_top, width - margin_x, art_bot], radius=28, outline=border_col, width=4)

        _draw_karaoke_subtitle(draw, scene, t, duration, width, height, is_vertical)

    return img


def render_scene_frame(
    scene: Scene,
    out_path: Path,
    fmt: str = "B",
    topic: str = "",
    t: float = 1.0,
    duration: float = 3.0,
) -> Path:
    """Simpan satu snapshot PNG dari scene (default pada t=1.0 dtk untuk thumbnail/pratinjau)."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img = render_scene_frame_at(scene, t=t, duration=duration, fmt=fmt, topic=topic)
    img.save(out_path, format="PNG")
    return out_path


def _probe_audio_duration(audio_path: Path) -> float:
    """Baca durasi file audio dalam detik menggunakan ffmpeg."""
    import imageio_ffmpeg

    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    proc = subprocess.run(
        [ffmpeg_exe, "-i", str(audio_path)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", proc.stderr)
    if not m:
        return 3.0
    hours, mins, secs = int(m.group(1)), int(m.group(2)), float(m.group(3))
    return max(0.5, hours * 3600 + mins * 60 + secs)


def synthesize_tts(text: str, out_path: Path, voice: str = DEFAULT_VOICE) -> float:
    """Hasilkan file MP3 dari teks Bahasa Indonesia menggunakan edge-tts dan kembalikan durasinya."""
    import edge_tts

    out_path.parent.mkdir(parents=True, exist_ok=True)

    async def _run() -> None:
        comm = edge_tts.Communicate(text, voice)
        await comm.save(str(out_path))

    asyncio.run(_run())
    return _probe_audio_duration(out_path)


def _render_animated_segment(
    ffmpeg_exe: str,
    scene: Scene,
    audio_path: Path,
    seg_path: Path,
    duration: float,
    fmt: str,
    topic: str,
    fps: int = 15,
) -> None:
    """Pipe rangkaian frame animasi RGB langsung ke FFmpeg untuk menghasilkan segmen MP4 yang bergerak halus."""
    is_vertical = fmt == "S"
    width, height = (1080, 1920) if is_vertical else (1920, 1080)
    total_frames = max(2, int(round(duration * fps)))

    cmd = [
        ffmpeg_exe,
        "-y",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-pix_fmt", "rgb24",
        "-s", f"{width}x{height}",
        "-r", str(fps),
        "-i", "-",
        "-i", str(audio_path),
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-shortest",
        str(seg_path),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    assert proc.stdin is not None
    try:
        for f_idx in range(total_frames):
            t = f_idx / fps
            frame_img = render_scene_frame_at(scene, t=t, duration=duration, fmt=fmt, topic=topic)
            proc.stdin.write(frame_img.tobytes())
        proc.stdin.close()
    except BrokenPipeError:
        pass
    stderr_bytes = proc.stderr.read() if proc.stderr else b""
    ret = proc.wait()
    if ret != 0:
        err_msg = stderr_bytes.decode("utf-8", errors="replace")[-400:]
        raise RuntimeError(f"FFmpeg gagal pada scene {scene.id}: {err_msg}")


def render_project(
    project: Project,
    voice: str = DEFAULT_VOICE,
    tts_fn: Callable[[str, Path, str], float] | None = None,
    fps: int = 15,
) -> Path:
    """Render seluruh scene di proyek menjadi video MP4 beranimasi lengkap dengan audio dan subtitle karaoke."""
    import imageio_ffmpeg
    from . import workflow

    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    brief = project.load_brief()
    sb = project.load_storyboard()
    if not sb.scenes:
        raise ValueError("Storyboard masih kosong. Tambahkan scene terlebih dahulu.")

    if any(s.page_type is None for s in sb.scenes):
        sb = map_storyboard_pages(sb)

    frames_dir = project.out_dir / "frames"
    audio_dir = project.out_dir / "audio"
    segments_dir = project.out_dir / "segments"
    for d in (frames_dir, audio_dir, segments_dir):
        d.mkdir(parents=True, exist_ok=True)

    synth = tts_fn or synthesize_tts
    audio_ext = ".wav" if tts_fn is not None else ".mp3"
    segment_files: list[Path] = []

    for s in sb.scenes:
        frame_path = frames_dir / f"scene_{s.id:03d}.png"
        audio_path = audio_dir / f"scene_{s.id:03d}{audio_ext}"
        seg_path = segments_dir / f"seg_{s.id:03d}.mp4"

        spoken = s.tts_text or s.narration
        dur = synth(spoken, audio_path, voice)
        s.duration = round(dur, 3)
        s.words = compute_word_timings(s.narration, s.duration)

        # Simpan thumbnail snapshot mid-scene
        render_scene_frame(s, frame_path, fmt=brief.format, topic=brief.topik, t=s.duration * 0.6, duration=s.duration)
        s.image_file = str(frame_path.relative_to(project.root))
        s.audio_file = str(audio_path.relative_to(project.root))

        # Render video segmen dengan animasi penuh
        _render_animated_segment(
            ffmpeg_exe=ffmpeg_exe,
            scene=s,
            audio_path=audio_path,
            seg_path=seg_path,
            duration=s.duration,
            fmt=brief.format,
            topic=brief.topik,
            fps=fps,
        )
        segment_files.append(seg_path)

    concat_list = segments_dir / "concat.txt"
    concat_lines = [f"file '{seg.resolve().as_posix()}'" for seg in segment_files]
    concat_list.write_text("\n".join(concat_lines), encoding="utf-8")

    out_video = project.out_dir / "video.mp4"
    cmd_concat = [
        ffmpeg_exe,
        "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_list),
        "-c", "copy",
        str(out_video),
    ]
    res_concat = subprocess.run(cmd_concat, capture_output=True, text=True)
    if res_concat.returncode != 0:
        raise RuntimeError(f"FFmpeg concat gagal: {res_concat.stderr[-400:]}")

    project.save_storyboard(sb)
    (project.out_dir / "naskah.srt").write_text(workflow.export_srt(project), encoding="utf-8", newline="\n")
    return out_video
