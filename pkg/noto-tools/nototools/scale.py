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

"""Routines for scaling a font."""

__author__ = 'roozbeh@google.com (Roozbeh Pournader)'

import sys

from fontTools import ttLib

def scale_font(font, factor):
    """Scales a font by a factor like 0.95 to make it 5% smaller."""
    head_table = font['head']
    head_table.unitsPerEm = int(round(head_table.unitsPerEm/float(factor)))

def main(argv):
    font = ttLib.TTFont(argv[2])
    scale_font(font, float(argv[1]))
    font.save(argv[3])

if __name__ == "__main__":
    main(sys.argv)

