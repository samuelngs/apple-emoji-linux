from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from fontTools.ttLib import TTFont


@dataclass(frozen=True)
class ShapedGlyph:
    gid: int
    name: str
    cluster: int
    x_advance: int
    y_advance: int
    x_offset: int
    y_offset: int


@dataclass(frozen=True)
class ShapeResult:
    sequence: tuple[int, ...]
    glyphs: tuple[ShapedGlyph, ...]

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(glyph.name for glyph in self.glyphs)


class ShapingOracle:
    def __init__(self, font_path: Path, font_number: int = 0) -> None:
        try:
            import uharfbuzz as hb
        except ImportError as e:
            raise ImportError("uharfbuzz is required for sequence GSUB generation") from e

        self._hb = hb
        self._font_path = font_path
        self._font_number = font_number
        self._ttfont = TTFont(font_path, fontNumber=font_number)
        self._glyph_order = self._ttfont.getGlyphOrder()
        self._notdef_gids = _notdef_gids(self._glyph_order)
        blob = hb.Blob(font_path.read_bytes())
        face = hb.Face(blob, font_number)
        self._hb_font = hb.Font(face)

    @property
    def ttfont(self) -> TTFont:
        return self._ttfont

    @property
    def glyph_order(self) -> list[str]:
        return self._glyph_order

    def close(self) -> None:
        self._ttfont.close()

    def shape(self, sequence: tuple[int, ...], *, drop_notdef: bool = True) -> ShapeResult:
        text = "".join(chr(cp) for cp in sequence)
        buf = self._hb.Buffer()
        buf.add_str(text)
        buf.guess_segment_properties()
        self._hb.shape(self._hb_font, buf)

        glyphs: list[ShapedGlyph] = []
        for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
            gid = int(info.codepoint)
            if drop_notdef and gid in self._notdef_gids:
                continue
            name = self._glyph_order[gid] if gid < len(self._glyph_order) else f"gid{gid}"
            glyphs.append(
                ShapedGlyph(
                    gid=gid,
                    name=name,
                    cluster=int(info.cluster),
                    x_advance=int(pos.x_advance),
                    y_advance=int(pos.y_advance),
                    x_offset=int(pos.x_offset),
                    y_offset=int(pos.y_offset),
                ),
            )
        return ShapeResult(sequence=sequence, glyphs=tuple(glyphs))


def shape_font_file(
    font_path: Path,
    sequence: tuple[int, ...],
    *,
    font_number: int = 0,
    drop_notdef: bool = True,
) -> ShapeResult:
    oracle = ShapingOracle(font_path, font_number=font_number)
    try:
        return oracle.shape(sequence, drop_notdef=drop_notdef)
    finally:
        oracle.close()


def _notdef_gids(glyph_order: list[str]) -> set[int]:
    names = {".notdef", "space", "uni00A0", "CR"}
    return {gid for gid, name in enumerate(glyph_order) if name in names}
