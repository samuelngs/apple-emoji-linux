#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import re
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PLACEHOLDER_RE = re.compile(r"\{\{[A-Z0-9_]+\}\}")


def main() -> int:
    args = _parse_args()
    date = datetime.strptime(args.date, "%Y%m%d").replace(tzinfo=timezone.utc)
    mapping = {
        "AUR_CONFIG_SHA256": _sha256(REPO_ROOT / "distro/aur/75-apple-color-emoji.conf"),
        "AUR_PKGVER": date.strftime("%Y.%m.%d"),
        "DEBIAN_DATE": format_datetime(date),
        "DEBIAN_VERSION": f"{args.package_version}+{args.date}.{args.short_sha}",
        "FONT_SHA256": _sha256(args.font),
        "RELEASE_TAG": args.release_tag,
        "RPM_CHANGELOG_DATE": date.strftime("%a %b %d %Y"),
        "RPM_RELEASE": f"0.{args.date}.{args.short_sha}",
        "RPM_VERSION": args.package_version,
    }

    if args.aur_dir is not None:
        _render(
            REPO_ROOT / "distro/aur/PKGBUILD.in",
            args.aur_dir / "PKGBUILD",
            mapping,
        )
    if args.debian_dir is not None:
        _render(
            REPO_ROOT / "distro/debian/changelog.in",
            args.debian_dir / "changelog",
            mapping,
        )
    if args.rpm_dir is not None:
        _render(
            REPO_ROOT / "distro/fedora/fonts-apple-color-emoji.spec.in",
            args.rpm_dir / "fonts-apple-color-emoji.spec",
            mapping,
        )
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render release package templates.")
    parser.add_argument("--release-tag", required=True)
    parser.add_argument("--date", required=True, help="UTC release date as YYYYMMDD")
    parser.add_argument("--short-sha", required=True)
    parser.add_argument("--font", required=True, type=Path)
    parser.add_argument("--package-version", default="2.0.0")
    parser.add_argument("--aur-dir", type=Path)
    parser.add_argument("--debian-dir", type=Path)
    parser.add_argument("--rpm-dir", type=Path)
    return parser.parse_args()


def _render(template_path: Path, output_path: Path, mapping: dict[str, str]) -> None:
    text = template_path.read_text(encoding="utf-8")
    for key, value in mapping.items():
        text = text.replace(f"{{{{{key}}}}}", value)
    unresolved = sorted(set(PLACEHOLDER_RE.findall(text)))
    if unresolved:
        raise ValueError(f"{template_path} has unresolved placeholder(s): {', '.join(unresolved)}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text, encoding="utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
