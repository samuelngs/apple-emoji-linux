from __future__ import annotations

from fontTools.ttLib import TTFont

from shaping.oracle import ShapeResult


def reference_hmetrics(font: TTFont, shape: ShapeResult) -> tuple[int, int]:
    hmtx = font["hmtx"]
    for glyph in shape.glyphs:
        if glyph.name in hmtx.metrics:
            return hmtx.metrics[glyph.name]
    for name, metrics in hmtx.metrics.items():
        if name.startswith("u") and metrics[0] > 0:
            return metrics
    return (font["head"].unitsPerEm, 0)


def reference_vmetrics(font: TTFont, shape: ShapeResult) -> tuple[int, int]:
    vmtx = font["vmtx"] if "vmtx" in font else None
    if vmtx is None:
        return reference_hmetrics(font, shape)
    for glyph in shape.glyphs:
        if glyph.name in vmtx.metrics:
            return vmtx.metrics[glyph.name]
    for name, metrics in vmtx.metrics.items():
        if name.startswith("u") and metrics[0] > 0:
            return metrics
    return reference_hmetrics(font, shape)


def add_empty_glyph_slots(
    font: TTFont,
    glyphs: list[tuple[str, tuple[int, int], tuple[int, int]]],
) -> dict[str, int]:
    if not glyphs:
        return {}

    glyph_order = list(font.getGlyphOrder())
    hmtx = font["hmtx"]
    vmtx = font["vmtx"] if "vmtx" in font else None
    glyf = font["glyf"] if "glyf" in font else None
    if glyf is not None:
        from fontTools.ttLib.tables._g_l_y_f import Glyph

    gid_by_name: dict[str, int] = {}
    for name, hmetrics, vmetrics in glyphs:
        if name in glyph_order:
            gid_by_name[name] = glyph_order.index(name)
            continue
        gid_by_name[name] = len(glyph_order)
        glyph_order.append(name)
        hmtx.metrics[name] = hmetrics
        if vmtx is not None:
            vmtx.metrics[name] = vmetrics
        if glyf is not None:
            glyph = Glyph()
            glyph.numberOfContours = 0
            glyf.glyphs[name] = glyph

    font.setGlyphOrder(glyph_order)
    if "maxp" in font:
        font["maxp"].numGlyphs = len(glyph_order)
    return gid_by_name
