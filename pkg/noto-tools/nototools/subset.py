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

"""Routines for subsetting fonts."""

__author__ = 'roozbeh@google.com (Roozbeh Pournader)'

import sys

from fontTools import subset

import coverage


def subset_font(source_file, target_file,
                include=None, exclude=None, options=None):
    """Subsets a font file.

    Subsets a font file based on a specified character set. If only include is
    specified, only characters from that set would be included in the output
    font.  If only exclude is specified, all characters except those in that
    set will be included.  If neither is specified, the character set will
    remain the same, but inaccessible glyphs will be removed.

    Args:
      source_file: Input file name.
      target_file: Output file name
      include: The list of characters to include from the source font.
      exclude: The list of characters to exclude from the source font.
      options: A dictionary listing which options should be different from the
          default.

    Raises:
      NotImplementedError: Both include and exclude were specified.
    """
    opt = subset.Options()

    opt.name_IDs = ['*']
    opt.name_legacy = True
    opt.name_languages = ['*']
    opt.layout_features = ['*']
    opt.notdef_outline = True
    opt.recalc_bounds = True
    opt.recalc_timestamp = True
    opt.canonical_order = True
    opt.drop_tables = ['+TTFA']

    if options is not None:
        for name, value in options.iteritems():
            setattr(opt, name, value)

    if include is not None:
        if exclude is not None:
            raise NotImplementedError(
                'Subset cannot include and exclude a set at the same time.')
        target_charset = include
    else:
        if exclude is None:
            exclude = []
        source_charset = coverage.character_set(source_file)
        target_charset = source_charset - set(exclude)

    font = subset.load_font(source_file, opt)
    subsetter = subset.Subsetter(options=opt)
    subsetter.populate(unicodes=target_charset)
    subsetter.subset(font)
    subset.save_font(font, target_file, opt)


def main(argv):
    """Subset the first argument to second, dropping unused parts of the font.
    """
    subset_font(argv[1], argv[2])


if __name__ == '__main__':
    main(sys.argv)
