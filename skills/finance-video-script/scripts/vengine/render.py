"""Render storyboard (scenes.json) dengan gambar latar AI full-screen, Ken Burns, glassmorphism RGBA, karaoke subtitle, audio TTS, dan MP4."""
from __future__ import annotations

import asyncio
import math
import re
import subprocess
import textwrap
from pathlib import Path
from typing import Callable

from PIL import Image, ImageDraw, ImageFont

from .image_gen import generate_project_images, render_fallback_canvas
from .page_mapper import map_storyboard_pages
from .project import Project
from .schema import Scene, WordTiming

# Palet warna sinematik
BG_DARK = (15, 23, 42)         # #0F172A
INK = (15, 23, 42)
ACCENT = (232, 163, 61)        # #E8A33D
POSITIVE = (52, 211, 153)      # #34D399 (cerah di atas glass gelap)
NEGATIVE = (248, 113, 113)     # #F87171
WHITE = (255, 255, 255)
MUTED = (203, 213, 225)

DEFAULT_VOICE = "id-ID-ArdiNeural"
_FONT_CACHE: dict[tuple[int, bool], ImageFont.FreeTypeFont | ImageFont.ImageFont] = {}
_VIGNETTE_CACHE: dict[tuple[int, int, bool], Image.Image] = {}


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


def _draw_text_with_shadow(
    draw: ImageDraw.ImageDraw,
    pos: tuple[int, int],
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    fill: tuple[int, ...],
    shadow_color: tuple[int, int, int, int] = (0, 0, 0, 210),
    offset: int = 3,
) -> None:
    x, y = pos
    draw.text((x + offset, y + offset), text, font=font, fill=shadow_color)
    draw.text((x, y), text, font=font, fill=fill)


def _draw_wrapped_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    fill: tuple[int, ...],
    center_x: int,
    start_y: int,
    max_chars: int,
    line_spacing: int = 14,
    shadow: bool = True,
) -> int:
    lines = textwrap.wrap(text, width=max_chars) or [text]
    y = start_y
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        tx = center_x - w // 2
        if shadow:
            _draw_text_with_shadow(draw, (tx, y), line, font=font, fill=fill)
        else:
            draw.text((tx, y), line, font=font, fill=fill)
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
    """Gambar subtitle karaoke sinematik langsung di atas vignette bawah (tanpa kotak pembungkus kaku)."""
    words = scene.words or compute_word_timings(scene.narration, duration)
    if not words:
        return
    act_idx = active_word_index(words, t)
    chunk_size = 7 if is_vertical else 11
    page_idx = act_idx // chunk_size
    chunk = words[page_idx * chunk_size : (page_idx + 1) * chunk_size]
    local_act = act_idx - page_idx * chunk_size

    margin_x = int(width * 0.07)
    sub_zone_top = int(height * 0.74) if is_vertical else int(height * 0.76)
    sub_zone_bot = int(height * 0.90) if is_vertical else int(height * 0.91)

    font = _load_font(46 if is_vertical else 42, bold=True)
    max_line_w = (width - 2 * margin_x) - 40

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

    line_h = 60 if is_vertical else 52
    total_h = len(lines) * line_h
    start_y = (sub_zone_top + sub_zone_bot - total_h) // 2

    for r_i, line in enumerate(lines):
        row_w = sum(x[2] for x in line) + space_w * max(0, len(line) - 1)
        x = width // 2 - row_w // 2
        y = start_y + r_i * line_h
        for idx, word_str, ww in line:
            if idx == local_act:
                pad_x, pad_y = 12, 6
                draw.rounded_rectangle(
                    [x - pad_x, y - pad_y, x + ww + pad_x, y + line_h - 8],
                    radius=14,
                    fill=(ACCENT[0], ACCENT[1], ACCENT[2], 245),
                )
                draw.text((x, y), word_str, font=font, fill=BG_DARK)
            elif idx < local_act:
                _draw_text_with_shadow(draw, (x, y), word_str, font=font, fill=WHITE)
            else:
                _draw_text_with_shadow(draw, (x, y), word_str, font=font, fill=(215, 222, 234))
            x += ww + space_w


