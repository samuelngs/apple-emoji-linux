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

"""Check Arimo/Tinos/Cousine fonts for metric compatibility with their
inspiration."""

import argparse
import os
from os import path
import re

from fontTools import ttLib

import cldr_data
import font_data
import lint_config
import render
import unicode_data

name_re = re.compile(r'(.+)-(.*)\.ttf')

family_map = {
    'Arimo': 'Arial',
    'Tinos': 'Times New Roman',
    'Cousine': 'Courier New'
}

style_map = {
    'Regular': '',
    'Bold': ' Bold',
    'Italic': ' Italic',
    'BoldItalic': ' Bold Italic'
}

_excluded_chars = None

def _get_excluded_chars():
  # we skip Arabic and Hebrew characters
  global _excluded_chars
  if not _excluded_chars:
    arabic_ranges = '[\u0600-\u06ff \u0750-\u077f \u08a0-\u08ff \ufb50-\ufdff \ufe70-\ufefc]'
    arabic_set = frozenset([ord(cp) for cp in cldr_data.unicode_set_string_to_list(arabic_ranges)])
    # includes sheqel sign, omit?
    hebrew_ranges = '[\u0590-\u05ff \u20aa \ufb1d-\ufb4f]'
    hebrew_set = frozenset([ord(cp) for cp in cldr_data.unicode_set_string_to_list(hebrew_ranges)])
    armenian_ranges = '[\u0530-\u058f \ufb13-\ufb17]'
    armenian_set = frozenset([ord(cp) for cp in cldr_data.unicode_set_string_to_list(armenian_ranges)])
    private_use_set = frozenset(range(0xe000, 0xf900))
    _excluded_chars = frozenset(arabic_set | hebrew_set | armenian_set | private_use_set)
  return _excluded_chars


def _get_class_defs(font):
  try:
    return font['GDEF'].table.GlyphClassDef.classDefs
  except (KeyError, AttributeError):
    return None


