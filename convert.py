#!/usr/bin/env python3
"""Convert Apple Color Emoji (sbix TTC) to a single CBDT/CBLC TTF for Linux or Windows."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from cbdt_cblc_builder import FontMetrics, build_cbdt, build_cblc
from cmap_utils import ensure_unicode_cmap
from sbix_reader import load_font, collect_sbix_glyphs
from skeleton_font import build_skeleton
from windows_compat import apply_windows_compat

LOG = logging.getLogger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Convert Apple Color Emoji (sbix TTC) to a single CBDT/CBLC TTF.",
    )
    parser.add_argument(
        "--input",
        "-i",
        type=Path,
        default=Path("/System/Library/Fonts/Apple Color Emoji.ttc"),
        help="Path to Apple Color Emoji.ttc (default: /System/Library/Fonts/Apple Color Emoji.ttc)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=Path("output/AppleColorEmoji.ttf"),
        help="Output TTF path (default: output/AppleColorEmoji.ttf)",
    )
    parser.add_argument(
        "--font-number",
        type=int,
        default=0,
        help="Font index in TTC (default: 0)",
    )
    parser.add_argument(
        "--ppem",
        type=int,
        default=96,
        help="Sbix strike ppem (default: 96)",
    )
    parser.add_argument(
        "--target",
        choices=["linux", "windows"],
        default="linux",
        help="Target platform: linux or windows (Segoe UI Emoji compatible) (default: linux)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Verbose logging",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)

    if not args.input.exists():
        LOG.error("Input not found: %s", args.input)
        return 1

    try:
        font = load_font(args.input, font_number=args.font_number)
    except Exception as e:
        LOG.error("Failed to load font: %s", e)
        return 1

    if "sbix" not in font:
        LOG.error("Font has no sbix table")
        return 1

    glyphs, strike_meta = collect_sbix_glyphs(font, ppem=args.ppem)
    if not glyphs:
        LOG.error("No glyphs with PNG data found")
        return 1

    LOG.info("Using strike ppem=%d, %d glyphs", strike_meta.ppem, len(glyphs))

    upem = font["head"].unitsPerEm
    ascent = font["hhea"].ascent
    descent = abs(font["hhea"].descent)
    font_metrics = FontMetrics(upem=upem, ascent=ascent, descent=descent)

    cbdt_bytes, locations = build_cbdt(glyphs, strike_meta.ppem, font_metrics)
    cblc_bytes = build_cblc(cbdt_bytes, glyphs, locations, strike_meta.ppem, font_metrics)

    is_windows = args.target == "windows"
    build_skeleton(
        font,
        cbdt_bytes,
        cblc_bytes,
        keep_outlines=is_windows,
        add_bitmap_tables=True,
    )
    ensure_unicode_cmap(font)
    if is_windows:
        apply_windows_compat(font)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    font.save(args.output)
    LOG.info("Wrote %s", args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
