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

"""Swat copyright, bump version."""


import argparse
import collections
import os
from os import path
import re

from nototools import autofix_for_release
from nototools import cldr_data
from nototools import font_data
from nototools import noto_fonts
from nototools import ttc_utils

from fontTools import ttLib
from fontTools import misc

_COPYRIGHT_ID = 0
_VERSION_ID = 5
_TRADEMARK_ID = 7
_MANUFACTURER_ID = 8
_DESIGNER_ID = 9
_DESCRIPTION_ID = 10
_VENDOR_URL_ID = 11
_DESIGNER_URL_ID = 12
_LICENSE_ID = 13
_LICENSE_URL_ID = 14

_NAME_ID_LABELS = {
    _COPYRIGHT_ID: 'copyright',
    _VERSION_ID: 'version',
    _TRADEMARK_ID: 'trademark',
    _MANUFACTURER_ID: 'manufacturer',
    _DESIGNER_ID: 'designer',
    _DESCRIPTION_ID: 'description',
    _VENDOR_URL_ID: 'vendor url',
    _DESIGNER_URL_ID: 'designer url',
    _LICENSE_ID: 'license',
    _LICENSE_URL_ID: 'license url',
}

_SIL_LICENSE = (
    'This Font Software is licensed under the SIL Open Font License, '
    'Version 1.1. This Font Software is distributed on an "AS IS" '
    'BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express '
    'or implied. See the SIL Open Font License for the specific language, '
    'permissions and limitations governing your use of this Font Software.')

_SIL_LICENSE_URL = "http://scripts.sil.org/OFL"

_NOTO_URL = "http://www.google.com/get/noto/"

_SCRIPT_KEYS = {
    'Aran': 'Urdu',
    'HST': 'Historic',
    'LGC': ''
}

_FAMILY_KEYS = {
  'Arimo': 'a',
  'Cousine':'b',
  'Tinos': 'c',
  'Noto': 'd',
}

_HINTED_TABLES_TO_DROP = autofix_for_release.TABLES_TO_DROP
_UNHINTED_TABLES_TO_DROP = (autofix_for_release.TABLES_TO_DROP +
                            ['fpgm', 'prep', 'cvt'])

_changes = {}

_autofix = collections.defaultdict(list)

_ttc_fonts = {}

def _swat_fonts(dst_root, dry_run):
  def family_key(family):
      return _FAMILY_KEYS.get(family, 'x' + family)
  def script_key(script):
      return (_SCRIPT_KEYS.get(script, None) or
              cldr_data.get_english_script_name(script))
  def compare_key(font):
    return (family_key(font.family),
            font.style,
            script_key(font.script),
            'a' if font.is_hinted else '',
            font.variant if font.variant else '',
            'UI' if font.is_UI else '',
            '' if font.weight == 'Regular' else font.weight,
            font.slope or '',
            font.fmt)
  fonts = noto_fonts.get_noto_fonts()
  for font in sorted(fonts, key=compare_key):
    _swat_font(font, dst_root, dry_run)

  if _ttc_fonts:
    _construct_ttc_fonts(fonts, dst_root, dry_run)


def _noto_relative_path(filepath):
  """Return relative path from some noto root, or None"""
  x = filepath.find('noto-fonts')
  if x == -1:
    x = filepath.find('noto-cjk')
    if x == -1:
      x = filepath.find('noto-emoji')
  if x == -1:
    return None
  return filepath[x:]


