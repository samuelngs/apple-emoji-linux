"""Strip PNG to chunks CBDT allows: IHDR, PLTE, tRNS, sRGB, IDAT, IEND."""

from __future__ import annotations

import struct

ALLOWED_CHUNKS = {b"IHDR", b"PLTE", b"tRNS", b"sRGB", b"IDAT", b"IEND"}
PNG_SIGNATURE = bytes((0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A))


def read_chunk(data: bytes, offset: int) -> tuple[bytes, bytes, bytes, int] | None:
    """One chunk at offset; (type, data, crc, next_offset) or None."""
    if offset + 12 > len(data):
        return None
    length = struct.unpack(">I", data[offset : offset + 4])[0]
    chunk_type = data[offset + 4 : offset + 8]
    end = offset + 8 + length + 4
    if end > len(data):
        return None
    chunk_data = data[offset + 8 : offset + 8 + length]
    crc = data[offset + 8 + length : end]
    return (chunk_type, chunk_data, crc, end)


def filter_png_chunks(png_data: bytes) -> bytes:
    """Keep only allowed chunks, preserve order. Pass through if not a PNG."""
    if not png_data.startswith(PNG_SIGNATURE):
        return png_data
    out = bytearray(PNG_SIGNATURE)
    offset = 8
    while offset < len(png_data):
        chunk = read_chunk(png_data, offset)
        if chunk is None:
            break
        chunk_type, chunk_data, crc, next_offset = chunk
        if chunk_type in ALLOWED_CHUNKS:
            out += struct.pack(">I", len(chunk_data))
            out += chunk_type
            out += chunk_data
            out += crc
        if chunk_type == b"IEND":
            break
        offset = next_offset
    return bytes(out)


def get_png_size(png_data: bytes) -> tuple[int, int] | None:
    """(width, height) from IHDR, or None."""
    if len(png_data) < 8 + 4 + 4 + 13:
        return None
    if not png_data.startswith(PNG_SIGNATURE):
        return None
    length = struct.unpack(">I", png_data[8:12])[0]
    if png_data[12:16] != b"IHDR" or length < 8:
        return None
    width, height = struct.unpack(">II", png_data[16:24])
    return (width, height)
