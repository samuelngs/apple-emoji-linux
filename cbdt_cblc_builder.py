"""Build CBDT and CBLC tables. CBDT Format 17 (small metrics + PNG), CBLC index format 1."""

from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Sequence

from png_filter import filter_png_chunks, get_png_size


@dataclass
class FontMetrics:
    upem: int
    ascent: int
    descent: int


def _div_round(a: float, b: float) -> int:
    return int(round(a / b))


def _small_glyph_metrics(
    width: int,
    height: int,
    ppem: int,
    font: FontMetrics,
) -> bytes:
    """SmallGlyphMetrics, big-endian. bearingY from height, clamped to int8."""
    y_bearing = min(_div_round(height * 5, 6), 127)
    advance = width
    return struct.pack(">BBbbB", height, width, 0, y_bearing, advance)


def build_cbdt(
    glyphs: Sequence[tuple[int, str, bytes]],
    ppem: int,
    font_metrics: FontMetrics,
) -> tuple[bytes, list[tuple[int, int, int]]]:
    """Build CBDT v3, Format 17. glyphs = (gid, name, png_bytes); returns bytes + (gid, offset, length) for CBLC."""
    out = bytearray(struct.pack(">HH", 3, 0))
    locations: list[tuple[int, int, int]] = []

    for gid, _name, png_data in glyphs:
        png_data = filter_png_chunks(png_data)
        size = get_png_size(png_data)
        if size is None:
            raise ValueError(f"Invalid PNG for glyph id {gid}")
        width, height = size

        metrics = _small_glyph_metrics(width, height, ppem, font_metrics)
        offset = len(out)
        out += metrics
        out += struct.pack(">I", len(png_data))
        out += png_data
        locations.append((gid, offset, len(metrics) + 4 + len(png_data)))

    return bytes(out), locations


def _sbit_line_metrics(
    ppem: int,
    font_metrics: FontMetrics,
    width_max: int,
) -> bytes:
    """SbitLineMetrics, big-endian."""
    line_height = _div_round((font_metrics.ascent + font_metrics.descent) * ppem, font_metrics.upem)
    ascender = min(_div_round(font_metrics.ascent * ppem, font_metrics.upem), 127)
    descender = -(line_height - ascender)
    descender = max(-128, min(127, descender))
    return struct.pack(">bbBbbbbbbbbb", ascender, descender, width_max, 0, 0, 0, 0, 0, 0, 0, 0, 0)


def build_cblc(
    cbdt_bytes: bytes,
    glyphs: Sequence[tuple[int, str, bytes]],
    locations: list[tuple[int, int, int]],
    ppem: int,
    font_metrics: FontMetrics,
) -> bytes:
    """Build CBLC v3, one strike, index format 1. locations from build_cbdt."""
    if not glyphs or not locations:
        raise ValueError("No glyphs for CBLC")

    width_max = 0
    for _gid, _name, png_data in glyphs:
        size = get_png_size(filter_png_chunks(png_data))
        if size:
            width_max = max(width_max, size[0])

    first_gid = min(loc[0] for loc in locations)
    last_gid = max(loc[0] for loc in locations)
    gid_to_offset = {gid: offset for gid, offset, _ in locations}
    base_offset = min(o for _, o, _ in locations)
    end_offset = locations[-1][1] + locations[-1][2]

    # index format 1: one offset per gid; missing glyphs point to next so size=0
    offsets_rel = []
    for i in range(last_gid - first_gid + 1):
        gid = first_gid + i
        start = gid_to_offset.get(gid)
        if start is None:
            for k in range(i + 1, last_gid - first_gid + 1):
                gid2 = first_gid + k
                if gid2 in gid_to_offset:
                    start = gid_to_offset[gid2]
                    break
            if start is None:
                start = end_offset
        offsets_rel.append(start - base_offset)
    offsets_rel.append(end_offset - base_offset)

    image_data_offset = base_offset
    index_subtable_data = struct.pack(">HHL", 1, 17, image_data_offset)
    for o in offsets_rel:
        index_subtable_data += struct.pack(">I", o)

    number_of_index_subtables = 1
    record_size = 8
    subtable_offset_in_list = number_of_index_subtables * record_size
    index_subtable_list = bytearray()
    index_subtable_list += struct.pack(">HHL", first_gid, last_gid, subtable_offset_in_list)
    index_subtable_list += index_subtable_data

    index_tables_size = len(index_subtable_list)
    color_ref = 0
    hori = _sbit_line_metrics(ppem, font_metrics, width_max)
    vert = hori

    header_size = 8
    bitmap_size_record_size = 48
    index_subtable_list_offset = header_size + bitmap_size_record_size

    bitmap_size = bytearray()
    bitmap_size += struct.pack(">IIII", index_subtable_list_offset, index_tables_size, number_of_index_subtables, color_ref)
    bitmap_size += hori
    bitmap_size += vert
    bitmap_size += struct.pack(">HHBBBb", first_gid, last_gid, ppem, ppem, 32, 1)

    out = bytearray()
    out += struct.pack(">HHI", 3, 0, 1)
    out += bitmap_size
    out += index_subtable_list

    return bytes(out)
