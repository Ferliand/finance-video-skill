"""Pembuatan prompt visual ber-style dan generator aset gambar full-screen (Pollinations Flux)."""
from __future__ import annotations

import hashlib
import io
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Callable

from PIL import Image, ImageDraw

from .brief import Brief
from .page_mapper import map_storyboard_pages
from .project import Project
from .schema import Scene, StoryBible

NEGATIVE_SUFFIX = "no text, no letters, no numbers, no watermark, clean composition"

STYLE_PRESETS: dict[str, str] = {
    "flat-vector": "modern flat vector illustration, warm editorial palette, soft gradients, atmospheric lighting, minimal facial detail",
    "3d-pixar": "3D Pixar Disney style render, Octane render, soft global illumination, warm cinematic lighting, expressive stylized environment",
    "anime-ghibli": "Studio Ghibli inspired anime background art, hand-painted gouache texture, lush warm lighting, cozy atmospheric detail",
    "cinematic-realistic": "cinematic photorealistic photography, 35mm lens, shallow depth of field, golden hour dramatic lighting, film grain",
    "watercolor": "artistic watercolor and ink illustration, soft pastel washes, warm paper texture, gentle lighting",
    "comic-book": "modern graphic novel illustration, bold clean ink lines, vibrant cel shading, dynamic lighting",
    "dark-moody": "dark moody cinematic concept art, deep slate shadows, warm amber rim lighting, dramatic contrast",
}

_MOOD_ATMOSPHERE: dict[str, str] = {
    "tense": "dramatic moody shadows, late night lamp light, tense financial atmosphere",
    "neutral": "calm organized desk setting, soft natural daylight, balanced composition",
    "warm": "warm golden morning sunlight, cozy Indonesian home interior, peaceful atmosphere",
    "uplift": "bright inspiring sunrise glow, growing green plant beside coins, hopeful upward perspective",
    "melancholy": "rainy window reflection, soft twilight tones, contemplative mood",
}

_PAGE_VISUAL_FALLBACK: dict[str, str] = {
    "punchline_card": "minimalist dramatic spotlight on a wooden table with a single glowing gold coin, wide negative space",
    "section_title": "clean architectural perspective of a modern workspace with warm sunlight beams, wide negative space",
    "calc_step": "neatly stacked savings jars and wooden abacus beads on a warm desk, soft bokeh background",
    "number_callout": "glowing glass savings jar filled with coins on a sunlit windowsill, shallow depth of field",
    "myth_card": "dramatic split lighting on a crossroads sign and a magnifying glass over financial notes",
    "before_after": "contrasting split scene from cluttered dark desk to a clean sunlit desk with a thriving plant",
    "cta_comment": "cozy desk with a warm cup of coffee, open notebook and glowing pen, inviting atmosphere",
}


def resolve_style_prefix(style: str | None) -> str:
    """Kembalikan string style dari preset atau custom style pengguna."""
    if not style or not style.strip():
        return STYLE_PRESETS["flat-vector"]
    key = style.strip().lower()
    if key in STYLE_PRESETS:
        return STYLE_PRESETS[key]
    return style.strip()


def _auto_visual_description(scene: Scene, brief: Brief) -> str:
    """Bangun deskripsi visual kontekstual jika scene belum memiliki image_prompt."""
    ptype = scene.page_type or "illustration"
    if ptype in _PAGE_VISUAL_FALLBACK:
        base_desc = _PAGE_VISUAL_FALLBACK[ptype]
    elif "PUNCH" in scene.tags:
        base_desc = _PAGE_VISUAL_FALLBACK["punchline_card"]
    elif "CALC" in scene.tags or "NUMBER" in scene.tags:
        base_desc = _PAGE_VISUAL_FALLBACK["calc_step"]
    elif "SECTION" in scene.tags:
        base_desc = _PAGE_VISUAL_FALLBACK["section_title"]
    elif "CTA" in scene.tags:
        base_desc = _PAGE_VISUAL_FALLBACK["cta_comment"]
    else:
        base_desc = "cozy Indonesian daily life financial scene with savings jar and notebook on wooden desk"
    mood_desc = _MOOD_ATMOSPHERE.get(scene.mood, _MOOD_ATMOSPHERE["neutral"])
    return f"{base_desc}, {mood_desc}"


