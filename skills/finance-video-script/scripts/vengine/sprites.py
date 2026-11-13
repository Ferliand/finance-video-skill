"""Utilitas Sprite Sheet (Grid 2x2) dan penghapus latar polos untuk arsitektur Layered Puppet (2.5D Puppet)."""
from __future__ import annotations

from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter


def remove_solid_background(img: Image.Image, tolerance: float = 38.0) -> Image.Image:
    """Hapus background polos dari tepi kanvas (flood-fill + soft edge) sehingga bagian dalam karakter tetap utuh."""
    try:
        from rembg import remove  # type: ignore
        return remove(img.convert("RGBA"))
    except Exception:
        pass

    rgba = img.convert("RGBA")
    arr = np.array(rgba, dtype=np.uint8)
    h, w, _ = arr.shape
    rgb = arr[:, :, :3].astype(np.float32)

    # Ambil sampel warna dominan tepi (4 sudut + tengah tepi) sebagai referensi background polos
    border_pixels = np.concatenate(
        [rgb[0, :, :], rgb[h - 1, :, :], rgb[:, 0, :], rgb[:, w - 1, :]],
        axis=0,
    )
    bg_color = np.median(border_pixels, axis=0)

    # Jarak warna Euclidean terhadap warna background tepi
    dist = np.linalg.norm(rgb - bg_color, axis=2)
    candidate_bg = dist <= tolerance

    # Connected flood-fill hanya dari piksel tepi luar agar warna mirip di dalam karakter tidak ikut terhapus
    visited = np.zeros((h, w), dtype=bool)
    q: deque[tuple[int, int]] = deque()
    for x in range(w):
        if candidate_bg[0, x]:
            visited[0, x] = True
            q.append((0, x))
        if candidate_bg[h - 1, x] and not visited[h - 1, x]:
            visited[h - 1, x] = True
            q.append((h - 1, x))
    for y in range(h):
        if candidate_bg[y, 0] and not visited[y, 0]:
            visited[y, 0] = True
            q.append((y, 0))
        if candidate_bg[y, w - 1] and not visited[y, w - 1]:
            visited[y, w - 1] = True
            q.append((y, w - 1))

    while q:
        cy, cx = q.popleft()
        for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
            if 0 <= ny < h and 0 <= nx < w and not visited[ny, nx] and candidate_bg[ny, nx]:
                visited[ny, nx] = True
                q.append((ny, nx))

    alpha = np.where(visited, 0, 255).astype(np.uint8)
    alpha_img = Image.fromarray(alpha, mode="L").filter(ImageFilter.GaussianBlur(radius=0.8))
    arr[:, :, 3] = np.array(alpha_img, dtype=np.uint8)
    return Image.fromarray(arr, mode="RGBA")


def trim_transparent(img: Image.Image, padding: int = 8) -> Image.Image:
    """Pangkas ruang transparan berlebih di sekeliling sprite dengan menyisakan sedikit padding."""
    rgba = img.convert("RGBA")
    bbox = rgba.getbbox()
    if not bbox:
        return rgba
    x0 = max(0, bbox[0] - padding)
    y0 = max(0, bbox[1] - padding)
    x1 = min(rgba.width, bbox[2] + padding)
    y1 = min(rgba.height, bbox[3] + padding)
    return rgba.crop((x0, y0, x1, y1))


def split_sprite_sheet_2x2(
    sheet_path: Path,
    out_dir: Path,
    pose_names: tuple[str, str, str, str] | list[str] = ("pose1", "pose2", "pose3", "pose4"),
    remove_bg: bool = True,
    tolerance: float = 38.0,
) -> list[Path]:
    """Potong 1 gambar Sprite Sheet Grid 2x2 menjadi 4 file PNG transparan terpisah."""
    if len(pose_names) != 4:
        raise ValueError("Sprite sheet 2x2 membutuhkan tepat 4 nama pose.")
    out_dir.mkdir(parents=True, exist_ok=True)
    with Image.open(sheet_path) as im:
        src = im.convert("RGBA")
    w, h = src.size
    mx, my = w // 2, h // 2
    # Pangkas 2% margin dalam di garis potong tengah agar garis grid tipis tidak ikut terbawa
    pad_x = max(2, int(w * 0.01))
    pad_y = max(2, int(h * 0.01))
    quadrants = [
        (0, 0, mx - pad_x, my - pad_y),
        (mx + pad_x, 0, w, my - pad_y),
        (0, my + pad_y, mx - pad_x, h),
        (mx + pad_x, my + pad_y, w, h),
    ]
    out_paths: list[Path] = []
    for name, box in zip(pose_names, quadrants):
        cell = src.crop(box)
        if remove_bg:
            cell = remove_solid_background(cell, tolerance=tolerance)
        cell = trim_transparent(cell)
        dst = out_dir / f"{name}.png"
        cell.save(dst, format="PNG")
        out_paths.append(dst)
    return out_paths
