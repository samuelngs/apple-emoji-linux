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

"""Autofix phase 3 binaries, and autohint.

Quick tool to make fixes to some fonts that are 'ok for release' but
still have issues.  Main goal here is to autohint fonts that can be
hinted.  We also put more info into the version string.
"""

# TODO: ideally, we don't autofix at all, but if we continue to do this
# it would be better to unify the lint checks and the autofix code to
# ensure they agree in their expectations.

import argparse
import datetime
import glob
import os
from os import path
import re
import subprocess

from fontTools import ttLib

from nototools import font_data
from nototools import noto_data
from nototools import noto_fonts
from nototools import tool_utils


_new_version_re = re.compile(r'^(?:keep|[12]\.\d{3})$')

def _check_version(version):
  if not (version is None or _new_version_re.match(version)):
    raise Exception(
        'version "%s" did not match regex "%s"' % (
            version, _new_version_re.pattern))


_version_info_re = re.compile(
    r'GOOG;noto-(?:fonts(?:-alpha)?|source):(\d{4})(\d{2})(\d{2}):([0-9a-f]{12})')

def _check_version_info(version_info):
  """ensure version info looks reasonable, for example:
  'GOOG;noto-fonts:20170220:a8a215d2e889'.  Raise an exception
  if it does not."""
  m = _version_info_re.match(version_info)
  if not m:
    raise Exception('version info "%s" did not match regex "%s"' % (
        version_info, _version_info_re.pattern))
  year = int(m.group(1))
  month = int(m.group(2))
  day = int(m.group(3))
  commit_hash = m.group(4)
  today = datetime.date.today()
  if 2017 <= year:
    try:
      encoded_date = datetime.date(year, month, day)
    except Exception as e:
      raise Exception(
          '%04d-%02d-%02d in %s is not a valid date' % (
              year, month, day, version_info))
    if encoded_date > today:
      raise Exception('%s in %s is after the current date' % (
          encoded_date, version_info))
  else:
    raise Exception('date in %s appears too far in the past' % version_info)


def _get_version_info(fonts):
  """If fonts are all from noto-fonts, use information from the current
  state of the repo to build a version string.  Otherwise return None."""

  # add '/' to distinguish between noto-fonts/ and noto-fonts-alpha/
  for repo_tag in ['[fonts]', '[fonts_alpha]', '[source]']:
    prefix = tool_utils.resolve_path(repo_tag) + '/'
    print 'trying prefix "%s"' % prefix
    if all(tool_utils.resolve_path(f).startswith(prefix) for f in fonts):
      return _get_fonts_repo_version_info(repo_tag)
    # else report the first failure
    for f in fonts:
      if not tool_utils.resolve_path(f).startswith(prefix):
        print '# failed at "%s"' % tool_utils.resolve_path(f)
        break

  print 'no prefix succeeded'
  return None


def _get_fonts_repo_version_info(repo_tag):
  prefix = tool_utils.resolve_path(repo_tag)

  commit, date, commit_msg = tool_utils.git_head_commit(prefix)

  # check that commit is on the upstream master
  if not tool_utils.git_check_remote_commit(prefix, commit):
    raise Exception(
        'commit %s (%s) not on upstream master branch' % (
            commit[:12], commit_msg.splitlines()[0].strip()))

  date_re = re.compile(r'(\d{4})-(\d{2})-(\d{2})')
  m = date_re.match(date)
  if not m:
    raise Exception('could not match "%s" with "%s"' % (date, date_re.pattern))
  ymd = ''.join(m.groups())

  # hack tag to get the formal repo name.  strip enclosing brackets...
  repo_name = 'noto-' + repo_tag[1:-1].replace('_', '-')
  return 'GOOG;%s:%s:%s' % (repo_name, ymd, commit[:12])


def _check_autohint(script):
  if script and not(
      script in ['no-script'] or script in noto_data.HINTED_SCRIPTS):
    raise Exception('not a hintable script: "%s"' % script)


