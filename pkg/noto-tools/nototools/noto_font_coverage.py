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

"""A tool to output charmap coverage of the noto font families."""

import argparse
import collections

from nototools import noto_fonts

def print_names(families):
  """Write the names of the families in sorted order."""
  family_names = [family.name for family in families.itervalues()]
  for name in sorted(family_names):
    print name


def check_cp(families, cp):
  return set([family.name for family in families.itervalues() if cp in family.charset])


def codepoints(cp_list):
  result = set()
  for cp in cp_list:
    if '-' in cp:
      low, high = cp.split('-')
      low = int(low, 16)
      high = int(high, 16)
      if (low > high):
        temp = low
        low = high
        high = temp
      for cp in range(low, high + 1):
        result.add(cp)
    else:
      result.add(int(cp, 16))
  return result


def to_ranges_str(cps):
  if not cps:
    return ''

  cps = sorted(cps)
  ranges = []

  def emit(first, last):
    if first != last:
      ranges.append('%04x-%04x' % (first, last))
    else:
      ranges.append('%04x' % first)

  first = cps[0]
  last = first
  for cp in cps[1:]:
    if cp == last + 1:
      last = cp
    else:
      emit(first, last)
      first = cp
      last = cp
  emit(first, last)
  return ' '.join(ranges)


def run(args, families):
  if args.names:
    print_names(families)

  cp_to_families = collections.defaultdict(set)
  if args.each:
    def each_emit(out_cps, out_families):
      if out_families:
        out_family_str = '\n  '.join(sorted(out_families))
      else:
        out_family_str = '<no coverage>'
      print '%s:\n  %s' % (to_ranges_str(out_cps), out_family_str)

    cps = codepoints(args.each)
    print 'families that contain any of %s, by cp' % to_ranges_str(cps)
    for family in families.itervalues():
      family_cps = family.charset & cps
      for cp in family_cps:
        cp_to_families[cp].add(family.name)

    if not cp_to_families:
      print 'no family supports any codepoint'
    else:
      cp_list = sorted(cps)
      cp = cp_list[0]
      out_cps = [cp]
      out_families = cp_to_families[cp]
      for cp in cp_list[1:]:
        next_families = cp_to_families[cp]
        if out_families == next_families:
          out_cps.append(cp)
        else:
          each_emit(out_cps, out_families)
          out_cps = [cp]
          out_families = next_families
      each_emit(out_cps, out_families)

  if args.any:
    missing = set()
    result = {}
    cps = sorted(codepoints(args.any))
    print 'families that contain any of %s' % to_ranges_str(cps)
    for cp in cps:
      family_names = check_cp(families, cp)
      if family_names:
        for family in family_names:
          if family in result:
            result[family].add(cp)
          else:
            result[family] = set([cp])
      else:
        missing.add(cp)
    if result:
      for k, v in sorted(result.iteritems()):
        print '  %s: %s' % (k, to_ranges_str(v))
    if missing:
      print '  not supported: %s' % to_ranges_str(missing)

  if args.all:
    cps = sorted(codepoints(args.all))
    print 'families that contain all of %s' % to_ranges_str(cps)
    result = set([family.name for family in families.itervalues()])
    for cp in cps:
      family_names = check_cp(families, cp)
      result &= family_names
    if result:
      print '\n'.join(['  %s' % name for name in sorted(result)])
    else:
      print 'no family contains all the codepoints'


def main():
  parser = argparse.ArgumentParser()
  parser.add_argument('--names', help='print family names', action='store_true')
  parser.add_argument('--each', help='for each code point, show supporting families',
                      metavar='cp', nargs='+')
  parser.add_argument('--any', help='show families that support any of the codepoints',
                      metavar='cp', nargs='+')
  parser.add_argument('--all', help='show families that support all of the codepoints',
                      metavar='cp', nargs='+')
  args = parser.parse_args()

  fonts = noto_fonts.get_noto_fonts()
  families = noto_fonts.get_families(fonts)
  run(args, families)

if __name__ == '__main__':
    main()
