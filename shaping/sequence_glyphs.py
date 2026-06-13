from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from fontTools.ttLib import TTFont

from models import BitmapGlyph, BitmapStrike
from progress import Progress
from shaping.bitmap_compose import (
    compose_shape_bitmap,
    glyph_from_strikes,
    source_fallback_strikes,
    strike_map,
)
from shaping.glyph_slots import (
    add_empty_glyph_slots,
    reference_hmetrics,
    reference_vmetrics,
)
from shaping.oracle import ShapeResult, ShapingOracle
from shaping.sequences import (
    SequenceRecord,
    SequenceRule,
    sequence_glyph_name,
)

LOG = logging.getLogger(__name__)


@dataclass(frozen=True)
class SequenceSkip:
    normalized_sequence: tuple[int, ...]
    raw_sequence: tuple[int, ...] | None
    reason: str


@dataclass(frozen=True)
class SequenceGlyphBuildResult:
    strikes: list[BitmapStrike]
    rules: tuple[SequenceRule, ...]
    skips: tuple[SequenceSkip, ...]


def materialize_sequence_glyphs(
    font: TTFont,
    source_font_path: Path,
    font_number: int,
    strikes: list[BitmapStrike],
    records: list[SequenceRecord],
) -> SequenceGlyphBuildResult:
    """Create generated glyph bitmaps and GSUB rules from sequence records."""
    oracle = ShapingOracle(source_font_path, font_number=font_number)
    try:
        return _materialize(font, oracle, strikes, records)
    finally:
        oracle.close()


def _materialize(
    font: TTFont,
    oracle: ShapingOracle,
    strikes: list[BitmapStrike],
    records: list[SequenceRecord],
) -> SequenceGlyphBuildResult:
    cmap = oracle.ttfont.getBestCmap() or {}
    strike_maps = [strike_map(strike) for strike in strikes]
    fallback_strikes = source_fallback_strikes(
        oracle.ttfont,
        {strike.ppem for strike in strikes},
    )
    fallback_maps = [strike_map(strike) for strike in fallback_strikes]
    rules: list[SequenceRule] = []
    skips: list[SequenceSkip] = []
    glyph_additions: dict[
        str,
        tuple[tuple[BitmapGlyph, ...], tuple[int, int], tuple[int, int]],
    ] = {}

    progress = Progress("Materializing sequence glyphs", len(records), LOG)
    progress.start()
    for record in records:
        normalized = record.normalized_sequence
        raw_candidates = _raw_candidates(record)

        if len(normalized) <= 1:
            _add_single_codepoint_variant_rules(
                oracle,
                cmap,
                record,
                raw_candidates,
                rules,
                skips,
            )
            progress.advance()
            continue

        shaped = _choose_source_shape(oracle, cmap, raw_candidates)
        if shaped is None:
            skips.append(SequenceSkip(normalized, None, "unsupported_source_shape"))
            progress.advance()
            continue

        raw_sequence, shape = shaped
        glyph_name = sequence_glyph_name(normalized)
        if glyph_name in font.getGlyphOrder():
            skips.append(SequenceSkip(normalized, raw_sequence, "generated_name_exists"))
            progress.advance()
            continue

        strike_glyphs = _build_sequence_bitmaps(
            glyph_name,
            shape,
            strikes,
            strike_maps,
            fallback_strikes,
            fallback_maps,
            font,
        )
        if strike_glyphs is None:
            skips.append(SequenceSkip(normalized, raw_sequence, "missing_source_bitmap"))
            progress.advance()
            continue

        glyph_additions[glyph_name] = strike_glyphs
        for components in _rule_components(normalized, record.raw_sequences):
            rules.append(
                SequenceRule(
                    components=components,
                    replacement=glyph_name,
                    normalized_sequence=normalized,
                    raw_sequence=components,
                ),
            )
        progress.advance()
    progress.finish()

    gid_by_name = add_empty_glyph_slots(
        font,
        [
            (name, hmetrics, vmetrics)
            for name, (_glyphs, hmetrics, vmetrics) in glyph_additions.items()
        ],
    )
    updated_strikes: list[BitmapStrike] = []
    for strike_index, strike in enumerate(strikes):
        additions: list[BitmapGlyph] = []
        for name, (glyphs, _hmetrics, _vmetrics) in glyph_additions.items():
            glyph = glyphs[strike_index]
            additions.append(
                BitmapGlyph(
                    gid=gid_by_name[name],
                    name=name,
                    png=glyph.png,
                    origin_x=glyph.origin_x,
                    origin_y=glyph.origin_y,
                ),
            )
        updated_strikes.append(BitmapStrike(ppem=strike.ppem, glyphs=strike.glyphs + tuple(additions)))

    LOG.info(
        "Materialized %d sequence glyphs, %d GSUB rules, %d skipped records",
        len(glyph_additions),
        len(rules),
        len(skips),
    )
    return SequenceGlyphBuildResult(
        strikes=updated_strikes,
        rules=tuple(rules),
        skips=tuple(skips),
    )


