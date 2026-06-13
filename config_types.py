from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


class ConfigError(ValueError):
    """Raised when a build recipe is invalid."""


@dataclass(frozen=True)
class NameRecordConfig:
    name_id: int
    platform_id: int
    platform_encoding_id: int
    language_id: int
    value: str


@dataclass(frozen=True)
class NamesConfig:
    family: str | None = None
    records: tuple[NameRecordConfig, ...] = ()


@dataclass(frozen=True)
class BitmapTransformsConfig:
    flip_directional_variants: bool = False


@dataclass(frozen=True)
class PngConfig:
    compress: bool = False
    strikes: tuple[int, ...] = ()
    max_colors: int = 128
    prefer_pngquant: bool = True


@dataclass(frozen=True)
class BitmapMetricsConfig:
    y_bearing: str = "five_sixths_height"
    line_source: str = "hhea"


@dataclass(frozen=True)
class GeneratedStrikesConfig:
    source: int
    sizes: tuple[int, ...]


@dataclass(frozen=True)
class BackfillMissingConfig:
    source: int


@dataclass(frozen=True)
class BitmapConfig:
    format: str = "cbdt_cblc"
    strikes: tuple[int, ...] = (96,)
    generated_strikes: GeneratedStrikesConfig | None = None
    backfill_missing: BackfillMissingConfig | None = None
    transforms: BitmapTransformsConfig = field(default_factory=BitmapTransformsConfig)
    png: PngConfig = field(default_factory=PngConfig)
    metrics: BitmapMetricsConfig = field(default_factory=BitmapMetricsConfig)


@dataclass(frozen=True)
class DropConfig:
    source_tables: bool = False
    outlines: bool = False
    vertical_metrics: bool = False
    dsig: bool = False
    after_shaping: tuple[str, ...] = ()


@dataclass(frozen=True)
class CmapEntryConfig:
    codepoint: int
    glyph: str


@dataclass(frozen=True)
class CmapConfig:
    bmp: bool = False
    ucs4: bool = False
    entries: tuple[CmapEntryConfig, ...] = ()


@dataclass(frozen=True)
class MetricsConfig:
    policy: str | None = None
    fs_type: str | None = None
    unicode_ranges: str | None = None
    hhea: dict[str, int] | None = None
    os2: dict[str, int | str | dict[str, int]] | None = None


@dataclass(frozen=True)
class HeadConfig:
    mac_style: int | None = None
    units_per_em: int | None = None


@dataclass(frozen=True)
class PostConfig:
    format: int | float | None = None


@dataclass(frozen=True)
class TablesConfig:
    drop: DropConfig = field(default_factory=DropConfig)
    cmap: CmapConfig = field(default_factory=CmapConfig)
    metrics: MetricsConfig | None = None
    head: HeadConfig | None = None
    post: PostConfig | None = None


@dataclass(frozen=True)
class GsubConfig:
    enabled: bool = False
    sequence_files: tuple[Path, ...] = ()
    project_sequence_files: tuple[Path, ...] = ()
    replace_morx: bool = False


@dataclass(frozen=True)
class ShapingConfig:
    gsub: GsubConfig | None = None


@dataclass(frozen=True)
class SplitConfig:
    enabled: bool = False
    chunk_kb: int = 500
    write_css: bool = False


@dataclass(frozen=True)
class BuildRecipe:
    names: NamesConfig
    bitmap: BitmapConfig
    tables: TablesConfig = field(default_factory=TablesConfig)
    shaping: ShapingConfig | None = None
    split: SplitConfig | None = None
