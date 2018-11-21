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

import argparse
import codecs
import csv
import math
from os import path
import sys

from nototools import cmap_data
from nototools import coverage
from nototools import generate_coverage_data
from nototools import tool_utils
from nototools import unicode_data

from fontTools import ttLib

default_version=6.0
default_coverage_file = 'noto_cmap_phase2.xml'

def get_defined_cps(version=default_version, exclude_ranges=None):
  defined_cps = unicode_data.defined_characters(version)
  if exclude_ranges:
    defined_cps -= tool_utils.parse_int_ranges(exclude_ranges)
  return defined_cps


def get_coverages(coverage_files):
  return [generate_coverage_data.read(f) for f in coverage_files]


def get_block_data(defined_cps, coverages, no_empty=False):
  block_data = []
  covered_cps_list = [
      tool_utils.parse_int_ranges(cov.cmapdata.ranges)
      for cov in coverages]
  for block_name in unicode_data.block_names():
    block_range = unicode_data.block_range(block_name)
    block_cps = unicode_data.block_chars(block_name)
    block_cps &= defined_cps
    if not block_cps:
      continue
    cov_info = []
    all_empty = True
    for covered_cps in covered_cps_list:
      block_covered_cps = covered_cps & block_cps
      if block_covered_cps:
        all_empty = False
      cov_info.append(block_covered_cps)
    if no_empty and all_empty:
      continue
    block_data.append(block_range + (block_name, block_cps, cov_info))
  return block_data


def write_block_coverage_html(block_data, names, msg, out_file=sys.stdout):
  cp_limit = 1000
  chart_width = 250
  chart_row_height = 8

  HEADER = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Block coverage</title>
  <style>
  td.range {font-family: monospace; text-align: right;}
  td.count {font-family: monospace; text-align: right;}
  td.pct {font-family: monospace; text-align: right;}
  div.chart {width:%dpx; position:relative;}
  div.tot {border: 1px solid black; padding: 1px;}
  div.bar {height: %dpx; background-color: green;}
  </style>
</head>
<body>
  <h2>Block coverage</h2>
""" % (chart_width, chart_row_height)
  FOOTER = """</body>
