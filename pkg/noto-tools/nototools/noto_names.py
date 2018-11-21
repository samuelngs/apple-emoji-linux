#!/usr/bin/env python
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

"""Determine how the names of members of noto families should be
represented.

There are two groups of routines, and a tool api.  One set of routines
generates information about family names from a collection of noto
fonts.  This information looks at all the subfamilies of a family and
generates a FamilyNameInfo object representing general information
about that family.  For instance, families with only regular/bold,
normal/italic subfamilies can use the original opentype name fields
and don't require preferred names.  These routines also read/write an xml
version of this data.

The other set of routines generates name information for a noto font,
using the family name info.  The family name info is required.  For
example, familes that have no_style_linking set will put Bold and Regular
in the original family name and not the subfamily.

The tool api lets you generate the family info file, and/or use it to
show how one or more fonts' names would be generated.

This of necessity incorporates noto naming conventions-- it expects
file names that follow noto conventions, and generates the corresponding
name table names.  So it is not useful for non-noto fonts.
"""

import argparse
import collections
import datetime
import glob
from os import path
import re
import sys

from nototools import cldr_data
from nototools import noto_fonts
from nototools import tool_utils
from nototools import unicode_data

from xml.etree import ElementTree as ET

# Standard values used in Noto fonts.

# Maximum number of characters in the original name field.
ORIGINAL_FAMILY_LIMIT = 32

# Regex values returned in NameTableData must start with ^ and end with $,
# since lint uses this to understand the value is a regex.
GOOGLE_COPYRIGHT_RE = r'^Copyright 20\d\d Google Inc. All Rights Reserved\.$'

ADOBE_COPYRIGHT_RE = (
    u"^Copyright \u00a9 2014(?:, 20\d\d)? Adobe Systems Incorporated "
    u"\(http://www.adobe.com/\)\.$")

NOTO_URL = "http://www.google.com/get/noto/"

SIL_LICENSE = (
    "This Font Software is licensed under the SIL Open Font License, "
    "Version 1.1. This Font Software is distributed on an \"AS IS\" "
    "BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express "
    "or implied. See the SIL Open Font License for the specific language, "
    "permissions and limitations governing your use of this Font Software.")

SIL_LICENSE_URL = "http://scripts.sil.org/OFL"

APACHE_LICENSE = "Licensed under the Apache License, Version 2.0"

APACHE_LICENSE_URL = "http://www.apache.org/licenses/LICENSE-2.0"

# default files where we store family name info
FAMILY_NAME_INFO_FILE='family_name_info.xml'
PHASE_2_FAMILY_NAME_INFO_FILE = '[tools]/nototools/data/family_name_info_p2.xml'
PHASE_3_FAMILY_NAME_INFO_FILE = '[tools]/nototools/data/family_name_info_p3.xml'

# Represents how we write family names in the name table.
#
# If no_style_linking is true, 'Bold' and 'Regular' weights become
# part of the family name and the subfamily is 'Regular' or 'Italic',
# otherwise 'Bold' and 'Regular' are not in the family name and
# go into the subfamily ('Regular' does not if 'Italic' is there).
# no_style_linking should not be set if there are no extra weights
# or widths.
#
# If use_preferred is true, there are subfamilies that don't fit into
# Regular Bold BoldItalic Italic, so generate the preferred names.
# Preferred names are actually WWS names, non-wws fields are promoted
# to the family and WWS name fields are never populated.
#
# If include_regular is true, postscript and full names include the subfamily
# when it is 'Regular' (CJK behavior) for phase 2.  Always included for
# phase 3.
FamilyNameInfo = collections.namedtuple(
    'FamilyNameInfo',
    'no_style_linking, use_preferred, include_regular, family_name_style')

# Represents expected name table data for a font.
# Fields expected to be empty are None.  Fields that are expected
# to be present but can have any value are '-'.
NameTableData = collections.namedtuple(
    'NameTableData',
    'copyright_re, original_family, original_subfamily, unique_id, '
    'full_name, version_re, postscript_name, trademark, manufacturer, '
    'designer, description_re, vendor_url, designer_url, license_text, '
    'license_url, preferred_family, preferred_subfamily, wws_family, '
    'wws_subfamily')

_SCRIPT_KEY_TO_FONT_NAME = {
    'Aran': 'Urdu',
    'HST': 'Historic',
    'LGC': None,
    'Zsye': None,
    'MONO': None,
    'SYM2': 'Symbols2',
    'MUSE': None,
}


# copied from noto_lint, we should have a better place for it.
def preferred_script_name(script_key):
  try:
    return unicode_data.human_readable_script_name(script_key)
  except KeyError:
    return cldr_data.get_english_script_name(script_key)


