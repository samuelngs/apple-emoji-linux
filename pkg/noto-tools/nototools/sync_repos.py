#!/usr/bin/env python
#
# Copyright 2017 Google Inc. All rights reserved.
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

"""Sync the noto repos to the given tags.

This helps prepare for generating website data.  We have the option
of requiring that the noto-fonts, noto-emoji, and noto-cjk repos are at
tagged releases.  This tool lets you specify release names, ensures the
release names are valid, and checks out those releases.  Main exits with
error code 100 if there is a failure."""

import argparse
import sys

from nototools import tool_utils

_REPOS = 'fonts emoji cjk'.split()
_REPO_PATHS = [tool_utils.resolve_path('[%s]' % r) for r in _REPOS]

def noto_check_clean():
  errors = []
  for r, p in zip(_REPOS, _REPO_PATHS):
    if not tool_utils.git_is_clean(p):
      errors.append(r)

  if errors:
    print >> sys.stderr, '%s %s not clean' % (
        ' '.join(errors), 'is' if len(errors) == 1 else 'are')
    return False
  return True


def noto_checkout_master(dry_run=False):
  """Check out the noto repos at master.  Return True if ok, else log
  error and return False."""

  if not noto_check_clean():
    return False

  if not dry_run:
    for p in _REPO_PATHS:
      tool_utils.git_checkout(p, 'master')
  else:
    print 'would have checked out master in %s' % (', '.join(_REPOS))

  return True


def noto_checkout(
    fonts_tag='latest', emoji_tag='latest', cjk_tag='latest', verbose=False,
    dry_run=False):
  """Check out the noto repos at the provided tags.  Return True if ok,
  else log error and return False.  Default is 'latest' for the latest
  tag."""

  if not noto_check_clean():
    return False

  requested_tags = [fonts_tag, emoji_tag, cjk_tag]
  failed_tags = []
  resolved_tags = []
  for r, p, t in zip(_REPOS, _REPO_PATHS, requested_tags):
    found = False
    tag_info = tool_utils.git_tags(p)
    for _, tag, _ in tag_info:
      if t == 'latest' or tag == t:
        resolved_tags.append(tag)
        found = True
        break
    if not found:
      failed_tags.append('%s: %s' % (r, t))

  if failed_tags:
    print >> sys.stderr, 'failed to find:\n  %s' % '\n  '.join(failed_tags)
    return False

  if not dry_run:
    for p, t in zip(_REPO_PATHS, resolved_tags):
      tool_utils.git_checkout(p, t)

  if verbose or dry_run:
    print '%schecked out:\n  %s' % (
        'would have ' if dry_run else '',
        '\n  '.join('%s: %s' % (r, t) for r, t in zip(_REPOS, resolved_tags)))

  return True


def main():
  parser = argparse.ArgumentParser()
  parser.add_argument(
      '-f', '--fonts_tag', help='tag for noto fonts repo (default latest)',
      metavar='tag', default='latest')
  parser.add_argument(
      '-e', '--emoji_tag', help='tag for noto emoji repo (default latest)',
      metavar='tag', default='latest')
  parser.add_argument(
      '-c', '--cjk_tag', help='tag for noto cjk repo (default latest)',
      metavar='tag', default='latest')
  parser.add_argument(
      '-m', '--master', help='use master branch for all repos',
      action='store_true')
  parser.add_argument(
      '-v', '--verbose', help='report tags chosen on success',
      action='store_true')
  parser.add_argument(
      '-n', '--dry_run', help='report tags chosen but take no other action',
      action='store_true')

  args = parser.parse_args()

  if args.master:
    result = noto_checkout_master(args.dry_run)
  else:
    result = noto_checkout(
        fonts_tag=args.fonts_tag, emoji_tag=args.emoji_tag,
        cjk_tag=args.cjk_tag, verbose=args.verbose, dry_run=args.dry_run)
  sys.exit(0 if result else 100)


if __name__ == '__main__':
  main()
