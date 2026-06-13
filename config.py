from __future__ import annotations

from pathlib import Path
from typing import Any

from config_types import (
    BackfillMissingConfig,
    BitmapConfig,
    BitmapMetricsConfig,
    BitmapTransformsConfig,
    BuildRecipe,
    CmapEntryConfig,
    CmapConfig,
    ConfigError,
    DropConfig,
    GeneratedStrikesConfig,
    GsubConfig,
    HeadConfig,
    MetricsConfig,
    NameRecordConfig,
    NamesConfig,
    PngConfig,
    PostConfig,
    ShapingConfig,
    SplitConfig,
    TablesConfig,
)
from config_validation import (
    optional_nonempty_str,
    parse_strikes,
    parse_table_tags,
    reject_unknown,
    require_bool,
    require_int,
    require_mapping,
    require_nonempty_str,
    resolve_recipe_path,
)


_TOP_LEVEL_KEYS = {"version", "names", "bitmap", "tables", "shaping", "split"}
_FORBIDDEN_TOP_LEVEL_KEYS = {"target", "builds", "profile", "linux", "windows", "web"}


def load_recipe(path: str | Path) -> BuildRecipe:
    try:
        import yaml
    except ModuleNotFoundError as e:
        raise ConfigError("PyYAML is required for --config builds") from e

    recipe_path = Path(path)
    with recipe_path.open(encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    data = require_mapping(raw, "recipe")
    forbidden = sorted(_FORBIDDEN_TOP_LEVEL_KEYS & data.keys())
    if forbidden:
        raise ConfigError(f"recipe must not contain target selector keys: {', '.join(forbidden)}")
    reject_unknown(data, _TOP_LEVEL_KEYS, "recipe")
    version = data.get("version")
    if version != 1:
        raise ConfigError("recipe.version must be 1")
    for section in ("names", "bitmap", "tables"):
        if section not in data:
            raise ConfigError(f"recipe.{section} is required")

    base_dir = recipe_path.parent
    return BuildRecipe(
        names=_parse_names(data["names"]),
        bitmap=_parse_bitmap(data["bitmap"], base_dir),
        tables=_parse_tables(data["tables"]),
        shaping=_parse_shaping(data.get("shaping"), base_dir),
        split=_parse_split(data.get("split")),
    )


def _parse_names(raw: Any) -> NamesConfig:
    data = require_mapping(raw, "names")
    reject_unknown(data, {"family", "records"}, "names")
    family = optional_nonempty_str(data.get("family"), "names.family")
    records = _parse_name_records(data.get("records"))
    if family and records:
        raise ConfigError("names.family and names.records are mutually exclusive")
    if not family and not records:
        raise ConfigError("names.family or names.records is required")
    return NamesConfig(family=family, records=records)


def _parse_name_records(raw: Any) -> tuple[NameRecordConfig, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, list) or not raw:
        raise ConfigError("names.records must be a non-empty list")
    records: list[NameRecordConfig] = []
    for index, item in enumerate(raw):
        path = f"names.records[{index}]"
        data = require_mapping(item, path)
        reject_unknown(
            data,
            {"name_id", "platform_id", "platform_encoding_id", "language_id", "value"},
            path,
        )
        records.append(
            NameRecordConfig(
                name_id=require_int(data.get("name_id"), f"{path}.name_id"),
                platform_id=require_int(data.get("platform_id"), f"{path}.platform_id"),
                platform_encoding_id=require_int(
                    data.get("platform_encoding_id"),
                    f"{path}.platform_encoding_id",
                ),
                language_id=require_int(data.get("language_id"), f"{path}.language_id"),
                value=require_nonempty_str(data.get("value"), f"{path}.value"),
            ),
        )
    return tuple(records)


def _parse_bitmap(raw: Any, base_dir: Path) -> BitmapConfig:
    data = require_mapping(raw, "bitmap")
    reject_unknown(
        data,
        {
            "format",
            "strikes",
            "generated_strikes",
            "backfill_missing",
            "transforms",
            "png",
            "metrics",
        },
        "bitmap",
    )
    bitmap_format = data.get("format", "cbdt_cblc")
    if bitmap_format != "cbdt_cblc":
        raise ConfigError("bitmap.format must be cbdt_cblc")
    strikes = parse_strikes(data.get("strikes"), "bitmap.strikes")
    generated = _parse_generated_strikes(data.get("generated_strikes"))
    if generated is not None:
        duplicated = sorted(set(strikes) & set(generated.sizes))
        if duplicated:
            raise ConfigError(
                "bitmap.generated_strikes.sizes must not duplicate bitmap.strikes: "
                + ", ".join(str(ppem) for ppem in duplicated),
            )
    return BitmapConfig(
        format=bitmap_format,
        strikes=strikes,
        generated_strikes=generated,
        backfill_missing=_parse_backfill_missing(data.get("backfill_missing")),
        transforms=_parse_transforms(data.get("transforms"), base_dir),
        png=_parse_png(data.get("png")),
        metrics=_parse_bitmap_metrics(data.get("metrics")),
    )


def _parse_generated_strikes(raw: Any) -> GeneratedStrikesConfig | None:
    if raw is None:
        return None
    data = require_mapping(raw, "bitmap.generated_strikes")
    reject_unknown(data, {"source", "sizes"}, "bitmap.generated_strikes")
    source = require_int(data.get("source"), "bitmap.generated_strikes.source")
    if source < 1 or source > 255:
        raise ConfigError("bitmap.generated_strikes.source must be between 1 and 255")
    return GeneratedStrikesConfig(
        source=source,
        sizes=parse_strikes(data.get("sizes"), "bitmap.generated_strikes.sizes"),
    )


def _parse_backfill_missing(raw: Any) -> BackfillMissingConfig | None:
    if raw is None:
        return None
    data = require_mapping(raw, "bitmap.backfill_missing")
    reject_unknown(data, {"source"}, "bitmap.backfill_missing")
    source = require_int(data.get("source"), "bitmap.backfill_missing.source")
    if source < 1 or source > 255:
        raise ConfigError("bitmap.backfill_missing.source must be between 1 and 255")
    return BackfillMissingConfig(source=source)


def _parse_bitmap_metrics(raw: Any) -> BitmapMetricsConfig:
    if raw is None:
        return BitmapMetricsConfig()
    data = require_mapping(raw, "bitmap.metrics")
    reject_unknown(data, {"y_bearing", "line_source"}, "bitmap.metrics")
    y_bearing = optional_nonempty_str(
        data.get("y_bearing"),
        "bitmap.metrics.y_bearing",
    )
    if y_bearing not in {None, "five_sixths_height", "full_height", "line_center"}:
        raise ConfigError("bitmap.metrics.y_bearing is invalid")
    line_source = optional_nonempty_str(
        data.get("line_source"),
        "bitmap.metrics.line_source",
    )
    if line_source not in {None, "hhea", "os2_win"}:
        raise ConfigError("bitmap.metrics.line_source is invalid")
    return BitmapMetricsConfig(
        y_bearing=y_bearing or "five_sixths_height",
        line_source=line_source or "hhea",
    )


def _parse_transforms(raw: Any, base_dir: Path) -> BitmapTransformsConfig:
    del base_dir
    if raw is None:
        return BitmapTransformsConfig()
    data = require_mapping(raw, "bitmap.transforms")
    reject_unknown(
        data,
        {"flip_directional_variants"},
        "bitmap.transforms",
    )
    return BitmapTransformsConfig(
        flip_directional_variants=require_bool(
            data.get("flip_directional_variants", False),
            "bitmap.transforms.flip_directional_variants",
        ),
    )


def _parse_png(raw: Any) -> PngConfig:
    if raw is None:
        return PngConfig()
    data = require_mapping(raw, "bitmap.png")
    reject_unknown(data, {"compress", "strikes", "max_colors", "prefer_pngquant"}, "bitmap.png")
    max_colors = require_int(data.get("max_colors", 128), "bitmap.png.max_colors")
    if max_colors < 2 or max_colors > 256:
        raise ConfigError("bitmap.png.max_colors must be between 2 and 256")
    return PngConfig(
        compress=require_bool(data.get("compress", False), "bitmap.png.compress"),
        strikes=parse_strikes(data["strikes"], "bitmap.png.strikes") if "strikes" in data else (),
        max_colors=max_colors,
        prefer_pngquant=require_bool(
            data.get("prefer_pngquant", True),
            "bitmap.png.prefer_pngquant",
        ),
    )


def _parse_tables(raw: Any) -> TablesConfig:
    data = require_mapping(raw, "tables")
    reject_unknown(data, {"drop", "cmap", "metrics", "head", "post"}, "tables")
    return TablesConfig(
        drop=_parse_drop(data.get("drop")),
        cmap=_parse_cmap(data.get("cmap")),
        metrics=_parse_metrics(data.get("metrics")),
        head=_parse_head(data.get("head")),
        post=_parse_post(data.get("post")),
    )


def _parse_drop(raw: Any) -> DropConfig:
    if raw is None:
        return DropConfig()
    data = require_mapping(raw, "tables.drop")
    reject_unknown(
        data,
        {"source_tables", "outlines", "vertical_metrics", "dsig", "after_shaping"},
        "tables.drop",
    )
    return DropConfig(
        source_tables=require_bool(data.get("source_tables", False), "tables.drop.source_tables"),
        outlines=require_bool(data.get("outlines", False), "tables.drop.outlines"),
        vertical_metrics=require_bool(
            data.get("vertical_metrics", False),
            "tables.drop.vertical_metrics",
        ),
        dsig=require_bool(data.get("dsig", False), "tables.drop.dsig"),
        after_shaping=parse_table_tags(
            data.get("after_shaping", []),
            "tables.drop.after_shaping",
        ),
    )


def _parse_cmap(raw: Any) -> CmapConfig:
    if raw is None:
        return CmapConfig()
    data = require_mapping(raw, "tables.cmap")
    reject_unknown(data, {"bmp", "ucs4", "entries"}, "tables.cmap")
    return CmapConfig(
        bmp=require_bool(data.get("bmp", False), "tables.cmap.bmp"),
        ucs4=require_bool(data.get("ucs4", False), "tables.cmap.ucs4"),
        entries=_parse_cmap_entries(data.get("entries")),
    )


def _parse_cmap_entries(raw: Any) -> tuple[CmapEntryConfig, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, list):
        raise ConfigError("tables.cmap.entries must be a list")
    entries: list[CmapEntryConfig] = []
    for index, item in enumerate(raw):
        path = f"tables.cmap.entries[{index}]"
        data = require_mapping(item, path)
        reject_unknown(data, {"codepoint", "glyph"}, path)
        codepoint = require_int(data.get("codepoint"), f"{path}.codepoint")
        if codepoint < 0 or codepoint > 0x10FFFF:
            raise ConfigError(f"{path}.codepoint must be a Unicode scalar value")
        entries.append(
            CmapEntryConfig(
                codepoint=codepoint,
                glyph=require_nonempty_str(data.get("glyph"), f"{path}.glyph"),
            ),
        )
    return tuple(entries)


def _parse_metrics(raw: Any) -> MetricsConfig | None:
    if raw is None:
        return None
    data = require_mapping(raw, "tables.metrics")
    reject_unknown(
        data,
        {"policy", "fs_type", "unicode_ranges", "hhea", "os2"},
        "tables.metrics",
    )
    policy = optional_nonempty_str(data.get("policy"), "tables.metrics.policy")
    if policy not in {None, "browser_safe"}:
        raise ConfigError("tables.metrics.policy is invalid")
    fs_type = optional_nonempty_str(data.get("fs_type"), "tables.metrics.fs_type")
    if fs_type not in {None, "installable", "editable"}:
        raise ConfigError("tables.metrics.fs_type is invalid")
    unicode_ranges = optional_nonempty_str(
        data.get("unicode_ranges"),
        "tables.metrics.unicode_ranges",
    )
    if unicode_ranges not in {None, "emoji"}:
        raise ConfigError("tables.metrics.unicode_ranges is invalid")
    return MetricsConfig(
        policy=policy,
        fs_type=fs_type,
        unicode_ranges=unicode_ranges,
        hhea=_parse_hhea_metrics(data.get("hhea")),
        os2=_parse_os2_metrics(data.get("os2")),
    )


def _parse_hhea_metrics(raw: Any) -> dict[str, int] | None:
    if raw is None:
        return None
    data = require_mapping(raw, "tables.metrics.hhea")
    reject_unknown(data, {"ascent", "descent", "line_gap"}, "tables.metrics.hhea")
    return {key: require_int(value, f"tables.metrics.hhea.{key}") for key, value in data.items()}


def _parse_os2_metrics(raw: Any) -> dict[str, int | str | dict[str, int]] | None:
    if raw is None:
        return None
    data = require_mapping(raw, "tables.metrics.os2")
    allowed = {
        "version",
        "x_avg_char_width",
        "us_weight_class",
        "us_width_class",
        "fs_type",
        "y_subscript_x_size",
        "y_subscript_y_size",
        "y_subscript_x_offset",
        "y_subscript_y_offset",
        "y_superscript_x_size",
        "y_superscript_y_size",
        "y_superscript_x_offset",
        "y_superscript_y_offset",
        "y_strikeout_size",
        "y_strikeout_position",
        "s_family_class",
        "s_typo_ascender",
        "s_typo_descender",
        "s_typo_line_gap",
        "us_win_ascent",
        "us_win_descent",
        "fs_selection",
        "us_first_char_index",
        "us_last_char_index",
        "s_cap_height",
        "sx_height",
        "us_max_context",
        "unicode_range_1",
        "unicode_range_2",
        "unicode_range_3",
        "unicode_range_4",
        "code_page_range_1",
        "code_page_range_2",
        "vendor_id",
        "panose",
    }
    reject_unknown(data, allowed, "tables.metrics.os2")
    parsed: dict[str, int | str | dict[str, int]] = {}
    for key, value in data.items():
        if key == "vendor_id":
            parsed[key] = require_nonempty_str(value, "tables.metrics.os2.vendor_id")
        elif key == "panose":
            panose = require_mapping(value, "tables.metrics.os2.panose")
            reject_unknown(
                panose,
                {
                    "family_type",
                    "serif_style",
                    "weight",
                    "proportion",
                    "contrast",
                    "stroke_variation",
                    "arm_style",
                    "letter_form",
                    "midline",
                    "x_height",
                },
                "tables.metrics.os2.panose",
            )
            parsed[key] = {
                panose_key: require_int(
                    panose_value,
                    f"tables.metrics.os2.panose.{panose_key}",
                )
                for panose_key, panose_value in panose.items()
            }
        else:
            parsed[key] = require_int(value, f"tables.metrics.os2.{key}")
    return parsed


def _parse_head(raw: Any) -> HeadConfig | None:
    if raw is None:
        return None
    data = require_mapping(raw, "tables.head")
    reject_unknown(data, {"mac_style", "units_per_em"}, "tables.head")
    mac_style = None
    if "mac_style" in data:
        mac_style = require_int(data.get("mac_style"), "tables.head.mac_style")
    if mac_style is not None and mac_style < 0:
        raise ConfigError("tables.head.mac_style must be non-negative")
    units_per_em = None
    if "units_per_em" in data:
        units_per_em = require_int(data.get("units_per_em"), "tables.head.units_per_em")
    if units_per_em is not None and not (16 <= units_per_em <= 16384):
        raise ConfigError("tables.head.units_per_em must be between 16 and 16384")
    return HeadConfig(mac_style=mac_style, units_per_em=units_per_em)


def _parse_post(raw: Any) -> PostConfig | None:
    if raw is None:
        return None
    data = require_mapping(raw, "tables.post")
    reject_unknown(data, {"format"}, "tables.post")
    post_format = data.get("format")
    if post_format not in {2, 2.0, 3, 3.0}:
        raise ConfigError("tables.post.format must be 2 or 3")
    return PostConfig(format=post_format)


def _parse_shaping(raw: Any, base_dir: Path) -> ShapingConfig | None:
    if raw is None:
        return None
    data = require_mapping(raw, "shaping")
    reject_unknown(data, {"gsub"}, "shaping")
    return ShapingConfig(gsub=_parse_gsub(data.get("gsub"), base_dir))


def _parse_gsub(raw: Any, base_dir: Path) -> GsubConfig | None:
    if raw is None:
        return None
    data = require_mapping(raw, "shaping.gsub")
    reject_unknown(
        data,
        {"enabled", "sequence_files", "project_sequence_files", "replace_morx"},
        "shaping.gsub",
    )
    enabled = require_bool(data.get("enabled", False), "shaping.gsub.enabled")
    sequence_files = _parse_path_list(
        data.get("sequence_files"),
        base_dir,
        "shaping.gsub.sequence_files",
    )
    project_sequence_files = _parse_path_list(
        data.get("project_sequence_files"),
        base_dir,
        "shaping.gsub.project_sequence_files",
    )
    if enabled and not sequence_files:
        raise ConfigError("shaping.gsub.sequence_files is required when GSUB is enabled")
    return GsubConfig(
        enabled=enabled,
        sequence_files=sequence_files,
        project_sequence_files=project_sequence_files,
        replace_morx=require_bool(data.get("replace_morx", False), "shaping.gsub.replace_morx"),
    )


def _parse_path_list(raw: Any, base_dir: Path, path: str) -> tuple[Path, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, list):
        raise ConfigError(f"{path} must be a list of paths")
    paths: list[Path] = []
    for index, value in enumerate(raw):
        paths.append(
            resolve_recipe_path(
                base_dir,
                require_nonempty_str(value, f"{path}[{index}]"),
            ),
        )
    return tuple(paths)


def _parse_split(raw: Any) -> SplitConfig | None:
    if raw is None:
        return None
    data = require_mapping(raw, "split")
    reject_unknown(data, {"enabled", "chunk_kb", "write_css"}, "split")
    chunk_kb = require_int(data.get("chunk_kb", 500), "split.chunk_kb")
    if chunk_kb <= 0:
        raise ConfigError("split.chunk_kb must be positive")
    return SplitConfig(
        enabled=require_bool(data.get("enabled", False), "split.enabled"),
        chunk_kb=chunk_kb,
        write_css=require_bool(data.get("write_css", False), "split.write_css"),
    )