# copied from cmap_data, it has a dependency on lint, lint has one
# on this, and python gives an unhelpful error message when there's
# circular dependencies.
def _prettify(root, indent=''):
  """Pretty-print the root element if it has no text and children
     by adding to the root text and each child's tail."""
  if not root.text and len(root):
    indent += '  '
    sfx = '\n' + indent
    root.text = sfx
    for elem in root:
      elem.tail = sfx
      _prettify(elem, indent)
    elem.tail = sfx[:-2]


def _preferred_cjk_parts(noto_font):
  # CJK treats mono as part of the family name.  This is odd
  # but we will go with the current Adobe naming.
  family_parts = [
      noto_font.family,
      noto_font.style,
      'Mono' if noto_font.is_mono else None]
  if noto_font.subset:
    family_parts.append(noto_font.subset)
  else:
    family_parts.append('CJK')
    cjk_script_to_name = {
        'Jpan': 'JP',
        'Kore': 'KR',
        'Hans': 'SC',
        'Hant': 'TC'
        }
    family_parts.append(cjk_script_to_name[noto_font.script])

  subfamily_parts = [
      noto_font.weight,
      noto_font.slope]
  return family_parts, subfamily_parts


def _preferred_non_cjk_parts(noto_font):
  """Return a tuple of preferred_family, preferred_subfamily).

  The preferred family is based on the family, style, script, and variant, the
  preferred_subfamily is based on the remainder.
  """

  family_parts = [
      noto_font.family,
      'Color' if noto_font.variant == 'color' else None,
      noto_font.style]

  script = noto_font.script
  if script in _SCRIPT_KEY_TO_FONT_NAME:
    # special case script key portion of name
    family_parts.append(_SCRIPT_KEY_TO_FONT_NAME[script])
  else:
    family_parts.append(preferred_script_name(script))
  if noto_font.variant != 'color':
    family_parts.append(noto_font.variant)

  include_weight = (noto_font.weight != 'Regular' or
    (not noto_font.width and not noto_font.slope))

  subfamily_parts = [
      'Mono' if noto_font.is_mono else None,
      'UI' if noto_font.is_UI else None,
      'Display' if noto_font.is_display else None,
      noto_font.width,
      noto_font.weight if include_weight else None,
      noto_font.slope]
  return family_parts, subfamily_parts


def _preferred_parts(noto_font):
  if noto_font.is_cjk:
    parts_pair = _preferred_cjk_parts(noto_font)
  else:
    parts_pair = _preferred_non_cjk_parts(noto_font)
  return filter(None, parts_pair[0]), filter(None, parts_pair[1])


def _shift_parts(family_parts, subfamily_parts, stop_fn):
  """Iterate over subfamily parts, removing from
  subfamily and appending to family, until stop_fn(part)
  returns true.  If subfamily_parts is empty, add
  'Regular'.  This works because for both original and
  wws subfamilies the order of parts is such that all
  parts that fail the stop_fn precede any that pass.
  Does not modify the input parts lists."""

  result_family_parts = family_parts[:]
  limit = len(subfamily_parts)
  i = 0
  while i < limit:
    part = subfamily_parts[i]
    if stop_fn(part):
      break
    result_family_parts.append(part)
    i += 1
  result_subfamily_parts = subfamily_parts[i:]
  if not result_subfamily_parts:
    result_subfamily_parts.append('Regular')
  return result_family_parts, result_subfamily_parts


_WWS_RE = re.compile(
    '(?:(?:Semi|Extra)?Condensed|%s|Italic)$' % '|'.join(noto_fonts.WEIGHTS))
def _is_wws_part(part):
  return _WWS_RE.match(part)


def _wws_parts(family_parts, subfamily_parts):
  return _shift_parts(family_parts, subfamily_parts, _is_wws_part)


_ORIGINAL_RE = re.compile('(?:Bold|Italic|Regular)$')
def _is_original_part(part):
    return _ORIGINAL_RE.match(part)


_LIMITED_ORIGINAL_RE = re.compile('(?:Italic)$')
def _is_limited_original_part(part):
  return _LIMITED_ORIGINAL_RE.match(part)


def _original_parts(family_parts, subfamily_parts, no_style_linking=False):
  """Set no_style_linking to true if weight should be in the family and not
  the subfamily."""
  stop_fn = _is_limited_original_part if no_style_linking else _is_original_part
  return _shift_parts(family_parts, subfamily_parts, stop_fn)


_SHORT_NAMES = {
    'Condensed': 'Cond',
    'SemiCondensed': 'SemCond',
    'ExtraCondensed': 'ExtCond',
    'DemiLight': 'DemLt',
    'ExtraLight': 'ExtLt',
    'Medium': 'Med',
    'SemiBold': 'SemBd',
    'ExtraBold': 'ExtBd',
    'Black': 'Blk',
    'Display': 'Disp',
}