def get_bumped_version(ttfont, is_hinted=None):
  """Return bumped values for the header and name tables."""

  names = font_data.get_name_records(ttfont)
  version = names[_VERSION_ID]
  m = re.match(r'Version (\d{1,5})\.(\d{1,5})( uh)?(;.*)?', version)
  if not m:
    print '! Could not match version string (%s)' % version
    return None, None

  major_version = m.group(1)
  minor_version = m.group(2)
  print 'old version: "%s"' % version
  if is_hinted == None:
    is_hinted = not bool(m.group(3))
    print 'computed hinted = %s' % is_hinted

  version_remainder = m.group(4)
  accuracy = len(minor_version)
  print_revision = font_data.printable_font_revision(ttfont, accuracy)
  # sanity check
  expected_revision = major_version + '.' + minor_version
  if expected_revision != print_revision:
    raise ValueError('! Expected revision \'%s\' but got revision \'%s\'' % (
        expected_revision, print_revision))

  # bump the minor version keeping significant digits:
  new_minor_version = str(int(minor_version) + 1).zfill(accuracy)
  new_revision = major_version + '.' + new_minor_version
  print 'Update revision from  \'%s\' to \'%s\'' % (
      expected_revision, new_revision)
  # double check we are going to properly round-trip this value
  float_revision = float(new_revision)
  fixed_revision = misc.fixedTools.floatToFixed(float_revision, 16)
  rt_float_rev = misc.fixedTools.fixedToFloat(fixed_revision, 16)
  rt_float_rev_int = int(rt_float_rev)
  rt_float_rev_frac = int(round((rt_float_rev - rt_float_rev_int) *
                                10 ** accuracy))
  rt_new_revision = (str(rt_float_rev_int) + '.' +
                     str(rt_float_rev_frac).zfill(accuracy))
  if new_revision != rt_new_revision:
    raise ValueError(
        '! Could not update new revision, expected \'%s\' but got \'%s\'' % (
        new_revision, rt_new_revision))

  new_version_string = 'Version ' + new_revision
  if not is_hinted:
    new_version_string += ' uh'
  if version_remainder:
    new_version_string += version_remainder

  return float_revision, new_version_string


