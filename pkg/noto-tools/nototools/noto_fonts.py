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

"""Some utilities to identify Noto fonts and collect them into families"""

import argparse
import collections
import os
from os import path
import re
import sys

from fontTools import ttLib

from nototools import cldr_data
from nototools import coverage
from nototools import font_data
from nototools import lang_data
from nototools import notoconfig
from nototools import noto_data
from nototools import tool_utils
from nototools import unicode_data

# The '[xxx]' syntax is used to get the noto-xxx value from notoconfig.
# for now we exclude alpha, the phase 3 fonts are here but we don't use
# them yet.
NOTO_FONT_PATHS = [
    '[fonts]/hinted', '[fonts]/unhinted', '[emoji]/fonts', '[cjk]']


ODD_SCRIPTS = {
  'CJKjp': 'Jpan',
  'CJKkr': 'Kore',
  'CJKsc': 'Hans',
  'CJKtc': 'Hant',
  'JP': 'Jpan',
  'KR': 'Kore',
  'SC': 'Hans',
  'TC': 'Hant',
  'NKo': 'Nkoo',
  'SumeroAkkadianCuneiform': 'Xsux',
  'Symbols': 'Zsym',
  'Emoji': 'Zsye',
}


def convert_to_four_letter(script_name):
  """Converts a script name from a Noto font file name to ISO 15924 code."""
  if not script_name:
    raise ValueError('empty script name')
  if script_name in ODD_SCRIPTS:
    return ODD_SCRIPTS[script_name]
  script_code = unicode_data.script_code(script_name)
  if script_code == 'Zzzz':
    raise ValueError('no script for %s' % script_name)
  return script_code


def preferred_script_name(script_key):
  # Returns the script_key if we have nothing else.
  try:
    return unicode_data.human_readable_script_name(script_key)
  except:
    return cldr_data.get_english_script_name(script_key)


_script_key_to_report_name = {
    'Aran': '(Urdu)',  # phase 2 usage
    'HST': '(Historic)',
    'LGC': '(LGC)',
    'SYM2': 'Symbols2'
}
def script_name_for_report(script_key):
    return (_script_key_to_report_name.get(script_key, None) or
            preferred_script_name(script_key))


# NotoFont maps a font path to information we assume the font to have, based
# on Noto path and naming conventions:
# - filepath: the path name from which we derived the information
# - family: family name, e.g. 'Arimo', 'Noto'
# - style: type style, e.g. 'Sans', 'Serif', might be None
# - script: four-letter script code or 'private use' code like 'Aran', 'LGC',
#     'HST'
# - variant: script variant like 'UI' or Syriac variants like 'Estrangela'
# - width: width name ('Condensed') or None
# - weight: weight name
# - slope: slope name ('Italic') or None
# - fmt: 'ttf', 'otf', or 'otc'
# - manufacturer: 'Adobe', 'Google', 'Khmertype', or 'Monotype'
# - license_type: 'sil' or 'apache'
# - is_hinted: boolean, true if hinted
# - is_mono: boolean, true if monospace (currently CJK Latin range, or legacy
#     LGC Mono)
# - is_display: boolean, true if display
# - is_UI: boolean, true if has UI in the name
# - is_UI_metrics: boolean true if must have UI metrics
# - is_cjk: boolean, true if a CJK font (from Adobe)
# - subset: name of cjk subset (KR, JA, SC, TC) for reduced-charset fonts
#     targeted at these languages
NotoFont = collections.namedtuple(
    'NotoFont',
    'filepath, family, style, script, variant, width, weight, slope, '
    'fmt, manufacturer, license_type, is_hinted, is_mono, is_UI, is_UI_metrics, '
    'is_display, is_cjk, subset')


# These are the ideal pseudo-css weights. 'ideal', because windows GDI limits us
# to weights >= 250 if we are to prevent auto-bolding, and 'pseudo-css' because
# css limits us to multiples of 100 currently.  The hope is that both of these
# restrictions eventually go away, so we encode the values as we wish they would
# be, and adjust when necessary based on context.
WEIGHTS = {
    'Thin': 100,
    'ExtraLight': 200,
    'Light': 300,
    'DemiLight': 350,  # used in cjk fonts
    'Regular': 400,
    'Medium': 500,
    'SemiBold': 600,
    'Bold': 700,
    'ExtraBold': 800,
    'Black': 900
}