_VERY_SHORT_NAMES = {
    'Condensed': 'Cn',
    'SemiCondensed': 'SmCn',
    'ExtraCondensed': 'XCn',
    'Thin': 'Th',
    'Light': 'Lt',
    'DemiLight': 'DmLt',
    'ExtraLight': 'XLt',
    'Medium': 'Md',
    'Bold': 'Bd',
    'SemiBold': 'SmBd',
    'ExtraBold': 'XBd',
    'Black': 'Bk',
    'Display': 'D',
}

# Only adjusts scripts whose names are > 10 chars in length.
# This is keyed off the full name since that's all we have when we
# need it.  If the name data changes this can break.
_SHORT_SCRIPTS = {
  'Anatolian Hieroglyphs': 'AnatoHiero',  # Hluw
  'Pahawh Hmong': 'PahHmong',  # Hmng
  'New Tai Lue': 'NewTaiLue',  # Talu
  'Syloti Nagri': 'SyloNagri',  # Sylo
  'Imperial Aramaic': 'ImpAramaic',  # Armi
  'SignWriting': 'SignWrit',  # Sgnw
  'Warang Citi': 'WarangCiti',  # Wara
  'Canadian Aboriginal': 'CanAborig',  # Cans
  'Egyptian Hieroglyphs': 'EgyptHiero',  # Egyp
  'Mende Kikakui': 'MendKik',  # Mend
  'Old Persian': 'OldPersian',  # Xpeo
  'Old North Arabian': 'OldNorArab',  # Narb
  'Caucasian Albanian': 'CaucAlban',  # Aghb
  'Meroitic Hieroglyphs': 'MeroHiero',  # Mero
  'Meroitic Cursive': 'MeroCursiv',  # Merc
  'Inscriptional Pahlavi': 'InsPahlavi',  # Phli
  'Old South Arabian': 'OldSouArab',  # Sarb
  'Psalter Pahlavi': 'PsaPahlavi',  # Phlp
  'Meetei Mayek': 'MeetMayek',  # Mtei
  'Sora Sompeng': 'SoraSomp',  # Sora
  'Inscriptional Parthian': 'InsParthi',  # Prti
  'Pau Cin Hau': 'PauCinHau',  # Pauc
  'Old Hungarian': 'OldHung',  # Hung
}

def _name_style_for_length(parts, limit):
  """Return a value indicating whether to use normal, short, very short, or
  extra short names to represent these parts, depending on what is
  required to ensure the length <= limit."""

  if limit == 0:
    return 'normal'
  name = ' '.join(parts)
  if len(name) <= limit:
    return 'normal'
  # shorten script names
  short_parts = [_SHORT_SCRIPTS.get(n, n) for n in parts]
  name = ' '.join(_SHORT_NAMES.get(n, n) for n in short_parts)
  if len(name) <= limit:
    return 'short'
  name = ' '.join(_VERY_SHORT_NAMES.get(n, n) for n in short_parts)
  if len(name) <= limit:
    return 'very short'
  name = name.replace(' ', '')
  if len(name) <= limit:
    return 'extra short'
  raise ValueError('cannot fit %s to length %d' % (parts, limit))


def _name_with_style(parts, name_style):
  """Return a name from parts, using the limit key to determine the style."""
  if name_style == 'normal':
    return ' '.join(parts)
  # preemtively shorten script names
  short_parts = [_SHORT_SCRIPTS.get(n, n) for n in parts]
  if name_style == 'short':
    return ' '.join(_SHORT_NAMES.get(n, n) for n in short_parts)
  name = ' '.join(_VERY_SHORT_NAMES.get(n, n) for n in short_parts)
  if name_style != 'very short':  # 'extra short'
    name = name.replace(' ', '')
  return name


def _names(family_parts, subfamily_parts, family_name_style='normal'):
  family = _name_with_style(family_parts, family_name_style)
  subfamily = ' '.join(subfamily_parts)
  return family, subfamily


def _preferred_names(preferred_family, preferred_subfamily, use_preferred):
  # Preferred names are actually WWS names
  if use_preferred:
    return _names(*_wws_parts(preferred_family, preferred_subfamily))
  return None, None


def _original_names(
    preferred_family, preferred_subfamily, no_style_linking,
    family_name_style):
  return _names(*_original_parts(
      preferred_family, preferred_subfamily, no_style_linking=no_style_linking),
                family_name_style=family_name_style)


