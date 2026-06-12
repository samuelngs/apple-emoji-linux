from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from config import BuildRecipe


@dataclass(frozen=True)
class BuildRequest:
    recipe: BuildRecipe
    input_path: Path
    output_path: Path
    font_number: int = 0
    recompute_ligatures: bool = False


@dataclass(frozen=True)
class BitmapGlyph:
    gid: int
    name: str
    png: bytes


@dataclass(frozen=True)
class BitmapStrike:
    ppem: int
    glyphs: tuple[BitmapGlyph, ...]
