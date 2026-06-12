from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from config import ConfigError, load_recipe
from models import BuildRequest
from pipeline import build

LOG = logging.getLogger(__name__)
DEFAULT_INPUT = Path("/System/Library/Fonts/Apple Color Emoji.ttc")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert Apple Color Emoji (sbix TTC) from a YAML build recipe.",
    )
    parser.add_argument(
        "--config",
        "-c",
        type=Path,
        required=True,
        help="YAML build recipe.",
    )
    parser.add_argument(
        "--input",
        "-i",
        type=Path,
        default=DEFAULT_INPUT,
        help=f"Path to Apple Color Emoji.ttc (default: {DEFAULT_INPUT})",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        required=True,
        help="Output TTF path.",
    )
    parser.add_argument(
        "--font-number",
        type=int,
        default=0,
        help="Font index in TTC (default: 0)",
    )
    parser.add_argument(
        "--recompute-ligatures",
        action="store_true",
        help="Override a configured GSUB recipe to recompute ligatures.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Verbose logging.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)

    try:
        build(request_from_args(args))
    except (ConfigError, OSError, ValueError) as e:
        LOG.error("%s", e)
        return 1
    return 0


def request_from_args(args: argparse.Namespace) -> BuildRequest:
    return BuildRequest(
        recipe=load_recipe(args.config),
        input_path=args.input,
        output_path=args.output,
        font_number=args.font_number,
        recompute_ligatures=args.recompute_ligatures,
    )


if __name__ == "__main__":
    sys.exit(main())