def _copyright_re(noto_font):
  # See comment at top of file about regex values
  if noto_font.manufacturer == 'Adobe':
    return ADOBE_COPYRIGHT_RE
  else:
    return GOOGLE_COPYRIGHT_RE


def _full_name(preferred_family, preferred_subfamily, include_regular):
  wws_family, wws_subfamily = _wws_parts(preferred_family, preferred_subfamily)
  result = wws_family[:]
  for n in wws_subfamily:
    if n not in result and (include_regular or n != 'Regular'):
      result.append(n)
  return ' '.join(result)


def _postscript_name(preferred_family, preferred_subfamily, include_regular):
  wws_family, wws_subfamily = _wws_parts(preferred_family, preferred_subfamily)
  # fix for names with punctuation
  punct_re = re.compile("[\s'-]")
  result = ''.join(punct_re.sub('', p) for p in wws_family)
  tail = [n for n in wws_subfamily if n not in wws_family]
  if tail:
    result += '-' + ''.join(tail)

  # fix for CJK
  def repl_fn(m):
    return 'CJK' + m.group(1).lower()
  result = re.sub('CJK(JP|KR|SC|TC)', repl_fn, result)

  if len(result) > 63:
    print >> sys.stderr, 'postscript name longer than 63 characters:\n"%s"' % (
        result)
  return result


def _version_re(noto_font, phase):
  # See comment at top of file about regex values
  if noto_font.manufacturer == 'Adobe':
    sub_len = 3
    hint_ext = ''
    ttfautohint_tag = ''
  else:
    if phase < 3:
      sub_len = 2
      ttfautohint_tag = ''
      if noto_font.manufacturer == 'Google':
        hint_ext = '' # no 'uh' suffix for unhinted Color Emoji font
      else:
        hint_ext = '' if noto_font.is_hinted else ' uh'
    else:
      sub_len = 3
      # in phase 3 we don't annotate the primary part of the version string,
      # but expect 'ttfautohint' to be present somewhere after a semicolon.
      hint_ext = ''
      ttfautohint_tag = 'ttfautohint' if noto_font.is_hinted else ''

  return r'^Version ([0-2])\.(\d{%d})%s(?:;.*%s.*)?$' % (
      sub_len, hint_ext, ttfautohint_tag)


def _trademark(noto_font):
  return '%s is a trademark of Google Inc.' % noto_font.family


def _manufacturer(noto_font):
  if noto_font.manufacturer == 'Adobe':
    return 'Adobe Systems Incorporated'
  if noto_font.manufacturer == 'Monotype':
    return 'Monotype Imaging Inc.'
  if noto_font.manufacturer == 'Khmertype':
    return 'Danh Hong'
  if noto_font.manufacturer == 'Google':
    return 'Google, Inc.'
  raise ValueError('unknown manufacturer "%s"' % noto_font.manufacturer)


DESIGNER_STRINGS = {
    'mti-chahine': 'Nadine Chahine - Monotype Design Team',
    'mti-bosma': 'Jelle Bosma - Monotype Design Team',
    'mti-hong': 'Danh Hong and the Monotype Design Team',
    'mti-indian': 'Indian Type Foundry and the Monotype Design Team',
    'mti-mitchel': 'Ben Mitchell and the Monotype Design Team',
    'mti-singh': 'Vaibhav Singh and the Monotype Design Team',
    'mti-thirst': 'Universal Thirst, Indian Type Foundry and the Monotype Design Team',
    'mti': 'Monotype Design Team',
}


FAMILY_ID_TO_DESIGNER_KEY_P3 = {
    'sans-arab': 'mti-chahine',
    'sans-beng': 'mti-bosma',
    'sans-deva': 'mti-bosma',
    'serif-gujr': 'mti-thirst',
    'serif-guru': 'mti-singh',
    'serif-knda': 'mti-thirst',
    'sans-khmr': 'mti-hong',
    'serif-khmr': 'mti-hong',
    'sans-mlym': 'mti-bosma',
    'serif-mymr': 'mti-mitchel',
    'sans-sinh': 'mti-bosma',
    'serif-sinh': 'mti-bosma',
    'sans-taml': 'mti-bosma',
    'serif-taml': 'mti-indian',
}