def build_scene_prompt(
    scene: Scene,
    brief: Brief,
    bible: StoryBible,
    style_override: str | None = None,
) -> str:
    """Gabungkan style prefix, descriptor tokoh, deskripsi visual scene, dan akhiran negatif."""
    style_prefix = resolve_style_prefix(style_override or brief.style)
    char_desc = {c.id: c.descriptor for c in bible.characters}
    parts = [style_prefix]
    for cid in scene.characters:
        if cid in char_desc and char_desc[cid]:
            parts.append(char_desc[cid])
    visual = (scene.image_prompt or "").strip() or _auto_visual_description(scene, brief)
    parts.append(visual)
    mood_hint = _MOOD_ATMOSPHERE.get(scene.mood)
    if mood_hint and mood_hint not in visual:
        parts.append(mood_hint)
    parts.append(NEGATIVE_SUFFIX)
    return ", ".join(parts)


def build_pollinations_url(
    prompt: str,
    width: int,
    height: int,
    seed: int,
    model: str = "flux",
) -> str:
    """Bangun URL Pollinations.ai untuk model Flux tanpa watermark."""
    encoded = urllib.parse.quote(prompt, safe="")
    return (
        f"https://image.pollinations.ai/prompt/{encoded}"
        f"?width={width}&height={height}&seed={seed}&model={model}&nologo=true&enhance=true"
    )


def _default_fetcher(url: str) -> bytes:
    """Unduh bytes gambar dari URL dengan retry eksponensial ringan."""
    last_err: Exception | None = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) vengine/1.0"},
            )
            with urllib.request.urlopen(req, timeout=45) as resp:
                return resp.read()
        except Exception as e:
            last_err = e
            if attempt < 2:
                time.sleep(2.0 * (attempt + 1))
    assert last_err is not None
    raise last_err


def render_fallback_canvas(scene: Scene, width: int, height: int) -> Image.Image:
    """Buat kanvas atmosferik full-screen bergradasi jika jaringan gagal/offline."""
    palettes = {
        "tense": ((18, 24, 38), (58, 32, 42), (232, 163, 61)),
        "warm": ((28, 36, 52), (78, 54, 38), (232, 163, 61)),
        "uplift": ((18, 42, 46), (38, 88, 72), (110, 210, 160)),
        "melancholy": ((20, 28, 44), (42, 54, 78), (148, 163, 184)),
        "neutral": ((22, 32, 48), (48, 66, 92), (232, 163, 61)),
    }
    top_c, bot_c, glow_c = palettes.get(scene.mood, palettes["neutral"])

    # Buat gradasi kecil lalu resize halus ke ukuran penuh agar sangat cepat
    grad_small = Image.new("RGB", (2, 128))
    for y in range(128):
        ratio = y / 127.0
        r = int(top_c[0] + (bot_c[0] - top_c[0]) * ratio)
        g = int(top_c[1] + (bot_c[1] - top_c[1]) * ratio)
        b = int(top_c[2] + (bot_c[2] - top_c[2]) * ratio)
        grad_small.putpixel((0, y), (r, g, b))
        grad_small.putpixel((1, y), (r, g, b))
    base = grad_small.resize((width, height), Image.Resampling.BILINEAR).convert("RGBA")

    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    cx, cy = width // 2, int(height * 0.42)
    for idx, radius_factor in enumerate((0.42, 0.28, 0.16)):
        rad = int(min(width, height) * radius_factor)
        alpha = 26 + idx * 18
        offset_x = ((scene.id * 53 + idx * 97) % 160) - 80
        offset_y = ((scene.id * 37 + idx * 61) % 120) - 60
        draw.ellipse(
            [cx + offset_x - rad, cy + offset_y - rad, cx + offset_x + rad, cy + offset_y + rad],
            fill=(glow_c[0], glow_c[1], glow_c[2], alpha),
        )
    return Image.alpha_composite(base, overlay).convert("RGB")


