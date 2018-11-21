#!/usr/bin/env python
#
# Copyright 2016 Google Inc. All rights reserved.
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

"""Display characters that are missing coverage.

Based on unicode 9 and the _OMITTED ranges in cmap_block_coverage.py."""

import argparse

from nototools import cmap_block_coverage
from nototools import cmap_data
from nototools import tool_utils
from nototools import unicode_data


def _covered_cps(cmap_file):
  all_cps = set()
  tree = cmap_data.read_cmap_data_file(cmap_file)
  for rowdata in tree.table.rows:
    if rowdata.script == 'EXCL':
      continue
    cps = tool_utils.parse_int_ranges(rowdata.ranges)
    all_cps |= cps
  return all_cps


def show_cps_by_block(cps):
  print '%d missing codepoints' % len(cps)
  block = None
  for cp in sorted(cps):
    new_block = unicode_data.block(cp)
    if new_block != block:
      print '# %s' % new_block
      block = new_block
    print '%5s %s' % ('%04x' % cp, unicode_data.name(cp))


def display_missing(cmap_file):
  print 'Checking data in %s' % cmap_file
  filename = tool_utils.resolve_path(cmap_file)
  cps = _covered_cps(filename)
  defined_cps = unicode_data.defined_characters(version=9.0)
  omitted = cmap_block_coverage._OMITTED
  expected_cps = defined_cps - omitted
  missing_cps = expected_cps - cps
  show_cps_by_block(missing_cps)


def main():
  default_cmap_name = 'noto_cmap_phase3.xml'

  parser = argparse.ArgumentParser()
  parser.add_argument(
      '-f', '--filename', help='cmap data file (default %s)' %
      default_cmap_name, default=default_cmap_name,  metavar='file')
  args = parser.parse_args()

  display_missing(args.filename)

if __name__ == '__main__':
  main()