def _expand_font_names(font_names, result=None):
  """font names can include names of files containing a list of names, open
  those recursively and add to the set."""
  def strip_comment(line):
    ix = line.find('#')
    if ix != -1:
      line = line[:ix]
    return line.strip()

  if result is None:
    result = set()
  for n in font_names:
    if not n.startswith('@'):
      result.add(n)
    else:
      filename = n[1:]
      with open(filename, 'r') as f:
        new_names = f.readlines()
      new_names = [strip_comment(n) for n in new_names]
      new_names = [n for n in new_names if n]
      _expand_font_names(new_names, result)
  return result

def autofix_fonts(
    font_names, src_root, dst_dir, release_dir, version, version_info, autohint,
    dry_run):
  dst_dir = tool_utils.resolve_path(dst_dir)
  dst_dir = tool_utils.ensure_dir_exists(dst_dir)

  font_names = sorted(_expand_font_names(font_names))
  print 'Processing %d fonts\n  %s' % (
      len(font_names), '\n  '.join(font_names[:5]) + '...')

  src_root = tool_utils.resolve_path(src_root)
  print 'Src root: %s' % src_root
  print 'Dest dir: %s' % dst_dir

  if release_dir is None:
    rel_dir = None
  else:
    rel_dir = tool_utils.resolve_path(release_dir)
    if not path.isdir(rel_dir):
      raise Exception('release dir "%s" does not exist' % rel_dir)

  if (version_info is None or version_info == '[fonts]' or
      version_info == '[fonts_alpha]'):
    if version_info is None:
      version_info = _get_version_info(font_names)
    else:
      version_info = _get_fonts_repo_version_info()

    if not version_info:
      raise Exception('could not compute version info from fonts')
    print 'Computed version_info: %s' % version_info
  else:
    _check_version_info(version_info)

  _check_version(version)
  _check_autohint(autohint)

  if dry_run:
    print '*** dry run %s***' % ('(autohint) ' if autohint else '')
  for f in font_names:
    f = path.join(src_root, f)
    fix_font(f, dst_dir, rel_dir, version, version_info, autohint, dry_run)


_version_re = re.compile(r'Version (\d+\.\d{2,3})')
def _extract_version(font):
  # Sometimes the fontRevision and version string don't match, and the
  # fontRevision is bad, so we prefer the version string.
  version = font_data.font_version(font)
  m = _version_re.match(version)
  if not m:
    raise Exception('could not match existing version "%s"' % version)
  return m.group(1)


def _version_str_to_mm(version):
  # return the pair of int values for the major and minor versions, plus
  # a boolean indicating whether this was a phase 2 version number.  That's
  # a hack, it is a phase 2 number if the initial release version < 2 or
  # if the minor version had two digits.  Of course this doesn't apply to
  # cjk but we shouldn't run this on cjk anyway.
  parts = version.split('.')
  mm = [int(n) for n in parts]
  is_phase2 = mm[0] < 2 or len(parts[1]) == 2
  return mm, is_phase2


def _mm_to_version_str(mm):
  return ('%d.%02d' if mm[0] == 1 else '%d.%03d') % tuple(mm)


def get_new_version(font, relfont, nversion):
  """Return a new version number.  font is the font we're updating,
  relfont is the released version of this font if it exists, or None,
  and nversion is the new version, 'keep', or None. If a new version is
  passed to us, use it unless it is lower than either existing version,
  in which case we raise an exception.  If the version is 'keep' and
  there is an existing release version, keep that.  Otherwise bump the
  release version, if it exists, or convert the old version to a 2.0 version
  as appropriate.  If the old version is a 2.0 version (e.g. Armenian was
  was '2.30' in phase 2), that value is mapped to 2.40."""

  version = _extract_version(font)
  rversion = _extract_version(relfont) if relfont else None

  if rversion:
    print 'Existing release version: %s' % rversion
    r_mm, r_is_phase2 = _version_str_to_mm(rversion)

  mm, is_phase2 = _version_str_to_mm(version)
  if nversion is not None:
    if nversion == 'keep':
      if rversion is not None:
        if r_is_phase2:
          print 'Warning, keeping phase 2 release version %s' % rversion
        return rversion
    else:
      n_mm, n_is_phase_2 = _version_str_to_mm(nversion)
      if n_is_phase2:
        raise Exception('bad phase 3 minor version ("%s")' % nversion)
      if rversion is not None:
        if n_mm < r_mm:
          raise Exception(
              'new version %s < release version %s' % (nversion, rversion))
      if n_mm < mm:
        raise Exception(
            'new version %s < old version %s' % (nversion, version))
      return nversion

  # No new verson string, so compute one.  If we have a phase 3 version,
  # start with that.  If it's a phase 2 number with a major version of 2,
  # force minor to '040' which is higher than any of the phase 2 minor
  # versions in this category.  Else if major < 2, bump to 2.  Else just
  # bump the release minor version.
  if rversion:
    if r_is_phase2:
      return '2.040' if r_mm[0] == 2 else '2.000'
    if r_mm[1] == 999:
      raise Exception('cannot bump version %s' % rversion)
    r_mm[1] += 1
    return _mm_to_version_str(r_mm)

  if mm[0] > 2:
    raise Exception('existing version too high "%s"' % version)

  if nversion == 'keep':
    return version

  return '2.000'



