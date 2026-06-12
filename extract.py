#!/usr/bin/env python3
"""Extract one emoji PNG from an sbix font."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from source.font_loader import load_font
from source.sbix import get_emoji_png


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract a single emoji as PNG from Apple Color Emoji TTC.",
    )
    parser.add_argument(
        "--emoji",
        "-e",
        required=True,
        help="Unicode codepoint in hex, e.g. 1F600 or 0x1F600",
    )
    parser.add_argument(
        "--ppem",
        "-p",
        type=int,
        default=96,
        help="Sbix strike ppem (default: 96, to match test fixtures). Uses closest if not available.",
    )
    parser.add_argument(
        "--input",
        "-i",
        type=Path,
        default=Path("/System/Library/Fonts/Apple Color Emoji.ttc"),
        help="Path to Apple Color Emoji.ttc",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        required=True,
        help="Output PNG path, e.g. tests/fixtures/1f600.png",
    )
    parser.add_argument(
        "--font-number",
        type=int,
        default=0,
        help="Font index in TTC (default: 0)",
    )
    args = parser.parse_args()

    emoji_hex = args.emoji.strip().lower().removeprefix("0x")
    try:
        codepoint = int(emoji_hex, 16)
    except ValueError:
        print(f"Invalid --emoji: {args.emoji!r}", file=sys.stderr)
        return 1

    if not args.input.exists():
        print(f"TTC not found: {args.input}", file=sys.stderr)
        return 1

    font = load_font(args.input, font_number=args.font_number)
    result = get_emoji_png(font, codepoint, ppem=args.ppem)
    if result is None:
        print(f"No PNG for U+{codepoint:04X} in {args.input}", file=sys.stderr)
        return 1

    png_bytes, actual_ppem = result
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(png_bytes)
    if actual_ppem != args.ppem:
        print(f"Used ppem={actual_ppem} (requested {args.ppem})", file=sys.stderr)
    print(f"Wrote {args.output} (U+{codepoint:04X}, ppem={actual_ppem})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
