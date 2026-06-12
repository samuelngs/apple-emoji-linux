"""PNG compression helpers for web output."""

from __future__ import annotations

import io
import shutil
import subprocess

PNG_SIGNATURE = bytes((0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A))

WEB_PNG_MAX_COLORS = 128


def _compress_with_pngquant(png_data: bytes, max_colors: int) -> bytes | None:
    if not shutil.which("pngquant"):
        return None
    try:
        r = subprocess.run(
            [
                "pngquant",
                str(max_colors),
                "--quality",
                "66-88",
                "--speed",
                "1",
                "--strip",
                "--nofs",
                "-f",
                "-",
            ],
            input=png_data,
            capture_output=True,
            timeout=30,
        )
        if r.returncode == 0 and r.stdout:
            return r.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return None


def _compress_with_pillow(png_data: bytes, max_colors: int) -> bytes:
    from PIL import Image

    img = Image.open(io.BytesIO(png_data))
    img = img.convert("RGBA")
    img = img.quantize(colors=max_colors)
    out = io.BytesIO()
    img.save(out, format="PNG", compress_level=9, optimize=True)
    return out.getvalue()


def compress_png(
    png_data: bytes,
    *,
    max_colors: int = WEB_PNG_MAX_COLORS,
    prefer_pngquant: bool = True,
) -> bytes:
    if not png_data.startswith(PNG_SIGNATURE):
        return png_data
    compressed = _compress_with_pngquant(png_data, max_colors) if prefer_pngquant else None
    if compressed is not None:
        return compressed
    try:
        return _compress_with_pillow(png_data, max_colors)
    except ImportError:
        raise ImportError(
            "Web output requires pngquant (recommended) or Pillow. "
            "Install: pngquant (system) and/or pip install pillow"
        ) from None
    except Exception:
        return png_data
