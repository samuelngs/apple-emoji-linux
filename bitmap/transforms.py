from __future__ import annotations

import logging

from fontTools.ttLib import TTFont

from bitmap.compression import compress_png
from bitmap.merge import add_merged_glyphs_to_font, merge_lr_glyphs, _merge_pngs
from bitmap.png import flip_png_horizontal
from config import BitmapConfig
from models import BitmapGlyph, BitmapStrike
from progress import Progress

LOG = logging.getLogger(__name__)


def apply_bitmap_transforms(
    source_font: TTFont,
    strikes: list[BitmapStrike],
    config: BitmapConfig,
) -> tuple[list[BitmapStrike], list[tuple[list[str], str]] | None]:
    """Apply configured bitmap transforms before CBDT/CBLC construction."""
    extra_ligatures: list[tuple[list[str], str]] | None = None
    transforms = config.transforms

    if transforms.merge_lr_halves is not None and strikes:
        primary = strikes[-1]
        cache_path = transforms.merge_lr_halves.cache
        if cache_path.exists():
            try:
                from generate_ligatures import load_multi_glyph_cache

                multi_ligs = load_multi_glyph_cache(cache_path)
                if not transforms.merge_lr_halves.include_skin_tone_variants:
                    multi_ligs = _without_skin_tone_variants(multi_ligs)
                if multi_ligs:
                    merged_glyphs, extra_ligatures = merge_lr_glyphs(
                        source_font,
                        multi_ligs,
                        ppem=primary.ppem,
                    )
                    if merged_glyphs:
                        add_merged_glyphs_to_font(
                            source_font,
                            merged_glyphs,
                        )
                        gid_by_name = {
                            name: source_font.getGlyphID(name)
                            for _gid, name, _png, _bitmap_width in merged_glyphs
                        }
                        strikes = _add_merged_glyphs_to_strikes(
                            multi_ligs,
                            strikes,
                            primary.ppem,
                            merged_glyphs,
                            gid_by_name,
                        )
                        LOG.info("Added %d merged L+R glyphs", len(merged_glyphs))
            except Exception as e:
                LOG.warning("Skipping L+R merge: %s", e)

    if transforms.flip_directional_variants:
        strikes = [_flip_directional_variants(strike) for strike in strikes]

    if config.png.compress:
        strikes = _compress_strike_pngs(strikes, config)

    return strikes, extra_ligatures


def _without_skin_tone_variants(
    multi_ligatures: list[tuple[list[str], list[str]]],
) -> list[tuple[list[str], list[str]]]:
    return [
        ligature
        for ligature in multi_ligatures
        if not any(_is_skin_tone_component(component) for component in ligature[0])
    ]


def _is_skin_tone_component(name: str) -> bool:
    base = name.split(".", 1)[0]
    if base.startswith("u"):
        try:
            codepoint = int(base[1:], 16)
        except ValueError:
            return False
        return 0x1F3FB <= codepoint <= 0x1F3FF
    return False


def _add_merged_glyphs_to_strikes(
    multi_ligatures: list[tuple[list[str], list[str]]],
    strikes: list[BitmapStrike],
    primary_ppem: int,
    primary_merged_glyphs: list[tuple[int, str, bytes, int]],
    gid_by_name: dict[str, int],
) -> list[BitmapStrike]:
    primary_by_name = {
        name: (png, bitmap_width)
        for _gid, name, png, bitmap_width in primary_merged_glyphs
    }
    out: list[BitmapStrike] = []
    for strike in strikes:
        if strike.ppem == primary_ppem:
            merged_for_strike = [
                (gid_by_name[name], name, png, bitmap_width)
                for name, (png, bitmap_width) in primary_by_name.items()
            ]
        else:
            merged_for_strike = _merge_lr_glyphs_from_strike(
                multi_ligatures,
                strike,
                gid_by_name,
            )

        additions = tuple(
            BitmapGlyph(gid=gid, name=name, png=png)
            for gid, name, png, _bitmap_width in merged_for_strike
        )
        out.append(BitmapStrike(ppem=strike.ppem, glyphs=strike.glyphs + additions))
    return out


def _merge_lr_glyphs_from_strike(
    multi_ligatures: list[tuple[list[str], list[str]]],
    strike: BitmapStrike,
    gid_by_name: dict[str, int],
) -> list[tuple[int, str, bytes, int]]:
    name_to_png = {glyph.name: glyph.png for glyph in strike.glyphs}
    seen_names: set[str] = set()
    merged: list[tuple[int, str, bytes, int]] = []
    for _comps, output_names in multi_ligatures:
        if len(output_names) != 2:
            continue
        left_name, right_name = output_names
        if not (left_name.endswith(".L") or right_name.endswith(".R")):
            continue
        merged_name = f"merged.{left_name}.{right_name}"
        if merged_name in seen_names or merged_name not in gid_by_name:
            continue
        left_png = name_to_png.get(left_name)
        right_png = name_to_png.get(right_name)
        if left_png is None or right_png is None:
            continue
        result = _merge_pngs(left_png, right_png)
        if result is None:
            continue
        png, bitmap_width = result
        merged.append((gid_by_name[merged_name], merged_name, png, bitmap_width))
        seen_names.add(merged_name)
    return merged


def _compress_strike_pngs(strikes: list[BitmapStrike], config: BitmapConfig) -> list[BitmapStrike]:
    total = sum(len(strike.glyphs) for strike in strikes)
    progress = Progress("Compressing glyph PNGs", total, LOG)
    out: list[BitmapStrike] = []
    progress.start()
    for strike in strikes:
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
        out.append(BitmapGlyph(gid=glyph.gid, name=glyph.name, png=png_data))
    if flipped:
        LOG.info("Flipped %d directional variant bitmaps", flipped)
    return BitmapStrike(ppem=strike.ppem, glyphs=tuple(out))
