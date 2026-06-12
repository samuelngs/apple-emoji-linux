from __future__ import annotations

from typing import TYPE_CHECKING

from config import HeadConfig
from fontTools.ttLib.tables import DefaultTable
from fontTools.ttLib.scaleUpem import scale_upem

if TYPE_CHECKING:
    from fontTools.ttLib import TTFont


def apply_head_policy(font: TTFont, config: HeadConfig | None) -> None:
    if config is None or "head" not in font:
        return
    if (
        config.units_per_em is not None
        and font["head"].unitsPerEm != config.units_per_em
    ):
        raw_morx = font.getTableData("morx") if "morx" in font else None
        scale_upem(font, config.units_per_em)
        if raw_morx is not None:
            table = DefaultTable.DefaultTable("morx")
            table.data = raw_morx
            font["morx"] = table
    if config.mac_style is not None:
        font["head"].macStyle = config.mac_style
