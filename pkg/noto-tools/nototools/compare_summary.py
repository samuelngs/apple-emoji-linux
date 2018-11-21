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

"""Compare summaries of ttf files in two noto file trees"""

__author__ = "dougfelt@google.com (Doug Felt)"

import argparse
import filecmp
import os
import os.path

from nototools import noto_lint
from nototools import summary
from nototools import tool_utils

def summary_to_map(summary_list):
  result = {}
  for tuple in summary_list:
    key = tuple[0]
    result[key] = tuple
  return result

def get_key_lists(base_map, target_map, base_root, target_root):
  added = []
  removed = []
  shared = []
  identical = []
  for k in sorted(base_map):
    target = target_map.get(k)
    if not target:
      removed.append(k)
    elif filecmp.cmp(os.path.join(base_root, k),
                     os.path.join(target_root, k)):
      identical.append(k)
    else:
      shared.append(k)
  for k in sorted(target_map):
    if not base_map.get(k):
      added.append(k)
  return added, removed, shared, identical

def print_keys(key_list):
  for k in key_list:
    print '  ' + k

def compare_table_info(base_info, target_info):
  biggest_deltas = []
  others = [] # checksum changes
  added = []
  removed = []

  for k in target_info:
    b_tup = base_info.get(k)
    t_tup = target_info.get(k)
    if not b_tup:
      added.append((k, t_tup[0]))
    else:
      b_len = b_tup[0]
      t_len = t_tup[0]
      delta = t_len - b_len
      if delta == 0:
        if b_tup[1] != t_tup[1]:
          others.append(k)
        continue
      biggest_deltas.append((k, delta))

  for k in base_info:
    if not target_info.get(k):
      removed.append(k)

  biggest_deltas.sort(lambda lhs,rhs: -cmp(abs(lhs[1]), abs(rhs[1])) or
                      cmp(lhs[0], rhs[0]))
  del biggest_deltas[5:]

  result = []
  if biggest_deltas:
    def print_delta(t):
      if t[1] == 0:
        return t[0]
      return '%s(%+d)' % t
    biggest_delta_strings = [print_delta(t) for t in biggest_deltas]
    # if a table changed size, the head table will change the checksum, don't
    # report this.
    others = [k for k in others if k != 'head']
    if len(others) > 0 and len(biggest_deltas) < 5:
      other_count = len(others)
      biggest_delta_strings.append('%s other%s' %
                                   (other_count, 's' if other_count != 1 else ''))
    result.append('changed ' + ', '.join(biggest_delta_strings))
  if added:
    result.append('added ' + ', '.join('%s(%s)' % t for t in sorted(added)))
  if removed:
    result.append('removed ' + ', '.join(sorted(removed)))
  return '; '.join(result)

def print_difference(k, base_tuple, target_tuple, other_difference):
  b_path, b_version, b_name, b_size, b_numglyphs, b_numchars, b_cmap, b_tableinfo = base_tuple
  t_path, t_version, t_name, t_size, t_numglyphs, t_numchars, t_cmap, t_tableinfo = target_tuple
  print '  ' + k
  versions_differ = b_version != t_version
  diff_list = []
  if versions_differ:
    if float(b_version) > float(t_version):
      msg = '(base is newer!)'
    else:
      msg = ''
    print '    version: %s vs %s %s' % (b_version, t_version, msg)
  if b_name != t_name:
    diff_list.append('name')
    print "    name: '%s' vs '%s'" % (b_name, t_name)
  if b_size != t_size:
    diff_list.append('size')
    delta = int(t_size) - int(b_size)
    if delta < 0:
      msg = '%d byte%s smaller' % (-delta, '' if delta == -1 else 's')
    else:
      msg = '%d byte%s bigger' % (delta, '' if delta == 1 else 's')
    print '    size: %s vs %s (%s)' % (b_size, t_size, msg)
  table_diffs = compare_table_info(b_tableinfo, t_tableinfo)
  if table_diffs:
    diff_list.append('table')
    print '    tables: %s' % table_diffs
  if b_numglyphs != t_numglyphs:
    diff_list.append('glyph count')
    delta = int(t_numglyphs) - int(b_numglyphs)
    if delta < 0:
      msg = '%d fewer glyph%s' % (-delta, '' if delta == -1 else 's')
    else:
      msg = '%d more glyph%s' % (delta, '' if delta == 1 else 's')
    print '    glyphs: %s vs %s (%s)' % (b_numglyphs, t_numglyphs, msg)
  if b_numchars != t_numchars:
    diff_list.append('char count')
    delta = int(t_numchars) - int(b_numchars)
    if delta < 0:
      msg = '%d fewer char%s' % (-delta, '' if delta == -1 else 's')
    else:
      msg = '%d more char%s' % (delta, '' if delta == 1 else 's')
    print '    chars: %s vs %s (%s)' % (b_numchars, t_numchars, msg)
  if b_cmap != t_cmap:
    removed_from_base = b_cmap - t_cmap
    if removed_from_base:
      print '    cmap removed: ' + noto_lint.printable_unicode_range(
        removed_from_base)
    added_in_target = t_cmap - b_cmap
    if added_in_target:
      print '    cmap added: ' + noto_lint.printable_unicode_range(
          added_in_target)
  if diff_list and not versions_differ:
    print '    %s differs but revision number is the same' % ', '.join(diff_list)
  if not diff_list and other_difference:
    print '    other difference'

