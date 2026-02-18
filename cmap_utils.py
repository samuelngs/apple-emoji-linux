"""Unicode cmap for CBDT output (platform 3, encoding 1 or 4)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fontTools.ttLib import TTFont


def ensure_unicode_cmap(font: TTFont) -> None:
    """Make sure we have a Unicode cmap; add platform 3 enc 4 from getBestCmap if not."""
    from fontTools.ttLib.tables._c_m_a_p import CmapSubtable

    cmap_table = font["cmap"]
    for t in cmap_table.tables:
        if t.platformID == 3 and t.platEncID in (1, 4):
            return
    best = font.getBestCmap()
    if not best:
        return
    subtable = CmapSubtable.newSubtable(4)
    subtable.platformID = 3
    subtable.platEncID = 4
    subtable.language = 0
    subtable.cmap = best
    cmap_table.tables.append(subtable)