def _get_font_info(f):
  font_info = noto_fonts.get_noto_font(f)
  if not font_info:
    raise Exception('not a noto font: "%s"' % f)
  return font_info


def _is_ui_metrics(f):
  return _get_font_info(f).is_UI_metrics


def _autohint_code(f, script):
  """Return 'not-hinted' if we don't hint this, else return the ttfautohint
  code, which might be None if ttfautohint doesn't support the script.
  Note that LGC and MONO return None."""

  if script == 'no-script':
    return script
  if not script:
    script = noto_fonts.script_key_to_primary_script(_get_font_info(f).script)
  return noto_data.HINTED_SCRIPTS.get(script, 'not-hinted')


def autohint_font(src, dst, script, dry_run):
  code = _autohint_code(src, script)
  if code == 'not-hinted':
    print 'Warning: no hinting information for %s, script %s' % (src, script)
    return

  if code == None:
    print 'Warning: unable to autohint %s' % src
    return

  if code == 'no-script':
    args = ['ttfautohint', '-t', '-W', src, dst]
  else:
    args = ['ttfautohint', '-t', '-W', '-f', code, src, dst]
  if dry_run:
    print 'dry run would autohint:\n  "%s"' % ' '.join(args)
    return

  hinted_dir = tool_utils.ensure_dir_exists(path.dirname(dst))
  try:
    subprocess.check_call(args)
  except Exception as e:
    print '### failed to autohint %s' % src
    # we failed to autohint, let's continue anyway
    # however autohint will have left an empty file there, remove it.
    try:
      os.remove(dst)
    except:
      pass


  print 'wrote autohinted %s using %s' % (dst, code)


def _alert(val_name, cur_val, new_val):
  if isinstance(cur_val, basestring):
    tmpl = 'update %s\n  from: "%s"\n    to: "%s"'
  else:
    tmpl = 'update %s\n  from: %4d\n    to: %4d'
  print  tmpl % (val_name, cur_val, new_val)


def _alert_and_check(val_name, cur_val, expected_val, max_diff):
  """if max_diff >= 0, curval must be <= expected_val + maxdiff,
  else curval must be >= expected_val + maxdiff"""
  _alert(val_name, cur_val, expected_val)
  if max_diff >= 0:
    err = cur_val > expected_val + max_diff
  else:
    err = cur_val < expected_val + max_diff
  if err:
    raise Exception(
        'bad difference in expected and actual %s' % val_name)


def _get_release_fontpath(f, rel_dir):
  """If rel_dir is not None, look for a font under 'hinted' or 'unhinted'
  depending on which of these is in the path f.  If neither is in f,
  look under rel_dir, and then rel_dir/unhinted.  If a match is found,
  return the path."""

  if rel_dir is None:
    return None

  hh = True
  bn = path.basename(f)
  if '/hinted/' in f:
    fp = path.join(rel_dir, 'hinted', bn)
  elif '/unhinted/' in f:
    fp = path.join(rel_dir, 'unhinted', bn)
  else:
    hh = False
    fp = path.join(rel_dir, bn)

  if path.isfile(fp):
    return fp

  if hh:
    return None

  fp = path.join(rel_dir, 'unhinted', bn)
  return fp if path.isfile(fp) else None


