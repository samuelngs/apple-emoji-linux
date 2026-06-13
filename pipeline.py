from __future__ import annotations

import io
import logging
from pathlib import Path

from bitmap.backfill import backfill_missing_glyphs
from bitmap.transforms import apply_bitmap_transforms
from bitmap.generated import generate_bitmap_strikes
from config import BuildRecipe
from models import BitmapGlyph, BitmapStrike, BuildRequest
from shaping.gsub import build_gsub_from_sequence_rules
from shaping.sequence_glyphs import SequenceGlyphBuildResult, materialize_sequence_glyphs
from shaping.sequences import SequenceRule, load_sequence_inventory
from source.font_loader import load_font
from source.sbix import collect_sbix_glyph_images, get_sbix_strikes
from tables.cbdt_cblc import (
    FontMetrics,
    build_cbdt_strikes,
    build_cblc_strikes,
)
from tables.cleanup import drop_dsig, drop_tables
from tables.cmap import apply_cmap_policy
from tables.head import apply_head_policy
from tables.metrics import apply_metrics_policy
from tables.names import apply_names_policy
from tables.post import apply_post_policy
from tables.skeleton import build_skeleton
from web.split import split_web_font, write_css

LOG = logging.getLogger(__name__)


def build(request: BuildRequest) -> list[Path]:
    """Build a font from a declarative recipe and explicit IO paths."""
    if not request.input_path.exists():
        raise FileNotFoundError(f"Input not found: {request.input_path}")

    font = load_font(request.input_path, font_number=request.font_number)
    if "sbix" not in font:
        raise ValueError("Font has no sbix table")

    strikes = _collect_configured_strikes(font, request.recipe)
    sequence_build = _materialize_sequences(font, strikes, request)
    if sequence_build is not None:
        strikes = sequence_build.strikes
    strikes = apply_bitmap_transforms(strikes, request.recipe.bitmap)

    apply_head_policy(font, request.recipe.tables.head)
    apply_metrics_policy(font, request.recipe.tables.metrics, _font_metrics(font))
    metrics = _font_metrics(font, request.recipe.bitmap.metrics.line_source)

    cbdt_bytes, strike_data = build_cbdt_strikes(
        [
            (
                strike.ppem,
                [(glyph.gid, glyph.name, glyph.png) for glyph in strike.glyphs],
            )
            for strike in strikes
        ],
        metrics,
        y_bearing=request.recipe.bitmap.metrics.y_bearing,
    )
    cblc_bytes = build_cblc_strikes(strike_data, metrics)

    drop = request.recipe.tables.drop
    build_skeleton(
        font,
        cbdt_bytes,
        cblc_bytes,
        keep_outlines=not drop.outlines,
        drop_vertical=drop.vertical_metrics,
        drop_source_tables=drop.source_tables,
        add_bitmap_tables=True,
    )

    apply_cmap_policy(font, request.recipe.tables.cmap)
    apply_names_policy(font, request.recipe.names)
    apply_post_policy(font, request.recipe.tables.post)
    if drop.dsig:
        drop_dsig(font)

    _apply_shaping_policy(font, request, sequence_build.rules if sequence_build else ())
    if drop.after_shaping:
        drop_tables(font, drop.after_shaping)

    request.output_path.parent.mkdir(parents=True, exist_ok=True)
    if request.recipe.split is not None and request.recipe.split.enabled:
        return _write_split_font(
            font,
            strikes[-1],
            metrics,
            request,
            sequence_build.rules if sequence_build else (),
        )

    font.save(request.output_path)
    LOG.info("Wrote %s", request.output_path)
    return [request.output_path]


