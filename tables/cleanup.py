from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fontTools.ttLib import TTFont

LOG = logging.getLogger(__name__)


def drop_dsig(font: TTFont) -> None:
    """Remove stale digital signatures after table rewrites."""
    if "DSIG" in font:
        del font["DSIG"]
        LOG.debug("Dropped DSIG table")


def drop_tables(font: TTFont, tags: tuple[str, ...] | list[str]) -> None:
    for tag in tags:
        if tag in font:
            del font[tag]
            LOG.info("Dropped table: %s", tag)