_FONT_NAME_REGEX = (
    # family should be prepended - this is so Roboto can be used with unittests
    # that use this regex to parse.
    '(Sans|Serif|Naskh|Kufi|Nastaliq|Emoji|ColorEmoji|Music)?'
    '(Mono(?:space)?)?'
    '(.*?)'
    '(Eastern|Estrangela|Western|Slanted|New|Unjoined)?'
    '(UI)?'
    '(Display)?'
    '-?'
    '((?:Semi|Extra)?Condensed)?'
    '(|%s)?' % '|'.join(WEIGHTS.keys()) +
    '(Italic)?'
    '\.(ttf|ttc|otf)')


_EXT_REGEX = re.compile(r'.*\.(?:ttf|ttc|otf)$')

def get_noto_font(filepath, family_name='Arimo|Cousine|Tinos|Noto',
                  phase=3):
  """Return a NotoFont if filepath points to a noto font, or None if we can't
  process the path."""

  filedir, filename = os.path.split(filepath)
  if not filedir:
    filedir = os.getcwd()
  match = match_filename(filename, family_name)
  if match:
    (family, style, mono, script, variant, ui, display, width, weight,
     slope, fmt) = match.groups()
  else:
    if _EXT_REGEX.match(filename):
      print >> sys.stderr, '%s did not match font regex' % filename
    return None

  is_cjk = filedir.endswith('noto-cjk')

  license_type = 'sil'

  if script in ['JP', 'KR', 'TC', 'SC']:
    subset = script
  else:
    subset = None

  # Special-case emoji style
  # (style can be None for e.g. Cousine, causing 'in' to fail, so guard)
  if style and 'Emoji' in style:
    script = 'Zsye'
    if style == 'ColorEmoji':
      style = 'Emoji'
      variant = 'color'
  if style and 'Music' in style:
    script = 'MUSE'

  is_mono = mono == 'Mono'

  if width not in [None, '', 'Condensed', 'SemiCondensed', 'ExtraCondensed']:
    print >> sys.stderr, 'noto_fonts: Unexpected width "%s"' % width
    if width in ['SemiCond', 'Narrow']:
      width = 'SemiCondensed'
    elif width == 'Cond':
      width = 'Condensed'
    else:
      width = '#'+ width + '#'

  if not script:
    if is_mono:
      script = 'MONO'
    else:
      script = 'LGC'
  elif script == 'Urdu':
    # Use 'Aran' for languages written in the Nastaliq Arabic style, like Urdu.
    # The font naming uses 'Urdu' which is not a script, but a language.
    assert family == 'Noto' and style == 'Nastaliq'
    script = 'Aran'
  elif script == 'Historic':
    script = 'HST'
  elif script == 'CJK':
    # leave script as-is
    pass
  elif script == 'Symbols2':
    script = 'SYM2'
  elif script not in ['MUSE', 'Zsye']:  # assigned above
    try:
      script = convert_to_four_letter(script)
    except ValueError:
      print >> sys.stderr, 'unknown script: %s for %s' % (script, filename)
      return None

  if not weight:
    weight = 'Regular'

  is_UI = ui == 'UI'
  is_UI_metrics = is_UI or style == 'Emoji' or (
      style == 'Sans' and script in noto_data.DEEMED_UI_SCRIPTS_SET)

  is_display = display == 'Display'
  if is_cjk:
    is_hinted = True
  elif filedir.endswith('alpha') or 'emoji' in filedir:
    is_hinted = False
  else:
    hint_status = path.basename(filedir)
    if (hint_status not in ['hinted', 'unhinted']
        and 'noto-source' not in filedir):
      # print >> sys.stderr, (
      #    'unknown hint status for %s, defaulting to unhinted') % filedir
      pass
    is_hinted = hint_status == 'hinted'

  manufacturer = (
      'Adobe' if is_cjk
      else 'Google' if script == 'Zsye' and variant == 'color'
      else 'Khmertype' if phase < 3 and script in ['Khmr', 'Cham', 'Laoo']
      else 'Monotype')

  return NotoFont(
      filepath, family, style, script, variant, width, weight, slope, fmt,
      manufacturer, license_type, is_hinted, is_mono, is_UI, is_UI_metrics,
      is_display, is_cjk, subset)


