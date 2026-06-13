from __future__ import annotations

import logging

from bitmap.compression import compress_png
from bitmap.png import flip_png_horizontal
from config import BitmapConfig
from models import BitmapGlyph, BitmapStrike
from progress import Progress

LOG = logging.getLogger(__name__)


def apply_bitmap_transforms(
    strikes: list[BitmapStrike],
    config: BitmapConfig,
) -> list[BitmapStrike]:
    """Apply configured bitmap transforms before CBDT/CBLC construction."""
    transforms = config.transforms

    if transforms.flip_directional_variants:
        strikes = [_flip_directional_variants(strike) for strike in strikes]

    if config.png.compress:
        strikes = _compress_strike_pngs(strikes, config)

    return strikes


def _compress_strike_pngs(strikes: list[BitmapStrike], config: BitmapConfig) -> list[BitmapStrike]:
    selected = set(config.png.strikes)
    total = sum(
        len(strike.glyphs)
        for strike in strikes
        if not selected or strike.ppem in selected
    )
    progress = Progress("Compressing glyph PNGs", total, LOG)
    out: list[BitmapStrike] = []
    progress.start()
    for strike in strikes:
        if selected and strike.ppem not in selected:
            out.append(strike)
            continue
        compressed_glyphs: list[BitmapGlyph] = []
        for glyph in strike.glyphs:
            compressed_glyphs.append(
                BitmapGlyph(
                    gid=glyph.gid,
                    name=glyph.name,
                    png=compress_png(
                        glyph.png,
                        max_colors=config.png.max_colors,
                        prefer_pngquant=config.png.prefer_pngquant,
                    ),
                    origin_x=glyph.origin_x,
                    origin_y=glyph.origin_y,
                ),
            )
            progress.advance()
        out.append(BitmapStrike(ppem=strike.ppem, glyphs=tuple(compressed_glyphs)))
    progress.finish()
    return out


def _flip_directional_variants(strike: BitmapStrike) -> BitmapStrike:
    name_to_png = {glyph.name: glyph.png for glyph in strike.glyphs}
    flipped = 0
    out = []
    for glyph in strike.glyphs:
        png_data = glyph.png
        if ".u27A1" in glyph.name:
            base_name = glyph.name.replace(".u27A1", "")
            base_png = name_to_png.get(base_name)
            if base_png is not None and base_png == png_data:
                png_data = flip_png_horizontal(png_data)
                flipped += 1
        out.append(
            BitmapGlyph(
                gid=glyph.gid,
                name=glyph.name,
                png=png_data,
                origin_x=glyph.origin_x,
                origin_y=glyph.origin_y,
            ),
        )
    if flipped:
        LOG.info("Flipped %d directional variant bitmaps", flipped)
    return BitmapStrike(ppem=strike.ppem, glyphs=tuple(out))
