from __future__ import annotations

import logging
from pathlib import Path
from urllib.request import Request, urlopen

LOG = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parent
SEQUENCE_DIR = ROOT_DIR / "sequences"

UNICODE_EMOJI_FILES = (
    "emoji-sequences.txt",
    "emoji-zwj-sequences.txt",
    "emoji-test.txt",
)
UNICODE_UCD_EMOJI_FILES = ("emoji-variation-sequences.txt",)
PROJECT_SEQUENCE_FILE = "project-sequences.txt"


def default_sequence_files() -> tuple[Path, ...]:
    names = (*UNICODE_EMOJI_FILES, *UNICODE_UCD_EMOJI_FILES)
    return tuple(SEQUENCE_DIR / name for name in names)


def default_project_sequence_files() -> tuple[Path, ...]:
    return (SEQUENCE_DIR / PROJECT_SEQUENCE_FILE,)


def update_unicode_sequence_files(
    version: str = "latest",
    *,
    output_dir: Path = SEQUENCE_DIR,
    timeout: int = 60,
) -> tuple[Path, ...]:
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    for name in UNICODE_EMOJI_FILES:
        written.append(_download_file(_emoji_url(version, name), output_dir / name, timeout))
    for name in UNICODE_UCD_EMOJI_FILES:
        written.append(_download_file(_ucd_emoji_url(version, name), output_dir / name, timeout))

    return tuple(written)


def _emoji_url(version: str, filename: str) -> str:
    if version == "latest":
        base = "https://unicode.org/Public/emoji/latest"
    else:
        base = f"https://unicode.org/Public/emoji/{version}"
    return f"{base}/{filename}"


def _ucd_emoji_url(version: str, filename: str) -> str:
    if version == "latest":
        base = "https://unicode.org/Public/UCD/latest/ucd/emoji"
    else:
        base = f"https://unicode.org/Public/{_ucd_version(version)}/ucd/emoji"
    return f"{base}/{filename}"


def _ucd_version(version: str) -> str:
    return version if version.count(".") == 2 else f"{version}.0"


def _download_file(url: str, output_path: Path, timeout: int) -> Path:
    LOG.info("Downloading %s", url)
    request = Request(url, headers={"User-Agent": "apple-emoji-ttf"})
    with urlopen(request, timeout=timeout) as response:
        body = response.read()

    tmp_path = output_path.with_suffix(output_path.suffix + ".tmp")
    tmp_path.write_bytes(body)
    tmp_path.replace(output_path)
    LOG.info("Wrote %s", output_path)
    return output_path
