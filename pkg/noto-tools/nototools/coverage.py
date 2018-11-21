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
"""Routines for character coverage of fonts."""

__author__ = 'roozbeh@google.com (Roozbeh Pournader)'

import argparse
import codecs
import os
from os import path
import re
import sys
import unicode_data

from nototools import lint_config

from fontTools import ttLib


def character_set(font):
  """Returns the character coverage of a font.

  Args:
    font: The input font's file name, or a TTFont.

  Returns:
    A frozenset listing the characters supported in the font.
  """
  if type(font) is str:
    font = ttLib.TTFont(font, fontNumber=0)
  cmap_table = font['cmap']
  cmaps = {}
  for table in cmap_table.tables:
    if (table.format, table.platformID, table.platEncID) in [
        (4, 3, 1), (12, 3, 10)
    ]:
      cmaps[table.format] = table.cmap
  if 12 in cmaps:
    cmap = cmaps[12]
  elif 4 in cmaps:
    cmap = cmaps[4]
  else:
    cmap = {}
  return frozenset(cmap.keys())


def convert_set_to_ranges(charset):
  """Converts a set of characters to a list of ranges."""
  working_set = set(charset)
  output_list = []
  while working_set:
    start = min(working_set)
    end = start + 1
    while end in working_set:
      end += 1
    output_list.append((start, end - 1))
    working_set.difference_update(range(start, end))
  return output_list


def _print_char_info(chars):
  for char in chars:
    try:
      name = unicode_data.name(char)
    except ValueError:
      name = '<Unassigned>'
    print 'U+%04X %s' % (char, name)


def _write_char_text(chars, filepath, chars_per_line, sep):
  def accept_cp(cp):
    cat = unicode_data.category(cp)
    return cat[0] not in ['M', 'C', 'Z'] or cat == 'Co'

  text = [unichr(cp) for cp in chars if accept_cp(cp)]
  filename, _ = path.splitext(path.basename(filepath))
  m = re.match(r'(.*)-(?:Regular|Bold|Italic|BoldItalic)', filename)
  if m:
    filename = m.group(1)
  filename += '_chars.txt'
  print 'writing file: %s' % filename
  print '%d characters (of %d)' % (len(text), len(chars))
  if chars_per_line > 0:
    lines = []
    for n in range(0, len(text), chars_per_line):
      substr = text[n:n + chars_per_line]
      lines.append(sep.join(cp for cp in substr))
    text = '\n'.join(lines)
  with codecs.open(filename, 'w', 'utf-8') as f:
    f.write(text)


def _process_font(filepath, args):
  char_set = character_set(filepath)
  if args.limit_set:
    char_set = char_set & args.limit_set
    if not char_set:
      print 'limit excludes all chars in %s' % filepath
      return
  sorted_chars = sorted(char_set)
  if args.info:
    _print_char_info(sorted_chars)
  if args.text:
    _write_char_text(sorted_chars, filepath, args.chars_per_line, args.sep)
  if args.ranges:
    print 'ranges:\n  ' + lint_config.write_int_ranges(sorted_chars, True)


def main():
  parser = argparse.ArgumentParser()
  parser.add_argument('files', help='Files to dump', metavar='file', nargs='+')
  parser.add_argument('--ranges',
                      help='Dump cmap as hex ranges',
                      action='store_true')
  parser.add_argument('--text',
                      help='Dump cmap as sample text',
                      action='store_true')
  parser.add_argument('--sep',
                      help='Separator between chars in text, default space',
                      default=' ')
  parser.add_argument('--info',
                      help='Dump cmap as cp and unicode name, one per line',
                      action='store_true')
  parser.add_argument('--chars_per_line',
                      help='Format text in lines of at most this '
                      'many codepoints,  0 to format as a single line',
                      type=int,
                      metavar='N',
                      default=32)
  parser.add_argument('--limit',
                      help='string of hex codepoint ranges limiting cmap '
                      'to output',
                      metavar='ranges')
  args = parser.parse_args()

  if not (args.ranges or args.text or args.info):
    args.info = True

  if args.limit:
    args.limit_set = lint_config.parse_int_ranges(args.limit)
    print 'limit to: ' + lint_config.write_int_ranges(args.limit_set)
  else:
    # make sure it exists so checks don't have to care
    args.limit_set = None

  for fontpath in args.files:
    print 'Font: ' + path.normpath(fontpath)
    _process_font(fontpath, args)


if __name__ == '__main__':
  main()
