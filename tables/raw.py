from __future__ import annotations

from typing import TYPE_CHECKING

from fontTools.ttLib.tables import DefaultTable

if TYPE_CHECKING:
    from fontTools.ttLib import TTFont


def add_raw_table(font: TTFont, tag: str, data: bytes) -> None:
    table = DefaultTable.DefaultTable(tag)
    table.data = data
    font[tag] = table