def _compute_seed(slug: str, scene_id: int) -> int:
    digest = hashlib.sha256(f"{slug}:{scene_id}".encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % 1_000_000


def generate_scene_image(
    scene: Scene,
    prompt: str,
    out_path: Path,
    width: int,
    height: int,
    seed: int,
    fetcher: Callable[[str], bytes] | None = None,
) -> Path:
    """Unduh gambar AI full-screen untuk satu scene atau simpan fallback atmosferik jika gagal."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fetch = fetcher or _default_fetcher
    url = build_pollinations_url(prompt, width=width, height=height, seed=seed)
    try:
        raw = fetch(url)
        with Image.open(io.BytesIO(raw)) as im:
            rgb = im.convert("RGB")
            iw, ih = rgb.size
            # Potong 4% tepi bawah/samping untuk memastikan bebas badge sudut, lalu resize ke ukuran penuh
            if iw >= 200 and ih >= 200:
                mx = int(iw * 0.02)
                my_bot = int(ih * 0.045)
                rgb = rgb.crop((mx, 0, iw - mx, ih - my_bot))
            if rgb.size != (width, height):
                rgb = rgb.resize((width, height), Image.Resampling.LANCZOS)
            rgb.save(out_path, format="PNG")
    except Exception:
        fallback = render_fallback_canvas(scene, width=width, height=height)
        fallback.save(out_path, format="PNG")
    return out_path


def generate_project_images(
    project: Project,
    style_override: str | None = None,
    scene_id: int | None = None,
    force: bool = False,
    fetcher: Callable[[str], bytes] | None = None,
) -> list[Path]:
    """Generate aset gambar full-screen untuk seluruh scene (atau satu scene) ke out/images/."""
    from . import workflow

    brief = project.load_brief()
    bible = project.load_bible()
    sb = project.load_storyboard()
    if not sb.scenes:
        raise ValueError("Storyboard masih kosong. Tambahkan scene terlebih dahulu.")

    if any(s.page_type is None for s in sb.scenes):
        sb = map_storyboard_pages(sb)

    if scene_id is not None and not any(s.id == scene_id for s in sb.scenes):
        valid_ids = ", ".join(str(s.id) for s in sb.scenes)
        raise ValueError(f"Scene {scene_id} tidak ditemukan. Scene yang tersedia: {valid_ids}")

    if style_override:
        brief.style = style_override
        from .brief import save_brief
        save_brief(brief, project.brief_path)

    is_vertical = brief.format == "S"
    width, height = (1080, 1920) if is_vertical else (1920, 1080)
    images_dir = project.out_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    generated_paths: list[Path] = []
    net_count = 0
    for s in sb.scenes:
        img_path = images_dir / f"scene_{s.id:03d}.png"
        s.image_file = str(img_path.relative_to(project.root))
        if scene_id is not None and s.id != scene_id:
            continue
        should_generate = force or (scene_id == s.id) or (not img_path.exists())
        if should_generate:
            if fetcher is None and net_count > 0:
                time.sleep(1.5)
            prompt = build_scene_prompt(s, brief, bible, style_override=style_override)
            seed = _compute_seed(project.slug, s.id)
            generate_scene_image(s, prompt, img_path, width=width, height=height, seed=seed, fetcher=fetcher)
            net_count += 1
        generated_paths.append(img_path)

    sb.style_prefix = resolve_style_prefix(style_override or brief.style)
    project.save_storyboard(sb)

    prompts = workflow.export_prompts(project, style_override=style_override)
    out_prompts = project.out_dir / "prompts.json"
    out_prompts.parent.mkdir(parents=True, exist_ok=True)
    out_prompts.write_text(json.dumps(prompts, ensure_ascii=False, indent=2), encoding="utf-8")

    return generated_paths