</html>
"""

  out_file.write(HEADER)
  if msg:
    out_file.write('  <p>')
    out_file.write(msg)
    out_file.write('\n')
  block_data.sort()
  out_file.write(
      '  <table>\n'
      '    <tr><th colspan=3>&nbsp;')
  for name in names:
    out_file.write('<th colspan=3>%s' % name)
  out_file.write('\n')
  out_file.write(
      '    <tr><th>Range<th>Block Name<th>Count')
  for _ in names:
    out_file.write('<th>Count<th>Pct<th>Chart')
  out_file.write('\n')

  max_block_size = max(len(t[3]) for t in block_data)
  if max_block_size > cp_limit:
    max_block_size = cp_limit
  for start, end, name, block_cps, block_covered_cps_list in block_data:
    range_str = '%04x-%04x' % (start, end)
    num_in_block = len(block_cps)
    tot_ht = 1 + int(math.floor(float(num_in_block) / cp_limit))
    tot_px = int(float(chart_width) * num_in_block / max_block_size / tot_ht)
    vir_cp_limit = int(float(num_in_block) / tot_ht)
    out_file.write('    <tr>')
    out_file.write('<td class="range">%s' % range_str)
    out_file.write('<td class="name">%s' % name)
    out_file.write('<td class="count">%s' % num_in_block)
    for block_covered_cps in block_covered_cps_list:
      num_covered = len(block_covered_cps)
      pct = '%d%%' % int(100.0 * num_covered / num_in_block)
      bar_ht = min(
          tot_ht, 1 + int(math.floor(float(num_covered) / vir_cp_limit)))
      bar_px = int(float(chart_width) * num_covered / max_block_size / bar_ht)
      out_file.write('<td class="count">%s' % num_covered)
      out_file.write('<td class="pct">%s' % pct)
      out_file.write('<td><div class="chart">')
      out_file.write('<div class="tot" style="width:%dpx; height:%dpx">' % (
          tot_px, tot_ht * chart_row_height))
      out_file.write('<div class="bar" style="width:%dpx; height:%dpx">' % (
          bar_px, bar_ht * chart_row_height))
      out_file.write('</div></div></div>\n')
  out_file.write(FOOTER)


def write_block_coverage_text(block_data, names, msg, out_file=sys.stdout):
  block_data.sort()
  print >> out_file, msg
  name_len = max(len(t[2]) for t in block_data)
  fmt_str = '%%%ds' % name_len
  fmt_str = '%13s ' + fmt_str + ' %5s'
  header_fmts = [
      '%%%ds' % max(10, len(name)) for name in names]
  header_parts = []
  header_parts.append(fmt_str % ('range', 'block name', 'count'))
  for fmt, name in zip(header_fmts, names):
    header_parts.append(fmt % name)
  print >> out_file, ' '.join(header_parts)
  for start, end, name, block_cps, block_covered_cps_list in block_data:
    line_parts = []
    range_str = '%04x-%04x' % (start, end)
    num_in_block = len(block_cps)
    line_parts.append(fmt_str % (range_str, name, num_in_block))
    for fmt, covered_cps in zip(header_fmts, block_covered_cps_list):
      num_covered = len(covered_cps)
      pct = '%d%%' % int(100.0 * num_covered / num_in_block)
      part_str = '%5d %4s' % (num_covered, pct)
      line_parts.append(fmt % part_str)
    print >> out_file, ' '.join(line_parts)
  out_file.flush()


def write_block_coverage_csv(block_data, names, msg, out_file=sys.stdout):
  block_data.sort()
  # nowhere to write msg
  csv_writer = csv.writer(out_file, delimiter=',')
  headers = ['range', 'block name', 'count']
  for name in names:
    headers.append(name + ' count')
    headers.append(name + ' pct')
  csv_writer.writerow(headers)
  for start, end, name, block_cps, block_covered_cps_list in block_data:
    range_str = '%04x-%04x' % (start, end)
    num_in_block = len(block_cps)
    row_parts = [range_str, name, num_in_block]
    for block_covered_cps in block_covered_cps_list:
      num_covered = len(block_covered_cps)
      pct = '%d%%' % int(100.0 * num_covered / num_in_block)
      row_parts.append(num_covered)
      row_parts.append(pct)
    csv_writer.writerow(row_parts)


def write_block_coverage(block_data, names, msg, fmt=None, out_file=sys.stdout):
  if not fmt:
    if not out_file:
      fmt = 'text'
    else:
      ext = path.splitext(out_file)[1]
      if not ext or ext in ['.txt', '.text']:
        fmt = 'text'
      elif ext in ['.htm', '.html']:
        fmt = 'html'
      elif ext in ['.csv']:
        fmt = 'csv'
  if out_file:
    tool_utils.ensure_dir_exists(path.dirname(out_file))
    with codecs.open(out_file, 'w', 'utf-8') as f:
      _write_block_coverage_fmt(block_data, names, msg, fmt, f)
  else:
    _write_block_coverage_fmt(block_data, names, msg, fmt, sys.stdout)


def _write_block_coverage_fmt(block_data, names, msg, fmt, out_file):
  if fmt == 'text':
    write_block_coverage_text(block_data, names, msg, out_file)
  elif fmt == 'html':
    write_block_coverage_html(block_data, names, msg, out_file)
  elif fmt == 'csv':
    write_block_coverage_csv(block_data, names, msg, out_file)
  else:
    raise ValueError('unknown format "%s"' % fmt)


def main():
  format_choices = 'text', 'html', 'csv'

  parser = argparse.ArgumentParser()
  parser.add_argument(
      '-uv', '--unicode_version', help='version of unicode to compare against '
      '(default %3.1f)' % default_version, metavar='version', type=float,
      default=default_version)
  parser.add_argument(
      '-ex', '--exclude_ranges', help='ranges to exclude', nargs='*',
      metavar='range')
  parser.add_argument(
      '-o', '--output_file', help='name of file to output (format defaults '
      'based on suffix)', metavar='file')
  parser.add_argument(
      '-fmt', '--format', help='format of output, defaults to text if no file',
      choices=format_choices)
  parser.add_argument(
      '-ne', '--no_empty', help='exclude empty blocks', action='store_true')
  parser.add_argument(
      '-c', '--coverage_data', help='coverage data files', nargs='+',
      metavar='file', required=True)
  parser.add_argument(
      '-m', '--message', help='message header for output', nargs='?',
      metavar='msg', const='--uv--')
  args = parser.parse_args()

  if args.exclude_ranges is None:
    args.exclude_ranges = []
  elif not args.exclude_ranges:
    # exclude c0-c1 controls if args is passed but no ranges specified
    args.exclude_ranges = ['0-1f 7f 80-9f']

  defined_cps = get_defined_cps(
      args.unicode_version, ' '.join(args.exclude_ranges))

  coverages = get_coverages(args.coverage_data)

  if args.message == '--uv--':
    args.message = 'Unicode version: %3.1f' % args.unicode_version

  block_data = get_block_data(defined_cps, coverages, args.no_empty)
  names = [cov.cmapdata.name for cov in coverages]
  write_block_coverage(
      block_data, names, args.message, args.format, args.output_file)

if __name__ == '__main__':
  main()
