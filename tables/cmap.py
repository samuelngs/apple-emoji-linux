"""Unicode cmap helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from config import CmapConfig

if TYPE_CHECKING:
    from fontTools.ttLib import TTFont


def _dedupe_cmap_subtables(font: TTFont) -> None:
    """Keep one cmap subtable per OpenType platform/encoding/language key."""
    cmap_table = font["cmap"]
    seen: set[tuple[int, int, int]] = set()
    unique = []
    for subtable in cmap_table.tables:
        key = (subtable.platformID, subtable.platEncID, subtable.language)
        if key in seen:
            continue
        seen.add(key)
        unique.append(subtable)
    cmap_table.tables = unique


def _full_unicode_cmap(font: TTFont) -> dict[int, str] | None:
    cmap_table = font["cmap"]
    for platform_id, plat_enc_id in ((3, 10), (3, 4)):
        for subtable in cmap_table.tables:
            if (
                subtable.platformID == platform_id
                and subtable.platEncID == plat_enc_id
                and hasattr(subtable, "cmap")
                and subtable.cmap
            ):
                return subtable.cmap
    return font.getBestCmap()


def ensure_unicode_cmap(font: TTFont) -> None:
    """Make sure we have a Windows Unicode BMP cmap."""
    from fontTools.ttLib.tables._c_m_a_p import CmapSubtable

    cmap_table = font["cmap"]
    for t in cmap_table.tables:
        if t.platformID == 3 and t.platEncID == 1:
            return
    full_cmap = _full_unicode_cmap(font)
    if not full_cmap:
        return
    bmp_cmap = {code: name for code, name in full_cmap.items() if 0 <= code <= 0xFFFF}
    if not bmp_cmap:
        return
    subtable = CmapSubtable.newSubtable(4)
    subtable.platformID = 3
    subtable.platEncID = 1
    subtable.language = 0
    subtable.cmap = bmp_cmap
    cmap_table.tables.append(subtable)
    _dedupe_cmap_subtables(font)


def add_cmap_platform_3_encoding_10(font: TTFont) -> None:
    """Add platform 3 encoding 10 (Unicode UCS-4) format 12 cmap."""
    from fontTools.ttLib.tables._c_m_a_p import CmapSubtable

    cmap_table = font["cmap"]
    for t in cmap_table.tables:
        if t.platformID == 3 and t.platEncID == 10:
            return
    full_cmap = _full_unicode_cmap(font)
    if not full_cmap:
        return
    subtable = CmapSubtable.newSubtable(12)
    subtable.platformID = 3
    subtable.platEncID = 10
    subtable.language = 0
    subtable.cmap = full_cmap.copy()
    cmap_table.tables.append(subtable)
    _dedupe_cmap_subtables(font)

def apply_cmap_policy(font: TTFont, config: CmapConfig) -> None:
    if config.bmp:
        ensure_unicode_cmap(font)
    if config.ucs4:
        add_cmap_platform_3_encoding_10(font)
    for entry in config.entries:
        add_cmap_entry(font, entry.codepoint, entry.glyph)
    _dedupe_cmap_subtables(font)


def add_cmap_entry(font: TTFont, codepoint: int, glyph_name: str) -> None:
    if glyph_name not in font.getGlyphOrder():
        raise ValueError(f"Configured cmap glyph does not exist: {glyph_name}")
    for subtable in font["cmap"].tables:
        cmap = getattr(subtable, "cmap", None)
        if cmap is None:
            continue
        if subtable.format == 4 and codepoint > 0xFFFF:
            continue
        cmap[codepoint] = glyph_name
