"""Build CBDT/CBLC bitmap tables."""

from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Sequence

from bitmap.png import filter_png_chunks, get_png_size


@dataclass
class FontMetrics:
    upem: int
    ascent: int
    descent: int


GlyphBitmap = tuple[int, str, bytes]
GlyphLocation = tuple[int, int, int]


@dataclass
class BitmapStrikeData:
    ppem: int
    glyphs: list[GlyphBitmap]
    locations: list[GlyphLocation]


def _div_round(a: float, b: float) -> int:
    return int(round(a / b))


def _small_glyph_metrics(
    width: int,
    height: int,
    ppem: int,
    font: FontMetrics,
    y_bearing: str = "five_sixths_height",
) -> bytes:
    if y_bearing == "full_height":
        bearing_y = min(height, 127)
    elif y_bearing == "line_center":
        ascender, descender, _width_max = _sbit_line_metric_values(ppem, font, width)
        bearing_y = min(_div_round(ascender + descender + height, 2), 127)
    else:
        bearing_y = min(_div_round(height * 5, 6), 127)
    advance = width
    return struct.pack(">BBbbB", height, width, 0, bearing_y, advance)


def build_cbdt(
    glyphs: Sequence[GlyphBitmap],
    ppem: int,
    font_metrics: FontMetrics,
    y_bearing: str = "five_sixths_height",
) -> tuple[bytes, list[GlyphLocation]]:
    """Build one CBDT strike."""
    cbdt_bytes, strike_data = build_cbdt_strikes(
        [(ppem, glyphs)],
        font_metrics,
        y_bearing=y_bearing,
    )
    return cbdt_bytes, strike_data[0].locations


def build_cbdt_strikes(
    strikes: Sequence[tuple[int, Sequence[GlyphBitmap]]],
    font_metrics: FontMetrics,
    y_bearing: str = "five_sixths_height",
) -> tuple[bytes, list[BitmapStrikeData]]:
    """Build CBDT v3 Format 17 data for one or more bitmap strikes."""
    out = bytearray(struct.pack(">HH", 3, 0))
    strike_data: list[BitmapStrikeData] = []

    for ppem, glyphs in strikes:
        locations: list[GlyphLocation] = []
        filtered_glyphs: list[GlyphBitmap] = []

        for gid, name, png_data in glyphs:
            png_data = filter_png_chunks(png_data)
            size = get_png_size(png_data)
            if size is None:
                raise ValueError(f"Invalid PNG for glyph id {gid}")
            width, height = size

            metrics = _small_glyph_metrics(width, height, ppem, font_metrics, y_bearing)
            offset = len(out)
            out += metrics
            out += struct.pack(">I", len(png_data))
            out += png_data
            locations.append((gid, offset, len(metrics) + 4 + len(png_data)))
            filtered_glyphs.append((gid, name, png_data))

        strike_data.append(
            BitmapStrikeData(ppem=ppem, glyphs=filtered_glyphs, locations=locations)
        )

    return bytes(out), strike_data


def _sbit_line_metrics(
    ppem: int,
    font_metrics: FontMetrics,
    width_max: int,
) -> bytes:
    ascender, descender, width_max = _sbit_line_metric_values(
        ppem,
        font_metrics,
        width_max,
    )
    return struct.pack(">bbB", ascender, descender, width_max) + struct.pack(">9b", 0, 0, 0, 0, 0, 0, 0, 0, 0)


def _sbit_line_metric_values(
    ppem: int,
    font_metrics: FontMetrics,
    width_max: int,
) -> tuple[int, int, int]:
    line_height = _div_round((font_metrics.ascent + font_metrics.descent) * ppem, font_metrics.upem)
    ascender = min(_div_round(font_metrics.ascent * ppem, font_metrics.upem), 127)
    descender = -(line_height - ascender)
    descender = max(-128, min(127, descender))
    return ascender, descender, width_max


INDEX_SUBTABLE_GLYPH_CHUNK = 256


def _runs_from_locations(
    locations: list[GlyphLocation],
) -> list[list[GlyphLocation]]:
    if not locations:
        return []
    sorted_locs = sorted(locations, key=lambda x: x[0])
    contiguous: list[list[tuple[int, int, int]]] = []
    run: list[tuple[int, int, int]] = [sorted_locs[0]]
    for gid, offset, length in sorted_locs[1:]:
        if gid == run[-1][0] + 1:
            run.append((gid, offset, length))
        else:
            contiguous.append(run)
            run = [(gid, offset, length)]
    contiguous.append(run)
    runs: list[list[tuple[int, int, int]]] = []
    for run in contiguous:
        for i in range(0, len(run), INDEX_SUBTABLE_GLYPH_CHUNK):
            runs.append(run[i : i + INDEX_SUBTABLE_GLYPH_CHUNK])
    return runs


