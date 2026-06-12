from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from config import MetricsConfig
from tables.cbdt_cblc import FontMetrics

if TYPE_CHECKING:
    from fontTools.ttLib import TTFont

LOG = logging.getLogger(__name__)


def apply_metrics_policy(
    font: TTFont,
    config: MetricsConfig | None,
    metrics: FontMetrics,
) -> None:
    if config is None:
        return
    apply_explicit_metrics(font, config)
    if config.policy == "browser_safe":
        update_os2_browser_safe(font, metrics)
    if config.fs_type == "installable":
        set_installable_embedding(font)
    elif config.fs_type == "editable":
        set_editable_embedding(font)
    if config.unicode_ranges == "emoji":
        set_emoji_unicode_ranges(font)


def apply_explicit_metrics(
    font: TTFont,
    config: MetricsConfig,
) -> None:
    scale = 1.0
    if config.hhea:
        _apply_explicit_hhea(font, config.hhea, scale)
    if config.os2:
        _apply_explicit_os2(font, config.os2, scale)


_OS2_ATTRS = {
    "version": "version",
    "x_avg_char_width": "xAvgCharWidth",
    "us_weight_class": "usWeightClass",
    "us_width_class": "usWidthClass",
    "fs_type": "fsType",
    "y_subscript_x_size": "ySubscriptXSize",
    "y_subscript_y_size": "ySubscriptYSize",
    "y_subscript_x_offset": "ySubscriptXOffset",
    "y_subscript_y_offset": "ySubscriptYOffset",
    "y_superscript_x_size": "ySuperscriptXSize",
    "y_superscript_y_size": "ySuperscriptYSize",
    "y_superscript_x_offset": "ySuperscriptXOffset",
    "y_superscript_y_offset": "ySuperscriptYOffset",
    "y_strikeout_size": "yStrikeoutSize",
    "y_strikeout_position": "yStrikeoutPosition",
    "s_family_class": "sFamilyClass",
    "s_typo_ascender": "sTypoAscender",
    "s_typo_descender": "sTypoDescender",
    "s_typo_line_gap": "sTypoLineGap",
    "us_win_ascent": "usWinAscent",
    "us_win_descent": "usWinDescent",
    "fs_selection": "fsSelection",
    "us_first_char_index": "usFirstCharIndex",
    "us_last_char_index": "usLastCharIndex",
    "s_cap_height": "sCapHeight",
    "sx_height": "sxHeight",
    "us_max_context": "usMaxContext",
    "unicode_range_1": "ulUnicodeRange1",
    "unicode_range_2": "ulUnicodeRange2",
    "unicode_range_3": "ulUnicodeRange3",
    "unicode_range_4": "ulUnicodeRange4",
    "code_page_range_1": "ulCodePageRange1",
    "code_page_range_2": "ulCodePageRange2",
    "vendor_id": "achVendID",
}

_SCALED_OS2_FIELDS = {
    "x_avg_char_width",
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
    "s_typo_ascender",
    "s_typo_descender",
    "s_typo_line_gap",
    "us_win_ascent",
    "us_win_descent",
    "s_cap_height",
    "sx_height",
}


def _apply_explicit_hhea(font: TTFont, values: dict[str, int], scale: float) -> None:
    if "hhea" not in font:
        return
    hhea = font["hhea"]
    if "ascent" in values:
        hhea.ascent = _scale_signed(values["ascent"], scale)
    if "descent" in values:
        hhea.descent = _scale_signed(values["descent"], scale)
    if "line_gap" in values:
        hhea.lineGap = _scale_signed(values["line_gap"], scale)


def _apply_explicit_os2(
    font: TTFont,
    values: dict[str, int | str | dict[str, int]],
    scale: float,
) -> None:
    if "OS/2" not in font:
        return
    os2 = font["OS/2"]
    for key, value in values.items():
        if key == "panose":
            _apply_explicit_panose(font, value)
            continue
        attr = _OS2_ATTRS[key]
        if key in _SCALED_OS2_FIELDS and isinstance(value, int):
            setattr(os2, attr, _scale_signed(value, scale))
        else:
            setattr(os2, attr, value)


def _apply_explicit_panose(font: TTFont, values) -> None:
    if "OS/2" not in font:
        return
    panose = font["OS/2"].panose
    attrs = {
        "family_type": "bFamilyType",
        "serif_style": "bSerifStyle",
        "weight": "bWeight",
        "proportion": "bProportion",
        "contrast": "bContrast",
        "stroke_variation": "bStrokeVariation",
        "arm_style": "bArmStyle",
        "letter_form": "bLetterForm",
        "midline": "bMidline",
        "x_height": "bXHeight",
    }
    for key, attr in attrs.items():
        if key in values:
            setattr(panose, attr, values[key])


def update_os2_browser_safe(font: TTFont, metrics: FontMetrics) -> None:
    """Fix browser clipping and embedding fields without changing naming policy."""
    if "OS/2" not in font:
        return
    os2 = font["OS/2"]
    if os2.usWinAscent == 0:
        os2.usWinAscent = metrics.ascent
        LOG.info("Fixed OS/2 usWinAscent: %d", os2.usWinAscent)
    if os2.usWinDescent == 0:
        os2.usWinDescent = metrics.descent
        LOG.info("Fixed OS/2 usWinDescent: %d", os2.usWinDescent)


def set_installable_embedding(font: TTFont) -> None:
    if "OS/2" in font and font["OS/2"].fsType != 0:
        font["OS/2"].fsType = 0
        LOG.info("Fixed OS/2 fsType to 0 (Installable)")


def set_editable_embedding(font: TTFont) -> None:
    if "OS/2" in font and font["OS/2"].fsType != 8:
        font["OS/2"].fsType = 8
        LOG.info("Set OS/2 fsType to 8 (Editable embedding)")


def set_emoji_unicode_ranges(font: TTFont) -> None:
    if "OS/2" not in font:
        return
    os2 = font["OS/2"]
    os2.ulUnicodeRange1 = 0x00000001 | (1 << 25)
    os2.ulUnicodeRange2 = (1 << (57 - 32)) | (1 << (58 - 32)) | (1 << (59 - 32))
    os2.ulUnicodeRange3 = 0
    os2.ulUnicodeRange4 = 0


def _scale_signed(value: int, scale: float) -> int:
    return int(round(value * scale))
