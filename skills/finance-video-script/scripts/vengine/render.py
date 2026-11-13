"""Render storyboard (scenes.json) dengan gambar latar AI full-screen, Ken Burns, glassmorphism RGBA, karaoke subtitle, audio TTS, dan MP4."""
from __future__ import annotations

import asyncio
import math
import re
import subprocess
import textwrap
from pathlib import Path
from typing import Callable

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageFont

from .image_gen import generate_project_images, render_fallback_canvas
from .page_mapper import map_storyboard_pages
from .project import Project
from .schema import Scene, WordTiming

# Palet warna sinematik & tipografi kontras tinggi
BG_DARK = (15, 23, 42)            # #0F172A
INK = (15, 23, 42)
ACCENT = (232, 163, 61)           # #E8A33D
HIGHLIGHT_YELLOW = (250, 204, 21) # #FACC15
HIGHLIGHT_MINT = (74, 222, 128)   # #4ADE80
STROKE_DARK = (11, 15, 25, 255)   # #0B0F19
POSITIVE = (52, 211, 153)         # #34D399
NEGATIVE = (248, 113, 113)        # #F87171
WHITE = (255, 255, 255)
MUTED = (203, 213, 225)

DEFAULT_VOICE = "id-ID-ArdiNeural"
_FONT_CACHE: dict[tuple[int, bool], ImageFont.FreeTypeFont | ImageFont.ImageFont] = {}
_VIGNETTE_CACHE: dict[tuple[int, int, bool], Image.Image] = {}
_ASSETS_FONTS_DIR = Path(__file__).resolve().parent.parent.parent / "assets" / "fonts"


