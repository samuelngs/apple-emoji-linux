from __future__ import annotations

from io import BytesIO

from fontTools.ttLib import TTFont
from PIL import Image

from bitmap.png import resize_png
from models import BitmapGlyph, BitmapStrike
from shaping.oracle import ShapeResult
from source.sbix import collect_sbix_glyph_images, get_sbix_strikes


def strike_map(strike: BitmapStrike) -> dict[str, BitmapGlyph]:
    return {glyph.name: glyph for glyph in strike.glyphs}


def source_fallback_strikes(font: TTFont, output_ppems: set[int]) -> list[BitmapStrike]:
    fallback: list[BitmapStrike] = []
    if "sbix" not in font:
        return fallback
    for ppem in sorted(get_sbix_strikes(font)):
        if ppem in output_ppems:
            continue
        glyphs, metadata = collect_sbix_glyph_images(font, ppem=ppem)
        fallback.append(
            BitmapStrike(
                ppem=metadata.ppem,
                glyphs=tuple(
                    BitmapGlyph(
                        gid=glyph.gid,
                        name=glyph.name,
                        png=glyph.png,
                        origin_x=glyph.origin_x,
                        origin_y=glyph.origin_y,
                    )
                    for glyph in glyphs
                ),
            ),
        )
    return fallback


def glyph_from_strikes(
    name: str,
    target_ppem: int,
    strikes: list[BitmapStrike],
    strike_maps: list[dict[str, BitmapGlyph]],
) -> BitmapGlyph | None:
    candidates: list[tuple[int, BitmapStrike, BitmapGlyph]] = []
    for strike, glyph_map in zip(strikes, strike_maps):
        glyph = glyph_map.get(name)
        if glyph is not None:
            candidates.append((abs(strike.ppem - target_ppem), strike, glyph))
    if not candidates:
        return None
    _distance, source_strike, source = min(candidates, key=lambda item: item[0])
    if source_strike.ppem == target_ppem:
        return source
    return BitmapGlyph(
        gid=source.gid,
        name=source.name,
        png=resize_png(source.png, target_ppem),
        origin_x=round(source.origin_x * target_ppem / source_strike.ppem),
        origin_y=round(source.origin_y * target_ppem / source_strike.ppem),
    )


def compose_shape_bitmap(
    shape: ShapeResult,
    strike: BitmapStrike,
    current_map: dict[str, BitmapGlyph],
    strikes: list[BitmapStrike],
    strike_maps: list[dict[str, BitmapGlyph]],
    font: TTFont,
) -> bytes | None:
    return _compose_positioned_shape(shape, strike, current_map, strikes, strike_maps, font)


def _compose_positioned_shape(
    shape: ShapeResult,
    strike: BitmapStrike,
    current_map: dict[str, BitmapGlyph],
    strikes: list[BitmapStrike],
    strike_maps: list[dict[str, BitmapGlyph]],
    font: TTFont,
) -> bytes | None:
    upem = font["head"].unitsPerEm
    scale = strike.ppem / upem
    placements: list[tuple[Image.Image, int, int]] = []
    pen_x = 0
    pen_y = 0
    for shaped_glyph in shape.glyphs:
        source = current_map.get(shaped_glyph.name) or glyph_from_strikes(
            shaped_glyph.name,
            strike.ppem,
            strikes,
            strike_maps,
        )
        if source is None:
            return None
        image = Image.open(BytesIO(source.png)).convert("RGBA")
        x = round((pen_x + shaped_glyph.x_offset) * scale) + source.origin_x
        y = round((-pen_y - shaped_glyph.y_offset) * scale) - source.origin_y
        placements.append((image, x, y))
        pen_x += shaped_glyph.x_advance
        pen_y += shaped_glyph.y_advance

    min_x = min(x for image, x, _y in placements)
    min_y = min(y for image, _x, y in placements)
    max_x = max(x + image.width for image, x, _y in placements)
    max_y = max(y + image.height for image, _x, y in placements)
    if max_x <= min_x or max_y <= min_y:
        return None

    if min_x >= 0 and min_y >= 0 and max_x <= strike.ppem and max_y <= strike.ppem:
        canvas = Image.new("RGBA", (strike.ppem, strike.ppem), (0, 0, 0, 0))
        for image, x, y in placements:
            canvas.paste(image, (x, y), image)
        return _to_png(canvas)

    combined = Image.new("RGBA", (max_x - min_x, max_y - min_y), (0, 0, 0, 0))
    for image, x, y in placements:
        combined.paste(image, (x - min_x, y - min_y), image)

    bbox = combined.getbbox()
    if bbox is None:
        return None
    cropped = combined.crop(bbox)
    return _fit_to_square_png(cropped, strike.ppem)


def _to_png(image: Image.Image) -> bytes:
    out = BytesIO()
    image.save(out, format="PNG", compress_level=6)
    return out.getvalue()


def _fit_to_square_png(image: Image.Image, ppem: int) -> bytes:
    scale = min(ppem / image.width, ppem / image.height)
    new_width = max(1, round(image.width * scale))
    new_height = max(1, round(image.height * scale))
    scaled = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (ppem, ppem), (0, 0, 0, 0))
    canvas.paste(
        scaled,
        ((ppem - new_width) // 2, (ppem - new_height) // 2),
        scaled,
    )
    return _to_png(canvas)
