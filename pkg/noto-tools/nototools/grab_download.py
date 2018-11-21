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

"""Base code for copying and unpacking font drops from vendors.

See grab_mt_download.py and grab_adobe_download.py"""

__author__ = "dougfelt@google.com (Doug Felt)"

import argparse
import os
import os.path
import re
import shutil
import zipfile

from fontTools import ttLib

import notoconfig


def grab_files(dst, files, src_vendor, name_date_re, extract_fn):
  """Get date from each filename in files, create a folder for it, under
  dst/drops, then extract the files to it."""

  # The zip indicates that the corresponding drop is good and built from it. But
  # we might have messed up along the way, so:
  # - if we have a drop and a zip, assume it's already handled
  # - if we have a drop but no zip, assume the drop needs to be rebuilt from the zip
  # - if we have a zip and no drop
  #   - if we have new zip, complain
  #   - else rebuild the drop from the old zip
  # - else build the drop, and if successful, save the zip

  for f in files:
    if not os.path.exists(f):
      print 'file \'%s\' does not exist, skipping' % f
      continue

    filename = os.path.basename(f)
    result = name_date_re.match(filename)
    if not result:
      print 'could not parse %s, skipping' % f
      continue

    name = result.group(1)
    date = '_'.join([d for d in result.group(2,3,4)])
    drop_dir = os.path.join(dst, 'drops', name + '_' + date)

    zip_dir = os.path.join(dst, 'zips')
    zip_filename = os.path.join(zip_dir, filename)
    if os.path.exists(drop_dir):
      if os.path.exists(zip_filename):
        print 'already have a %s drop and zip for %s' % (src_vendor, filename)
        continue
      else:
        # clean up, assume needs rebuild
        shutil.rmtree(drop_dir)
    else:
      if os.path.exists(zip_filename):
        if os.path.realpath(f) != os.path.realpath(zip_filename):
          print 'already have a zip file named %s for %s' % (zip_filename, f)
          continue

    os.mkdir(drop_dir)
    extract_fn(drop_dir, f)

    if not os.path.exists(zip_filename):
      print 'writing %s to %s' % (f, zip_filename)
      shutil.copy2(f, zip_filename)


def matching_files_in_dir(src, namere):
  """Iterate over files in src with names matching namere, returning the list."""
  filelist = []
  for f in os.listdir(src):
    path = os.path.join(src, f)
    if not os.path.isfile(path):
      continue
    if not re.search(namere, f):
      continue
    filelist.append(path)
  if not filelist:
    print "no files in %s matched '%s'" % (src, namere)
  return filelist


def invoke_main(src_vendor, name_date_re, extract_fn, default_params = {}):
  """Grab the files.

  src_vendor is a string, currently either Adobe or Monotype.
  name_date_re is a regex, it should extract name, year, month, and day fields from the filename
  extract_fn is a fn to to extract a file, it takes two args, a dest dir and the zip file name.

  default_params are default values for argparse.  They can be:
  - default_srcdir
  - default_dstdir
  - default_regex

  The default regex and the name_date_re are superficially similar, but different in
  purpose.  The default_regex is used to select files under the src directory. The
  name_date_re is used to extract the date from the file name.  Both apply to the
  file name, but the default_regex can be anything, while name_date_re needs to select
  four groups, where the 2nd, 3rd, and 4th are the year, month, and day (yes this is
  brittle, but all of this is).

  The dest directory must exist and should have 'zips' and 'drops' subdirs."""

  if not src_vendor:
    print 'must define src_vendor'
    return
  if not name_date_re:
    print 'must define name_date_re'
    return
  if not extract_fn:
    print 'must define extract_fn'
    return

  default_srcdir = default_params.get('default_srcdir')
  default_dstdir = default_params.get('default_dstdir')
  default_regex = default_params.get('default_regex')

  parser = argparse.ArgumentParser(description='Copy and extract drop from %s.' %
                                   src_vendor)
  parser.add_argument('-dd', '--dstdir', help='destination directory (default %s)' %
                      default_dstdir, default=default_dstdir, metavar='dst')
  parser.add_argument('-sd', '--srcdir', help='source directory (default %s)' %
                      default_srcdir, default=default_srcdir, metavar='src')
  parser.add_argument('--name', help='file name regex to match (default \'%s\')' %
                      default_regex, default=default_regex, metavar='re')
  parser.add_argument('--srcs', help='source files (if defined, use instead of srcdir+name)',
                      nargs="*", metavar='zip')
  args = parser.parse_args()

  if not os.path.exists(args.dstdir):
    print '%s does not exists or is not a directory' % args.dstdir
    return

  if not args.srcs:
    if not os.path.isdir(args.srcdir):
      print '%s does not exist or is not a directory' % args.srcdir
      return
    filelist = matching_files_in_dir(args.srcdir, args.name)
  else:
    filelist = args.srcs

  grab_files(args.dstdir, filelist, src_vendor, name_date_re, extract_fn)
