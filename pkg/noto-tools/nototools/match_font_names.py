#!/usr/bin/env python

"""Find fonts under some root whose names match the provided names.
If the provided name contains '-' then include only names with that style
after the hyphen, otherwise include all styles.

The name list is the same as that used to swat file versions."""

import argparse
import os
from os import path
import re

from nototools import tool_utils

def _build_regex(names):
  parts = []
  for name in names:
    ix = name.find('-')
    if ix == -1:
      parts.append(r'%s-' % name)
    else:
      prefix = name[:ix]
      suffix = name[ix+1:]
      parts.append(r'%s-.*%s' % (prefix, suffix))
  full_exp = '^(?:' + '|'.join(parts) + ').*\.ttf$'
  return re.compile(full_exp)


def match_files(src_dir, names):
  matched_files = set()
  src_dir = tool_utils.resolve_path(src_dir)
  print '# root: %s' % src_dir
  name_re = _build_regex(names)
  for root, dirs, files in os.walk(src_dir):
    effective_root = root[len(src_dir)+1:]
    for f in files:
      if name_re.match(f):
        matched_files.add(path.join(effective_root, f))
  return sorted(matched_files)


def _print_list(names):
  if not names:
    return
  for n in names:
    print n


def _collect_names(names):
  all_names = set()

  def scan_name(n):
    n = n.strip()
    if not n:
      return
    if n[0] != '@':
      all_names.add(n)
      return
    with open(n[1:], 'r') as f:
      lines = f.readlines()
    for l in lines:
      ix = l.find('#')
      if ix != -1:
        l = l[:ix]
      scan_name(l)

  for n in names:
    scan_name(n)
  return sorted(all_names)


def main():
  parser = argparse.ArgumentParser();
  parser.add_argument(
      '-f', '--files', help='list of names and/or files (prefixed with \'@\'',
      metavar='name', required=True, nargs='+')
  parser.add_argument(
      '-s', '--src_dir', help='directory under which to search for files',
      metavar='dir', required=True)
  args = parser.parse_args();
  _print_list(match_files(args.src_dir, _collect_names(args.files)));


if __name__ == '__main__':
  main()
