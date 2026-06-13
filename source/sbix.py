"""Read PNG glyphs from sbix strikes."""

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


@dataclass(frozen=True)
class SbixGlyphImage:
    gid: int
    name: str
    png: bytes
    origin_x: int
    origin_y: int
    metadata: StrikeMetadata


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


def _glyph_origin(glyph_obj) -> tuple[int, int]:
    return (
        int(getattr(glyph_obj, "originOffsetX", 0) or 0),
        int(getattr(glyph_obj, "originOffsetY", 0) or 0),
    )


def _resolve_image_record(
    glyph_obj,
    strike_glyphs: dict,
    *,
    origin_x: int = 0,
    origin_y: int = 0,
) -> tuple[bytes, int, int] | None:
    """Follow dupe/flip refs to get image bytes and accumulated origin offsets."""
    own_x, own_y = _glyph_origin(glyph_obj)
    origin_x += own_x
    origin_y += own_y
    if glyph_obj.imageData is not None:
        return glyph_obj.imageData, origin_x, origin_y
    if getattr(glyph_obj, "is_reference_type", lambda: False)():
        ref_name = getattr(glyph_obj, "referenceGlyphName", None)
        if ref_name and ref_name in strike_glyphs:
            return _resolve_image_record(
                strike_glyphs[ref_name],
                strike_glyphs,
                origin_x=origin_x,
                origin_y=origin_y,
            )
    return None


def _resolve_image_data(glyph_obj, strike_glyphs: dict) -> bytes | None:
    """Follow dupe/flip refs to get the actual image bytes."""
    record = _resolve_image_record(glyph_obj, strike_glyphs)
    if record is None:
        return None
    return record[0]


def iter_sbix_glyphs(
    font: TTFont,
    ppem: int | None = None,
    *,
    validate_png: bool = True,
) -> Generator[tuple[int, str, bytes, StrikeMetadata], None, None]:
    for image in iter_sbix_glyph_images(font, ppem=ppem, validate_png=validate_png):
        yield image.gid, image.name, image.png, image.metadata


def iter_sbix_glyph_images(
    font: TTFont,
    ppem: int | None = None,
    *,
    validate_png: bool = True,
) -> Generator[SbixGlyphImage, None, None]:
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
        record = _resolve_image_record(glyph_obj, strike_glyphs)
        if not record:
            continue
        raw, origin_x, origin_y = record
        if validate_png and not raw.startswith(PNG_SIGNATURE):
            LOG.warning("Glyph %s has non-PNG sbix data, skipping", glyph_name)
            continue
        try:
            gid = font.getGlyphID(glyph_name)
        except KeyError:
            continue
        yield SbixGlyphImage(
            gid=gid,
            name=glyph_name,
            png=raw,
            origin_x=origin_x,
            origin_y=origin_y,
            metadata=metadata,
        )


def collect_sbix_glyphs(
    font: TTFont,
    ppem: int | None = None,
    *,
    validate_png: bool = True,
) -> tuple[list[tuple[int, str, bytes]], StrikeMetadata]:
    images, meta = collect_sbix_glyph_images(font, ppem=ppem, validate_png=validate_png)
    return [(image.gid, image.name, image.png) for image in images], meta


def collect_sbix_glyph_images(
    font: TTFont,
    ppem: int | None = None,
    *,
    validate_png: bool = True,
) -> tuple[list[SbixGlyphImage], StrikeMetadata]:
    meta: StrikeMetadata | None = None
    images: list[SbixGlyphImage] = []
    for image in iter_sbix_glyph_images(font, ppem=ppem, validate_png=validate_png):
        images.append(image)
        m = image.metadata
        if meta is None:
            meta = m
    if meta is None:
        strikes = get_sbix_strikes(font)
        strike_ppem = max(strikes.keys()) if ppem is None else ppem
        meta = StrikeMetadata(ppem=strike_ppem, resolution=72)
    return images, meta


def get_emoji_png(
    font: TTFont,
    codepoint: int,
    ppem: int | None = None,
) -> tuple[bytes, int] | None:
    cmap = font.getBestCmap()
    if not cmap or codepoint not in cmap:
        return None
    glyph_name = cmap[codepoint]
    strikes = get_sbix_strikes(font)
    if not strikes:
        return None
    available = sorted(strikes.keys())
    if ppem is not None:
        if ppem in strikes:
            strike_ppem = ppem
        else:
            strike_ppem = min(available, key=lambda p: abs(p - ppem))
    else:
        strike_ppem = max(available)
    strike = strikes[strike_ppem]
    if glyph_name not in strike.glyphs:
        return None
    raw = _resolve_image_data(strike.glyphs[glyph_name], strike.glyphs)
    if not raw or not raw.startswith(PNG_SIGNATURE):
        return None
    return (raw, strike_ppem)
