from __future__ import annotations

from pathlib import Path

from fontTools.ttLib import TTFont


def load_font(font_path: str | Path, font_number: int = 0) -> TTFont:
    """Load one font face from a TTF/TTC path."""
    path = Path(font_path)
    if not path.exists():
        raise FileNotFoundError(f"TTC not found: {path}")
    return TTFont(path, fontNumber=font_number)