def _swat_font(noto_font, dst_root, dry_run):
  filepath = noto_font.filepath
  basename = path.basename(filepath)
  if noto_font.is_cjk:
    print '# Skipping cjk font %s' % basename
    return
  if noto_font.fmt == 'ttc':
    print '# Deferring ttc font %s' % basename
    _ttc_fonts[noto_font] = ttc_utils.ttcfile_filenames(filepath)
    return

  ttfont = ttLib.TTFont(filepath, fontNumber=0)

  names = font_data.get_name_records(ttfont)

  # create relative root path
  rel_filepath = _noto_relative_path(filepath)
  if not rel_filepath:
    raise ValueError('Could not identify noto root of %s' % filepath)

  print '-----\nUpdating %s' % rel_filepath

  dst_file = path.join(dst_root, rel_filepath)

  try:
    new_revision, new_version_string = get_bumped_version(
        ttfont, noto_font.is_hinted)
  except ValueError as e:
    print e
    return

  print '%s: %s' % ('Would write' if dry_run else 'Writing', dst_file)

  new_trademark = "%s is a trademark of Google Inc." % noto_font.family

  # description field should be set.
  # Roozbeh has note, make sure design field has information
  # on whether the font is hinted.
  # Missing in Lao and Khmer, default in Cham.
  if (cldr_data.get_english_script_name(noto_font.script) in
      ['Lao', 'Khmer', 'Cham']):
    new_description =  'Data %shinted.' % ('' if noto_font.is_hinted else 'un')
  # elif noto_font.vendor is 'Monotype':
  elif not noto_font.is_cjk and noto_font.family == 'Noto':
    new_description = (
      'Data %shinted. Designed by Monotype design team.' %
      ('' if noto_font.is_hinted else 'un'))
  else:
    new_description = None

  if re.match(r'^Copyright 201\d Google Inc. All Rights Reserved\.$',
              names[_COPYRIGHT_ID]):
    new_copyright = None
  else:
    new_copyright = '!!'

  if names.get(_DESIGNER_ID) in [
      'Steve Matteson',
      'Monotype Design Team',
      'Danh Hong',
      ]:
    new_designer = None
  elif names.get(_DESIGNER_ID) == 'Monotype Design team':
    new_designer = 'Monotype Design Team'
  elif (_DESIGNER_ID not in names
        and cldr_data.get_english_script_name(noto_font.script) == 'Khmer'):
    new_designer = 'Danh Hong'
  else:
    new_designer = '!!'

  if names.get(_DESIGNER_URL_ID) in [
      'http://www.monotype.com/studio',
      'http://www.khmertype.org',
      ]:
    new_designer_url = None
  elif names.get(_DESIGNER_URL_ID) in [
      'http://www.monotypeimaging.com/ProductsServices/TypeDesignerShowcase',
      ]:
    new_designer_url = 'http://www.monotype.com/studio'
  elif names.get(_DESIGNER_URL_ID) in [
      'http://www.khmertype.blogspot.com',
      'http://www.khmertype.blogspot.com/',
      'http://khmertype.blogspot.com/',
      'http://wwwkhmertype.blogspot.com.com/',
      ]:
    new_designer_url = 'http://www.khmertype.org'
  else:
    new_designer_url = '!!!'

  if names.get(_MANUFACTURER_ID) in [
      'Monotype Imaging Inc.',
      'Danh Hong',
      ]:
    new_manufacturer = None
  else:
    new_manufacturer = '!!!'

  def update(name_id, new, newText=None):
    old = names.get(name_id)
    if new and (new != old):
      if not dry_run and not '!!!' in new:
        font_data.set_name_record(ttfont, name_id, new, addIfMissing='win')

      label = _NAME_ID_LABELS[name_id]
      oldText = '\'%s\'' % old if old else 'None'
      newText = newText or ('\'%s\'' % new)
      print '%s:\n  old: %s\n  new: %s' % (label, oldText, newText or new)

      label_change = _changes.get(label)
      if not label_change:
        label_change = {}
        _changes[label] = label_change
      new_val_change = label_change.get(new)
      if not new_val_change:
        new_val_change = {}
        label_change[new] = new_val_change
      old_val_fonts = new_val_change.get(old)
      if not old_val_fonts:
        old_val_fonts = []
        new_val_change[old] = old_val_fonts
      old_val_fonts.append(noto_font.filepath)

  update(_COPYRIGHT_ID, new_copyright)
  update(_VERSION_ID, new_version_string)
  update(_TRADEMARK_ID, new_trademark)
  update(_MANUFACTURER_ID, new_manufacturer)
  update(_DESIGNER_ID, new_designer)
  update(_DESCRIPTION_ID, new_description)
  update(_VENDOR_URL_ID, _NOTO_URL)
  update(_DESIGNER_URL_ID, new_designer_url)
  update(_LICENSE_ID, _SIL_LICENSE, newText='(OFL)')
  update(_LICENSE_URL_ID, _SIL_LICENSE_URL)

  if autofix_for_release.fix_fstype(ttfont):
    _autofix['fstype'].append(noto_font.filepath)
  if autofix_for_release.fix_vendor_id(ttfont):
    _autofix['vendor_id'].append(noto_font.filepath)
  if autofix_for_release.fix_attachlist(ttfont):
    _autofix['attachlist'].append(noto_font.filepath)
  if noto_font.is_hinted:
    tables_to_drop = _HINTED_TABLES_TO_DROP
  else:
    tables_to_drop = _UNHINTED_TABLES_TO_DROP
    if autofix_for_release.drop_hints(ttfont):
      _autofix['drop_hints'].append(noto_font.filepath)
  if autofix_for_release.drop_tables(ttfont, tables_to_drop):
    _autofix['drop_tables'].append(noto_font.filepath)
  if noto_font.family == 'Noto':
    if autofix_for_release.fix_linegap(ttfont):
      _autofix['linegap'].append(noto_font.filepath)
  if autofix_for_release.fix_os2_unicoderange(ttfont):
    _autofix['os2_unicoderange'].append(noto_font.filepath)

  if dry_run:
    return

  ttfont['head'].fontRevision = float_revision

  dst_dir = path.dirname(dst_file)
  if not path.isdir(dst_dir):
    os.makedirs(dst_dir)
  ttfont.save(dst_file)
  print 'Wrote file.'


