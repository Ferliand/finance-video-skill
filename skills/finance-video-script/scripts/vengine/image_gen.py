"""Pembuatan prompt visual ber-style dan generator aset gambar full-screen (Pollinations Flux)."""
from __future__ import annotations

from .brief import Brief
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