class FontCompare(object):
  test_names = frozenset(['cmap', 'advance', 'hhea', 'OS/2', 'bounds', 'gdef'])

  @staticmethod
  def check_test_list(test_list):
    if not test_list:
      return FontCompare.test_names

    enabled_tests = None
    failed = False
    for test in test_list:
      if test not in FontCompare.test_names:
        print 'unknown test: \'%s\'' % test
        failed = True
    if failed:
      print 'tests are: %s' % (','.join(sorted(FontCompare.test_names)))
      return None
    return frozenset(test_list)

  @staticmethod
  def get_codepoints(range_list):
    if not range_list:
      return None
    return lint_config.parse_int_ranges(range_list, True)

  def __init__(self, target, test, incremental, emit_config, ignored_cp, only_cp,
               enabled_tests):
    self.target = target
    self.test = test
    self.incremental = incremental # target is different version of same file
    self.emit_config = emit_config # generate config lines
    self.enabled_tests = enabled_tests or FontCompare.test_names

    self.target_cmap = font_data.get_cmap(target)
    self.test_cmap = font_data.get_cmap(test)

    target_chars = set(self.target_cmap.keys()) - _get_excluded_chars()
    if ignored_cp:
      target_chars -= ignored_cp
    if only_cp:
      target_chars &= only_cp
    self.target_chars = target_chars

    # Assume version has two decimal places, which MTI fonts do but Adobe's do not.
    target_version = font_data.printable_font_revision(target)
    test_version = font_data.printable_font_revision(test)

    target_names = font_data.get_name_records(target)
    test_names = font_data.get_name_records(test)
    self._log('target name: %s %s, version: %s' % (target_names[1], target_names[2], target_version))
    self._log('test name: %s %s, version %s' % (test_names[1], test_names[2], test_version))

    if emit_config:
      font_family = test_names[1]
      font_subfamily = test_names[2].replace(' ', '')
      self._config('name like %s; weight like %s; version == %s' %
                   (font_family, font_subfamily, test_version))

  def _log(self, msg):
    """Write a message that should not go to config output."""
    if not self.emit_config:
      print msg

  def _logerr(self, msg):
    """Write an error that should not go to config output."""
    # this is an error, but lint doesn't check for it, so no point in emitting a comment.
    if not self.emit_config:
      print msg

  def _err(self, msg):
    """Write a message that should go to config as a comment, or just be logged."""
    if self.emit_config:
      print '# ' + msg
    else:
      print msg

  def _config(self, msg):
    """Write a message that should go to config."""
    if self.emit_config:
      print msg

  def _check_attribute(self, target_obj, test_obj, attr):
    target_value = getattr(target_obj, attr)
    test_value = getattr(test_obj, attr)
    if target_value == test_value:
      return None
    return (attr, test_value, target_value)

  def _check_attributes(self, target_obj, test_obj, attr_list):
    result = []
    for a in attr_list:
      r = self._check_attribute(target_obj, test_obj, a)
      if r:
        result.append(r)
    return result

  def _test_gid(self, cp):
    return self.test.getGlyphID(self.test_cmap[cp], requireReal=True)

  def _target_gid(self, cp):
    return self.target.getGlyphID(self.target_cmap[cp], requireReal=True)

  def _cp_error_msg(self, cp, test_msg, target_msg):
    test_gid = self._test_gid(cp)
    target_gid = self._target_gid(cp)
    if self.emit_config:
      # omit character name for brevity
      return 'cp %04x (gid %d) %s but target (gid %d) %s' % (
          cp, test_gid, test_msg, target_gid, target_msg)
    else:
      cp_name = unicode_data.name(cp)
      return 'cp %04x (gid %d) %s but target (gid %d) %s (%s)' % (
          cp, test_gid, test_msg, target_gid, target_msg, cp_name)

  def _skip(self, test_name):
    if test_name in self.enabled_tests:
      self._log('Check %s' % test_name)
      return False
    return True

  def check_cmaps(self):
    if self._skip('cmap'):
      return
    self._log('target cmap size: %d, test cmap size: %d' % (
          len(self.target_cmap), len(self.test_cmap)))

    missing_chars = self.target_chars - set(self.test_cmap.keys())
    if missing_chars:
      self._logerr('Missing %d chars' % len(missing_chars))
      self._logerr(lint_config.write_int_ranges(missing_chars, True))

  def check_advances(self):
    if self._skip('advance'):
      return

    target_metrics = self.target['hmtx'].metrics
    test_metrics = self.test['hmtx'].metrics

    differences = []
    for cp in self.target_chars:
      if cp not in self.test_cmap:
        continue
      target_advance = target_metrics[self.target_cmap[cp]][0]
      test_advance = test_metrics[self.test_cmap[cp]][0]
      if target_advance != test_advance:
        differences.append((cp, test_advance, target_advance))

    # No current lint test requires specific advances of arbitrary glyphs.
    if differences:
      self._logerr('%d codepoints have advance differences' % len(differences))
      for cp, ta, fa in sorted(differences):
        self._logerr(self._cp_error_msg(cp, 'advance is %d' % fa, 'advance is %d' % ta))

  def check_hhea(self):
    if self._skip('hhea'):
      return

    target_hhea = self.target['hhea']
    test_hhea = self.test['hhea']
    failed_attrs = self._check_attributes(target_hhea, test_hhea, [
        'ascent', 'descent', 'lineGap'])

    if not failed_attrs:
      self._config('disable head/hhea')
      return

    for attr, test_val, target_val in sorted(failed_attrs):
      if self.emit_config:
        print 'enable head/hhea/%s' % attr.lower()
      else:
        print 'font hhea %s was %d but target was %d' % (attr, test_val, target_val)

  def check_os2(self):
    if self._skip('OS/2'):
      return

    target_os2 = self.target['OS/2']
    test_os2 = self.test['OS/2']
    attr_name_map = {
        'sTypoAscender': 'ascender',
        'sTypoDescender': 'descender',
        'sTypoLineGap': 'linegap'
        }
    failed_attrs = self._check_attributes(target_os2, test_os2, attr_name_map.keys())
    if not failed_attrs:
      self._config('disable head/os2')
      return

    for attr, test_val, target_val in sorted(failed_attrs):
      if self.emit_config:
        print 'enable head/os2/%s' % attr_name_map[attr]
      else:
        print 'font OS/2 %s was %d but target was %d' % (attr, test_val, target_val)

  def check_glyph_bounds(self):
    # Don't compare the actual bounds, but whether they exceed the limits when the target
    # font does not.
    if self._skip('bounds'):
      return

    target_glyphset = self.target.getGlyphSet()
    test_glyphset = self.test.getGlyphSet()

    target_max = self.target['OS/2'].usWinAscent
    test_max = self.test['OS/2'].usWinAscent
    target_min = -self.target['OS/2'].usWinDescent
    test_min = -self.test['OS/2'].usWinDescent

    # We need to align the glyph ids, but once we get past the cmap it gets more and more
    # complicated to do this.  For now we'll just check the directly mapped glyphs.
    differences = []
    for cp in self.target_chars:
      if cp not in self.test_cmap:
        continue
      target_glyph_name = self.target_cmap[cp]
      test_glyph_name = self.test_cmap[cp]
      target_ttglyph = target_glyphset[target_glyph_name]
      test_ttglyph = test_glyphset[test_glyph_name]
      target_ymin, target_ymax = render.get_glyph_cleaned_extents(
          target_ttglyph, target_glyphset)
      test_ymin, test_ymax = render.get_glyph_cleaned_extents(
          test_ttglyph, test_glyphset)
      target_exceeds_max = target_ymax > target_max
      target_exceeds_min = target_ymin < target_min
      test_exceeds_max = test_ymax > test_max
      test_exceeds_min = test_ymin < test_min
      max_failure = test_exceeds_max and not target_exceeds_max
      min_failure = test_exceeds_min and not target_exceeds_min
      if max_failure or min_failure:
        differences.append((cp, max_failure, test_ymax, min_failure, test_ymin))

    if not differences:
      self._config('disable bounds/glyph')
      return

    self._err('%d glyphs have bounds errors' % len(differences))
    self._err('glyph bounds limits max %d, min %d' % (test_max, test_min))

    max_failures = []
    min_failures = []
    for cp, max_failure, ymax, min_failure, ymin in sorted(differences):
      if max_failure:
        self._err(self._cp_error_msg(cp, 'above max (%d)' % ymax, 'is not'))
        if self.emit_config:
          test_gid = self._test_gid(cp)
          max_failures.append(test_gid)
      if min_failure:
        self._err(self._cp_error_msg(cp, 'below min (%d)' % ymin, 'is not'))
        if self.emit_config:
          test_gid = self._test_gid(cp)
          min_failures.append(test_gid)
    if self.emit_config:
      if max_failures:
        self._config('enable bounds/glyph/ymax only gid %s' %
                     lint_config.write_int_ranges(max_failures, False))
      if min_failures:
        self._config('enable bounds/glyph/ymin only gid %s' %
                     lint_config.write_int_ranges(min_failures, False))


  def _check_gdef_class_defs(self, mark_glyphs):
    """Return False if we cannot check classDef-related info."""
    self._log('Check gdef classDefs')

    target_class_defs = _get_class_defs(self.target)
    test_class_defs = _get_class_defs(self.test)

    if mark_glyphs:
      if not target_class_defs:
        self._err('Have mark glyphs, but target does not have classDefs table.')
        self._config('exclude /gdef/classdef/not_present')
      if not test_class_defs:
        self._logerr('Have mark glyphs, but test does not have classDefs table.')

    if (target_class_defs is not None) != (test_class_defs is not None):
      if target_class_defs:
        self._logerr('Target has classDefs but test does not.')
      else:
        self._logerr('Test has classDefs but target does not.')
      return False

    return bool(target_class_defs)

  def _check_gdef_marks(self, mark_glyphs):
    self._log('Check gdef marks')

    if not mark_glyphs:
      self._log('No mark glyphs in target')
      return

    target_class_defs = _get_class_defs(self.target)
    test_class_defs = _get_class_defs(self.test)
    assert target_class_defs and test_class_defs

    differences = []
    for cp in mark_glyphs:
      if not cp in self.test_cmap:
        continue
      target_glyph = self.target_cmap[cp]
      test_glyph = self.test_cmap[cp]
      if target_glyph in target_class_defs and test_glyph not in test_class_defs:
        differences.append((cp, -1))
      else:
        target_glyph_class = target_class_defs[target_glyph]
        test_glyph_class = test_class_defs[test_glyph]
        if target_glyph_class == 3 and test_glyph_class != 3:
          differences.append((cp, test_glyph_class))

    if differences:
      self._err('%d mark glyphs have classDef errors' % len(differences))
      missing_list = []
      incorrect_list = []
      for cp, gc in sorted(differences):
        if gc == -1:
          self._err(self._cp_error_msg(cp, 'has no classDef', 'does'))
          missing_list.append(cp)
        else:
          self._err(self._cp_error_msg(
              cp, 'has non-combining-mark glyph class %d' % gc, 'is correct'))
          incorrect_list.append(cp)

      if missing_list:
        self._config('enable gdef/classdef/unlisted only cp %s' %
                     lint_config.write_int_ranges(missing_list, True))
      if incorrect_list:
        self._config('enable gdef/classdef/combining_mismatch only cp %s' %
                     lint_config.write_int_ranges(incorrect_list, True))

  def _check_gdef_combining(self):
    self._log('Check gdef combining')

    target_class_defs = _get_class_defs(self.target)
    test_class_defs = _get_class_defs(self.test)
    assert target_class_defs and test_class_defs

    differences = []
    for cp in self.target_chars:
      if not cp in self.test_cmap:
        continue
      target_glyph = self.target_cmap[cp]
      test_glyph = self.test_cmap[cp]
      target_class = target_class_defs.get(target_glyph, -1)
      test_class = test_class_defs.get(test_glyph, -1)
      if target_class != test_class:
        differences.append((cp, test_class, target_class))

    if differences:
      cp_list = []
      self._err('%d glyphs have classDef differences' % len(differences))
      for cp, test_class, target_class in sorted(differences):
        target_msg = 'has class %d' % target_class if target_class != -1 else 'not in classDef'
        test_msg = 'has class %d' % test_class if test_class != -1 else 'not in classDef'
        self._err(self._cp_error_msg(cp, test_msg, target_msg))
        cp_list.append(cp)

      self._config('enable gdef/classdef/not_combining_mismatch only cp %s' %
                   lint_config.write_int_ranges(cp_list, True))

  def check_gdef(self):
    if self._skip('gdef'):
      return

    mark_glyphs = [cp for cp in self.target_chars if unicode_data.category(cp) == 'Mn']
    if self._check_gdef_class_defs(mark_glyphs):
      self._check_gdef_marks(mark_glyphs)
      self._check_gdef_combining()

  def check_all(self):
    self.check_cmaps()
    self.check_advances()
    self.check_hhea()
    self.check_os2()
    self.check_glyph_bounds()
    self.check_gdef()


