"""Build the output font skeleton."""

from __future__ import annotations

from fontTools.ttLib import TTFont
from tables.raw import add_raw_table

TABLES_TO_DROP = [
    "cvt ",
    "fpgm",
    "prep",
    "CFF ",
    "CFF2",
    "VORG",
    "sbix",
]

def drop_tables(
    font: TTFont,
    extra: list[str] | None = None,
    *,
    source_tables: bool = True,
    keep_outlines: bool = True,
) -> None:
    tags = list(TABLES_TO_DROP) if source_tables else []
    if not keep_outlines:
        tags = tags + ["glyf", "loca"]
    if extra:
        tags = tags + extra
    for tag in tags:
        if tag in font:
            del font[tag]


def build_skeleton(
    font: TTFont,
    cbdt_bytes: bytes,
    cblc_bytes: bytes,
    *,
    drop_vertical: bool = False,
    keep_outlines: bool = True,
    drop_source_tables: bool = True,
    add_bitmap_tables: bool = True,
) -> None:
    drop_tables(
        font,
        source_tables=drop_source_tables,
        keep_outlines=keep_outlines,
    )
    if drop_vertical:
        for tag in ("vhea", "vmtx"):
            if tag in font:
                del font[tag]

    if add_bitmap_tables:
        add_raw_table(font, "CBDT", cbdt_bytes)
        add_raw_table(font, "CBLC", cblc_bytes)