def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    key = (size, bold)
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]
    bold_local = str(_ASSETS_FONTS_DIR / "PlusJakartaSans-ExtraBold.ttf")
    candidates = (
        [bold_local, "segoeuib.ttf", "arialbd.ttf", "calibrib.ttf", "DejaVuSans-Bold.ttf"]
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


_NO_BREAK_AFTER_WORDS = {
    "di", "ke", "dari", "pada", "untuk", "dengan", "tanpa", "agar", "supaya",
    "yang", "dan", "atau", "karena", "sebab", "seperti", "menuju", "dalam",
    "akan", "bisa", "dapat", "ikut", "harus", "mulai", "saat", "ketika", "jika",
}
_COMPOUND_NEXT_WORDS = {
    ("malam", "hari"), ("siang", "hari"), ("pagi", "hari"), ("sore", "hari"),
    ("masa", "depan"), ("masa", "depanmu"), ("tanpa", "terasa"), ("setiap", "hari"),
    ("uang", "sisa"), ("kebiasaan", "baru"), ("layar", "ponsel"), ("baterai", "fokus"),
}


def _chunk_words_semantic(words: list[WordTiming], max_words: int = 5) -> list[list[WordTiming]]:
    """Pecah kata subtitle berdasarkan kesatuan frasa makna (Semantic Chunking), bukan potong kaku per N kata."""
    if not words:
        return []
    if len(words) <= max_words:
        return [list(words)]

    chunks: list[list[WordTiming]] = []
    cur: list[WordTiming] = []
    min_words = max(2, max_words - 2)
    n = len(words)

    for i, wt in enumerate(words):
        cur.append(wt)
        if i == n - 1:
            break

        w_clean = re.sub(r"[^\w]", "", wt.word.lower())
        next_clean = re.sub(r"[^\w]", "", words[i + 1].word.lower())
        has_punct = wt.word.endswith((",", ".", "!", "?", ";", ":"))

        # Jika jumlah kata masih di bawah batas minimum, jangan potong kecuali ada titik
        if len(cur) < min_words and not wt.word.endswith((".", "!", "?")):
            continue

        # Jangan memutus tepat setelah kata depan/penghubung atau di tengah frasa majemuk jika masih muat
        is_protected_pair = (w_clean in _NO_BREAK_AFTER_WORDS) or ((w_clean, next_clean) in _COMPOUND_NEXT_WORDS)
        if is_protected_pair and len(cur) < max_words + 1:
            continue

        # Potong pada tanda baca atau saat mencapai max_words (dan kata berikutnya bukan pasangan terlindung)
        if has_punct or len(cur) >= max_words:
            # Hindari menyisakan 1 kata yatim di chunk terakhir
            if n - (i + 1) == 1 and len(cur) <= max_words:
                continue
            chunks.append(cur)
            cur = []

    if cur:
        chunks.append(cur)
    return chunks


def _balance_subtitle_lines(
    word_items: list[tuple[int, str, int]],
    space_w: int,
    max_line_w: int,
) -> list[list[tuple[int, str, int]]]:
    """Bagi kata subtitle menjadi maksimal 2 baris yang lebarnya seimbang (textWrap: 'balance') tanpa kata depan menggantung."""
    if not word_items:
        return []
    total_w = sum(x[2] for x in word_items) + space_w * max(0, len(word_items) - 1)
    if total_w <= max_line_w and len(word_items) <= 3:
        return [word_items]

    best_split: int | None = None
    best_score = float("inf")
    n = len(word_items)
    for split_i in range(1, n):
        left = word_items[:split_i]
        right = word_items[split_i:]
        w_left = sum(x[2] for x in left) + space_w * max(0, len(left) - 1)
        w_right = sum(x[2] for x in right) + space_w * max(0, len(right) - 1)
        if w_left > max_line_w or w_right > max_line_w:
            continue
        penalty = 0.0
        last_left_clean = re.sub(r"[^\w]", "", left[-1][1].lower())
        if last_left_clean in _NO_BREAK_AFTER_WORDS:
            penalty += 5000.0
        if len(right) == 1 and n >= 3:
            penalty += 3000.0
        score = abs(w_left - w_right) + penalty
        if score < best_score:
            best_score = score
            best_split = split_i

    if best_split is not None:
        return [word_items[:best_split], word_items[best_split:]]

    # Fallback greedy wrap bila teks sangat panjang
    lines: list[list[tuple[int, str, int]]] = []
    cur_line: list[tuple[int, str, int]] = []
    cur_w = 0
    for item in word_items:
        if cur_line and cur_w + space_w + item[2] > max_line_w:
            lines.append(cur_line)
            cur_line = [item]
            cur_w = item[2]
        else:
            cur_w += (space_w if cur_line else 0) + item[2]
            cur_line.append(item)
    if cur_line:
        lines.append(cur_line)
    return lines[:2]


def _draw_karaoke_subtitle(
    draw: ImageDraw.ImageDraw,
    scene: Scene,
    t: float,
    duration: float,
    width: int,
    height: int,
    is_vertical: bool,
) -> None:
    """Gambar subtitle dengan Plus Jakarta Sans ExtraBold, outer stroke (#0B0F19), drop shadow, balanced lines & safe zone 9:16."""
    words = scene.words or compute_word_timings(scene.narration, duration)
    if not words:
        return
    act_idx = active_word_index(words, t)
    max_words = 5 if is_vertical else 9
    chunks = _chunk_words_semantic(words, max_words=max_words)

    chunk: list[WordTiming] = chunks[0]
    local_act = 0
    offset = 0
    for ch in chunks:
        if offset + len(ch) > act_idx:
            chunk = ch
            local_act = act_idx - offset
            break
        offset += len(ch)

    # 9:16 Safe Zone: min 90px kiri/kanan (maxWidth ~880px), subtitle di 280px–380px dari tepi bawah
    font_size = 56 if is_vertical else 48
    font = _load_font(font_size, bold=True)
    max_line_w = min(880, width - 180) if is_vertical else min(1320, width - 240)
    sub_zone_bot = (height - 280) if is_vertical else (height - 110)
    sub_zone_top = (height - 430) if is_vertical else (height - 240)

    space_w = draw.textbbox((0, 0), " ", font=font)[2]
    measured: list[tuple[int, str, int]] = []
    for idx, wt in enumerate(chunk):
        wb = draw.textbbox((0, 0), wt.word, font=font)
        measured.append((idx, wt.word, wb[2] - wb[0]))

    lines = _balance_subtitle_lines(measured, space_w=space_w, max_line_w=max_line_w)
    line_h = int(round(font_size * 1.22))
    total_h = len(lines) * line_h
    start_y = max(sub_zone_top, sub_zone_bot - total_h)

    stroke_w = 6 if is_vertical else 5  # outer stroke ~10-12px total di sekeliling huruf (paint-order: stroke fill)
    for r_i, line in enumerate(lines):
        row_w = sum(x[2] for x in line) + space_w * max(0, len(line) - 1)
        x = width // 2 - row_w // 2
        y = start_y + r_i * line_h
        for idx, word_str, ww in line:
            word_fill = HIGHLIGHT_YELLOW if idx == local_act else WHITE
            # Multi-layer soft drop shadow (0px 8px 16px rgba(0,0,0,0.65))
            draw.text(
                (x, y + 8),
                word_str,
                font=font,
                fill=(0, 0, 0, 165),
                stroke_width=stroke_w,
                stroke_fill=(0, 0, 0, 140),
            )
            draw.text(
                (x, y + 4),
                word_str,
                font=font,
                fill=(0, 0, 0, 110),
                stroke_width=stroke_w,
                stroke_fill=(0, 0, 0, 100),
            )
            # Outer stroke (#0B0F19) digambar di luar huruf lalu diisi warna utama (paint-order: stroke fill)
            draw.text(
                (x, y),
                word_str,
                font=font,
                fill=word_fill,
                stroke_width=stroke_w,
                stroke_fill=STROKE_DARK,
            )
            x += ww + space_w


# ---------- Full-Screen Ken Burns, Claymation Stop-Motion & Vignette Helpers ----------
def _detect_clay_motion_mode(scene: Scene) -> str:
    """Deteksi mode animasi stop-motion claymation dari motion_prompt atau end_image_file."""
    mp = (scene.motion_prompt or "").lower()
    if any(k in mp for k in ("switch", "flip", "illuminat")) or scene.end_image_file or scene.end_image_prompt:
        return "switch_light"
    if any(k in mp for k in ("bobbing", "battery", "slump", "sigh")):
        return "bob_and_sigh"
    if any(k in mp for k in ("flicker", "screen", "breathing")):
        return "zoom_flicker"
    return "ken_burns"


def _apply_tilt_shift_dof(img: Image.Image) -> Image.Image:
    """Terapkan efek lensa makro tilt-shift (blur lembut di tepi atas dan bawah panggung miniatur)."""
    w, h = img.size
    blurred = img.filter(ImageFilter.GaussianBlur(radius=4))
    mask_small = Image.new("L", (1, 128), 0)
    for i in range(128):
        yn = i / 127.0
        if yn < 0.11:
            a = int(210 * ((1.0 - yn / 0.11) ** 1.5))
        elif yn > 0.89:
            a = int(210 * (((yn - 0.89) / 0.11) ** 1.5))
        else:
            a = 0
        mask_small.putpixel((0, i), _clamp_int(a))
    mask = mask_small.resize((w, h), Image.Resampling.BILINEAR)
    return Image.composite(blurred, img, mask)


def _make_smooth_radial_glow(
    width: int,
    height: int,
    center_xy: tuple[float, float],
    color: tuple[int, int, int],
    max_alpha: int,
    radius_scale: float = 0.55,
) -> Image.Image:
    """Buat layer RGBA pendaran cahaya radial yang benar-benar halus tanpa cincin lingkaran keras."""
    gw, gh = 64, 64
    small = Image.new("RGBA", (gw, gh), (0, 0, 0, 0))
    cx, cy = center_xy[0] * gw, center_xy[1] * gh
    max_d = max(gw, gh) * radius_scale
    for y in range(gh):
        for x in range(gw):
            dist = math.hypot(x - cx, y - cy)
            if dist < max_d:
                falloff = (1.0 - dist / max_d) ** 2.2
                a = _clamp_int(int(max_alpha * falloff))
                small.putpixel((x, y), (color[0], color[1], color[2], a))
    return small.resize((width, height), Image.Resampling.BICUBIC)


def _interpolate_progressive_poses(
    poses: list[Image.Image],
    p: float,
    order: tuple[int, ...] | None = None,
) -> Image.Image:
    """Pilih keyframe pose secara progresif satu arah (Start -> Mid -> End) dengan instant cut stop-motion tanpa cross-dissolve."""
    seq = [poses[i % len(poses)] for i in order] if order else list(poses)
    n = len(seq)
    if n == 1:
        return seq[0]

    # Bagi progres [0..1] menjadi n bagian merata dengan instant cut tegas (tanpa opacity blend agar bebas ghosting)
    idx = min(n - 1, int(_clamp(p, 0.0, 0.9999) * n))
    return seq[idx]


def _apply_clay_stop_motion(
    raw_bg: Image.Image,
    end_bg: Image.Image | None,
    scene: Scene,
    width: int,
    height: int,
    t: float,
    duration: float,
    pose_images: list[Image.Image] | None = None,
) -> Image.Image:
    """Render gerak claymation progresif satu arah (tanpa ping-pong loop, kamera stabil & transisi S-curve mulus)."""
    if raw_bg.size != (width, height):
        raw_bg = raw_bg.resize((width, height), Image.Resampling.BICUBIC)
    if end_bg is not None and end_bg.size != (width, height):
        end_bg = end_bg.resize((width, height), Image.Resampling.BICUBIC)

    poses: list[Image.Image] = []
    if pose_images:
        for pim in pose_images:
            poses.append(pim.resize((width, height), Image.Resampling.BICUBIC) if pim.size != (width, height) else pim)

    mode = _detect_clay_motion_mode(scene)
    p_smooth = _clamp(t / max(0.1, duration))
    ease_p = _ease_out_cubic(p_smooth)

    if mode == "zoom_flicker":
        # Busur progresif 1 arah (tanpa diulang): Pose 1 (Buka mata) -> Pose 3 (Alis lelah) -> Pose 2 (Mata terpejam lelah)
        active_bg = raw_bg
        if len(poses) >= 3:
            active_bg = _interpolate_progressive_poses(poses, p_smooth, order=(0, 2, 1))
        elif len(poses) == 2:
            active_bg = _interpolate_progressive_poses(poses, p_smooth, order=(0, 1))

        # Slow push-in kamera yang 100% mulus (tanpa jitter/goyangan acak)
        zoom = 1.0 + 0.10 * ease_p
        crop_w = max(1, int(round(width / zoom)))
        crop_h = max(1, int(round(height / zoom)))
        px = (width - crop_w) // 2
        py = int(round((height - crop_h) * 0.42))
        frame = active_bg.crop((px, py, px + crop_w, py + crop_h)).resize((width, height), Image.Resampling.BICUBIC)

        flicker_intensity = 0.60 + 0.40 * (0.5 + 0.5 * math.sin(t * 3.0))
        glow = _make_smooth_radial_glow(
            width,
            height,
            center_xy=(0.5, 0.55),
            color=(70, 170, 255),
            max_alpha=int(56 * flicker_intensity),
            radius_scale=0.52,
        )
        out = Image.alpha_composite(frame.convert("RGBA"), glow).convert("RGB")
        return _apply_tilt_shift_dof(out)

    if mode == "bob_and_sigh":
        # Busur progresif 1 arah selaras audio: Pose 2 (Hela napas [sighs] di awal) -> Pose 1 (Netral) -> Pose 3 (Melirik cemas ke baterai merah)
        if len(poses) >= 3:
            active_bg = _interpolate_progressive_poses(poses, p_smooth, order=(1, 0, 2))
            zoom = 1.0 + 0.06 * ease_p
            crop_w = max(1, int(round(width / zoom)))
            crop_h = max(1, int(round(height / zoom)))
            px = (width - crop_w) // 2
            py = int(round((height - crop_h) * 0.38))
            composed = active_bg.crop((px, py, px + crop_w, py + crop_h)).resize((width, height), Image.Resampling.BICUBIC)
            return _apply_tilt_shift_dof(composed)

        base = raw_bg.copy()
        bob_dy = int(round(math.sin(t * 2.6) * 12))
        icon_shifted = ImageChops.offset(base, 0, bob_dy)
        slump_p = _ease_out_cubic(_clamp((p_smooth - 0.20) / 0.65))
        slump_dy = int(round(slump_p * 12))
        body_shifted = ImageChops.offset(base, 0, slump_dy)

        band_small = Image.new("L", (1, 256), 0)
        for i in range(256):
            yn = i / 255.0
            if yn < 0.03:
                a = int(255 * (yn / 0.03))
            elif yn <= 0.26:
                a = 255
            elif yn < 0.30:
                a = int(255 * (1.0 - (yn - 0.26) / 0.04))
            else:
                a = 0
            band_small.putpixel((0, i), _clamp_int(a))
        icon_mask = band_small.resize((width, height), Image.Resampling.BILINEAR)
        composed = Image.composite(icon_shifted, body_shifted, icon_mask)
        return _apply_tilt_shift_dof(composed)

    if mode == "switch_light":
        # Busur progresif 4 tahap satu arah: Mendekat -> Menyentuh bawah -> Dorong tengah -> Sakelar atas menyala terang
        if len(poses) >= 3:
            stage_img = _interpolate_progressive_poses(poses, p_smooth)
            warm_factor = _clamp((p_smooth - 0.45) / 0.35)
            zoom = 1.0 + 0.06 * ease_p
            crop_w = max(1, int(round(width / zoom)))
            crop_h = max(1, int(round(height / zoom)))
            px = (width - crop_w) // 2
            py = int(round((height - crop_h) * 0.48))
            frame = stage_img.crop((px, py, px + crop_w, py + crop_h)).resize((width, height), Image.Resampling.BICUBIC)

            if warm_factor > 0.0:
                bloom = _make_smooth_radial_glow(
                    width,
                    height,
                    center_xy=(0.45, 0.42),
                    color=(255, 220, 130),
                    max_alpha=int(42 * warm_factor),
                    radius_scale=0.68,
                )
                frame = Image.alpha_composite(frame.convert("RGBA"), bloom).convert("RGB")
            return _apply_tilt_shift_dof(frame)

        # Fallback 2-keyframe: Start Frame -> End Frame dengan S-curve blend halus
        dim_start = raw_bg if end_bg is not None else ImageEnhance.Brightness(raw_bg).enhance(0.68)
        bright_end = end_bg if end_bg is not None else ImageEnhance.Brightness(raw_bg).enhance(1.25)
        flip_p = 0.5 - 0.5 * math.cos(math.pi * _clamp((p_smooth - 0.30) / 0.35))
        frame = Image.blend(dim_start, bright_end, flip_p)
        if flip_p > 0.05:
            bloom = _make_smooth_radial_glow(
                width,
                height,
                center_xy=(0.45, 0.42),
                color=(255, 220, 130),
                max_alpha=int(44 * flip_p),
                radius_scale=0.68,
            )
            frame = Image.alpha_composite(frame.convert("RGBA"), bloom).convert("RGB")
        return _apply_tilt_shift_dof(frame)

    return _apply_fullscreen_ken_burns(raw_bg, width=width, height=height, p=p_smooth, scene_id=scene.id)
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


def _resolve_scene_end_bg(
    scene: Scene,
    width: int,
    height: int,
    end_bg_image: Image.Image | None,
) -> Image.Image | None:
    if end_bg_image is not None:
        return end_bg_image.convert("RGB")
    if scene.end_image_file:
        p = Path(scene.end_image_file)
        if p.exists():
            try:
                with Image.open(p) as im:
                    return im.convert("RGB")
            except Exception:
                pass
    return None


# ---------- Core Animated Full-Screen Frame Renderer ----------
def render_scene_frame_at(
    scene: Scene,
    t: float,
    duration: float,
    fmt: str = "B",
    topic: str = "",
    bg_image: Image.Image | None = None,
    end_bg_image: Image.Image | None = None,
    pose_images: list[Image.Image] | None = None,
) -> Image.Image:
    """Render satu frame Image full-screen pada waktu t (detik) dengan Ken Burns / Clay Stop-Motion & glassmorphism RGBA."""
    duration = max(0.5, duration)
    t = _clamp(t, 0.0, duration)
    p = t / duration
    intro_p = _ease_out_cubic(_clamp(t / 0.45))

    is_vertical = fmt == "S"
    width, height = (1080, 1920) if is_vertical else (1920, 1080)
    ptype = scene.page_type or "illustration"

    # 1. Layer Dasar: Full-Screen AI Image + Clay Stop-Motion atau Ken Burns
    raw_bg = _resolve_scene_bg(scene, width=width, height=height, bg_image=bg_image)
    raw_end_bg = _resolve_scene_end_bg(scene, width=width, height=height, end_bg_image=end_bg_image)
    if scene.motion_prompt or raw_end_bg is not None or (pose_images and len(pose_images) >= 2):
        zoomed_bg = _apply_clay_stop_motion(
            raw_bg,
            raw_end_bg,
            scene,
            width=width,
            height=height,
            t=t,
            duration=duration,
            pose_images=pose_images,
        )
    else:
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

    # Progress bar tipis elegan diletakkan tepat di atas area teks subtitle (safe zone 9:16, bukan di y=0)
    bar_h = 4
    bar_y = (height - 460) if is_vertical else (height - 265)
    bar_margin = 100 if is_vertical else 120
    bar_total_w = width - 2 * bar_margin
    draw.rounded_rectangle([bar_margin, bar_y, width - bar_margin, bar_y + bar_h], radius=2, fill=(255, 255, 255, 45))
    prog_w = max(8, int(bar_total_w * p))
    draw.rounded_rectangle(
        [bar_margin, bar_y, bar_margin + prog_w, bar_y + bar_h],
        radius=2,
        fill=(HIGHLIGHT_YELLOW[0], HIGHLIGHT_YELLOW[1], HIGHLIGHT_YELLOW[2], 220),
    )

    font_badge = _load_font(26 if is_vertical else 22, bold=True)
    font_title = _load_font(60 if is_vertical else 54, bold=True)
    font_formula = _load_font(74 if is_vertical else 68, bold=True)

    cx = width // 2
    margin_x = int(width * 0.08)

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
    end_bg_image: Image.Image | None = None,
    pose_images: list[Image.Image] | None = None,
) -> Path:
    """Simpan satu snapshot PNG dari scene (default pada t=1.0 dtk untuk thumbnail/pratinjau)."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img = render_scene_frame_at(
        scene,
        t=t,
        duration=duration,
        fmt=fmt,
        topic=topic,
        bg_image=bg_image,
        end_bg_image=end_bg_image,
        pose_images=pose_images,
    )
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
    """Hasilkan file MP3 dari teks Bahasa Indonesia menggunakan edge-tts atau ElevenLabs API dan kembalikan durasinya."""
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if voice.lower().startswith("elevenlabs:"):
        import json
        import os
        import urllib.request

        voice_id = voice.split(":", 1)[1].strip()
        api_key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("ELEVENLABS_API_KEY belum diset di environment variable.")
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        payload = json.dumps(
            {
                "text": text,
                "model_id": "eleven_multilingual_v2",
                "voice_settings": {
                    "stability": 0.48,
                    "similarity_boost": 0.80,
                    "style": 0.28,
                    "use_speaker_boost": True,
                },
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            headers={
                "xi-api-key": api_key,
                "Content-Type": "application/json",
                "Accept": "audio/mpeg",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            out_path.write_bytes(resp.read())
        return _probe_audio_duration(out_path)

    import edge_tts

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
    end_bg_image: Image.Image | None = None,
    pose_images: list[Image.Image] | None = None,
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
                scene,
                t=t,
                duration=duration,
                fmt=fmt,
                topic=topic,
                bg_image=bg_image,
                end_bg_image=end_bg_image,
                pose_images=pose_images,
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


def split_full_audio_to_scenes(
    ffmpeg_exe: str,
    full_audio_path: Path,
    scenes: list[Scene],
    audio_dir: Path,
) -> list[Path]:
    """Potong otomatis 1 file MP3 utuh (mis. hasil ElevenLabs) menjadi out/audio/scene_XXX.mp3 berdasarkan deteksi jeda."""
    total_dur = _probe_audio_duration(full_audio_path)
    audio_dir.mkdir(parents=True, exist_ok=True)
    n = len(scenes)
    if n == 1:
        dst = audio_dir / f"scene_{scenes[0].id:03d}.mp3"
        dst.write_bytes(full_audio_path.read_bytes())
        return [dst]

    proc = subprocess.run(
        [ffmpeg_exe, "-i", str(full_audio_path), "-af", "silencedetect=noise=-32dB:d=0.22", "-f", "null", "-"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    starts = [float(x) for x in re.findall(r"silence_start:\s*([0-9.]+)", proc.stderr)]
    ends = [float(x) for x in re.findall(r"silence_end:\s*([0-9.]+)", proc.stderr)]
    silences = [
        (s, e)
        for s, e in zip(starts, ends)
        if s > 0.25 and e < total_dur - 0.20
    ]

    word_counts = [max(1, len((sc.narration or "").split())) for sc in scenes]
    total_words = sum(word_counts)
    cum = 0
    split_points: list[float] = [0.0]
    used_indices: set[int] = set()
    for idx in range(n - 1):
        cum += word_counts[idx]
        expected_t = (cum / total_words) * total_dur
        best_i = -1
        best_dist = 9999.0
        for s_i, (s_start, s_end) in enumerate(silences):
            if s_i in used_indices:
                continue
            mid = 0.5 * (s_start + s_end)
            if mid <= split_points[-1] + 0.4:
                continue
            dist = abs(mid - expected_t)
            if dist < best_dist:
                best_dist = dist
                best_i = s_i
        if best_i >= 0 and best_dist < max(2.5, total_dur * 0.25):
            used_indices.add(best_i)
            s_start, s_end = silences[best_i]
            # Potong di 35% jeda agar helaan napas/ekspresi sebelum kalimat berikutnya ikut masuk ke scene berikutnya
            cut_t = s_start + 0.35 * (s_end - s_start)
        else:
            cut_t = max(split_points[-1] + 0.5, expected_t)
        split_points.append(round(cut_t, 3))
    split_points.append(round(total_dur, 3))

    out_paths: list[Path] = []
    for i, sc in enumerate(scenes):
        t0, t1 = split_points[i], split_points[i + 1]
        dst = audio_dir / f"scene_{sc.id:03d}.mp3"
        cmd = [
            ffmpeg_exe,
            "-y",
            "-i",
            str(full_audio_path),
            "-ss",
            f"{t0:.3f}",
            "-to",
            f"{t1:.3f}",
            "-c:a",
            "libmp3lame",
            "-q:a",
            "2",
            str(dst),
        ]
        subprocess.run(cmd, capture_output=True, text=True)
        out_paths.append(dst)
    return out_paths


def render_project(
    project: Project,
    voice: str = DEFAULT_VOICE,
    tts_fn: Callable[[str, Path, str], float] | None = None,
    fps: int = 15,
    style_override: str | None = None,
    image_fetcher: Callable[[str], bytes] | None = None,
    keep_audio: bool = False,
    full_audio_path: Path | None = None,
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
    images_dir = project.out_dir / "images"
    for d in (frames_dir, audio_dir, segments_dir):
        d.mkdir(parents=True, exist_ok=True)

    if full_audio_path is not None:
        if not full_audio_path.exists():
            raise ValueError(f"File audio tidak ditemukan: {full_audio_path}")
        split_full_audio_to_scenes(ffmpeg_exe, full_audio_path, sb.scenes, audio_dir)
        keep_audio = True

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

        end_bg_img: Image.Image | None = None
        if s.end_image_file:
            end_p = project.root / s.end_image_file
            if end_p.exists():
                with Image.open(end_p) as loaded_end:
                    end_bg_img = loaded_end.convert("RGB")

        # Deteksi otomatis keyframe multi-pose (scene_XXX_pose1.png, pose2.png, dst.)
        pose_imgs: list[Image.Image] = []
        pose_paths = sorted(images_dir.glob(f"scene_{s.id:03d}_pose*.png"))
        if pose_paths:
            s.pose_files = [str(pp.relative_to(project.root)) for pp in pose_paths]
            for pp in pose_paths:
                with Image.open(pp) as loaded_pose:
                    pose_imgs.append(loaded_pose.convert("RGB"))

        spoken = s.tts_text or s.narration
        if keep_audio and audio_path.exists() and audio_path.stat().st_size > 100:
            dur = _probe_audio_duration(audio_path)
        else:
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
            end_bg_image=end_bg_img,
            pose_images=pose_imgs or None,
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
            end_bg_image=end_bg_img,
            pose_images=pose_imgs or None,
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