# ---------- Full-Screen Ken Burns & Vignette Helpers ----------
def _apply_fullscreen_ken_burns(
    bg: Image.Image,
    width: int,
    height: int,
    p: float,
    scene_id: int,
) -> Image.Image:
    """Terapkan efek kamera Ken Burns (zoom & pan halus) secara full-screen dari tepi ke tepi."""
    if bg.size != (width, height):
        bg = bg.resize((width, height), Image.Resampling.BILINEAR)
    zoom = 1.0 + 0.09 * p
    crop_w = max(1, int(width / zoom))
    crop_h = max(1, int(height / zoom))
    direction = 1.0 if (scene_id % 2 == 1) else -1.0
    pan_factor_x = _clamp(0.5 + direction * 0.28 * math.sin(p * math.pi), 0.0, 1.0)
    pan_factor_y = _clamp(0.5 - direction * 0.18 * math.cos(p * math.pi), 0.0, 1.0)
    pan_x = int((width - crop_w) * pan_factor_x)
    pan_y = int((height - crop_h) * pan_factor_y)
    return bg.crop((pan_x, pan_y, pan_x + crop_w, pan_y + crop_h)).resize(
        (width, height), Image.Resampling.BILINEAR
    )


def _get_vignette_overlay(width: int, height: int, darken_center: bool) -> Image.Image:
    """Bangun (dan cache) layer RGBA gradasi gelap di bawah untuk subtitle & peredupan tengah opsional."""
    key = (width, height, darken_center)
    if key in _VIGNETTE_CACHE:
        return _VIGNETTE_CACHE[key]

    steps = 256
    strip = Image.new("RGBA", (1, steps))
    base_mid_alpha = 95 if darken_center else 0
    for i in range(steps):
        y_norm = i / (steps - 1)
        if y_norm < 0.10:
            # Sedikit bayangan di pucuk atas untuk badge tipis
            t_top = 1.0 - (y_norm / 0.10)
            alpha = max(base_mid_alpha, int(85 * (t_top ** 1.6)))
        elif y_norm > 0.64:
            # Vignette sinematik di bagian bawah untuk keterbacaan subtitle karaoke
            t_bot = (y_norm - 0.64) / 0.36
            alpha = max(base_mid_alpha, int(225 * (t_bot ** 1.4)))
        else:
            alpha = base_mid_alpha
        strip.putpixel((0, i), (8, 12, 22, _clamp_int(alpha)))

    vignette = strip.resize((width, height), Image.Resampling.BILINEAR)
    _VIGNETTE_CACHE[key] = vignette
    return vignette


def _clamp_int(val: int, lo: int = 0, hi: int = 255) -> int:
    return max(lo, min(hi, val))


def _draw_ambient_particles(
    draw: ImageDraw.ImageDraw,
    width: int,
    height: int,
    t: float,
    scene_id: int,
) -> None:
    """Gambar partikel cahaya lembut melayang di atas latar full-screen agar frame terasa hidup."""
    for i in range(6):
        seed_x = (scene_id * 131 + i * 197) % 1000 / 1000.0
        seed_y = (scene_id * 73 + i * 251) % 1000 / 1000.0
        px = int(width * (0.12 + 0.76 * seed_x) + math.sin(t * 1.4 + i) * 26)
        py = int(height * (0.16 + 0.50 * seed_y) - (t * 28 + i * 20) % 90)
        rad = 4 + (i % 3) * 3
        alpha = 45 + int(25 * math.sin(t * 2.5 + i))
        draw.ellipse(
            [px - rad, py - rad, px + rad, py + rad],
            fill=(ACCENT[0], ACCENT[1], ACCENT[2], _clamp_int(alpha)),
        )


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


def _resolve_scene_bg(
    scene: Scene,
    width: int,
    height: int,
    bg_image: Image.Image | None,
) -> Image.Image:
    if bg_image is not None:
        return bg_image.convert("RGB")
    if scene.image_file:
        p = Path(scene.image_file)
        if p.exists():
            try:
                with Image.open(p) as im:
                    return im.convert("RGB")
            except Exception:
                pass
    return render_fallback_canvas(scene, width=width, height=height)