def _get_release_font(f, rel_dir):
  fp = _get_release_fontpath(f, rel_dir)
  return None if fp is None else ttLib.TTFont(fp)


def fix_font(f, dst_dir, rel_dir, version, version_info, autohint, dry_run):
  print '\n-----\nfont:', f
  font = ttLib.TTFont(f)

  relfont = _get_release_font(f, rel_dir)
  expected_font_revision = get_new_version(font, relfont, version)
  if expected_font_revision != None:
    font_revision = font_data.printable_font_revision(font, 3)
    if font_revision != expected_font_revision:
      _alert('revision', font_revision, expected_font_revision)
      font['head'].fontRevision = float(expected_font_revision)

    names = font_data.get_name_records(font)
    NAME_ID = 5
    font_version = names[NAME_ID]
    expected_version = (
        'Version %s;%s' % (expected_font_revision, version_info))
    if font_version != expected_version:
      _alert('version string', font_version, expected_version)
      font_data.set_name_record(font, NAME_ID, expected_version)

  expected_upem = 1000
  upem = font['head'].unitsPerEm
  if upem != expected_upem:
    print 'expected %d upem but got %d upem' % (expected_upem, upem)

  if _is_ui_metrics(f):
    if upem == 2048:
      expected_ascent = 2163
      expected_descent = -555
    elif upem == 1000:
      expected_ascent = 1069
      expected_descent = -293
    else:
      raise Exception('no expected ui ascent/descent for upem: %d' % upem)

    font_ascent = font['hhea'].ascent
    font_descent = font['hhea'].descent
    if font_ascent != expected_ascent:
      _alert_and_check('ascent', font_ascent, expected_ascent, 2)
      font['hhea'].ascent = expected_ascent
      font['OS/2'].sTypoAscender = expected_ascent
      font['OS/2'].usWinAscent = expected_ascent

    if font_descent != expected_descent:
      _alert_and_check('descent', font_descent, expected_descent, -2)
      font['hhea'].descent = expected_descent
      font['OS/2'].sTypoDescender = expected_descent
      font['OS/2'].usWinDescent = -expected_descent

  tool_utils.ensure_dir_exists(path.join(dst_dir, 'unhinted'))

  fname = path.basename(f)
  udst = path.join(dst_dir, 'unhinted', fname)
  if dry_run:
    print 'dry run would write:\n  "%s"' % udst
  else:
    font.save(udst)
    print 'wrote %s' % udst

  if autohint:
    hdst = path.join(dst_dir, 'hinted', fname)
    autohint_font(udst, hdst, autohint, dry_run)


def main():
  parser = argparse.ArgumentParser()
  parser.add_argument(
      '-d', '--dest_dir', help='directory into which to write swatted fonts',
      metavar='dir', default='swatted')
  parser.add_argument(
      '-r', '--release_dir', help='directory containing release fonts (opt '
      ' [fonts])', metavar='dir', nargs='?', const='[fonts]')
  parser.add_argument(
      '-f', '--fonts', help='paths of fonts to swat (to fetch from a file'
      'use "@filename")', metavar='font', nargs='+')
  parser.add_argument(
      '-s', '--src_root', help='common root of all paths of fonts',
      default='')
  parser.add_argument(
      '-i', '--version_info', help='version info string (opt [fonts] to use '
      'fonts info)', metavar='str', nargs='?', const='[fonts]')
  parser.add_argument(
      '-v', '--version', help='force version (opt keep)',
      metavar='ver', nargs='?', const='keep')
  parser.add_argument(
      '-a', '--autohint', help='autohint fonts (opt no-script)',
      metavar='code', nargs='?', const='no-script')
  parser.add_argument(
      '-n', '--dry_run', help='process checks but don\'t fix',
      action='store_true')
  args = parser.parse_args()

  autofix_fonts(
      args.fonts, args.src_root, args.dest_dir, args.release_dir, args.version,
      args.version_info, args.autohint, args.dry_run)


if __name__ == '__main__':
  main()