def _construct_ttc_fonts(fonts, dst_root, dry_run):
  # _ttc_fonts contains a map from a font path to a list of likely names
  # of the component fonts.  The component names are based off the
  # postscript name in the name table of the component, so 1) might not
  # accurately represent the font, and 2) don't indicate whether the
  # component is hinted.  We deal with the former by rejecting and
  # reporting ttcs where any name fails to match, and with the latter
  # by assuming all the components are hinted or not based on whether
  # the original is in a 'hinted' or 'unhinted' directory.

  # build a map from basename to a list of noto_font objects
  basename_to_fonts = collections.defaultdict(list)
  for font in fonts:
    if font.fmt != 'ttc':
      basename = path.basename(font.filepath)
      basename_to_fonts[basename].append(font)

  for ttcfont, components in sorted(_ttc_fonts.iteritems()):
    rel_filepath = _noto_relative_path(ttcfont.filepath)
    print '-----\nBuilding %s' % rel_filepath

    component_list = []
    # note the component order must match the original ttc, so
    # we must process in the provided order.
    for component in components:
      possible_components = basename_to_fonts.get(component)
      if not possible_components:
        print '! no match for component named %s in %s' % (
            component, rel_path)
        component_list = []
        break

      matched_possible_component = None
      for possible_component in possible_components:
        if possible_component.is_hinted == ttcfont.is_hinted:
          if matched_possible_component:
            print '! already matched possible component %s for %s' % (
                matched_possible_component.filename,
                possible_component_filename)
            matched_possible_component = None
            break
          matched_possible_component = possible_component
      if not matched_possible_component:
        print 'no matched component named %s' % component
        component_list = []
        break
      component_list.append(matched_possible_component)
    if not component_list:
      print '! cannot generate ttc font %s' % rel_path
      continue

    print 'components:\n  ' + '\n  '.join(
        _noto_relative_path(font.filepath) for font in component_list)
    if dry_run:
      continue

    dst_ttc = path.join(dst_root, rel_filepath)
    src_files = [path.join(dst_root, _noto_relative_path(font.filepath))
                 for font in component_list]
    ttc_utils.build_ttc(dst_ttc, src_files)
    print 'Built %s' % dst_ttc


def main():
  parser = argparse.ArgumentParser()
  parser.add_argument('-n', '--dry_run', help='Do not write fonts',
                      action='store_true')
  parser.add_argument('--dst_root',
                      help='root of destination (default /tmp/swat)',
                      metavar='dst', default='/tmp/swat')
  parser.add_argument('--details', help='show change details',
                      action='store_true')
  args = parser.parse_args()

  _swat_fonts(args.dst_root, args.dry_run)

  print '------\nchange summary\n'
  for name_key in sorted(_changes):
    print '%s:' % name_key
    new_vals = _changes[name_key]
    for new_val in sorted(new_vals):
      print '  change to \'%s\':' % new_val
      old_vals = new_vals[new_val]
      for old_val in sorted(old_vals):
        print '    from %s (%d files)%s' % (
            '\'%s\'' % old_val if old_val else 'None',
            len(old_vals[old_val]), ':' if args.details else '')
        if args.details:
          for file_name in sorted(old_vals[old_val]):
            x = file_name.rfind('/')
            if x > 0:
              x = file_name.rfind('/', 0, x)
            print '      ' + file_name[x:]

  print '------\nautofix summary\n'
  for fix_key in sorted(_autofix):
    fixed_files = _autofix[fix_key]
    print '%s (%d):' % (fix_key, len(fixed_files))
    for file_name in sorted(fixed_files):
      x = file_name.rfind('/')
      if x > 0:
        x = file_name.rfind('/', 0, x)
        print '    ' + file_name[x:]


if __name__ == "__main__":
    main()
