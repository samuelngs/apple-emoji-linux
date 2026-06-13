"""Render fixture emoji through Chromium and compare the screenshots."""

from __future__ import annotations

import argparse
import re
import shutil
import sys
import tempfile
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

TEST_FONT_FAMILY = "TestAppleEmoji"
FIXTURE_PPEM = 96  # recipes include a 96 ppem strike, so fixtures line up

HEX_STEM_RE = re.compile(r"^[0-9a-f]{1,8}$")


def _discover_fixtures(fixtures_dir: Path) -> list[tuple[int, Path]]:
    out: list[tuple[int, Path]] = []
    if not fixtures_dir.is_dir():
        return out
    for p in fixtures_dir.glob("*.png"):
        stem = p.stem.lower()
        if HEX_STEM_RE.match(stem):
            try:
                out.append((int(stem, 16), p))
            except ValueError:
                pass
    return sorted(out, key=lambda x: x[0])


def _platform_font(root: Path) -> Path:
    import platform
    if platform.system() == "Windows":
        return root / "output/AppleColorEmoji-Windows.ttf"
    return root / "output/AppleColorEmoji-Linux.ttf"


HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
@font-face {{
  font-family: "{font_family}";
  src: url("{font_url}");
}}
#emoji {{
  font-family: "{font_family}", sans-serif;
  font-size: {font_size}px;
  line-height: 1;
  width: {size}px;
  height: {size}px;
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}}
</style>
</head>
<body>
<div id="emoji">{emoji}</div>
</body>
</html>
"""


def _find_free_port():
    with __import__("socket").socket() as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def _composite_on_white(img: "Image.Image") -> "Image.Image":
    from PIL import Image
    white = Image.new("RGBA", img.size, (255, 255, 255, 255))
    return Image.alpha_composite(white, img)


def _image_similarity(ref: "Image.Image", got: "Image.Image") -> float:
    from PIL import Image
    if ref.size != got.size:
        return 0.0
    ref = _composite_on_white(ref.convert("RGBA"))
    got = got.convert("RGBA")
    ra = ref.load()
    ga = got.load()
    w, h = ref.size
    tol = 12
    same = 0
    for x in range(w):
        for y in range(h):
            pr, pg = ra[x, y], ga[x, y]
            for i in range(4):
                if abs(pr[i] - pg[i]) <= tol:
                    same += 1
    return same / (w * h * 4)


def run_font_render_emoji(
    font_path: Path,
    codepoint: int,
    fixture_png: Path,
    serve_dir: str,
    font_filename: str,
    port: int,
    similarity_threshold: float = 0.80,
    save_results_dir: Path | None = None,
) -> tuple[float, str | None]:
    from playwright.sync_api import sync_playwright
    emoji_char = chr(codepoint)
    size = FIXTURE_PPEM
    html = HTML_TEMPLATE.format(
        font_family=TEST_FONT_FAMILY,
        font_url=font_filename,
        font_size=FIXTURE_PPEM,
        size=size,
        emoji=emoji_char,
    )
    (Path(serve_dir) / "index.html").write_text(html, encoding="utf-8")
    url = f"http://127.0.0.1:{port}/index.html"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": size, "height": size}, device_scale_factor=1)
            page.goto(url, wait_until="networkidle")
            page.wait_for_function("document.fonts.ready")
            loaded = page.evaluate(
                "(family) => document.fonts.check('" + str(FIXTURE_PPEM) + "px ' + family)",
                TEST_FONT_FAMILY,
            )
            if not loaded:
                raise AssertionError(f"Font {TEST_FONT_FAMILY!r} did not load for U+{codepoint:04X}")
            screenshot_path = Path(serve_dir) / "rendered.png"
            page.locator("#emoji").screenshot(path=str(screenshot_path))
            if save_results_dir is not None:
                save_results_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(screenshot_path, save_results_dir / f"{codepoint:x}.png")
            from PIL import Image
            ref = Image.open(fixture_png).convert("RGBA")
            got = Image.open(screenshot_path).convert("RGBA")
            if got.size != ref.size:
                got = got.resize(ref.size, Image.Resampling.LANCZOS)
            sim = _image_similarity(ref, got)
            print(f"U+{codepoint:04X} similarity {sim:.2%}")
            if sim < similarity_threshold:
                return (sim, f"U+{codepoint:04X} similarity {sim:.2%} < {similarity_threshold:.0%}")
            return (sim, None)
        finally:
            browser.close()


def run_font_render(
    font_path: Path,
    emoji_fixtures: list[tuple[int, Path]],
    similarity_threshold: float = 0.80,
    save_results_dir: Path | None = None,
) -> None:
    font_path = font_path.resolve()
    if not font_path.exists():
        raise FileNotFoundError(f"Font not found: {font_path}")
    if not emoji_fixtures:
        raise ValueError("No emoji fixtures found in tests/fixtures (add PNGs via extract.py)")

    serve_dir = tempfile.mkdtemp(prefix="font_render_")
    try:
        font_filename = font_path.name
        shutil.copy2(font_path, Path(serve_dir) / font_filename)

        port = _find_free_port()
        handler = type(
            "DirHandler",
            (SimpleHTTPRequestHandler,),
            {"__init__": lambda self, *a, **k: SimpleHTTPRequestHandler.__init__(
                self, *a, directory=serve_dir, **k
            )},
        )
        server = HTTPServer(("127.0.0.1", port), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        failures: list[tuple[int, float, str]] = []  # (codepoint, similarity, message)
        try:
            for codepoint, fixture_png in emoji_fixtures:
                try:
                    sim, err = run_font_render_emoji(
                        font_path,
                        codepoint,
                        fixture_png,
                        serve_dir,
                        font_filename,
                        port,
                        similarity_threshold=similarity_threshold,
                        save_results_dir=save_results_dir,
                    )
                    if err is not None:
                        failures.append((codepoint, sim, err))
                except Exception as e:
                    failures.append((codepoint, float("nan"), str(e)))
            if failures:
                lines = [f"  {msg}" for (_, _, msg) in failures]
                raise AssertionError(
                    f"{len(failures)} emoji failed (of {len(emoji_fixtures)} checked):\n" + "\n".join(lines)
                )
        finally:
            server.shutdown()
    finally:
        shutil.rmtree(serve_dir, ignore_errors=True)


def _main() -> int:
    parser = argparse.ArgumentParser(description="Check that the built TTF renders emoji in Chromium; compares to fixture PNGs.")
    parser.add_argument("font", nargs="?", help="Path to the TTF. Default: platform font (Linux or Windows build).")
    parser.add_argument("--similarity", type=float, default=0.80, help="Min similarity to pass (default 0.80).")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent
    fixtures_dir = Path(__file__).resolve().parent / "fixtures"
    emoji_fixtures = _discover_fixtures(fixtures_dir)
    if not emoji_fixtures:
        print("No fixture PNGs in tests/fixtures. Add some with: python extract.py --emoji 1F600 --ppem 96 --output tests/fixtures/1f600.png", file=sys.stderr)
        return 1

    font_path = Path(args.font) if args.font else _platform_font(root)
    try:
        run_font_render(
            font_path,
            emoji_fixtures,
            similarity_threshold=args.similarity,
            save_results_dir=Path(__file__).resolve().parent / "results",
        )
        print(f"PASS {font_path} ({len(emoji_fixtures)} emoji)")
    except Exception as e:
        print(f"FAIL {font_path}: {e}", file=sys.stderr)
        return 1
    return 0


def test_font_render() -> None:
    import pytest
    root = Path(__file__).resolve().parent.parent
    fixtures_dir = Path(__file__).resolve().parent / "fixtures"
    emoji_fixtures = _discover_fixtures(fixtures_dir)
    if not emoji_fixtures:
        pytest.skip("No fixture PNGs in tests/fixtures; add via extract.py --emoji <HEX> --ppem 96 --output tests/fixtures/<hex>.png")
    font_path = _platform_font(root)
    if not font_path.exists():
        pytest.skip(f"Font not built: {font_path}")
    run_font_render(
        font_path,
        emoji_fixtures,
        save_results_dir=Path(__file__).resolve().parent / "results",
    )


if __name__ == "__main__":
    sys.exit(_main())
