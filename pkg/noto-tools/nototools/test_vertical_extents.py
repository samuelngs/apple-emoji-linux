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

"""Tests vertical extents of fonts for fitting in specified boundaries.

Usage:
test_vertical_extents.py font.ttf [language [ymin ymax]] < sample_text.[txt|xtb]

specifying the language is useful when language-specific features are
supported in the font, like in the case of Marathi, Persian, and Urdu.

Typically, ymin and ymax shouldn't be specified. If not specified, they will
be checked according to Noto specs.

For fonts that don't have UI in their files name but should be tested
according to UI specs, ymin and ymax should be specified on the command line.
"""

__author__ = 'roozbeh@google.com (Roozbeh Pournader)'

import itertools
import os
import re
import sys
import xml.etree.ElementTree

import coverage
import font_caching
import render


def _regular_expression_from_set(character_set):
    """Returns a regexp matching any sequence of a set of input characters.
    """
    character_set -= set(range(0x00, 0x20))  # Remove ASCII controls

    literal_list = []
    for code in character_set:
        char = unichr(code)
        if char in ['\\', '[', ']', '^', '-']:
            char = '\\' + char
        literal_list.append(char)
    regexp = '[' + ''.join(literal_list) + ']+'
    return re.compile(regexp)


def test_rendering(
    data, font_file_name, min_allowed, max_allowed, language=None):
    """Test the rendering of the input data in a given font.
    
    The input data is first filtered for sequences supported in the font.
    """
    font_characters = coverage.character_set(font_file_name)
    # Hack to add ASCII digits, even if the font doesn't have them,
    # to keep potential frequency info in the input intact
    font_characters |= set(range(ord('0'), ord('9')+1))

    supported_chars_regex = _regular_expression_from_set(font_characters)

    harfbuzz_input = []
    for match in supported_chars_regex.finditer(data):
        harfbuzz_input.append(match.group(0))

    harfbuzz_input = '\n'.join(harfbuzz_input)

    return render.test_text_vertical_extents(
        harfbuzz_input, font_file_name, min_allowed, max_allowed, language)


def test_rendering_from_file(
    file_handle, font_file_name, min_allowed, max_allowed, language=None):
    """Test the rendering of the contents of a file for vertical extents.
    
    Supports both text files and XTB files.
    """

    input_data = file_handle.read()

    if input_data.startswith('<?xml'):
        # XML mode, assume .xtb file
        root = xml.etree.ElementTree.fromstring(input_data)
        assert root.tag == 'translationbundle'

        test_strings = []
        for child in root:
            if child.text is not None:
                test_strings.append(child.text)
        input_data = '\n'.join(test_strings)

    else:
        # Assume text file, with all the data as one large string
        input_data = unicode(input_data, 'UTF-8')

    # Now, input_data is just a long string, with new lines as separators.

    return test_rendering(
        input_data, font_file_name, min_allowed, max_allowed, language)


def test_all_combinations(
    max_len, font_file_name, min_allowed, max_allowed, language=None):
    """Tests the rendering of all combinations up to certain length."""

    font_characters = coverage.character_set(font_file_name)
    font_characters -= set(range(0x00, 0x20))  # Remove ASCII controls
    font_characters = [unichr(code) for code in font_characters]
    font_characters = sorted(font_characters)

    all_strings = []
    for length in range(1, max_len+1):
        all_combinations = itertools.product(font_characters, repeat=length)
        all_strings += [''.join(comb) for comb in all_combinations]

    test_data = '\n'.join(all_strings)
    return test_rendering(
        test_data, font_file_name, min_allowed, max_allowed, language)


def _is_noto_ui_font(font_file_name):
    """Returns true if a font file is a Noto UI font."""
    base_name = os.path.basename(font_file_name)
    return base_name.startswith('Noto') and 'UI-' in base_name


def main(argv):
    """Test vertical extents to make sure they stay within specified bounds."""
    font_file_name = argv[1]

    if len(argv) > 2:
        language = argv[2]
    else:
        language = None

    if len(argv) > 4:
        ymin = int(argv[3])
        ymax = int(argv[4])
    else:
        font = font_caching.open_font(font_file_name)
        ymin = -font['OS/2'].usWinDescent
        ymax = font['OS/2'].usWinAscent
        if _is_noto_ui_font(font_file_name):
            ymin = max(ymin, -555)
            ymax = min(ymax, 2163)

    exceeding_lines = test_rendering_from_file(
        sys.stdin, font_file_name, ymin, ymax, language)

    for line_bounds, text_piece in exceeding_lines:
        print text_piece.encode('UTF-8'), line_bounds

    # print test_all_combinations(3, font_file_name, ymin, ymax)


if __name__ == '__main__':
    main(sys.argv)