def check_font(target_file, test_file, incremental_version=False, emit_config=False,
               reverse=False, ignored_cp=None, only_cp=None, enabled_tests=None):
  target = ttLib.TTFont(target_file)
  test = ttLib.TTFont(test_file)
  if reverse:
    print 'reversing comparison'
    temp = target
    target = test
    test = temp

  print
  if not emit_config:
    print 'target is previous version' if incremental_version else 'target is reference font'
  FontCompare(target, test, incremental_version, emit_config, ignored_cp, only_cp,
              enabled_tests).check_all()


def get_reference_name_1(name):
    m = name_re.match(name)
    if not m:
      raise ValueError('font name %s does not match expected pattern' % name)
    family = m.group(1)
    style = m.group(2)

    target_family = family_map.get(family)
    if not target_family:
      raise ValueError('unrecognized font family %s' % family)

    target_style = style_map.get(style)
    if target_style is None:
      raise ValueError('unrecognized style \'%s\'' % style)

    return target_family + target_style + '.ttf'


_ref_name_2_map = {
    'Arimo-Regular.ttf': 'arial.ttf',
    'Arimo-Bold.ttf': 'arialbd.ttf',
    'Arimo-Italic.ttf': 'ariali.ttf',
    'Arimo-BoldItalic.ttf': 'arialbi.ttf',
    'Cousine-Regular.ttf': 'cour.ttf',
    'Cousine-Bold.ttf': 'courbd.ttf',
    'Cousine-Italic.ttf': 'couri.ttf',
    'Cousine-BoldItalic.ttf': 'courbi.ttf',
    'Tinos-Regular.ttf': 'times.ttf',
    'Tinos-Bold.ttf': 'timesbd.ttf',
    'Tinos-Italic.ttf': 'timesi.ttf',
    'Tinos-BoldItalic.ttf': 'timesbi.ttf'
}