def _designer(noto_font, phase):
  if noto_font.manufacturer == 'Adobe':
    return '-'
  if noto_font.manufacturer == 'Monotype':
    if phase == 3:
      family_id = noto_fonts.noto_font_to_family_id(noto_font)
      designer_key = FAMILY_ID_TO_DESIGNER_KEY_P3.get(family_id)
      if designer_key:
        return DESIGNER_STRINGS[designer_key]
    if noto_font.family == 'Noto':
      if noto_font.style == 'Serif' and noto_font.script in [
          'Beng', 'Gujr', 'Knda', 'Mlym', 'Taml', 'Telu']:
        return 'Indian Type Foundry'
      if noto_font.script == 'Arab' and phase == 3:
        return 'Nadine Chahine'
      return 'Monotype Design Team'
    if noto_font.family in ['Arimo', 'Cousine', 'Tinos']:
      return 'Steve Matteson'
    raise ValueError('unknown family "%s"' % noto_font.family)
  if noto_font.manufacturer == 'Khmertype':
    return 'Danh Hong'
  if noto_font.manufacturer == 'Google':
    return 'Google, Inc.'
  raise ValueError('unknown manufacturer "%s"' % noto_font.manufacturer)


def _designer_url(noto_font):
  if noto_font.manufacturer == 'Adobe':
    return 'http://www.adobe.com/type/'
  if noto_font.manufacturer == 'Monotype':
    return 'http://www.monotype.com/studio'
  if noto_font.manufacturer == 'Khmertype':
    return 'http://www.khmertype.org'
  if noto_font.manufacturer == 'Google':
    return 'http://www.google.com/get/noto/'
  raise ValueError('unknown manufacturer "%s"' % noto_font.manufacturer)


def _description_re(noto_font, phase):
  # See comment at top of file about regex values
  if noto_font.manufacturer == 'Adobe':
    return '-'
  if noto_font.manufacturer == 'Google' and noto_font.variant == 'color':
    return 'Color emoji font using CBDT glyph data.'
  if phase < 3:
    hint_prefix = 'Data %shinted.' % (
        '' if noto_font.is_hinted else 'un')
  else:
    # In phase 3 no hint prefix at all regardless of hinted or unhinted.
    hint_prefix = ''

  designer = ''
  if noto_font.manufacturer == 'Monotype':
    if noto_font.family == 'Noto':
      designer = 'Designed by Monotype design team.'
      if hint_prefix:
        hint_prefix += ' '
    else:
      # Arimo, Tinos, and Cousine don't currently mention hinting in their
      # descriptions, but they probably should.
      # TODO(dougfelt): swat them to fix this.
      return '-'
  return '^%s%s$' % (hint_prefix, designer)


def _license_text(noto_font):
  if noto_font.license_type == 'sil':
    return SIL_LICENSE
  if noto_font.license_type == 'apache':
    return APACHE_LICENSE
  raise ValueError('unknown license type "%s"' % noto_font.license_type)


def _license_url(noto_font):
  if noto_font.license_type == 'sil':
    return SIL_LICENSE_URL
  if noto_font.license_type == 'apache':
    return APACHE_LICENSE_URL
  raise ValueError('unknown license type "%s"' % noto_font.license_type)


def name_table_data(noto_font, family_to_name_info, phase):
  """Returns a NameTableData for this font given the family_to_name_info."""
  family_id = noto_fonts.noto_font_to_wws_family_id(noto_font)
  try:
    info = family_to_name_info[family_id]
  except KeyError:
    print >> sys.stderr, 'no family name info for "%s"' % family_id
    return None

  family_parts, subfamily_parts = _wws_parts(*_preferred_parts(noto_font))
  if not info.use_preferred and subfamily_parts not in [
      ['Regular'],
      ['Bold'],
      ['Italic'],
      ['Bold', 'Italic']]:
    print >> sys.stderr, (
        'Error in family name info: %s requires preferred names, but info '
        'says none are required.' % path.basename(noto_font.filepath))
    print >> sys.stderr, subfamily_parts
    return None

  # for phase 3 we'll now force include_regular
  include_regular = phase == 3 or info.include_regular

  ofn, osfn = _original_names(
      family_parts, subfamily_parts, info.no_style_linking,
      info.family_name_style)
  # If we limit the original names (to put weights into the original family)
  # then we need a preferred name to undo this.  When info is read or generated,
  # the code should ensure use_preferred is set.
  pfn, psfn = _preferred_names(
      family_parts, subfamily_parts, info.use_preferred)
  if pfn and pfn == ofn:
    pfn = None
  if psfn and psfn == osfn:
    psfn = None

  return NameTableData(
      copyright_re=_copyright_re(noto_font),
      original_family=ofn,
      original_subfamily=osfn,
      unique_id='-',
      full_name=_full_name(family_parts, subfamily_parts, include_regular),
      version_re=_version_re(noto_font, phase),
      postscript_name=_postscript_name(
          family_parts, subfamily_parts, include_regular),
      trademark=_trademark(noto_font),
      manufacturer=_manufacturer(noto_font),
      designer=_designer(noto_font, phase),
      description_re=_description_re(noto_font, phase),
      vendor_url=NOTO_URL,
      designer_url=_designer_url(noto_font),
      license_text=_license_text(noto_font),
      license_url=_license_url(noto_font),
      preferred_family=pfn,
      preferred_subfamily=psfn,
      wws_family=None,
      wws_subfamily=None)