def _raw_candidates(record: SequenceRecord) -> tuple[tuple[int, ...], ...]:
    seen: set[tuple[int, ...]] = set()
    out: list[tuple[int, ...]] = []
    for sequence in (*record.raw_sequences, record.normalized_sequence):
        if sequence and sequence not in seen:
            seen.add(sequence)
            out.append(sequence)
    return tuple(sorted(out, key=lambda seq: (len(seq), seq.count(0xFE0F), seq)))


def _add_single_codepoint_variant_rules(
    oracle: ShapingOracle,
    cmap: dict[int, str],
    record: SequenceRecord,
    raw_candidates: tuple[tuple[int, ...], ...],
    rules: list[SequenceRule],
    skips: list[SequenceSkip],
) -> None:
    normalized = record.normalized_sequence
    if len(normalized) != 1:
        return
    replacement = cmap.get(normalized[0])
    if replacement is None:
        skips.append(SequenceSkip(normalized, None, "missing_single_codepoint_cmap"))
        return
    for raw_sequence in raw_candidates:
        if len(raw_sequence) <= 1:
            continue
        shape = oracle.shape(raw_sequence)
        if not shape.glyphs:
            skips.append(SequenceSkip(normalized, raw_sequence, "empty_source_shape"))
            continue
        if len(shape.glyphs) == 1:
            replacement = shape.glyphs[0].name
        rules.append(
            SequenceRule(
                components=raw_sequence,
                replacement=replacement,
                normalized_sequence=normalized,
                raw_sequence=raw_sequence,
            ),
        )


def _choose_source_shape(
    oracle: ShapingOracle,
    cmap: dict[int, str],
    raw_candidates: tuple[tuple[int, ...], ...],
) -> tuple[tuple[int, ...], ShapeResult] | None:
    for raw_sequence in raw_candidates:
        shape = oracle.shape(raw_sequence)
        if not shape.glyphs:
            continue
        if _is_unchanged_component_output(raw_sequence, shape, cmap):
            continue
        return raw_sequence, shape
    return None


def _is_unchanged_component_output(
    raw_sequence: tuple[int, ...],
    shape: ShapeResult,
    cmap: dict[int, str],
) -> bool:
    ignorable = {0x200D, 0xFE0F}
    components = tuple(cmap.get(cp) for cp in raw_sequence if cp not in ignorable)
    if any(name is None for name in components):
        return False
    return shape.names == components


def _build_sequence_bitmaps(
    glyph_name: str,
    shape: ShapeResult,
    strikes: list[BitmapStrike],
    strike_maps: list[dict[str, BitmapGlyph]],
    fallback_strikes: list[BitmapStrike],
    fallback_maps: list[dict[str, BitmapGlyph]],
    font: TTFont,
) -> tuple[tuple[BitmapGlyph, ...], tuple[int, int], tuple[int, int]] | None:
    glyphs_by_strike: list[BitmapGlyph] = []
    for strike, strike_map in zip(strikes, strike_maps):
        if len(shape.glyphs) == 1:
            source = strike_map.get(shape.glyphs[0].name) or glyph_from_strikes(
                shape.glyphs[0].name,
                strike.ppem,
                strikes + fallback_strikes,
                strike_maps + fallback_maps,
            )
            if source is None:
                return None
            glyphs_by_strike.append(
                BitmapGlyph(
                    gid=-1,
                    name=glyph_name,
                    png=source.png,
                    origin_x=source.origin_x,
                    origin_y=source.origin_y,
                ),
            )
        else:
            png = compose_shape_bitmap(
                shape,
                strike,
                strike_map,
                strikes + fallback_strikes,
                strike_maps + fallback_maps,
                font,
            )
            if png is None:
                return None
            glyphs_by_strike.append(BitmapGlyph(gid=-1, name=glyph_name, png=png))

    hmetrics = reference_hmetrics(font, shape)
    vmetrics = reference_vmetrics(font, shape)
    return tuple(glyphs_by_strike), hmetrics, vmetrics


def _rule_components(
    normalized: tuple[int, ...],
    raw_sequences: tuple[tuple[int, ...], ...],
) -> tuple[tuple[int, ...], ...]:
    seen: set[tuple[int, ...]] = set()
    out: list[tuple[int, ...]] = []
    for sequence in (normalized, *raw_sequences):
        if len(sequence) > 1 and sequence not in seen:
            seen.add(sequence)
            out.append(sequence)
    return tuple(out)
