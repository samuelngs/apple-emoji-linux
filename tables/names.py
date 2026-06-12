from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from config import NamesConfig

if TYPE_CHECKING:
    from fontTools.ttLib import TTFont

LOG = logging.getLogger(__name__)

SEGOE_UI_EMOJI_NAME_RECORDS: tuple[tuple[int, int, int, int, str], ...] = (
    (0, 1, 0, 0, "© 2025 Microsoft Corporation. All Rights Reserved."),
    (1, 1, 0, 0, "Segoe UI Emoji"),
    (2, 1, 0, 0, "Regular"),
    (3, 1, 0, 0, "Segoe UI Emoji"),
    (4, 1, 0, 0, "Segoe UI Emoji"),
    (5, 1, 0, 0, "Version 1.60"),
    (6, 1, 0, 0, "SegoeUIEmoji"),
    (7, 1, 0, 0, "Segoe is a trademark of the Microsoft group of companies."),
    (8, 1, 0, 0, "Microsoft Corporation"),
    (11, 1, 0, 0, "http://www.microsoft.com/typography/fonts/"),
    (
        13,
        1,
        0,
        0,
        "Microsoft supplied font. You may use this font to create, display and "
        "print content as permitted by the license terms, or terms of use, of "
        "the Microsoft product, service or content in which this font was "
        "included. You may only (i) embed this font in content as permitted by "
        "the embedding restrictions included in this font; and (ii) temporarily "
        "download this font to a printer or other output device to help print "
        "content. Any other use is prohibited.",
    ),
    (14, 1, 0, 0, "http://www.microsoft.com/typography/fonts/"),
    (2, 3, 1, 1027, "Normal"),
    (2, 3, 1, 1029, "obyčejné"),
    (2, 3, 1, 1030, "Normal"),
    (2, 3, 1, 1031, "Standard"),
    (2, 3, 1, 1032, "Κανονικά"),
    (0, 3, 1, 1033, "© 2025 Microsoft Corporation. All Rights Reserved."),
    (1, 3, 1, 1033, "Segoe UI Emoji"),
    (2, 3, 1, 1033, "Regular"),
    (3, 3, 1, 1033, "Segoe UI Emoji"),
    (4, 3, 1, 1033, "Segoe UI Emoji"),
    (5, 3, 1, 1033, "Version 1.60"),
    (6, 3, 1, 1033, "SegoeUIEmoji"),
    (7, 3, 1, 1033, "Segoe is a trademark of the Microsoft group of companies."),
    (8, 3, 1, 1033, "Microsoft Corporation"),
    (11, 3, 1, 1033, "http://www.microsoft.com/typography/fonts/"),
    (
        13,
        3,
        1,
        1033,
        "Microsoft supplied font. You may use this font to create, display and "
        "print content as permitted by the license terms, or terms of use, of "
        "the Microsoft product, service or content in which this font was "
        "included. You may only (i) embed this font in content as permitted by "
        "the embedding restrictions included in this font; and (ii) temporarily "
        "download this font to a printer or other output device to help print "
        "content. Any other use is prohibited.",
    ),
    (14, 3, 1, 1033, "http://www.microsoft.com/typography/fonts/"),
    (19, 3, 1, 1033, "😂😍😭💁👍💋🐱🦉🌺🌲🍓🍕🎂🏰🏠🚄🚒🛫🛍"),
    (2, 3, 1, 1034, "Normal"),
    (2, 3, 1, 1035, "Normaali"),
    (2, 3, 1, 1036, "Normal"),
    (2, 3, 1, 1038, "Normál"),
    (2, 3, 1, 1040, "Normale"),
    (2, 3, 1, 1043, "Standaard"),
    (2, 3, 1, 1044, "Normal"),
    (2, 3, 1, 1045, "Normalny"),
    (2, 3, 1, 1046, "Normal"),
    (2, 3, 1, 1049, "Обычный"),
    (2, 3, 1, 1051, "Normálne"),
    (2, 3, 1, 1053, "Normal"),
    (2, 3, 1, 1055, "Normal"),
    (2, 3, 1, 1060, "Navadno"),
    (2, 3, 1, 1069, "Arrunta"),
    (2, 3, 1, 2058, "Normal"),
    (2, 3, 1, 2070, "Normal"),
    (2, 3, 1, 3082, "Normal"),
    (2, 3, 1, 3084, "Normal"),
)


def apply_names_policy(font: TTFont, config: NamesConfig) -> None:
    if config.records:
        update_font_names_from_records(font, config.records)
    elif config.family:
        update_font_family(font, config.family)


def update_font_family(font: TTFont, family: str) -> None:
    postscript = "".join(ch for ch in family if not ch.isspace())
    name_table = font["name"]
    for rec in name_table.names:
        if rec.nameID in {1, 4, 16, 21}:
            rec.string = family
        elif rec.nameID in {2, 17, 22}:
            rec.string = "Regular"
        elif rec.nameID == 6:
            rec.string = postscript
    LOG.debug("Updated family name records to %s", family)

def update_font_names_from_records(font: TTFont, records) -> None:
    name_table = font["name"]
    name_table.names = []

    for record in records:
        if hasattr(record, "name_id"):
            name_id = record.name_id
            platform_id = record.platform_id
            plat_enc_id = record.platform_encoding_id
            lang_id = record.language_id
            value = record.value
        else:
            name_id, platform_id, plat_enc_id, lang_id, value = record
        name_table.setName(value, name_id, platform_id, plat_enc_id, lang_id)

    LOG.debug("Updated name table from explicit records")