def _create_family_to_subfamilies(notofonts):
  """Return a map from preferred family name to set of preferred subfamilies.
  Note these are WWS family/subfamilies now."""
  family_to_subfamilies = collections.defaultdict(set)
  for noto_font in notofonts:
    family, subfamily = _names(*_wws_parts(*_preferred_parts(noto_font)))
    family_to_subfamilies[family].add(subfamily)
  return family_to_subfamilies


_NON_ORIGINAL_WEIGHT_PARTS = frozenset(
    w for w in noto_fonts.WEIGHTS
    if w not in ['Bold', 'Regular'])
_ORIGINAL_PARTS = frozenset(['Bold', 'Regular', 'Italic'])
_WWS_PARTS = frozenset(
    ['SemiCondensed', 'ExtraCondensed', 'Condensed', 'Italic'] +
    list(noto_fonts.WEIGHTS))


def _select_name_style(styles):
  for style in ['extra short', 'very short', 'short']:
    if style in styles:
      return style
  return 'normal'


def create_family_to_name_info(notofonts, phase, extra_styles):
  if phase not in [2, 3]:
    raise ValueError('expected phase 2 or 3 but got "%s"' % phase)

  family_to_parts = collections.defaultdict(set)
  family_to_name_styles = collections.defaultdict(set)
  cjk_families = set()
  for noto_font in notofonts:
    family_id = noto_fonts.noto_font_to_wws_family_id(noto_font)
    preferred_family, preferred_subfamily = _preferred_parts(noto_font)
    _, subfamily_parts = _wws_parts(preferred_family, preferred_subfamily)
    family_to_parts[family_id].update(subfamily_parts)
    # It's been asserted that the family name can't be longer than 32 chars.
    # Assume this is only true for nameID 1 and not nameID 16 or 17.
    family_parts, _ = _original_parts(preferred_family, preferred_subfamily)
    family_name_style = _name_style_for_length(
        family_parts, ORIGINAL_FAMILY_LIMIT)
    family_to_name_styles[family_id].add(family_name_style)
    if noto_font.is_cjk:
      cjk_families.add(family_id)

  # If extra_styles is true, we assume all wws styles are present.  The
  # practical import of this is that use_preferred will be true, and the
  # family name style will be short enough to accommodate the longest
  # wws style name.  So we just synthesize this and run each font through
  # one more time with those styles.
  # For a given wws id the fonts should all be wws variants.  Since we
  # substitute fixed wws values, any font with the same wws id will do.
  #
  # This is a kludge, as it duplicates a lot of the above code.
  if extra_styles:
    seen_ids = set()
    for noto_font in notofonts:
      if noto_font.is_cjk:
        # Don't do this for cjk
        continue
      family_id = noto_fonts.noto_font_to_wws_family_id(noto_font)
      if family_id in seen_ids:
        continue
      seen_ids.add(family_id)
      preferred_family, _ = _preferred_parts(noto_font)
      preferred_subfamily = filter(None, [
          'Mono' if noto_font.is_mono else None,
          'UI' if noto_font.is_UI else None,
          'Display' if noto_font.is_display else None,
          'ExtraCondensed',  # longest width name
          'ExtraLight', # longest weight name
          'Italic'])  # longest slope name
      _, subfamily_parts = _wws_parts(preferred_family, preferred_subfamily)
      family_to_parts[family_id].update(subfamily_parts)
      family_parts, _ = _original_parts(preferred_family, preferred_subfamily)
      family_name_style = _name_style_for_length(
          family_parts, ORIGINAL_FAMILY_LIMIT)
      family_to_name_styles[family_id].add(family_name_style)


  result = {}
  for family_id, part_set in family_to_parts.iteritems():
    # Even through CJK mono fonts are in their own families and have only
    # bold and regular weights, they behave like they have more weights like
    # the rest of CJK.
    family_is_cjk = family_id in cjk_families
    no_style_linking = phase == 2 and family_is_cjk
    use_preferred = no_style_linking or bool(part_set - _ORIGINAL_PARTS)
    # Keep 'Regular' in the postscript/full name only for CJK in phase 2,
    # or always if phase 3.
    include_regular = phase == 3 or family_is_cjk
    name_style = 'normal' if phase == 2 else _select_name_style(
        family_to_name_styles[family_id])
    result[family_id] = FamilyNameInfo(
        no_style_linking, use_preferred, include_regular, name_style)
  return result