def print_changed(key_list, base_map, target_map, comparefn):
  for k in key_list:
    base_tuple = base_map.get(k)
    target_tuple = target_map.get(k)
    other_difference = comparefn(base_tuple, target_tuple)
    print_difference(k, base_tuple, target_tuple, other_difference)

def tuple_compare(base_t, target_t):
  return base_t == target_t

def tuple_compare_no_size(base_t, target_t):
  for i in range(len(base_t)):
    if i == 3:
      continue
    if base_t[i] != target_t[i]:
      return False
  return True

def compare_summary(base_root, target_root, name=None, comparefn=tuple_compare,
                    show_added=True, show_removed=True, show_identical=True,
                    show_paths=True):
  base_map = summary_to_map(summary.summarize(base_root, name))
  target_map = summary_to_map(summary.summarize(target_root, name))
  added, removed, changed, identical = get_key_lists(base_map, target_map,
                                                     base_root, target_root)

  # no nonlocal in 2.7
  have_output_hack = [False]

  def header_line(msg):
    if have_output_hack[0]:
      print
    else:
      have_output_hack[0] = True
    if msg:
      print msg

  if show_paths:
    header_line(None)
    print 'base root: ' + base_root
    print 'target root: ' + target_root
  if show_added and added:
    header_line('added')
    print_keys(added)
  if show_removed and removed:
    header_line('removed')
    print_keys(removed)
  if changed:
    header_line('changed')
    print_changed(changed, base_map, target_map, comparefn)
  if show_identical and identical:
    header_line('identical')
    print_keys(identical)

def main():
  parser = argparse.ArgumentParser()
  parser.add_argument('-b', '--base_root', help='root of directory tree, base for comparison '
                      '(default [fonts])', metavar='dir', default='[fonts]')
  parser.add_argument('-t', '--target_root', help='root of directory tree, target for comparison',
                      metavar='dir', required=True)
  parser.add_argument('--name', help='only examine files whose subpath+names contain this regex')
  parser.add_argument('--compare_size', help='include size in comparisons',
                      action='store_true')
  parser.add_argument('--removed',  help='list files not in target', action='store_true')
  parser.add_argument('--added', help='list files not in base', action='store_true')
  parser.add_argument('--identical', help='list files that are identical in base and target',
                      action='store_true')
  parser.add_argument('--nopaths', help='do not print root paths', action='store_false',
                      default=True, dest='show_paths')
  args = parser.parse_args()

  args.base_root = tool_utils.resolve_path(args.base_root)
  args.target_root = tool_utils.resolve_path(args.target_root)

  if not os.path.isdir(args.base_root):
    print 'base_root %s does not exist or is not a directory' % args.base_root
    return

  if not os.path.isdir(args.target_root):
    print 'target_root %s does not exist or is not a directory' % args.target_root
    return

  comparefn = tuple_compare if args.compare_size else tuple_compare_no_size

  compare_summary(args.base_root, args.target_root, args.name, comparefn,
                  args.added, args.removed, args.identical, args.show_paths)

if __name__ == '__main__':
  main()
