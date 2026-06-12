#!/usr/bin/env python3
"""Merge Apple left/right half bitmaps for GSUB ligatures."""

from __future__ import annotations

import io
import logging
from typing import TYPE_CHECKING

from PIL import Image

if TYPE_CHECKING:
    from fontTools.ttLib import TTFont

LOG = logging.getLogger(__name__)


def merge_lr_glyphs(
    source_font: "TTFont",
    multi_ligatures: list[tuple[list[str], list[str]]],
    ppem: int | None = None,
) -> tuple[list[tuple[int, str, bytes, int]], list[tuple[list[str], str]]]:
    """Return merged glyph PNGs and their ligature rules."""
    from source.sbix import get_sbix_strikes

    if "sbix" not in source_font:
        LOG.warning("Source font has no sbix table; skipping L+R merge")
        return [], []

    strikes = get_sbix_strikes(source_font)
    strike_ppem = max(strikes.keys()) if ppem is None else ppem
    if strike_ppem not in strikes:
        LOG.warning("ppem %d not in strikes; skipping L+R merge", strike_ppem)
        return [], []

    strike = strikes[strike_ppem]
    strike_glyphs = strike.glyphs

    merged_glyphs: list[tuple[int, str, bytes, int]] = []
    extra_ligatures: list[tuple[list[str], str]] = []
    next_gid = len(source_font.getGlyphOrder())
    seen_names: set[str] = set()

    skipped_non_lr = 0
    for comps, output_names in multi_ligatures:
        if len(output_names) != 2:
            skipped_non_lr += 1
            continue

        left_name, right_name = output_names[0], output_names[1]

        if not (left_name.endswith(".L") or right_name.endswith(".R")):
            skipped_non_lr += 1
            continue

        left_png = _get_glyph_png(left_name, strike_glyphs)
        right_png = _get_glyph_png(right_name, strike_glyphs)

        if left_png is None or right_png is None:
            LOG.debug(
                "Skipping merge for %s: missing bitmap (L=%s R=%s)",
                "+".join(comps), left_name, right_name,
            )
            continue

        result = _merge_pngs(left_png, right_png)
        if result is None:
            continue
        merged_png, bitmap_width = result

        merged_name = f"merged.{left_name}.{right_name}"
        if merged_name in seen_names:
            extra_ligatures.append((comps, merged_name))
            continue
        seen_names.add(merged_name)

        merged_glyphs.append((next_gid, merged_name, merged_png, bitmap_width))
        extra_ligatures.append((comps, merged_name))
        next_gid += 1

    if skipped_non_lr:
        LOG.info("Skipped %d non-L/R multi-glyph entries", skipped_non_lr)
    LOG.info(
        "Merged %d L+R glyph pairs into %d new glyphs, %d ligature entries",
        len(merged_glyphs), len(seen_names), len(extra_ligatures),
    )
    return merged_glyphs, extra_ligatures


def _get_glyph_png(name: str, strike_glyphs: dict) -> bytes | None:
    from source.sbix import PNG_SIGNATURE, _resolve_image_data

    if name not in strike_glyphs:
        return None
    raw = _resolve_image_data(strike_glyphs[name], strike_glyphs)
    if raw is None or not raw.startswith(PNG_SIGNATURE):
        return None
    return raw


def _merge_pngs(left_png: bytes, right_png: bytes) -> tuple[bytes, int] | None:
    """Merge two half images into a square PNG."""
    try:
        left_img = Image.open(io.BytesIO(left_png)).convert("RGBA")
        right_img = Image.open(io.BytesIO(right_png)).convert("RGBA")

        ppem = max(left_img.height, right_img.height)

        left_box = left_img.getbbox()
        right_box = right_img.getbbox()
        if not left_box or not right_box:
            return None
        left_crop = left_img.crop(left_box)
        right_crop = right_img.crop(right_box)

        combined_w = left_crop.width + right_crop.width
        combined_h = max(left_crop.height, right_crop.height)
        combined = Image.new("RGBA", (combined_w, combined_h), (0, 0, 0, 0))

        left_y = (combined_h - left_crop.height) // 2
        right_y = (combined_h - right_crop.height) // 2
        combined.paste(left_crop, (0, left_y), left_crop)
        combined.paste(right_crop, (left_crop.width, right_y), right_crop)

        cw, ch = combined.size
        scale = min(ppem / cw, ppem / ch)
        new_w = max(1, round(cw * scale))
        new_h = max(1, round(ch * scale))
        scaled = combined.resize((new_w, new_h), Image.LANCZOS)

        canvas = Image.new("RGBA", (ppem, ppem), (0, 0, 0, 0))
        paste_x = (ppem - new_w) // 2
        paste_y = (ppem - new_h) // 2
        canvas.paste(scaled, (paste_x, paste_y), scaled)

        buf = io.BytesIO()
        canvas.save(buf, format="PNG")
        return buf.getvalue(), ppem

    except Exception as e:
        LOG.warning("Failed to merge PNGs: %s", e)
        return None


def add_merged_glyphs_to_font(
    font: "TTFont",
    merged_glyphs: list[tuple[int, str, bytes, int]],
) -> None:
    """Add empty glyph slots for merged bitmap glyphs."""
    if not merged_glyphs:
        return

    glyph_order = list(font.getGlyphOrder())
    hmtx = font["hmtx"]
    vmtx = font["vmtx"] if "vmtx" in font else None
    glyf = font["glyf"] if "glyf" in font else None
    if glyf is not None:
        from fontTools.ttLib.tables._g_l_y_f import Glyph

    ref_width = 0
    for name in glyph_order:
        if name.startswith("u") and name in hmtx.metrics:
            w, _ = hmtx.metrics[name]
            if w > 0:
                ref_width = w
                break
    ref_vmetrics = (ref_width, 0)
    if vmtx is not None:
        for name in glyph_order:
            if name.startswith("u") and name in vmtx.metrics:
                ref_vmetrics = vmtx.metrics[name]
                break

    for _gid, name, _png, _bitmap_width in merged_glyphs:
        glyph_order.append(name)
        hmtx.metrics[name] = (ref_width, 0)
        if vmtx is not None:
            vmtx.metrics[name] = ref_vmetrics
        if glyf is not None:
            glyph = Glyph()
            glyph.numberOfContours = 0
            glyf.glyphs[name] = glyph

    font.setGlyphOrder(glyph_order)
    if "maxp" in font:
        font["maxp"].numGlyphs = len(glyph_order)
    LOG.info("Added %d merged glyphs to font glyph order", len(merged_glyphs))
