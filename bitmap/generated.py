from __future__ import annotations

import logging
from io import BytesIO

from fontTools.ttLib import TTFont
from PIL import Image

from config_types import GeneratedStrikesConfig
from models import BitmapGlyph, BitmapStrike
from progress import Progress
from source.sbix import collect_sbix_glyphs, get_sbix_strikes

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

    source_glyphs, _metadata = collect_sbix_glyphs(font, ppem=config.source)
    if not source_glyphs:
        raise ValueError(f"Generated bitmap strike source ppem={config.source} has no PNG glyphs")

    strikes: list[BitmapStrike] = []
    total = len(source_glyphs) * len(config.sizes)
    progress = Progress("Generating bitmap strikes", total, LOG)
    progress.start()
    for ppem in config.sizes:
        glyphs: list[BitmapGlyph] = []
        for gid, name, png_data in source_glyphs:
            glyphs.append(
                BitmapGlyph(
                    gid=gid,
                    name=name,
                    png=_resize_png(png_data, ppem),
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


def _resize_png(png_data: bytes, ppem: int) -> bytes:
    image = Image.open(BytesIO(png_data)).convert("RGBA")
    if image.size != (ppem, ppem):
        image = image.resize((ppem, ppem), Image.Resampling.LANCZOS)

    out = BytesIO()
    image.save(out, format="PNG", compress_level=6)
    return out.getvalue()