def get_reference_name_2(name):
  return _ref_name_2_map.get(name)


def get_target_path(name, target_dir):
  target_name = get_reference_name_2(name)
  if not target_name:
    raise ValueError('could not find target name for %s' % name)
  target_path = path.join(target_dir, target_name)
  if not path.isfile(target_path):
    # fall back
    target_name = get_reference_name_1(name)
    target_path = path.join(target_dir, target_name)
  return target_path


def check_fonts(target_dir, fonts, incremental_version=False, emit_config=False, reverse=False,
                ignored_cp=None, only_cp=None, enabled_tests=None):
  for font in fonts:
    target_name = path.basename(font)
    if not incremental_version:
      target_path = get_target_path(target_name, target_dir)
    else:
      target_path = path.join(target_dir, target_name)

    if not path.isfile(target_path):
      raise ValueError('could not find %s in target dir %s' % (
          target_name, target_dir))

    check_font(target_path, font, incremental_version, emit_config, reverse, ignored_cp,
               only_cp, enabled_tests)


def main():
  default_target = '/usr/local/google/home/dougfelt/msfonts'

  parser = argparse.ArgumentParser()
  parser.add_argument('fonts', metavar='font', nargs='+', help='fonts to check')
  parser.add_argument('-t', '--target', metavar='dir', help='target font dir (default %s)' %
                      default_target, default=default_target)
  parser.add_argument('-iv', '--incremental_version', help='target font is a previous drop from MTI',
                      action='store_true')
  parser.add_argument('-c', '--config', help='emit config spec', action='store_true')
  parser.add_argument('--test', metavar='test',  help='test only named tests (%s)' %
                      sorted(FontCompare.test_names), nargs='+')
  parser.add_argument('-r', '--reverse', help='reverse direction of comparison', action='store_true')
  parser.add_argument('-ic', '--ignore_codepoints', metavar = 'ranges',
                      help='report no errors on these codepoints (hex ranges separated by space)')
  parser.add_argument('-oc', '--only_codepoints', metavar = 'ranges',
                      help='only report errors on these codepoints (hex ranges separated by space)')
  args = parser.parse_args()

  enabled_tests = FontCompare.check_test_list(args.test)
  if not enabled_tests:
    return

  ignored_cp = FontCompare.get_codepoints(args.ignore_codepoints)
  only_cp = FontCompare.get_codepoints(args.only_codepoints)

  check_fonts(args.target, args.fonts, args.incremental_version, args.config, args.reverse,
              ignored_cp, only_cp, enabled_tests)


if __name__ == "__main__":
    main()
