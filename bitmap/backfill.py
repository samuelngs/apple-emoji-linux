from __future__ import annotations

import logging

from fontTools.ttLib import TTFont

from bitmap.png import resize_png
from config_types import BackfillMissingConfig
from models import BitmapGlyph, BitmapStrike
from source.sbix import collect_sbix_glyph_images, get_sbix_strikes

LOG = logging.getLogger(__name__)


def backfill_missing_glyphs(
    font: TTFont,
    strikes: list[BitmapStrike],
    config: BackfillMissingConfig | None,
) -> list[BitmapStrike]:
    if config is None:
        return strikes

    available = set(get_sbix_strikes(font))
    if config.source not in available:
        raise ValueError(
            f"Bitmap backfill source ppem={config.source} is not in source font "
            f"{sorted(available)}",
        )

    source_glyphs, _metadata = collect_sbix_glyph_images(font, ppem=config.source)
    source_by_name = {glyph.name: glyph for glyph in source_glyphs}
    out: list[BitmapStrike] = []

    for strike in strikes:
        present = {glyph.name for glyph in strike.glyphs}
        missing = sorted(
            (glyph for name, glyph in source_by_name.items() if name not in present),
            key=lambda glyph: glyph.gid,
        )
        if not missing:
            out.append(strike)
            continue

        additions = tuple(
            BitmapGlyph(
                gid=glyph.gid,
                name=glyph.name,
                png=resize_png(glyph.png, strike.ppem),
                origin_x=round(glyph.origin_x * strike.ppem / config.source),
                origin_y=round(glyph.origin_y * strike.ppem / config.source),
            )
            for glyph in missing
        )
        out.append(
            BitmapStrike(
                ppem=strike.ppem,
                glyphs=tuple(sorted(strike.glyphs + additions, key=lambda glyph: glyph.gid)),
            ),
        )
        LOG.info(
            "Backfilled %d missing glyphs in strike ppem=%d from ppem=%d",
            len(additions),
            strike.ppem,
            config.source,
        )

    return out
