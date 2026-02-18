"""Read sbix strikes and PNG glyphs from Apple Color Emoji (or any sbix TTC)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Generator

from fontTools.ttLib import TTFont

LOG = logging.getLogger(__name__)

PNG_SIGNATURE = bytes((0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A))


@dataclass
class StrikeMetadata:
    ppem: int
    resolution: int


def load_font(ttc_path: str | Path, font_number: int = 0) -> TTFont:
    """Load one face from a TTC."""
    path = Path(ttc_path)
    if not path.exists():
        raise FileNotFoundError(f"TTC not found: {path}")
    return TTFont(path, fontNumber=font_number)


def get_sbix_strikes(font: TTFont) -> dict[int, Any]:
    """Strikes keyed by ppem. Raises if no sbix table."""
    if "sbix" not in font:
        raise ValueError("Font has no 'sbix' table")
    return font["sbix"].strikes


def _resolve_image_data(glyph_obj, strike_glyphs: dict) -> bytes | None:
    """Follow dupe/flip refs to get the actual image bytes."""
    if glyph_obj.imageData is not None:
        return glyph_obj.imageData
    if getattr(glyph_obj, "is_reference_type", lambda: False)():
        ref_name = getattr(glyph_obj, "referenceGlyphName", None)
        if ref_name and ref_name in strike_glyphs:
            return _resolve_image_data(strike_glyphs[ref_name], strike_glyphs)
    return None


def iter_sbix_glyphs(
    font: TTFont,
    ppem: int | None = None,
    *,
    validate_png: bool = True,
) -> Generator[tuple[int, str, bytes, StrikeMetadata], None, None]:
    """Yield (gid, name, png_bytes, metadata) for each glyph with PNG in the chosen strike. ppem=None uses largest strike."""
    strikes = get_sbix_strikes(font)
    if not strikes:
        raise ValueError("Font has no sbix strikes")
    if ppem is not None and ppem not in strikes:
        raise ValueError(f"ppem {ppem} not in strikes {sorted(strikes.keys())}")
    strike_ppem = max(strikes.keys()) if ppem is None else ppem
    strike = strikes[strike_ppem]
    metadata = StrikeMetadata(ppem=strike.ppem, resolution=getattr(strike, "resolution", 72))

    glyph_order = font.getGlyphOrder()
    strike_glyphs = strike.glyphs

    for glyph_name in glyph_order:
        if glyph_name not in strike_glyphs:
            continue
        glyph_obj = strike_glyphs[glyph_name]
        raw = _resolve_image_data(glyph_obj, strike_glyphs)
        if not raw:
            continue
        if validate_png and not raw.startswith(PNG_SIGNATURE):
            LOG.warning("Glyph %s has non-PNG sbix data, skipping", glyph_name)
            continue
        try:
            gid = font.getGlyphID(glyph_name)
        except KeyError:
            continue
        yield gid, glyph_name, raw, metadata


def collect_sbix_glyphs(
    font: TTFont,
    ppem: int | None = None,
    *,
    validate_png: bool = True,
) -> tuple[list[tuple[int, str, bytes]], StrikeMetadata]:
    """Same as iter_sbix_glyphs but returns a list and the strike metadata."""
    ordered: list[tuple[int, str, bytes]] = []
    meta: StrikeMetadata | None = None
    for gid, name, png_data, m in iter_sbix_glyphs(font, ppem=ppem, validate_png=validate_png):
        ordered.append((gid, name, png_data))
        if meta is None:
            meta = m
    if meta is None:
        strikes = get_sbix_strikes(font)
        strike_ppem = max(strikes.keys()) if ppem is None else ppem
        meta = StrikeMetadata(ppem=strike_ppem, resolution=72)
    return ordered, meta