def _build_info_element(family, info):
  attrs = {'family': family}
  for attr in FamilyNameInfo._fields:
    val = getattr(info, attr)
    if attr == 'family_name_style':
      # only write family length style if not 'normal'
      if val != 'normal':
        attrs[attr] = val
    elif val:
      attrs[attr] = 't'
  # Don't have to write it out since no_style_linking implies use_preferred
  if 'no_style_linking' in attrs and 'use_preferred' in attrs:
    del attrs['use_preferred']
  return ET.Element('info', attrs)


def _build_tree(family_to_name_info, pretty=False):
  date = str(datetime.date.today())
  root = ET.Element('family_name_data', date=date)
  for family in sorted(family_to_name_info):
    info = family_to_name_info[family]
    root.append(_build_info_element(family, info))
  if pretty:
    _prettify(root)
    root.tail='\n'
  return ET.ElementTree(element=root)


def _read_info_element(info_node):
  def bval(attr):
    return bool(info_node.get(attr, False))
  def nval(attr):
    return info_node.get(attr, 'normal')
  # no_style_linking implies use_preferred
  return FamilyNameInfo(
      bval('no_style_linking'),
      bval('no_style_linking') or bval('use_preferred') or bval('use_wws'),
      bval('include_regular'),
      nval('family_name_style'))


def _read_tree(root):
  family_to_name_info = {}
  for node in root:
    if node.tag != 'info':
      raise ValueError('unknown node in tree: "%s"' % node.tag)
    family = node.get('family').strip()
    family_to_name_info[family] = _read_info_element(node)
  return family_to_name_info


def write_family_name_info_file(family_to_name_info, filename, pretty=False):
  filename = tool_utils.resolve_path(filename)
  _build_tree(family_to_name_info, pretty).write(
      filename, encoding='utf8', xml_declaration=True)


def write_family_name_info(family_to_name_info, pretty=False):
  return ET.tostring(
      _build_tree(family_to_name_info, pretty).getroot(),
      encoding='utf-8')


_PHASE_TO_NAME_INFO_CACHE = {}
_PHASE_TO_FILENAME = {
    2: PHASE_2_FAMILY_NAME_INFO_FILE,
    3: PHASE_3_FAMILY_NAME_INFO_FILE
}
def family_to_name_info_for_phase(phase):
  """Phase is an int, either 2 or 3."""
  result = _PHASE_TO_NAME_INFO_CACHE.get(phase, None)
  if not result:
    filename = _PHASE_TO_FILENAME[phase]
    result = read_family_name_info_file(filename)
    _PHASE_TO_NAME_INFO_CACHE[phase] = result
  return result


def read_family_name_info_file(filename):
  """Returns a map from preferred family name to FontNameInfo."""
  filename = tool_utils.resolve_path(filename)
  return _read_tree(ET.parse(filename).getroot())


def read_family_name_info(text):
  """Returns a map from preferred family name to FontNameInfo."""
  return _read_tree(ET.fromstring(text))


def _create_family_to_faces(notofonts, name_fn):
  """Notofonts is a collection of NotoFonts.  Return a map from
  preferred family to a list of preferred subfamily."""

  family_to_faces = collections.defaultdict(set)
  for noto_font in notofonts:
    if noto_font.fmt == 'ttc':
      continue
    family, subfamily = name_fn(noto_font)
    family_to_faces[family].add(subfamily)
  return family_to_faces


def _dump_family_to_faces(family_to_faces):
  for family in sorted(family_to_faces):
    print '%s:\n  %s' % (
        family, '\n  '.join(sorted(family_to_faces[family])))


def _dump_name_data(name_data):
  if not name_data:
    print '  Error: no name data'
    return True

  err = False
  for attr in NameTableData._fields:
    value = getattr(name_data, attr)
    if value:
      if attr == 'original_family' and len(value) > ORIGINAL_FAMILY_LIMIT:
        print '## family too long (%2d): %s' % (len(value), value)
        err = True
      print '  %20s: %s' % (attr, value)
    else:
      print '  %20s: <none>' % attr
  return err


def _dump_family_names(notofonts, family_to_name_info, phase):
  err_names = []
  for font in sorted(notofonts, key=lambda f: f.filepath):
    name_data = name_table_data(font, family_to_name_info, phase)
    print
    print font.filepath
    if _dump_name_data(name_data):
      err_names.append(font.filepath)
  if err_names:
    print '## %d names too long:\n  %s' % (
        len(err_names), '\n  '.join(err_names))


def _dump(fonts, info_file, phase):
  """Display information about fonts, using name info from info_file."""
  family_to_name_info = read_family_name_info_file(info_file)
  _dump_family_names(fonts, family_to_name_info, phase)