def build_cblc(
    cbdt_bytes: bytes,
    glyphs: Sequence[GlyphBitmap],
    locations: list[GlyphLocation],
    ppem: int,
    font_metrics: FontMetrics,
) -> bytes:
    """Build one CBLC strike."""
    del cbdt_bytes
    return build_cblc_strikes(
        [BitmapStrikeData(ppem=ppem, glyphs=list(glyphs), locations=locations)],
        font_metrics,
    )


def _index_subtable_list(locations: list[GlyphLocation]) -> bytes:
    if not locations:
        raise ValueError("No glyphs for CBLC")

    runs = _runs_from_locations(locations)

    record_size = 8
    index_subtable_list = bytearray()
    subtable_chunks: list[bytes] = []

    for run in runs:
        run_first = run[0][0]
        run_last = run[-1][0]
        base_offset = run[0][1]
        run_end = run[-1][1] + run[-1][2]
        offsets_rel = [run[i][1] - base_offset for i in range(len(run))]
        offsets_rel.append(run_end - base_offset)

        subtable_data = bytearray()
        subtable_data += struct.pack(">HHL", 1, 17, base_offset)
        for o in offsets_rel:
            subtable_data += struct.pack(">I", o)
        subtable_chunks.append(bytes(subtable_data))

    array_size = len(runs) * record_size
    offset_into_list = array_size
    for i, run in enumerate(runs):
        index_subtable_list += struct.pack(
            ">HHL", run[0][0], run[-1][0], offset_into_list
        )
        offset_into_list += len(subtable_chunks[i])
    for chunk in subtable_chunks:
        index_subtable_list += chunk

    return bytes(index_subtable_list)


def _width_max(glyphs: Sequence[GlyphBitmap]) -> int:
    width_max = 0
    for _gid, _name, png_data in glyphs:
        size = get_png_size(png_data)
        if size:
            width_max = max(width_max, size[0])
    return width_max


def _bitmap_size_record(
    strike: BitmapStrikeData,
    font_metrics: FontMetrics,
    *,
    index_subtable_list_offset: int,
    index_tables_size: int,
) -> bytes:
    number_of_index_subtables = len(_runs_from_locations(strike.locations))
    first_gid = min(loc[0] for loc in strike.locations)
    last_gid = max(loc[0] for loc in strike.locations)
    color_ref = 0
    width_max = _width_max(strike.glyphs)
    hori = _sbit_line_metrics(strike.ppem, font_metrics, width_max)
    vert = hori

    bitmap_size = bytearray()
    bitmap_size += struct.pack(
        ">IIII",
        index_subtable_list_offset,
        index_tables_size,
        number_of_index_subtables,
        color_ref,
    )
    bitmap_size += hori
    bitmap_size += vert
    bitmap_size += struct.pack(
        ">HHBBBb",
        first_gid,
        last_gid,
        strike.ppem,
        strike.ppem,
        32,
        1,
    )
    return bytes(bitmap_size)


def build_cblc_strikes(
    strikes: Sequence[BitmapStrikeData],
    font_metrics: FontMetrics,
) -> bytes:
    """Build CBLC v3 with one BitmapSize record per strike."""
    if not strikes:
        raise ValueError("No strikes for CBLC")
    for strike in strikes:
        if not strike.glyphs or not strike.locations:
            raise ValueError(f"No glyphs for CBLC strike ppem={strike.ppem}")

    header_size = 8
    bitmap_size_record_size = 48
    index_subtable_lists = [_index_subtable_list(strike.locations) for strike in strikes]

    bitmap_size_records = bytearray()
    index_subtable_list_offset = header_size + bitmap_size_record_size * len(strikes)
    for strike, index_subtable_list in zip(strikes, index_subtable_lists):
        bitmap_size_records += _bitmap_size_record(
            strike,
            font_metrics,
            index_subtable_list_offset=index_subtable_list_offset,
            index_tables_size=len(index_subtable_list),
        )
        index_subtable_list_offset += len(index_subtable_list)

    out = bytearray()
    out += struct.pack(">HHI", 3, 0, len(strikes))
    out += bitmap_size_records
    for index_subtable_list in index_subtable_lists:
        out += index_subtable_list

    return bytes(out)
