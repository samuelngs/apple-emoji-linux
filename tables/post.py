from __future__ import annotations

from typing import TYPE_CHECKING

from config import PostConfig

if TYPE_CHECKING:
    from fontTools.ttLib import TTFont


def apply_post_policy(font: TTFont, config: PostConfig | None) -> None:
    if config is None or "post" not in font:
        return
    if config.format is not None:
        font["post"].formatType = float(config.format)

