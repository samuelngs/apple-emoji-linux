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

"""Display unicode coverage of a set of cmaps."""

import argparse
import collections

from nototools import cmap_data
from nototools import unicode_data
from nototools import tool_utils

_MISSING_SCRIPTS = frozenset(['<MISSING>'])
_OMITTED_SCRIPTS = frozenset(['(omitted)'])
_OMITTED = tool_utils.parse_int_ranges("""
    0001-000c 000e-001f  # C0 controls
    007f-009f  # del and C1 controls
    d800-dfff  # surrogates
    e000-f8ff  # pua
    fe00-fe0f  # variation selectors
    feff  # BOM
    e0000-e007f # tags
    e0100-e01ff # supplementary variation selectors
    f0000-ffffd # supplementary PUA
    # fe000-fe4e4 fe4ef-fe82b fe82d fe838-ffffd  # plane 15 PUA - emoji
    100000-10ffff  # plane 16 pua""")
_LGC_LIST = ['LGC', 'Latn', 'Grek', 'Cyrl']


def _get_scripts(cp, cp_to_scripts):
  scripts = cp_to_scripts.get(cp, None)
  if not scripts:
    scripts = _OMITTED_SCRIPTS if cp in _OMITTED else _MISSING_SCRIPTS
  return scripts


def _script_names(scripts):
    script_list = []
    # sort LGC first
    for lgc in _LGC_LIST:
      if lgc in scripts:
        script_list.append(lgc)
    script_list += [s for s in sorted(scripts) if s not in _LGC_LIST]
    return ', '.join(script_list)


def _create_cp_to_scripts(data, only_scripts=None):
  cp_to_scripts = collections.defaultdict(set)
  all_scripts = set()
  skip_set = frozenset(['Zinh', 'Zyyy', 'Zzzz'])
  cjk_set = frozenset('Bopo,Hang,Hani,Hans,Hant,Hira,Jpan,Kana,Kore'.split(','))
  lgc_set = frozenset('Latn,Grek,Cyrl'.split(','))
  for row in data.table.rows:
    script = row.script
    if only_scripts and script not in only_scripts:
      continue
    if script in skip_set:
      continue
    if script in cjk_set:
      script = 'CJK'
    if script in lgc_set:
      script = 'LGC'
    all_scripts.add(script)
    chars = tool_utils.parse_int_ranges(row.ranges)
    for cp in chars:
      cp_to_scripts[cp].add(script)
  return cp_to_scripts, all_scripts


def _list_details(start_cp, limit_cp, defined_cps, defined_count, details):
  num = 0
  initial_cp = start_cp
  while num < details - 1 and num < defined_count:
    if initial_cp in defined_cps:
      print '%13d %04x %s' % (
          num + 1, initial_cp, unicode_data.name(initial_cp, '(unnamed)'))
      num += 1
    initial_cp += 1
  if num < defined_count:
    final_cp = limit_cp - 1
    final_name = None
    while final_cp >= initial_cp:
      if final_cp in defined_cps:
        final_name = unicode_data.name(final_cp, '(unnamed)')
        num += 1
        break
      final_cp -= 1
    if final_name and num < defined_count:
      middle_cp = final_cp - 1
      while middle_cp >= initial_cp:
        if middle_cp in defined_cps:
          print '%13s' % '...'
          break
        middle_cp -= 1
    if final_name:
      print '%13d %04x %s' % (defined_count, final_cp, final_name)

def _is_empty_scripts(scripts):
  return (not scripts
          or scripts == _MISSING_SCRIPTS
          or scripts == _OMITTED_SCRIPTS)

def _list_range(
    start_cp, limit_cp, defined_cps, defined_count, scripts, all_scripts,
    only_scripts, details):

  if limit_cp != start_cp + 1:
    range_text = '%04x-%04x' % (start_cp, limit_cp - 1)
  else:
    range_text = '%04x' % start_cp

  if not scripts:
    num_scripts = 0
    script_names = '(none)'
  elif _is_empty_scripts(scripts):
    num_scripts = 0
    script_names = iter(scripts).next()
  else:
    num_scripts = len(scripts)
    if scripts == all_scripts and scripts != only_scripts:
      # only use 'all' if we're not limiting scripts
      script_names = '(all)'
    else:
      script_names = _script_names(scripts)
  print '%13s %6d %3s in %3d %7s: %s' % (
      range_text, defined_count, 'cps' if defined_count != 1 else 'cp',
      num_scripts, 'scripts' if num_scripts != 1 else 'script',
      script_names)

  if details > 0:
    _list_details(start_cp, limit_cp, defined_cps, defined_count, details)


