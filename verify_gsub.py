#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from emoji_data import default_project_sequence_files, default_sequence_files
from shaping.oracle import ShapingOracle
from shaping.sequences import (
    SequenceRecord,
    format_sequence,
    load_sequence_inventory,
    sequence_glyph_name,
)

LOG = logging.getLogger(__name__)
DEFAULT_INPUT = Path("/System/Library/Fonts/Apple Color Emoji.ttc")
DEFAULT_SEQUENCE_FILES = default_sequence_files()
DEFAULT_PROJECT_SEQUENCE_FILES = default_project_sequence_files()


def main(argv: list[str] | None = None) -> int:
    parser = _arg_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)

    records = load_sequence_inventory(args.sequence_file, args.project_sequence_file)
    source = ShapingOracle(args.input, font_number=args.font_number)
    generated = ShapingOracle(args.font)
    try:
        mismatches = verify_records(source, generated, records, limit=args.limit)
    finally:
        source.close()
        generated.close()

    report = {
        "records": len(records),
        "mismatches": len(mismatches),
        "items": mismatches,
    }
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")
        LOG.info("Wrote %s", args.report)
    else:
        print(json.dumps(report, indent=2))

    LOG.info("Verified %d records, %d mismatches", len(records), len(mismatches))
    return 1 if mismatches else 0


def verify_records(
    source: ShapingOracle,
    generated: ShapingOracle,
    records: list[SequenceRecord],
    *,
    limit: int | None = None,
) -> list[dict[str, object]]:
    generated_order = set(generated.glyph_order)
    generated_cmap = generated.ttfont.getBestCmap() or {}
    gsub_rules = _saved_gsub_rules(generated.ttfont)
    mismatches: list[dict[str, object]] = []

    for record in records:
        normalized = record.normalized_sequence
        expected_sequence_glyph = sequence_glyph_name(normalized)
        for raw_sequence in record.raw_sequences:
            source_shape = source.shape(raw_sequence)
            generated_shape = generated.shape(raw_sequence)
            reason = _mismatch_reason(
                record,
                raw_sequence,
                generated_shape.names,
                expected_sequence_glyph,
                expected_sequence_glyph in generated_order,
                generated_cmap,
                gsub_rules,
            )
            if reason is None:
                continue
            mismatches.append(
                {
                    "raw_sequence": format_sequence(raw_sequence),
                    "normalized_sequence": format_sequence(normalized),
                    "source_output_glyphs": list(source_shape.names),
                    "generated_output_glyphs": list(generated_shape.names),
                    "source_positions": [
                        _position_dict(glyph) for glyph in source_shape.glyphs
                    ],
                    "generated_positions": [
                        _position_dict(glyph) for glyph in generated_shape.glyphs
                    ],
                    "reason": reason,
                },
            )
            if limit is not None and len(mismatches) >= limit:
                return mismatches
    return mismatches


def _mismatch_reason(
    record: SequenceRecord,
    raw_sequence: tuple[int, ...],
    generated_names: tuple[str, ...],
    expected_sequence_glyph: str,
    has_expected_sequence_glyph: bool,
    generated_cmap: dict[int, str],
    gsub_rules: dict[tuple[str, ...], str],
) -> str | None:
    normalized = record.normalized_sequence
    component_names = tuple(generated_cmap.get(cp) for cp in raw_sequence)
    saved_replacement = None
    if len(component_names) >= 2 and not any(name is None for name in component_names):
        saved_replacement = gsub_rules.get(component_names)  # type: ignore[arg-type]

    if len(normalized) > 1:
        expected = saved_replacement or expected_sequence_glyph
        if saved_replacement is None and not has_expected_sequence_glyph:
            return "missing_generated_sequence_glyph"
        if generated_names != (expected,):
            return "sequence_did_not_shape_to_generated_glyph"
        return None

    if len(raw_sequence) <= 1:
        return None
    expected = saved_replacement or (generated_cmap.get(normalized[0]) if normalized else None)
    if expected is None:
        return "missing_single_codepoint_cmap"
    if generated_names != (expected,):
        return "single_codepoint_variant_left_residual_glyphs"
    return None


def _saved_gsub_rules(font) -> dict[tuple[str, ...], str]:
    rules: dict[tuple[str, ...], str] = {}
    if "GSUB" not in font:
        return rules
    gsub = font["GSUB"].table
    if not getattr(gsub, "LookupList", None):
        return rules
    for lookup in gsub.LookupList.Lookup:
        if lookup.LookupType != 4:
            continue
        for subtable in lookup.SubTable:
            ligatures = getattr(subtable, "ligatures", None)
            if not ligatures:
                continue
            for first, ligature_list in ligatures.items():
                for ligature in ligature_list:
                    rules[(first, *ligature.Component)] = ligature.LigGlyph
    return rules


def _position_dict(glyph) -> dict[str, object]:
    return {
        "name": glyph.name,
        "cluster": glyph.cluster,
        "advance": [glyph.x_advance, glyph.y_advance],
        "offset": [glyph.x_offset, glyph.y_offset],
    }


def _arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify generated emoji GSUB shaping.")
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help=f"Path to Apple Color Emoji.ttc (default: {DEFAULT_INPUT})",
    )
    parser.add_argument("--font", type=Path, required=True, help="Generated font to verify.")
    parser.add_argument("--font-number", type=int, default=0, help="Source TTC font index.")
    parser.add_argument(
        "--sequence-file",
        type=Path,
        action="append",
        default=list(DEFAULT_SEQUENCE_FILES),
        help="Unicode-style sequence file. Can be passed more than once.",
    )
    parser.add_argument(
        "--project-sequence-file",
        type=Path,
        action="append",
        default=list(DEFAULT_PROJECT_SEQUENCE_FILES),
        help="Project override sequence file. Can be passed more than once.",
    )
    parser.add_argument("--report", type=Path, help="Write JSON mismatch report.")
    parser.add_argument("--limit", type=int, help="Stop after this many mismatches.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging.")
    return parser


if __name__ == "__main__":
    sys.exit(main())
