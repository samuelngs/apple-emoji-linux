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

"""Quick summary of ttf files in noto file tree"""

__author__ = "dougfelt@google.com (Doug Felt)"

import argparse
import os
import os.path
import re
import sys

from fontTools import ttLib

import noto_lint
import font_data

def get_largest_cmap(font):
  cmap_table = font['cmap']
  cmap = None
  for table in cmap_table.tables:
    tup = (table.format, table.platformID, table.platEncID)
    if tup == (4, 3, 1):
      # Continue scan because we prefer the other cmap if it exists.
      cmap = table.cmap
    elif tup == (12, 3, 10):
      # Stop scan if we find this cmap. Should be strictly larger than the other.
      cmap = table.cmap
      break
  return cmap

def cmap_count(font):
  return len(get_largest_cmap(font))

def summarize_file(root, path):
  font = ttLib.TTFont(path)
  table_info = {}
  reader = font.reader
  for tag in reader.keys():
    entry = reader.tables[tag]
    entry_len = entry.length
    entry_checkSum = int(entry.checkSum)
    if entry_checkSum < 0:
      entry_checkSum += 0x100000000
    table_info[tag] = (entry_len, entry_checkSum)

  relpath = path[len(root) + 1:]
  size = os.path.getsize(path)
  # Printable_font_revision requires you specify the accuracy of digits.
  # ttLib apparently reads the fixed values as a float, so it loses the info.
  # Adobe fonts use 3 digits, so the default from printable_font_revision of 2
  # is insufficient.
  # Assume that the name from the name table is accurate, and use it instead.
  version_string = noto_lint.font_version(font);
  match = re.match(r'Version (\d+\.\d+)', version_string)
  if match:
    version = match.group(1)
  else:
    version = noto_lint.printable_font_revision(font) # default 2
  num_glyphs = len(font.getGlyphOrder())
  full_name = font_data.get_name_records(font)[4]
  cmap = set(get_largest_cmap(font).keys()) # copy needed? what's the lifespan?
  num_chars = len(cmap)
  font.close()

  return (relpath, version, full_name, size, num_glyphs, num_chars, cmap, table_info)

def summarize(root, name=None):
  result = []
  name_re = re.compile(name) if name else None
  for parent, _, files in os.walk(root):
    for f in sorted(files):
      if f.endswith('.ttf') or f.endswith('.otf'):
        path = os.path.join(parent, f)
        if name_re:
          relpath = path[len(root) + 1:]
          if not name_re.search(relpath):
            continue
        result.append(summarize_file(root, path))
  return result


def print_tup(tup, short):
  def to_str(idx, val):
    if idx == 7 and type(val) == type({}):
      parts = []
      for tag in sorted(val):
        parts.append('%s=%s' % (tag, val[tag][0]))
      result = ', '.join(parts)
    else:
      if idx == 6 and type(val) == type(set()):
        result = noto_lint.printable_unicode_range(val)
      else:
        result = str(val)
    if ' ' in result:
      result = '"%s"' % result
    return result

  line = [to_str(idx, val) for idx, val in enumerate(tup)
          if not (short and (idx == 3 or idx == 6 or idx == 7))]
  print '\t'.join(line)

def print_summary(summary_list, short):
  labels = ('path', 'version', 'name', 'size', 'num_glyphs', 'num_chars', 'cmap', 'table_info')
  print_tup(labels, short)
  for tup in summary_list:
    print_tup(tup, short)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('root', help='root of directory tree')
    parser.add_argument('--name', help='only report files where name regex matches '
                        'some portion of the path under root'),
    parser.add_argument('-s', '--short', help='shorter summary format',
                        action='store_true')
    args = parser.parse_args()

    if not os.path.isdir(args.root):
      print '%s does not exist or is not a directory' % args.root
    else:
      root = os.path.abspath(args.root)
      print "root: %s, name: %s" % (root, args.name if args.name else '[all]')
      print_summary(summarize(root, name=args.name), args.short)

if __name__ == "__main__":
    main()
