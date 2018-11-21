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

"""Copy downloaded font zip files from Monotype into noto directory
structure.

This leverages some properties of the font drops.  The drops come in
zip files with an underscore and 8-digit date suffix before the extension.
This reflects the date of the drop. For each zip of this type we build
a root named for the date in the target directory.

Most drops contain a two-level tree with the font name and a suffix of
either '_hinted or '_unhinted' on the top level, and the relevant data
underneath.  Our structure just uses 'hinted' or 'unhinted', so we
convert, putting these under the root for the zip.

Some drops have a single level tree, we examine the fonts to determine if
they have hints (probably all do not) and assign it to one of our trees based
on that.

Other files with names matching the font name (in particular, .csv files
corresponding to our linter output) are put into the folder matching the
font.  Files that are not in a two-level hierarchy and do not correspond to
a font are put at the top level.

Other tools (for updating the internal staging repo) work off the structure
built by this tool.
"""

__author__ = "dougfelt@google.com (Doug Felt)"

import argparse
import cStringIO
import os
import os.path
import re
import shutil
import sys
import zipfile

from fontTools import ttLib

import grab_download
import notoconfig

def write_data_to_file(data, root, subdir, filename):
  dstdir = os.path.join(root, subdir)
  if not os.path.exists(dstdir):
    os.mkdir(dstdir)
  with open(os.path.join(dstdir, filename), 'wb') as f:
    f.write(data)
  print 'extracted \'%s\' into %s' % (filename, subdir)


def unzip_to_directory_tree(drop_dir, filepath):
  hint_rx = re.compile(r'_((?:un)?hinted)/(.+)')
  plain_rx = re.compile(r'[^/]+')
  zf = zipfile.ZipFile(filepath, 'r')
  print 'extracting files from %s to %s' % (filepath, drop_dir)
  count = 0
  mapped_names = []
  unmapped = []
  for name in zf.namelist():
    # skip names representing portions of the path
    if name.endswith('/'):
      continue
    # get the blob
    try:
      data = zf.read(name)
    except KeyError:
      print 'did not find %s in zipfile' % name
      continue

    result = hint_rx.search(name)
    if result:
      # we know where it goes
      subdir = result.group(1)
      filename = result.group(2)
      write_data_to_file(data, drop_dir, subdir, filename)
      count += 1
      continue

    result = plain_rx.match(name)
    if not result:
      print "subdir structure without hint/unhint: '%s'" % name
      continue

    # we have to figure out where it goes.
    # if it's a .ttf file, we look for 'fpgm'
    # and 'prep' and if they are present, we put
    # it into hinted, else unhinted.
    # if it's not a .ttf file, but it starts with
    # the name of a .ttf file (sans suffix), we put
    # it in the same subdir the .ttf file went into.
    # else we put it at drop_dir (no subdir).
    if name.endswith('.ttf'):
      blobfile = cStringIO.StringIO(data)
      font = ttLib.TTFont(blobfile)
      subdir = 'hinted' if font.get('fpgm') or font.get('prep') else 'unhinted'
      write_data_to_file(data, drop_dir, subdir, name)
      count += 1

      basename = os.path.splitext(name)[0]
      mapped_names.append((basename, subdir))
      continue

    # get to these later
    unmapped.append((name, data))

  # write the remainder
  if unmapped:
    for name, data in unmapped:
      subdir = ''
      for mapped_name, mapped_subdir in mapped_names:
        if name.startswith(mapped_name):
          subdir = mapped_subdir
          break
      write_data_to_file(data, drop_dir, subdir, name)
      count += 1

  print 'extracted %d files' % count


def main():
  params = {
      'default_srcdir': os.path.expanduser('~/Downloads'),
      'default_dstdir': notoconfig.values.get('monotype_data'),
      'default_regex': r'Noto.*_\d{8}.zip',
  }
  grab_download.invoke_main(
      src_vendor='Monotype',
      name_date_re= re.compile(r'(.*)_(\d{4})(\d{2})(\d{2})\.zip'),
      extract_fn=unzip_to_directory_tree,
      default_params=params)


if __name__ == "__main__":
    main()
