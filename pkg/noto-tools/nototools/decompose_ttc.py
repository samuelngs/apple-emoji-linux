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

"""Decompose a TTC file to its pieces."""

__author__ = 'roozbeh@google.com (Roozbeh Pournader)'

import sys

from fontTools import ttLib
from fontTools.ttLib import sfnt


def main(argv):
    """Decompose all fonts provided in the command line."""
    for font_file_name in argv[1:]:
        with open(font_file_name, 'rb') as font_file:
            font = sfnt.SFNTReader(font_file, fontNumber=0)
            num_fonts = font.numFonts
        for font_number in range(num_fonts):
            font = ttLib.TTFont(font_file_name, fontNumber=font_number)
            font.save('%s-part%d' % (font_file_name, font_number))

if __name__ == '__main__':
    main(sys.argv)

