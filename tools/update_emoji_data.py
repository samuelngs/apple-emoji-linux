#!/usr/bin/env python3
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from emoji_data import SEQUENCE_DIR, update_unicode_sequence_files


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Update vendored Unicode emoji sequence data.")
    parser.add_argument(
        "--version",
        default="latest",
        help="Unicode emoji version to download, for example 16.0. Defaults to latest.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=SEQUENCE_DIR,
        help=f"Output directory. Defaults to {SEQUENCE_DIR}.",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging.")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)
    update_unicode_sequence_files(args.version, output_dir=args.output_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
