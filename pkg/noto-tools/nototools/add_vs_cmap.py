#!/usr/bin/env python
#
# Copyright 2015 Google Inc. All rights reserved.
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

"""Modify an Emoji font to populate cmap 14 variation selector subtable.

This uses the unicode variation selector data, finds all characters in the
standard cmap that match, and generates a cmap format 14 subtable indicating
that they have the provided presentation (emoji by default).  No fonts
are processed if any already has a format 14 subtable.  Modified fonts
are written to the provided dir and optionally have a provided suffix
appended (before the extension).  An output file name can be provided
in which case only one input file is allowed."""

import argparse
import os
from os import path
import re
import sys

from fontTools import ttLib
from fontTools.ttLib.tables import _c_m_a_p

from nototools import font_data
from nototools import unicode_data
from nototools import tool_utils

VS_TEXT = 0xFE0E
VS_EMOJI = 0xFE0F

def modify_font(font_name, font, presentation, emoji_variants):
  cmap_table = font_data.get_cmap(font)
  emoji = set(cmap_table.keys()) & emoji_variants
  if not emoji:
    print 'no emoji match those in %s' % font_name
    return
  uvs = VS_EMOJI if presentation == 'emoji' else VS_TEXT
  cmap14 = _c_m_a_p.CmapSubtable.newSubtable(14)
  cmap14.cmap = {}
  cmap14.uvsDict = {uvs: [[c, None] for c in sorted(emoji)]}
  cmap14.platformID = 0
  cmap14.platEncID = 5
  cmap14.language = 0xFF # what fontTools would have used
  font['cmap'].tables.append(cmap14)


def modify_fonts(font_names, presentation='emoji', output=None, suffix=None,
                 dst_dir=None, vs_added=None):
  assert dst_dir
  if output:
    assert len(font_names) == 1

  for font_name in font_names:
    font = ttLib.TTFont(font_name)
    if font_data.get_variation_sequence_cmap(font):
      # process no font if any already has a var selector cmap
      raise ValueError('font %s already has a format 14 cmap' % font_name)

  if not path.exists(dst_dir):
    os.makedirs(dst_dir)

  emoji_variants = unicode_data.get_unicode_emoji_variants()
  if vs_added:
    emoji_variants = emoji_variants | vs_added

  for font_name in font_names:
    font = ttLib.TTFont(font_name)
    modify_font(font_name, font, presentation, emoji_variants)
    if output:
      new_name = output
    else:
      new_name = path.basename(font_name)
      if suffix:
        name, ext = path.splitext(new_name)
        new_name = name + suffix + ext
    font.save(path.join(dst_dir, new_name))


def main():
  parser = argparse.ArgumentParser()
  parser.add_argument(
      '-d', '--dstdir',
      help='destination directory for modified files, default /tmp/vs',
      metavar = 'dir',
      default='/tmp/vs')
  parser.add_argument(
      '-p', '--presentation',
      help='presentation of glyphs in the font, default "emoji"',
      choices=['emoji', 'text'],
      default='emoji')
  parser.add_argument(
      '-s', '--suffix',
      metavar='suffix',
      help='suffix to add to file names for output, goes before extension')
  parser.add_argument(
      '-o', '--output',
      metavar='filename',
      help='output file name, requires only one input file')
  parser.add_argument(
      '-vs', '--vs_added',
      help='extra ranges to treat as having the requested presentation',
      metavar='range', nargs='+')
  parser.add_argument(
      'files',
      help='files to modify',
      metavar='file',
      nargs='+')

  # argparse fails with named arguments that have leading hyphen.  You
  # can work around this by using a short arg and concatenating it and
  # the argument together, e.g. '-s-foo'.
  # Both parse_known_args and inserting '--' between the key and its
  # value fail, though.
  args = parser.parse_args()
  vs_set = None
  if args.vs_added:
    vs_set = tool_utils.parse_int_ranges(' '.join(args.vs_added))

  modify_fonts(args.files, presentation=args.presentation, output=args.output,
               suffix=args.suffix, dst_dir=args.dstdir, vs_added=vs_set)

if __name__ == '__main__':
  main()
