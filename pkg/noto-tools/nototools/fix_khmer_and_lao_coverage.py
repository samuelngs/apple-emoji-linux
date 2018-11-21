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

"""Fix Khmer and Lao fonts for better coverage."""

__author__ = "roozbeh@google.com (Roozbeh Pournader)"

import os
import sys

from fontTools import ttLib

from nototools import coverage
from nototools import font_data
from nototools import opentype_data


def merge_chars_from_bank(orig_font, bank_font, target_font, chars):
    """Merge glyphs from a bank font to another font.
    
    Only the glyphs themselves, the horizontal metrics, and the cmaps will be
    copied.
    """
    bank_font = ttLib.TTFont(bank_font)
    orig_font = ttLib.TTFont(orig_font)

    bank_cmap = font_data.get_cmap(bank_font)
    extra_cmap = {}
    for char in sorted(chars):
        assert char in bank_cmap
        bank_glyph_name = bank_cmap[char]
        assert bank_glyph_name not in orig_font['glyf'].glyphs
        orig_font['glyf'][bank_glyph_name] = bank_font['glyf'][bank_glyph_name]
        orig_font['hmtx'][bank_glyph_name] = bank_font['hmtx'][bank_glyph_name]
        extra_cmap[char] = bank_glyph_name
    font_data.add_to_cmap(orig_font, extra_cmap)
    orig_font.save(target_font)


_UNHINTED_FONTS_DIR = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        os.pardir,
       'fonts',
       'individual',
       'unhinted'))


def main(argv):
    """Fix all the fonts given in the command line.
    
    If they are Lao fonts, make sure they have ZWSP and dotted circle. If they
    are Khmer fonts, make sure they have ZWSP, joiners, and dotted circle."""

    for font_name in argv[1:]:
        if 'Khmer' in font_name:
            script = 'Khmr'
        elif 'Lao' in font_name:
            script = 'Laoo'
        needed_chars = set(opentype_data.SPECIAL_CHARACTERS_NEEDED[script])

        lgc_font_name = (
            os.path.basename(font_name).replace('Khmer', '').replace('Lao', ''))
        lgc_font_name = os.path.join(_UNHINTED_FONTS_DIR, lgc_font_name)

        font_charset = coverage.character_set(font_name)
        missing_chars = needed_chars - font_charset
        if missing_chars:
            merge_chars_from_bank(
                font_name,
                lgc_font_name,
                os.path.dirname(font_name)+'/new/'+os.path.basename(font_name),
                missing_chars)


if __name__ == '__main__':
    main(sys.argv)