def _write(fonts, info_file, phase, extra_styles):
  """Build family name info from font_paths and write to info_file.
  Write to stdout if info_file is None."""
  family_to_name_info =  create_family_to_name_info(fonts, phase, extra_styles)
  if info_file:
    write_family_name_info_file(family_to_name_info, info_file, pretty=True)
  else:
    print write_family_name_info(family_to_name_info, pretty=True)


def _test(fonts, phase, extra_styles):
  """Build name info from font_paths and dump the names for them."""
  family_to_name_info = create_family_to_name_info(fonts, phase, extra_styles)
  print write_family_name_info(family_to_name_info, pretty=True)
  _dump_family_names(fonts, family_to_name_info, phase)


def _info(fonts):
  """Group fonts into families and list the subfamilies for each."""
  family_to_subfamilies = _create_family_to_subfamilies(fonts)
  for family in sorted(family_to_subfamilies):
    print '%s:\n  %s' % (
        family, '\n  '.join(sorted(family_to_subfamilies[family])))


def _read_filename_list(filenames):
  with open(filenames, 'r') as f:
    return [n.strip() for n in f if n]


def _collect_paths(dirs, files):
  paths = []
  if dirs:
    for d in dirs:
      d = tool_utils.resolve_path(d)
      paths.extend(n for n in glob.glob(path.join(d, '*')))
  if files:
    for fname in files:
      if fname[0] == '@':
        paths.extend(_read_filename_list(fname[1:]))
      else:
        paths.append(tool_utils.resolve_path(fname))
  return paths


def _get_noto_fonts(font_paths):
  FMTS = frozenset(['ttf', 'otf'])
  SCRIPTS = frozenset(['CJK', 'HST'])
  fonts = []
  for p in font_paths:
    font = noto_fonts.get_noto_font(p)
    if font and font.fmt in FMTS and font.script not in SCRIPTS:
      fonts.append(font)
  return fonts


def main():
  CMDS = ['dump', 'write', 'test', 'info']
  HELP = """
  dump  - read the family info file, and display the names to generate
          for some fonts.
  write - collect all the names of the provided fonts, and write a family name
          info file if one was provided (via -i or -p), else write to stdout.
  test  - collect all the names of the provided fonts, show the family name
          info file that would be generated, and show the names to generate
          for those fonts.
  info  - collect the preferred names of the provided fonts, and display them.
  """

  parser = argparse.ArgumentParser(
      epilog=HELP, formatter_class=argparse.RawDescriptionHelpFormatter)
  parser.add_argument(
      '-i', '--info_file', metavar='fname',
      help='name of xml family info file, overrides name based on phase, '
      'use \'-\' to write to stdout')
  parser.add_argument(
      '-p', '--phase', metavar = 'phase', type=int,
      help='determine info file name by phase (2 or 3)')
  parser.add_argument(
      '-d', '--dirs', metavar='dir', help='font directories to examine '
      '(use "[noto]" for noto fonts/cjk/emoji font dirs)', nargs='+')
  parser.add_argument(
      '-f', '--files', metavar='fname', help='fonts to examine, prefix with'
      '\'@\' to read list from file', nargs='+')
  parser.add_argument(
      '-x', '--extra_styles', help='assume all wws styles for write/test',
      action='store_true')
  parser.add_argument(
      'cmd', metavar='cmd', help='operation to perform (%s)' % ', '.join(CMDS),
      choices=CMDS)
  args = parser.parse_args()

  if args.dirs:
    for i in range(len(args.dirs)):
      if args.dirs[i] == '[noto]':
        args.dirs[i] = None
        args.dirs.extend(noto_fonts.NOTO_FONT_PATHS)
        args.dirs = filter(None, args.dirs)
        break

  paths = _collect_paths(args.dirs, args.files)
  fonts = _get_noto_fonts(paths)
  if not fonts:
    print 'Please specify at least one directory or file'
    return

  if not args.info_file:
    if args.phase:
      args.info_file = _PHASE_TO_FILENAME[args.phase]
      print 'using name info file: "%s"' % args.info_file

  if args.cmd == 'dump':
    if not args.info_file:
      print 'must specify an info file to dump'
      return
    info_file = tool_utils.resolve_path(args.info_file)
    if not path.exists(info_file):
      print '"%s" does not exist.' % args.info_file
      return
    _dump(fonts, info_file, args.phase)
  elif args.cmd == 'write':
    if not args.phase:
      print 'Must specify phase when generating info.'
      return
    out = None if args.info_file == '-' else args.info_file
    _write(fonts, out, args.phase, args.extra_styles)
  elif args.cmd == 'test':
    _test(fonts, args.phase, args.extra_styles)
  elif args.cmd == 'info':
    _info(fonts)


if __name__ == "__main__":
  main()
