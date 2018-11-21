#!/usr/bin/env python
#
# Copyright 2014 Google Inc. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Drop hints from a font."""

__author__ = 'roozbeh@google.com (Roozbeh Pournader)'

import array
import sys

from fontTools import ttLib


def drop_hints_from_glyphs(font):
    """Drops the hints from a font's glyphs."""
    glyf_table = font['glyf']
    for glyph_index in range(len(glyf_table.glyphOrder)):
        glyph_name = glyf_table.glyphOrder[glyph_index]
        glyph = glyf_table[glyph_name]
        if glyph.numberOfContours > 0:
            if glyph.program.bytecode:
                glyph.program.bytecode = array.array('B')


def drop_tables(font, tables):
    """Drops the listed tables from a font."""
    for table in tables:
        if table in font:
            del font[table]


def main(argv):
    """Drop the hints from the first file specified and save as second."""
    font = ttLib.TTFont(argv[1])

    drop_hints_from_glyphs(font)
    drop_tables(font, ['cvt ', 'fpgm', 'hdmx', 'LTSH', 'prep', 'VDMX'])

    font.save(argv[2])


if __name__ == '__main__':
    main(sys.argv)
