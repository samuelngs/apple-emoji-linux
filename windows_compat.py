"""Windows/DirectWrite compat so the font can replace Segoe UI Emoji."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fontTools.ttLib import TTFont

LOG = logging.getLogger(__name__)


def apply_windows_compat(font: TTFont) -> None:
    """Cmap, names, OS/2, head, post. Use when --target windows."""
    ensure_windows_cmap(font)
    update_font_names_segoe(font)
    update_os2_directwrite(font)
    update_head_table(font)
    update_post_table(font)


def ensure_windows_cmap(font: TTFont) -> None:
    """BMP subtable (3/1) plus Format 12 for full Unicode."""
    from fontTools.ttLib.tables._c_m_a_p import CmapSubtable

    cmap = font["cmap"]
    has_bmp = False
    full_subtable = None

    for t in cmap.tables:
        if t.platformID == 3 and t.platEncID == 1:
            has_bmp = True
        if t.platformID == 3 and t.platEncID in (4, 10):
            full_subtable = t
            break

    if full_subtable is None:
        best = font.getBestCmap()
        if best:
            bmp_cmap = {c: n for c, n in best.items() if 0 <= c <= 0xFFFF}
            if bmp_cmap:
                bmp_subtable = CmapSubtable.newSubtable(4)
                bmp_subtable.platformID = 3
                bmp_subtable.platEncID = 1
                bmp_subtable.language = 0
                bmp_subtable.cmap = bmp_cmap
                cmap.tables.insert(0, bmp_subtable)
                LOG.debug("Added Windows Unicode BMP cmap (%d chars)", len(bmp_cmap))
        return

    if not has_bmp and hasattr(full_subtable, "cmap"):
        bmp_subtable = CmapSubtable.newSubtable(4)
        bmp_subtable.platformID = 3
        bmp_subtable.platEncID = 1
        bmp_subtable.language = 0
        bmp_subtable.cmap = {
            code: name
            for code, name in full_subtable.cmap.items()
            if 0 <= code <= 0xFFFF
        }
        cmap.tables.insert(0, bmp_subtable)
        LOG.debug("Added Windows Unicode BMP cmap (%d chars)", len(bmp_subtable.cmap))

    for i, t in enumerate(cmap.tables):
        if t.platformID == 3 and t.platEncID in (4, 10) and getattr(t, "format", 0) != 12:
            if hasattr(t, "cmap") and t.cmap:
                fmt12 = CmapSubtable.newSubtable(12)
                fmt12.platformID = 3
                fmt12.platEncID = 10
                fmt12.language = 0
                fmt12.cmap = t.cmap.copy()
                cmap.tables[i] = fmt12
                LOG.debug("Converted to Format 12 cmap for full Unicode")
            break


def update_font_names_segoe(font: TTFont) -> None:
    """Names to Segoe UI Emoji so we can replace seguiemj."""
    from fontTools.ttLib.tables._n_a_m_e import NameRecord

    name_table = font["name"]
    name_table.names = []

    names = [
        (1, "Segoe UI Emoji"),
        (2, "Regular"),
        (3, "Microsoft:Segoe UI Emoji Regular:2023"),
        (4, "Segoe UI Emoji"),
        (5, "Version 1.00"),
        (6, "SegoeUIEmoji"),
        (16, "Segoe UI Emoji"),
        (17, "Regular"),
        (21, "Segoe UI Emoji"),
        (22, "Regular"),
    ]

    for platform_id, plat_enc_id, lang_id in [
        (3, 1, 0x409),
        (3, 10, 0x409),
        (1, 0, 0),
    ]:
        for name_id, value in names:
            rec = NameRecord()
            rec.nameID = name_id
            rec.platformID = platform_id
            rec.platEncID = plat_enc_id
            rec.langID = lang_id
            rec.string = value
            name_table.names.append(rec)

    LOG.debug("Updated name table to Segoe UI Emoji")


def update_os2_directwrite(font: TTFont) -> None:
    """OS/2 for DirectWrite / Segoe replacement."""
    if "OS/2" not in font:
        return
    os2 = font["OS/2"]
    os2.version = 4
    os2.usWeightClass = 400
    os2.usWidthClass = 5
    os2.fsType = 0
    os2.sFamilyClass = 0

    os2.sTypoAscender = 1069
    os2.sTypoDescender = -293
    os2.sTypoLineGap = 0

    os2.fsSelection = 64 | (1 << 7)  # USE_TYPO_METRICS for DirectWrite

    os2.usFirstCharIndex = 0x20
    os2.usLastCharIndex = 0x1F6FF

    os2.ulUnicodeRange1 = 0x00000001 | (1 << 25)
    os2.ulUnicodeRange2 = (1 << (57 - 32)) | (1 << (58 - 32)) | (1 << (59 - 32))
    os2.ulUnicodeRange3 = 0
    os2.ulUnicodeRange4 = 0

    panose = os2.panose
    panose.bFamilyType = 5
    panose.bSerifStyle = 0
    panose.bWeight = 5
    panose.bProportion = 0
    panose.bContrast = 0
    panose.bStrokeVariation = 0
    panose.bArmStyle = 0
    panose.bLetterform = 0
    panose.bMidline = 0
    panose.bXHeight = 0

    LOG.debug("Updated OS/2 for DirectWrite")


def update_head_table(font: TTFont) -> None:
    """Clear macStyle."""
    if "head" in font:
        font["head"].macStyle = 0


def update_post_table(font: TTFont) -> None:
    """post format 3 for Windows."""
    if "post" in font:
        font["post"].formatType = 3.0
