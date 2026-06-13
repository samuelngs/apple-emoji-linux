from __future__ import annotations

import logging

from fontTools.ttLib import TTFont

from config_types import GeneratedStrikesConfig
from models import BitmapGlyph, BitmapStrike
from bitmap.png import resize_png
from progress import Progress
from source.sbix import collect_sbix_glyph_images, get_sbix_strikes

LOG = logging.getLogger(__name__)


def generate_bitmap_strikes(
    font: TTFont,
    config: GeneratedStrikesConfig | None,
) -> list[BitmapStrike]:
    if config is None:
        return []

    available = set(get_sbix_strikes(font))
    if config.source not in available:
        raise ValueError(
            f"Generated bitmap strike source ppem={config.source} is not in source font "
            f"{sorted(available)}",
        )

    source_glyphs, _metadata = collect_sbix_glyph_images(font, ppem=config.source)
    if not source_glyphs:
        raise ValueError(f"Generated bitmap strike source ppem={config.source} has no PNG glyphs")

    strikes: list[BitmapStrike] = []
    total = len(source_glyphs) * len(config.sizes)
    progress = Progress("Generating bitmap strikes", total, LOG)
    progress.start()
    for ppem in config.sizes:
        glyphs: list[BitmapGlyph] = []
        for glyph in source_glyphs:
            glyphs.append(
                BitmapGlyph(
                    gid=glyph.gid,
                    name=glyph.name,
                    png=resize_png(glyph.png, ppem),
                    origin_x=round(glyph.origin_x * ppem / config.source),
                    origin_y=round(glyph.origin_y * ppem / config.source),
                ),
            )
            progress.advance()
        strikes.append(BitmapStrike(ppem=ppem, glyphs=tuple(glyphs)))
        LOG.info(
            "Generated strike ppem=%d from ppem=%d, %d glyphs",
            ppem,
            config.source,
            len(glyphs),
        )
    progress.finish()
    return strikes