def _collect_configured_strikes(font, recipe: BuildRecipe) -> list[BitmapStrike]:
    available = set(get_sbix_strikes(font))
    missing = [ppem for ppem in recipe.bitmap.strikes if ppem not in available]
    if missing:
        raise ValueError(
            "Requested bitmap strike ppem(s) not in source font: "
            + ", ".join(str(ppem) for ppem in missing),
        )

    strikes: list[BitmapStrike] = []
    for ppem in recipe.bitmap.strikes:
        glyphs, strike_meta = collect_sbix_glyph_images(font, ppem=ppem)
        if not glyphs:
            raise ValueError(f"Bitmap strike ppem={ppem} has no PNG glyphs")
        strike = BitmapStrike(
            ppem=strike_meta.ppem,
            glyphs=tuple(
                BitmapGlyph(
                    gid=glyph.gid,
                    name=glyph.name,
                    png=glyph.png,
                    origin_x=glyph.origin_x,
                    origin_y=glyph.origin_y,
                )
                for glyph in glyphs
            ),
        )
        strikes.append(strike)
        LOG.info("Using strike ppem=%d, %d glyphs", strike.ppem, len(strike.glyphs))

    strikes = backfill_missing_glyphs(font, strikes, recipe.bitmap.backfill_missing)
    strikes.extend(generate_bitmap_strikes(font, recipe.bitmap.generated_strikes))
    return sorted(strikes, key=lambda strike: strike.ppem)


def _materialize_sequences(
    font,
    strikes: list[BitmapStrike],
    request: BuildRequest,
) -> SequenceGlyphBuildResult | None:
    shaping = request.recipe.shaping
    if shaping is None or shaping.gsub is None or not shaping.gsub.enabled:
        return None

    records = load_sequence_inventory(
        shaping.gsub.sequence_files,
        shaping.gsub.project_sequence_files,
    )
    LOG.info("Loaded %d normalized emoji sequence records", len(records))
    return materialize_sequence_glyphs(
        font,
        request.input_path,
        request.font_number,
        strikes,
        records,
    )


def _font_metrics(font, line_source: str = "hhea") -> FontMetrics:
    if line_source == "os2_win" and "OS/2" in font:
        return FontMetrics(
            upem=font["head"].unitsPerEm,
            ascent=font["OS/2"].usWinAscent,
            descent=font["OS/2"].usWinDescent,
        )
    return FontMetrics(
        upem=font["head"].unitsPerEm,
        ascent=font["hhea"].ascent,
        descent=abs(font["hhea"].descent),
    )


def _apply_shaping_policy(
    font,
    request: BuildRequest,
    sequence_rules: tuple[SequenceRule, ...],
) -> None:
    shaping = request.recipe.shaping
    if shaping is None or shaping.gsub is None or not shaping.gsub.enabled:
        return

    gsub = shaping.gsub
    gsub_table = build_gsub_from_sequence_rules(font, sequence_rules)
    if gsub_table is None:
        return
    font["GSUB"] = gsub_table
    if gsub.replace_morx and "morx" in font:
        del font["morx"]
    LOG.info("Applied configured GSUB shaping policy")


def _write_split_font(
    font,
    primary_strike: BitmapStrike,
    metrics: FontMetrics,
    request: BuildRequest,
    sequence_rules: tuple[SequenceRule, ...],
) -> list[Path]:
    split = request.recipe.split
    if split is None:
        return []

    buf = io.BytesIO()
    font.save(buf)
    chunks = split_web_font(
        buf.getvalue(),
        [(glyph.gid, glyph.name, glyph.png) for glyph in primary_strike.glyphs],
        request.output_path,
        ppem=primary_strike.ppem,
        font_metrics=metrics,
        y_bearing=request.recipe.bitmap.metrics.y_bearing,
        max_chunk_bytes=split.chunk_kb * 1024,
        sequence_rules=sequence_rules,
    )
    if not chunks:
        LOG.warning("No chunk files written (font has no cmap entries)")
        return []

    if split.write_css:
        css_path = request.output_path.with_suffix(".css")
        write_css(css_path, chunks, font_family=_css_family(request.recipe))
        LOG.info("Wrote %s", css_path)
        return [path for _range, path in chunks] + [css_path]
    return [path for _range, path in chunks]


def _css_family(recipe: BuildRecipe) -> str:
    if recipe.names.family:
        return recipe.names.family
    for record in recipe.names.records:
        if record.name_id == 1 and record.platform_id == 3:
            return record.value
    return "Apple Color Emoji"
