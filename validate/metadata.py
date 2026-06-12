from __future__ import annotations

from pathlib import Path
from typing import Any

from fontTools.ttLib import TTFont


POLICY_NAME_IDS = {1, 2, 4, 6, 16, 17, 21, 22}


def metadata_snapshot(font_path: str | Path) -> dict[str, Any]:
    """Return a compact metadata snapshot for generated-font regression tests."""
    font = TTFont(font_path)
    try:
        return {
            "tables": list(font.keys()),
            "glyph_count": len(font.getGlyphOrder()),
            "bitmap_strikes": _bitmap_strikes(font),
            "cmap_records": _cmap_records(font),
            "names": _name_records(font),
            "head": _head_values(font),
            "hhea": _hhea_values(font),
            "os2": _os2_values(font),
            "post": _post_values(font),
        }
    finally:
        font.close()


def _bitmap_strikes(font: TTFont) -> list[dict[str, int]]:
    if "CBLC" not in font:
        return []
    return [
        {
            "ppem_x": strike.bitmapSizeTable.ppemX,
            "ppem_y": strike.bitmapSizeTable.ppemY,
            "start_glyph": strike.bitmapSizeTable.startGlyphIndex,
            "end_glyph": strike.bitmapSizeTable.endGlyphIndex,
            "subtables": len(strike.indexSubTables),
        }
        for strike in font["CBLC"].strikes
    ]


def _cmap_records(font: TTFont) -> list[dict[str, int]]:
    if "cmap" not in font:
        return []
    return [
        {
            "platform_id": subtable.platformID,
            "platform_encoding_id": subtable.platEncID,
            "language": subtable.language,
            "format": subtable.format,
            "entries": len(getattr(subtable, "cmap", {}) or {}),
        }
        for subtable in font["cmap"].tables
    ]


def _name_records(font: TTFont) -> dict[str, list[str]]:
    if "name" not in font:
        return {}
    out: dict[str, set[str]] = {}
    for rec in font["name"].names:
        if rec.nameID not in POLICY_NAME_IDS:
            continue
        try:
            value = rec.toUnicode()
        except UnicodeDecodeError:
            continue
        out.setdefault(str(rec.nameID), set()).add(value)
    return {name_id: sorted(values) for name_id, values in sorted(out.items())}


def _head_values(font: TTFont) -> dict[str, int] | None:
    if "head" not in font:
        return None
    head = font["head"]
    return {
        "units_per_em": head.unitsPerEm,
        "mac_style": head.macStyle,
        "y_min": head.yMin,
        "y_max": head.yMax,
    }


def _hhea_values(font: TTFont) -> dict[str, int] | None:
    if "hhea" not in font:
        return None
    hhea = font["hhea"]
    return {
        "ascent": hhea.ascent,
        "descent": hhea.descent,
        "line_gap": hhea.lineGap,
    }


def _os2_values(font: TTFont) -> dict[str, int] | None:
    if "OS/2" not in font:
        return None
    os2 = font["OS/2"]
    return {
        "version": os2.version,
        "fs_type": os2.fsType,
        "fs_selection": os2.fsSelection,
        "typo_ascender": os2.sTypoAscender,
        "typo_descender": os2.sTypoDescender,
        "typo_line_gap": os2.sTypoLineGap,
        "win_ascent": os2.usWinAscent,
        "win_descent": os2.usWinDescent,
        "unicode_range_1": os2.ulUnicodeRange1,
        "unicode_range_2": os2.ulUnicodeRange2,
        "unicode_range_3": os2.ulUnicodeRange3,
        "unicode_range_4": os2.ulUnicodeRange4,
    }


def _post_values(font: TTFont) -> dict[str, float] | None:
    if "post" not in font:
        return None
    return {"format": font["post"].formatType}

