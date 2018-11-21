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

"""Create a curated subset of NotoSansSymbols."""

__author__ = 'roozbeh@google.com (Roozbeh Pournader)'

import sys

import subset


def main(argv):
    """Subset the Noto Symbols font which is given as the argument."""
    source_file_name = argv[1]

    target_coverage = {
        0x20BA,  # TURKISH LIRA SIGN
        0x20BC,  # MANAT SIGN
        0x20BD,  # RUBLE SIGN
        0x22EE,  # VERTICAL ELLIPSIS
        0x25AB,  # WHITE SMALL SQUARE
        0x25FB,  # WHITE MEDIUM SQUARE
        0x25FC,  # BLACK MEDIUM SQUARE
        0x25FD,  # WHITE MEDIUM SMALL SQUARE
        0x25FE,  # BLACK MEDIUM SMALL SQUARE
        0x2600,  # BLACK SUN WITH RAYS
        0x266B,  # BEAMED EIGHTH NOTES
        0x26AA,  # MEDIUM WHITE CIRCLE
        0x26AB,  # MEDIUM BLACK CIRCLE
        0x2757,  # HEAVY EXCLAMATION MARK SYMBOL
        0x2934,  # ARROW POINTING RIGHTWARDS THEN CURVING UPWARDS
        0x2935,  # ARROW POINTING RIGHTWARDS THEN CURVING DOWNWARDS
        0x2B05,  # LEFTWARDS BLACK ARROW
        0x2B06,  # UPWARDS BLACK ARROW
        0x2B07,  # DOWNWARDS BLACK ARROW
        0x2B1B,  # BLACK LARGE SQUARE
        0x2B1C,  # WHITE LARGE SQUARE
        0x2B50,  # WHITE MEDIUM STAR
        0x2B55,  # HEAVY LARGE CIRCLE
    }
    target_coverage.update(range(0x2800, 0x28FF+1))  # Braille symbols

    subset.subset_font(
        source_file_name,
        'NotoSansSymbols-Regular-Subsetted.ttf',
        include=target_coverage)


if __name__ == '__main__':
    main(sys.argv)
