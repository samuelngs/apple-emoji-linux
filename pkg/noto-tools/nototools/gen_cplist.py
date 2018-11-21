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

"""
Generate lists of codepoints prefixed with 'u' or 'uni' from cmap data file.

Occasionally the designers want data in this format to create lists of files
for their tools, so let's just save this script.
"""

import argparse
from os import path
import sys

from nototools import cmap_data
from nototools import tool_utils


def glyphstr(cp):
  return ('uni%04x' % cp) if cp < 0x10000 else ('u%05x' % cp)


def glyphstrs(cps):
  return '\n'.join(glyphstr(cp) for cp in sorted(cps))


def write_cp_list(cps, fname):
  with open(fname, 'w') as f:
    f.write(glyphstrs(cps))
    f.write('\n')


def generate_single(cmapdata, script, outfile):
  for row in cmapdata.table.rows:
    if script == row.script:
      cps = tool_utils.parse_int_ranges(row.ranges)
      write_cp_list(cps, outfile)
      print >> sys.stderr, 'wrote %s to %s' % (script, outfile)
      return
  raise ValueError('no script "%s" in cmap data' % script)


def generate(cmapdata, dst_dir, scripts, namepats):
  if not scripts:
    raise ValueError('no scripts')

  if not namepats:
    raise ValueError('no namepats')

  if len(scripts) != len(namepats):
    if len(namepats) != 1:
      raise ValueError(
          'Have %d script%s but %d namepats' %
          (len(scripts), '' if len(scripts) == 1 else 's', len(namepats)))
    if '%s' not in namepats[0] and len(scripts) > 1:
      raise ValueError(
          'Have multiple scripts but single namepat "%s" has no substitution'
          % namepats[0])
    namepats = [namepats[0]] * len(scripts)

  dst_dir = tool_utils.ensure_dir_exists(dst_dir)
  for s, n in zip(scripts, namepats):
    outfile = path.join(dst_dir, (n % s) if '%s' in n else n)
    generate_single(cmapdata, s, outfile)


def main():
  default_cmap = '[tools]/nototools/data/noto_cmap_phase3.xml'
  default_namepats = ['cps_%s.txt']

  epilog = """If a namepat contains the string "%s" then the script id will
  be substituted for it. If one namepat is provided it is used for all scripts,
  otherwise there should be as many namepats as there are scripts."""

  parser = argparse.ArgumentParser(epilog=epilog)
  parser.add_argument(
      '-c', '--cmap_file', help='cmap data file to use (default %s)' %
      default_cmap, default=default_cmap, metavar='file')
  parser.add_argument(
      '-d', '--dest_dir', help='directory for output, (defaults to current '
      'directory)', metavar='dir', default='.')
  parser.add_argument(
      '-s', '--scripts', help='script ids of data to output', nargs='+',
      metavar='id', required=True)
  parser.add_argument(
      '-n', '--namepats', help='name patterns used to generate output '
      'filenames (default "cps_%%s.txt")',
      default=default_namepats, metavar='npat', nargs='+')
  args = parser.parse_args()

  cmap_filepath = tool_utils.resolve_path(args.cmap_file)
  cmapdata = cmap_data.read_cmap_data_file(cmap_filepath)
  generate(cmapdata, args.dest_dir, args.scripts, args.namepats)


if __name__ == '__main__':
  main()
