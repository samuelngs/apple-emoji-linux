#!/usr/bin/env python
# -*- coding: UTF-8 -*-
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

"""Update cldr data under third_party from local svn snapshot."""

import argparse
import contextlib
import os
import shutil
import string
import subprocess

import notoconfig
import tool_utils

CLDR_SUBDIRS = [
  'common/main',
  'common/properties',
  'exemplars/main',
  'seed/main']

CLDR_FILES = [
  'common/supplemental/likelySubtags.xml',
  'common/supplemental/supplementalData.xml']

README_TEMPLATE = """URL: http://unicode.org/cldr/trac/export/$version/trunk
Version: r$version $tag
License: Unicode
License File: LICENSE

Description:
CLDR data files for language and country information.

Local Modifications:
No Modifications.
"""

def update_cldr(noto_repo, cldr_repo, update=False, cldr_tag=''):
  """Copy needed directories/files from cldr_repo to noto_repo/third_party/cldr."""

  noto_repo = os.path.abspath(noto_repo)
  cldr_repo = os.path.abspath(cldr_repo)

  noto_cldr = os.path.join(noto_repo, 'third_party/cldr')
  tool_utils.check_dir_exists(noto_cldr)
  tool_utils.check_dir_exists(cldr_repo)

  if not tool_utils.git_is_clean(noto_repo):
    print 'Please fix'
    return

  if update:
    tool_utils.svn_update(cldr_repo)

  # get version of cldr.  Unfortunately, this doesn't know about tags.
  cldr_version = tool_utils.svn_get_version(cldr_repo)

  # prepare and create README.third_party
  readme_text = string.Template(README_TEMPLATE).substitute(version=cldr_version,
                                                            tag=cldr_tag)
  with open(os.path.join(noto_cldr, 'README.third_party'), 'w') as f:
    f.write(readme_text)

  # remove/replace directories
  for subdir in CLDR_SUBDIRS:
    src = os.path.join(cldr_repo, subdir)
    dst = os.path.join(noto_cldr, subdir)
    print 'replacing directory %s...' % subdir
    shutil.rmtree(dst)
    shutil.copytree(src, dst)

  # replace files
  for f in CLDR_FILES:
    print 'replacing file %s...' % f
    src = os.path.join(cldr_repo, f)
    dst = os.path.join(noto_cldr, f)
    shutil.copy(src, dst)

  # stage changes in cldr dir
  tool_utils.git_add_all(noto_cldr)

  # print commit message
  tag_string = (' tag %s' % cldr_tag) if cldr_tag else ''
  print 'Update CLDR data to SVN r%s%s.' % (cldr_version, tag_string)


def main():
  default_noto = notoconfig.values.get('noto')
  default_cldr = notoconfig.values.get('cldr')

  parser = argparse.ArgumentParser()
  parser.add_argument('--cldr', help='directory of local cldr svn repo (default %s)' %
                      default_cldr, default=default_cldr)
  parser.add_argument('--update_cldr', help='update cldr before running', action='store_true')
  parser.add_argument('--cldr_tag', help='tag name to use for cldr (default empty)', default='')
  parser.add_argument('--noto', help='directory of local noto git repo (default %s)' %
                      default_noto, default=default_noto)
  parser.add_argument('--branch', help='confirm current branch of noto git repo')
  args = parser.parse_args()

  if not args.cldr or not args.noto:
    print "Missing either or both of cldr and noto locations."
    return

  if args.branch:
    cur_branch = tool_utils.git_get_branch(args.noto)
    if cur_branch != args.branch:
      print "Expected branch '%s' but %s is in branch '%s'." % (args.branch, args.noto, cur_branch)
      return

  update_cldr(args.noto, args.cldr, args.update_cldr, args.cldr_tag)


if __name__ == '__main__':
    main()