def match_filename(filename, family_name):
    """Match just the file name."""
    return re.match('(%s)' % family_name + _FONT_NAME_REGEX, filename)


def parse_weight(name):
    """Parse the weight specifically from a name."""
    match = re.search('|'.join(WEIGHTS.keys()), name)
    if not match:
        return 'Regular'
    return match.group(0)


def script_key_to_scripts(script_key):
  """Return a set of scripts for a script key.  The script key is used by
  a font to define the set of scripts it supports.  Some keys are ours,
  e.g. 'LGC', and some are standard script codes that map to multiple
  scripts, like 'Jpan'.  In either case we need to be able to map a script
  code (either unicode character script code, or more general iso script
  code) to a font, and we do so by finding it in the list returned here."""
  if script_key == 'LGC':
    return frozenset(['Latn', 'Grek', 'Cyrl'])
  elif script_key == 'Aran':
    return frozenset(['Arab'])
  elif script_key == 'HST':
    raise ValueError('!do not know scripts for HST script key')
  elif script_key == 'MONO':
    # TODO: Mono doesn't actually support all of Latn, we need a better way
    # to deal with pseudo-script codes like this one.
    return frozenset(['Latn'])
  elif script_key in ['MUSE', 'SYM2']:
    return frozenset(['Zsym'])
  else:
    return lang_data.script_includes(script_key)


def script_key_to_primary_script(script_key):
  """We need a default script for a font, and fonts using a 'script key' support
  multiple fonts.  This lets us pick a default sample for a font based on it.
  The sample is named with a script that can include 'Jpan' so 'Jpan' should be
  the primary script in this case."""
  if script_key == 'LGC':
    return 'Latn'
  if script_key == 'Aran':
    return 'Arab'
  if script_key == 'HST':
    raise ValueError('!do not know scripts for HST script key')
  if script_key == 'MONO':
    return 'Latn'
  if script_key in ['MUSE', 'SYM2']:
    return 'Zsym'
  if script_key not in lang_data.scripts():
    raise ValueError('!not a script key: %s' % script_key)
  return script_key


def noto_font_to_family_id(notofont):
  # exclude 'noto-' from head of key, they all start with it except
  # arimo, cousine, and tinos, and we can special-case those.
  # For cjk with subset we ignore script and use 'cjk' plus the subset.
  # For cjk, we ignore the mono/non-mono distinctions, since we don't
  # display different samples or provide different download bundles based
  # on this.
  tags = []
  if notofont.family != 'Noto':
    tags.append(notofont.family)
  if notofont.style:
    tags.append(notofont.style)
  if notofont.is_mono and not notofont.is_cjk:
    tags.append('mono')
  if notofont.is_cjk and notofont.subset:
    tags.append('cjk')
    tags.append(notofont.subset)
  else:
    # Sans Mono should get tag sans-mono, but 'Mono' (phase 2 name) should get
    # tag mono-mono, and Sans/Serif Mono CJK should not include mono in tag.
    # Above we've already added mono for non-cjk fonts, so if the style is not
    # empty we don't want to add mono a second time.
    if not (notofont.style and notofont.script.lower() == 'mono'):
      tags.append(notofont.script)
  if notofont.variant:
    tags.append(notofont.variant)
  # split display variants into their own family.  In particular, the family
  # name of display fonts includes 'Display' and we don't want that as part
  # of the overall family name.
  if notofont.is_display:
    tags.append('display')
  key = '-'.join(tags).lower()
  return key


def noto_font_to_wws_family_id(notofont):
  """Return an id roughly corresponding to the wws family.  Used to identify
  naming rules for the corresponding fonts. Compare to noto_font_to_family_id,
  which corresponds to a preferred family and is used to determine the language
  support for those fonts.  For example, 'Noto Sans Devanagari UI' and
  'Noto Sans Devanagari' support the same languages (e.g. have the same cmap)
  but have different wws family names and different name rules (names for the
  UI variant use very short abbreviations).
  CJK font naming does reflect 'mono' so we add it back to the id."""
  id = noto_font_to_family_id(notofont)
  if notofont.is_cjk and notofont.is_mono:
    id += '-mono'
  if notofont.is_UI:
    id += '-ui'
  if notofont.is_display:
    id += '-display'
  return id


