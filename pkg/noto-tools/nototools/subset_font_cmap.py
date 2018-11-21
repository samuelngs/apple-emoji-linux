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

"""Like subset.py, but with command-line options."""

import argparse
from os import path

from fontTools import subset

from nototools import coverage
from nototools import font_data
from nototools import swat_license
from nototools import tool_utils


def _get_default_options():
  opt = subset.Options()
  opt.name_IDs = ['*']
  opt.name_legacy = True
  opt.name_languages = ['*']
  opt.layout_features = ['*']
  opt.notdef_outline = True
  opt.recalc_bounds = True
  opt.recalc_timestamp = True
  opt.canonical_order = True
  return opt


_DEFAULT_OPTIONS = _get_default_options()

_VERSION_ID = 5  # name table version string ID


def subset_font_cmap(
  srcname, dstname, exclude=None, include=None, bump_version=True):

  opt = _DEFAULT_OPTIONS

  font = subset.load_font(srcname, opt)
  target_charset = set(font_data.get_cmap(font).keys())

  if include is not None:
    target_charset &= include
  if exclude is not None:
    target_charset -= exclude

  subsetter = subset.Subsetter(options=opt)
  subsetter.populate(unicodes=target_charset)
  subsetter.subset(font)

  if bump_version:
    # assume version string has 'uh' if unhinted, else hinted.
    revision, version_string = swat_license.get_bumped_version(font)
    font['head'].fontRevision = revision
    font_data.set_name_record(font, _VERSION_ID, version_string)

  subset.save_font(font, dstname, opt)


def subset_fonts_cmap(
    fonts, dstdir, exclude=None, include=None, bump_version=True):
  dstdir = tool_utils.ensure_dir_exists(dstdir)
  for srcname in fonts:
    dstname = path.join(dstdir, path.basename(srcname))
    subset_font_cmap(srcname, dstname, exclude, include, bump_version)


def main():
  parser = argparse.ArgumentParser()
  parser.add_argument(
      '-i', '--include', help='ranges of characters to include',
      metavar='range', nargs='+')
  parser.add_argument(
      '-e', '--exclude', help='ranges of characters to exclude '
      '(applied after include)',
      metavar='range', nargs='+')
  parser.add_argument(
      '-d', '--dstdir', help='directory to write new files to',
      metavar='dir')
  parser.add_argument(
      '-b', '--bump_version', help='bump version (default true)',
      metavar='bool', type=bool, default=True)
  parser.add_argument(
      'fonts', help='fonts to subset',
      metavar='font', nargs='+')
  args = parser.parse_args()

  if args.exclude:
    args.exclude = tool_utils.parse_int_ranges(' '.join(args.exclude))
  if args.include:
    args.include = tool_utils.parse_int_ranges(' '.join(args.include))
  subset_fonts_cmap(
      args.fonts, args.dstdir, exclude=args.exclude, include=args.include,
      bump_version=args.bump_version)


if __name__ == '__main__':
  main()