# ---------- Core Animated Full-Screen Frame Renderer ----------
def render_scene_frame_at(
    scene: Scene,
    t: float,
    duration: float,
    fmt: str = "B",
    topic: str = "",
    bg_image: Image.Image | None = None,
) -> Image.Image:
    """Render satu frame Image full-screen pada waktu t (detik) dengan Ken Burns & glassmorphism RGBA."""
    duration = max(0.5, duration)
    t = _clamp(t, 0.0, duration)
    p = t / duration
    intro_p = _ease_out_cubic(_clamp(t / 0.45))

    is_vertical = fmt == "S"
    width, height = (1080, 1920) if is_vertical else (1920, 1080)
    ptype = scene.page_type or "illustration"

    # 1. Layer Dasar: Full-Screen AI Image + Ken Burns Zoom/Pan
    raw_bg = _resolve_scene_bg(scene, width=width, height=height, bg_image=bg_image)
    zoomed_bg = _apply_fullscreen_ken_burns(raw_bg, width=width, height=height, p=p, scene_id=scene.id)

    # 2. Layer Vignette Sinematik (gelap di bawah untuk subtitle, redup halus di tengah untuk kartu overlay)
    needs_center_dim = ptype in (
        "punchline_card",
        "section_title",
        "calc_step",
        "number_callout",
        "myth_card",
        "before_after",
        "cta_comment",
    )
    vignette = _get_vignette_overlay(width, height, darken_center=needs_center_dim)
    canvas = Image.alpha_composite(zoomed_bg.convert("RGBA"), vignette)

    # 3. Layer Overlay RGBA (Glassmorphism + Partikel + Tipografi)
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    _draw_ambient_particles(draw, width, height, t=t, scene_id=scene.id)

    # Progress bar tipis elegan di tepi paling atas (6px)
    bar_h = 6
    draw.rectangle([0, 0, width, bar_h], fill=(255, 255, 255, 55))
    prog_w = max(8, int(width * p))
    draw.rectangle([0, 0, prog_w, bar_h], fill=(ACCENT[0], ACCENT[1], ACCENT[2], 235))

    font_badge = _load_font(26 if is_vertical else 22, bold=True)
    font_title = _load_font(60 if is_vertical else 54, bold=True)
    font_formula = _load_font(74 if is_vertical else 68, bold=True)

    cx = width // 2
    margin_x = int(width * 0.07)

    words = scene.words or compute_word_timings(scene.narration, duration)
    act_idx = active_word_index(words, t)

    if ptype == "punchline_card":
        card_top = int(height * 0.24) + int((1.0 - intro_p) * 35)
        card_bot = int(height * 0.66)
        draw.rounded_rectangle(
            [margin_x, card_top, width - margin_x, card_bot],
            radius=32,
            fill=(15, 23, 42, 175),
            outline=(ACCENT[0], ACCENT[1], ACCENT[2], 190),
            width=2,
        )
        pill_w, pill_h = 320, 50
        pill_y = card_top + 36
        draw.rounded_rectangle([cx - pill_w // 2, pill_y, cx + pill_w // 2, pill_y + pill_h], radius=25, fill=ACCENT)
        lbl = "PRINSIP UTAMA"
        lb = draw.textbbox((0, 0), lbl, font=font_badge)
        draw.text((cx - (lb[2] - lb[0]) // 2, pill_y + 10), lbl, font=font_badge, fill=BG_DARK)

        visible_words = [w.word for i, w in enumerate(words) if i <= act_idx] or [scene.narration]
        partial_text = " ".join(visible_words)
        text_y = card_top + 120
        end_y = _draw_wrapped_text(
            draw,
            f'"{partial_text}"',
            font_title,
            WHITE,
            cx,
            text_y,
            max_chars=20 if is_vertical else 32,
            line_spacing=20,
        )
        line_half = int(200 * _ease_out_cubic(p))
        draw.rounded_rectangle([cx - line_half, end_y + 24, cx + line_half, end_y + 32], radius=4, fill=ACCENT)

    elif ptype == "section_title":
        slide_offset = int((1.0 - intro_p) * 85)
        card_top = int(height * 0.28) + slide_offset
        card_bot = int(height * 0.62) + slide_offset
        draw.rounded_rectangle(
            [margin_x, card_top, width - margin_x, card_bot],
            radius=32,
            fill=(15, 23, 42, 175),
            outline=(ACCENT[0], ACCENT[1], ACCENT[2], 190),
            width=2,
        )
        pill_w, pill_h = 270, 50
        pill_y = card_top + 36
        draw.rounded_rectangle([cx - pill_w // 2, pill_y, cx + pill_w // 2, pill_y + pill_h], radius=25, fill=ACCENT)
        lbl = "BAGIAN BARU"
        lb = draw.textbbox((0, 0), lbl, font=font_badge)
        draw.text((cx - (lb[2] - lb[0]) // 2, pill_y + 10), lbl, font=font_badge, fill=BG_DARK)

        _draw_wrapped_text(
            draw,
            scene.narration,
            font_title,
            WHITE,
            cx,
            card_top + 120,
            max_chars=22 if is_vertical else 34,
            line_spacing=20,
        )

    elif ptype in ("calc_step", "number_callout"):
        card_top = int(height * 0.18) + int((1.0 - intro_p) * 40)
        card_bot = int(height * 0.62)
        draw.rounded_rectangle(
            [margin_x, card_top, width - margin_x, card_bot],
            radius=32,
            fill=(15, 23, 42, 190),
            outline=(ACCENT[0], ACCENT[1], ACCENT[2], 210),
            width=3,
        )
        _draw_text_with_shadow(draw, (margin_x + 45, card_top + 36), "SIMULASI HITUNGAN", font_badge, POSITIVE)

        lhs, target_val = _extract_formula_numbers(scene.props.get("formula") or scene.notes)
        count_p = _ease_out_cubic(_clamp((p - 0.10) / 0.72))

        if target_val is not None:
            current_val = target_val * count_p
            lhs_y = card_top + 115
            _draw_wrapped_text(draw, f"Rp {lhs} =", _load_font(44, bold=True), MUTED, cx, lhs_y, max_chars=30)
            val_str = f"Rp {_format_id_int(current_val)}"
            _draw_wrapped_text(draw, val_str, font_formula, POSITIVE, cx, lhs_y + 85, max_chars=24)
        else:
            _draw_wrapped_text(draw, f"Rp {lhs}", font_formula, WHITE, cx, (card_top + card_bot) // 2 - 40, max_chars=24)

        meter_x1, meter_x2 = margin_x + 55, width - margin_x - 55
        meter_y = card_bot - 65
        draw.rounded_rectangle([meter_x1, meter_y, meter_x2, meter_y + 20], radius=10, fill=(255, 255, 255, 45))
        fill_x2 = meter_x1 + max(20, int((meter_x2 - meter_x1) * count_p))
        draw.rounded_rectangle([meter_x1, meter_y, fill_x2, meter_y + 20], radius=10, fill=POSITIVE)

        _draw_karaoke_subtitle(draw, scene, t, duration, width, height, is_vertical)

    elif ptype == "myth_card":
        card_top = int(height * 0.20)
        card_bot = int(height * 0.60)
        draw.rounded_rectangle(
            [margin_x, card_top, width - margin_x, card_bot],
            radius=32,
            fill=(28, 16, 24, 190),
            outline=(NEGATIVE[0], NEGATIVE[1], NEGATIVE[2], 210),
            width=3,
        )
        _draw_text_with_shadow(draw, (margin_x + 45, card_top + 36), "MITOS / ANGGAPAN KELIRU", font_badge, NEGATIVE)

        text_y = card_top + 115
        end_y = _draw_wrapped_text(
            draw,
            scene.narration,
            _load_font(46 if is_vertical else 42, bold=True),
            WHITE,
            cx,
            text_y,
            max_chars=24 if is_vertical else 36,
            line_spacing=18,
        )
        strike_p = _ease_out_cubic(_clamp((p - 0.20) / 0.45))
        if strike_p > 0:
            sx1 = margin_x + 65
            sx2 = sx1 + int((width - 2 * margin_x - 130) * strike_p)
            sy_mid = (text_y + end_y) // 2
            draw.line([(sx1, sy_mid - 18), (sx2, sy_mid + 18)], fill=NEGATIVE, width=10)

        _draw_karaoke_subtitle(draw, scene, t, duration, width, height, is_vertical)

    elif ptype == "before_after":
        top_box = (margin_x, int(height * 0.16), width - margin_x, int(height * 0.38))
        bot_box = (margin_x, int(height * 0.42), width - margin_x, int(height * 0.64))

        draw.rounded_rectangle(
            top_box,
            radius=26,
            fill=(38, 18, 24, 180),
            outline=(NEGATIVE[0], NEGATIVE[1], NEGATIVE[2], 200),
            width=3,
        )
        _draw_text_with_shadow(draw, (top_box[0] + 35, top_box[1] + 24), "KONDISI LAMA (DULU)", font_badge, NEGATIVE)

        reveal_p = _ease_out_cubic(_clamp((p - 0.25) / 0.45))
        if reveal_p > 0.05:
            offset = int((1.0 - reveal_p) * 75)
            b_box = (bot_box[0], bot_box[1] + offset, bot_box[2], bot_box[3] + offset)
            draw.rounded_rectangle(
                b_box,
                radius=26,
                fill=(14, 38, 32, 185),
                outline=(POSITIVE[0], POSITIVE[1], POSITIVE[2], 210),
                width=3,
            )
            _draw_text_with_shadow(draw, (b_box[0] + 35, b_box[1] + 24), "KONDISI SEKARANG", font_badge, POSITIVE)

        _draw_karaoke_subtitle(draw, scene, t, duration, width, height, is_vertical)

    elif ptype == "cta_comment":
        card_top = int(height * 0.20) + int((1.0 - intro_p) * 40)
        card_bot = int(height * 0.62)
        draw.rounded_rectangle(
            [margin_x, card_top, width - margin_x, card_bot],
            radius=32,
            fill=(15, 23, 42, 190),
            outline=(ACCENT[0], ACCENT[1], ACCENT[2], 210),
            width=3,
        )
        _draw_wrapped_text(draw, "TULIS KOMITMENMU DI KOMENTAR", font_badge, ACCENT, cx, card_top + 42, max_chars=34)

        input_y1 = card_top + 120
        input_y2 = input_y1 + 105
        draw.rounded_rectangle(
            [margin_x + 45, input_y1, width - margin_x - 45, input_y2],
            radius=20,
            fill=(8, 12, 22, 210),
            outline=(255, 255, 255, 180),
            width=2,
        )
        cta_sample = "Hari ke-1"
        typed_len = max(1, int(len(cta_sample) * _clamp(p * 1.6)))
        cursor_char = "|" if int(t * 4) % 2 == 0 else " "
        typed_str = f">  {cta_sample[:typed_len]}{cursor_char}"
        _draw_text_with_shadow(draw, (margin_x + 80, input_y1 + 24), typed_str, _load_font(44, bold=True), ACCENT)

        _draw_karaoke_subtitle(draw, scene, t, duration, width, height, is_vertical)

    else:
        # Illustration full-screen: visual AI memenuhi layar tanpa kotak pembatas, hanya subtitle karaoke di bawah
        _draw_karaoke_subtitle(draw, scene, t, duration, width, height, is_vertical)

    final_img = Image.alpha_composite(canvas, overlay).convert("RGB")
    return final_img


def render_scene_frame(
    scene: Scene,
    out_path: Path,
    fmt: str = "B",
    topic: str = "",
    t: float = 1.0,
    duration: float = 3.0,
    bg_image: Image.Image | None = None,
) -> Path:
    """Simpan satu snapshot PNG dari scene (default pada t=1.0 dtk untuk thumbnail/pratinjau)."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img = render_scene_frame_at(scene, t=t, duration=duration, fmt=fmt, topic=topic, bg_image=bg_image)
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
    bg_image: Image.Image | None = None,
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
            frame_img = render_scene_frame_at(
                scene, t=t, duration=duration, fmt=fmt, topic=topic, bg_image=bg_image
            )
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
    style_override: str | None = None,
    image_fetcher: Callable[[str], bytes] | None = None,
) -> Path:
    """Render seluruh scene di proyek menjadi video MP4 full-screen lengkap dengan aset gambar AI, audio, dan subtitle karaoke."""
    import imageio_ffmpeg
    from . import workflow

    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    brief = project.load_brief()
    sb = project.load_storyboard()
    if not sb.scenes:
        raise ValueError("Storyboard masih kosong. Tambahkan scene terlebih dahulu.")

    if any(s.page_type is None for s in sb.scenes):
        sb = map_storyboard_pages(sb)
        project.save_storyboard(sb)

    # Jika dipanggil dalam mode pengujian cepat (tts_fn disuplai tapi image_fetcher tidak), hindari jaringan
    effective_fetcher = image_fetcher
    if effective_fetcher is None and tts_fn is not None:
        def _offline_test_fetcher(_url: str) -> bytes:
            raise OSError("offline test mode")
        effective_fetcher = _offline_test_fetcher

    # Pastikan aset gambar full-screen tersedia di out/images/
    generate_project_images(project, style_override=style_override, fetcher=effective_fetcher)
    sb = project.load_storyboard()

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

        bg_img: Image.Image | None = None
        if s.image_file:
            img_p = project.root / s.image_file
            if img_p.exists():
                with Image.open(img_p) as loaded:
                    bg_img = loaded.convert("RGB")

        spoken = s.tts_text or s.narration
        dur = synth(spoken, audio_path, voice)
        s.duration = round(dur, 3)
        s.words = compute_word_timings(s.narration, s.duration)

        render_scene_frame(
            s,
            frame_path,
            fmt=brief.format,
            topic=brief.topik,
            t=s.duration * 0.6,
            duration=s.duration,
            bg_image=bg_img,
        )
        s.audio_file = str(audio_path.relative_to(project.root))

        _render_animated_segment(
            ffmpeg_exe=ffmpeg_exe,
            scene=s,
            audio_path=audio_path,
            seg_path=seg_path,
            duration=s.duration,
            fmt=brief.format,
            topic=brief.topik,
            fps=fps,
            bg_image=bg_img,
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