_special_wws_names = {
    'arimo-lgc': ['Arimo'],
    'cousine-lgc': ['Cousine'],
    'emoji-zsye': ['Noto', 'Emoji'],
    'emoji-zsye-color': ['Noto', 'Color', 'Emoji'],
    'kufi-arab': ['Noto', 'Kufi', 'Arabic'],
    'mono-mono': ['Noto', 'Mono'],
    'music-muse': ['Noto', 'Music'],
    'naskh-arab': ['Noto', 'Naskh', 'Arabic'],
    'naskh-arab-ui': ['Noto', 'Naskh', 'Arabic', 'UI'],
    'nastaliq-aran': ['Noto', 'Nastaliq', 'Urdu'],
    'tinos-lgc': ['Tinos'],
}

def wws_family_id_to_name_parts(wws_id):
  """Return the list of family name parts corresponding to the wws id."""

  # first handle special cases:
  parts = _special_wws_names.get(wws_id)
  if parts:
    return parts

  part_keys = wws_id.split('-')
  key = part_keys[0]
  if key == 'sans':
    parts = ['Noto', 'Sans']
  elif key == 'serif':
    parts = ['Noto', 'Serif']
  script = part_keys[1]
  if script == 'lgc':
    # do nothing, we don't label this pseudo-script
    pass
  elif script == 'cjk':
    if len(part_keys) == 2:
      parts.append('CJK')
    else:
      parts.append(part_keys[2].upper())
  elif script in ['hans', 'hant', 'jpan', 'kore']:
    # mono comes before CJK in the name
    if len(part_keys) > 2 and part_keys[2] == 'mono':
      parts.append('Mono')
      part_keys = part_keys[:2] # trim mono so we don't try to add it again
    parts.append('CJK')
    if script == 'hans':
      parts.append('sc')
    elif script == 'hant':
      parts.append('tc')
    elif script == 'jpan':
      parts.append('jp')
    else:
      parts.append('kr')
  elif script == 'sym2':
    parts.append('Symbols2')
  elif script == 'phag':
    # allow hyphenated name in name table
    parts.append('Phags-pa')
  else:
    # Mono works as a script. The phase 2 'mono-mono' tag was special-cased
    # above so it won't get added a second time.
    script_name = preferred_script_name(script.title())
    script_name = script_name.replace(' ', '').replace("'", '').replace('-', '')
    parts.append(script_name)
  if len(part_keys) > 2:
    extra = part_keys[2]
    if extra in ['tc', 'sc', 'jp', 'kr']:
      pass
    elif extra == 'ui':
      parts.append('UI')
    elif extra in ['eastern', 'estrangela', 'western', 'display', 'unjoined']:
      parts.append(extra.title())
    else:
      raise Exception('unknown extra tag in %s' % wws_id)
  return parts


def get_noto_fonts(paths=NOTO_FONT_PATHS):
  """Scan paths for fonts, and create a NotoFont for each one, returning a list
  of these.  'paths' defaults to the standard noto font paths, using notoconfig."""

  font_dirs = filter(None, [tool_utils.resolve_path(p) for p in paths])
  print 'Getting fonts from: %s' % font_dirs

  all_fonts = []
  for font_dir in font_dirs:
    for filename in os.listdir(font_dir):
      if not _EXT_REGEX.match(filename):
        continue

      filepath = path.join(font_dir, filename)
      font = get_noto_font(filepath)
      if not font:
        print >> sys.stderr, 'bad font filename in %s: \'%s\'.' % (
            (font_dir, filename))
        continue

      all_fonts.append(font)

  return all_fonts


def get_font_family_name(font_file):
    font = ttLib.TTFont(font_file, fontNumber=0)
    name_record = font_data.get_name_records(font)
    try:
      name = name_record[16]
    except KeyError:
      name = name_record[1]
      if name.endswith('Regular'):
        name = name.rsplit(' ', 1)[0]
    return name


# NotoFamily provides additional information about related Noto fonts.  These
# fonts have weight/slope/other variations but have the same cmap, script
# support, etc. Most of this information is held in a NotoFont that is the
# representative member.  Fields are:

# - name: name of the family
# - family_id: a family_id for the family
# - rep_member: the representative member, some of its data is common to all
#     members
# - charset: the character set, must the the same for all members
# - hinted_members: list of members that are hinted
# - unhinted_members: list of members that are unhinted
# When both hinted_members and unhinted_members are present, they correspond.
NotoFamily = collections.namedtuple(
    'NotoFamily',
    'name, family_id, rep_member, charset, hinted_members, unhinted_members')

