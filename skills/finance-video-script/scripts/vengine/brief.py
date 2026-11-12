"""Brief per video: satu-satunya input yang diisi manusia (selain panduan)."""
from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field


class Brief(BaseModel):
    topik: str
    format: Literal["A", "B", "S"] = "B"           # A = cerita, B = panduan langkah, S = short-form (Shorts/TikTok)
    durasi_menit: float = Field(10, ge=0.5, le=30)
    style: str = "flat-vector"
    audiens_spesifik: str = ""
    angka_kunci: dict[str, int | float | str] = Field(default_factory=dict)
    jumlah_bagian: int = Field(3, ge=2, le=5)  # transformasi (A) / strategi (B)
    tokoh: dict[str, dict] = Field(default_factory=dict)   # khusus format A
    instrumen_boleh_disebut: list[str] = Field(default_factory=list)
    cta: dict = Field(default_factory=dict)
    catatan_khusus: str = ""


def load_brief(path: Path) -> Brief:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return Brief(**data)


def save_brief(brief: Brief, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(brief.model_dump(), sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