def _list_blocks(
    start, limit, defined_cps, cp_to_scripts, all_scripts, only_scripts,
    details):
  start_cp = -1
  defined_count = 0
  block = None
  showed_block = False
  scripts = None
  skip_empty = bool(only_scripts)
  for cp in range(start, limit):
    is_defined = cp in defined_cps
    cp_block = unicode_data.block(cp)
    cp_scripts = _get_scripts(cp, cp_to_scripts) if is_defined else None
    if cp_block != block or (
        cp_scripts and scripts and cp_scripts != scripts):
      if block and block != 'No_Block':
        if not (skip_empty and _is_empty_scripts(scripts)):
          if not showed_block:
            print '...' if block == 'No_Block' else block
            showed_block = True
          _list_range(
              start_cp, cp, defined_cps, defined_count, scripts, all_scripts,
              only_scripts, details)
      start_cp = cp
      defined_count = 0
      if cp_block != block:
        block = cp_block
        showed_block = False
        scripts = None
    if is_defined:
      scripts = cp_scripts
      defined_count += 1
  if not (skip_empty and _is_empty_scripts(scripts)):
    if not showed_block:
      print '...' if block == 'No_Block' else block
    _list_range(
        start_cp, limit, defined_cps, defined_count, scripts, all_scripts,
        only_scripts, details)


def _summarize_block(block, block_count, defined_count, script_counts):
  if block == 'No_Block':
    print '...'
    return

  if block_count == defined_count:
    print '%s (%d cps)' % (block, defined_count)
  else:
    print '%s (%d of %d cps)' % (block, defined_count, block_count)

  lower_limit = int(defined_count / 10)
  groups = collections.defaultdict(list)
  for script, count in script_counts.iteritems():
    groupnum = int(count / 5) * 5
    if groupnum < lower_limit:
      groupnum = 0
    groups[groupnum].append((script, count))

  for key in sorted(groups, reverse=True):
    group_list = groups[key]
    low = 0x110000
    hi = -1
    scripts = set()
    for g in group_list:
      count = g[1]
      if count < low:
        low = count
      if count > hi:
        hi = count
      scripts.add(g[0])

    if low == hi:
      if hi == defined_count:
        count = 'all'
      else:
        count = '%d' % hi
    else:
      count = '%d-%d' % (low, hi)
    script_names = _script_names(scripts)
    print '%6s: %s' % (count, script_names)


def _summarize_blocks(start, limit, defined_cps, cp_to_scripts, all_scripts):
  block = None
  block_count = 0
  defined_count = 0
  script_counts = None
  for cp in range(start, limit):
    cp_block = unicode_data.block(cp)
    if cp_block != block:
      if block:
        _summarize_block(
            block, block_count, defined_count, script_counts)
      block = cp_block
      block_count = 0
      defined_count = 0
      script_counts = collections.defaultdict(int)

    block_count += 1
    is_defined = cp in defined_cps and cp not in _OMITTED
    if not is_defined:
      continue

    defined_count += 1
    scripts = _get_scripts(cp, cp_to_scripts)
    for script in scripts:
      script_counts[script] += 1
  _summarize_block(block, block_count, defined_count, script_counts)


def block_coverage(
    cmap_file, start=0, limit=0x20000, only_scripts=None, details=0,
    summary=False):
  data = cmap_data.read_cmap_data_file(cmap_file)
  cp_to_scripts, all_scripts = _create_cp_to_scripts(data, only_scripts)
  defined_cps = unicode_data.defined_characters(version=9.0)

  if summary:
    _summarize_blocks(
        start, limit, defined_cps, cp_to_scripts, all_scripts)
  else:
    _list_blocks(
        start, limit, defined_cps, cp_to_scripts, all_scripts, only_scripts,
        details)


def main():
  parser = argparse.ArgumentParser()
  parser.add_argument(
      'cmap_file', help='cmap data file',
      metavar='file')
  parser.add_argument(
      '-d', '--details', help='show details on N characters in each range'
      ' (3 if no value provided)', metavar='num', default=0, const=3,
      type=int, nargs='?')
  parser.add_argument(
      '-s', '--summary', help='show summary of block usage only',
      action='store_true')
  parser.add_argument(
      '-r', '--range', help='range of characters to show (default 0-1ffff)',
      metavar='range', default='0-1ffff')
  parser.add_argument(
      '-sc', '--scripts', help='limit scripts to show',
      metavar='script', nargs='+', default=None)

  args = parser.parse_args()
  ranges = tool_utils.parse_int_ranges(args.range)
  start = min(ranges)
  end = max(ranges)
  if end > 0x10ffff:
    end = 0x10ffff;
  limit = end + 1

  if args.scripts:
    args.scripts = frozenset(args.scripts)
  block_coverage(
      args.cmap_file, start, limit, args.scripts, args.details, args.summary)


if __name__ == "__main__":
  main()