def get_families(fonts):
  """Group fonts into families, separate into hinted and unhinted, select
  representative."""

  family_id_to_fonts = collections.defaultdict(set)
  families = {}
  for font in fonts:
    family_id = noto_font_to_family_id(font)
    family_id_to_fonts[family_id].add(font)

  for family_id, fonts in family_id_to_fonts.iteritems():
    hinted_members = []
    unhinted_members = []
    rep_member = None
    rep_backup = None  # used in case all fonts are ttc fonts
    for font in fonts:
      if font.is_hinted:
        hinted_members.append(font)
      else:
        unhinted_members.append(font)
      if not rep_member:
        if font.weight == 'Regular' and font.slope is None and not (
            font.is_cjk and font.is_mono) and not font.is_UI:
          # We assume here that there's no difference between a hinted or
          # unhinted rep_member in terms of what we use it for.  The other
          # filters are to ensure the fontTools font name is a good stand-in
          # for the family name.
          if font.fmt == 'ttc' and not rep_backup:
            rep_backup = font
          else:
            rep_member = font

    rep_member = rep_member or rep_backup
    if not rep_member:
      raise ValueError(
          'Family %s does not have a representative font.' % family_id)

    name = get_font_family_name(rep_member.filepath)

    if rep_member.fmt in {'ttf', 'otf'}:
      charset = coverage.character_set(rep_member.filepath)
    else:
      # was NotImplemented, but bool(NotImplemented) is True
      charset = None

    families[family_id] = NotoFamily(
        name, family_id, rep_member, charset, hinted_members, unhinted_members)

  return families


def get_family_filename(family):
  """Returns a filename to use for a family zip of hinted/unhinted members.
     This is basically the postscript name with weight/style removed.
  """
  font = ttLib.TTFont(family.rep_member.filepath, fontNumber=0)
  name_record = font_data.get_name_records(font)
  try:
    name = name_record[6]
    ix = name.find('-')
    if ix >= 0:
      name = name[:ix]
  except KeyError:
    name = name_record[1]
    if name.endswith('Regular'):
      name = name.rsplit(' ', 1)[0]
    name = name.replace(' ', '')
  return name


def _all_noto_font_key_to_names(paths):
  """return a map from wws key to the family portion of the font file name"""
  wws_key_to_family_name = {}
  for font in get_noto_fonts(paths):
    fontname, _ = path.splitext(path.basename(font.filepath))
    ix = fontname.find('-')
    familyname = fontname if ix == -1 else fontname[:ix]
    wws_key = noto_font_to_wws_family_id(font)
    if wws_key_to_family_name.get(wws_key, familyname) != familyname:
      print '!!! mismatching font names for key %s: %s and %s' % (
          wws_key, wws_key_to_family_name[wws_key], familyname)
    else:
      wws_key_to_family_name[wws_key] = familyname
  return wws_key_to_family_name


def test(paths):
  """test name generation to make sure we match the font name from the wws id"""
  wws_key_to_family_name = _all_noto_font_key_to_names(paths)
  for key, val in sorted(wws_key_to_family_name.items()):
    print key, val
    name = ''.join(wws_family_id_to_name_parts(key))
    if name != val:
      raise Exception('!!! generated name %s does not match' % name)


def main():
  parser = argparse.ArgumentParser()
  parser.add_argument(
      '-d', '--dirs', help='list of directories to find fonts in',
      metavar='dir', nargs='+')
  parser.add_argument(
      '-t', '--test', help='test mapping from wws key back to font file name',
      nargs='?', const=True, metavar='bool')
  args = parser.parse_args()

  if args.test:
    if not args.dirs:
      # when testing name generation we add the alpha fonts
      args.dirs = NOTO_FONT_PATHS + [
          '[fonts_alpha]/from-pipeline/unhinted/ttf/sans',
          '[fonts_alpha]/from-pipeline/unhinted/ttf/serif']
    test(args.dirs)
  else:
    if not args.dirs:
      # when not testing we just use the standard fonts
      args.dirs = NOTO_FONT_PATHS
    fonts = get_noto_fonts(paths=args.dirs)
    for font in fonts:
      print font.filepath
      for attr in font._fields:
        print '  %15s: %s' % (attr, getattr(font, attr))


if __name__ == "__main__":
    main()
