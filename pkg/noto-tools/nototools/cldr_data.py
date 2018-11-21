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

import argparse
import collections
import os
from os import path
import re
import unicode_data
import xml.etree.cElementTree as ElementTree

from nototools import extra_locale_data

TOOLS_DIR = path.abspath(path.join(path.dirname(__file__), os.pardir))
CLDR_DIR = path.join(TOOLS_DIR, 'third_party', 'cldr')

# control print of debug/trace info when we synthesize the data
_DEBUG = False

# for inspection/debugging, allow turning off of extra locale data
_USE_EXTRA_LOCALE_DATA = True

# Maps from a less-specific tag to tuple of lang, script, region
# Keys either have a lang or 'und'.  If lang, then script or region.  If und,
# then either script or region or both.
_LIKELY_SUBTAGS = {}

def _parse_likely_subtags():
  if _LIKELY_SUBTAGS:
    return

  data_file = path.join(CLDR_DIR, 'common', 'supplemental', 'likelySubtags.xml')
  tree = ElementTree.parse(data_file)

  for tag in tree.findall('likelySubtags/likelySubtag'):
    from_tag = tag.get('from').replace('_', '-')
    to_tag = tag.get('to').split('_')
    _LIKELY_SUBTAGS[from_tag] = to_tag
    # print 'likely subtag from %s -> %s' % (from_tag, to_tag)

  _LIKELY_SUBTAGS.update(extra_locale_data.LIKELY_SUBTAGS)


# from language elements
# lang has no script tag
_LANG_TO_REGIONS = collections.defaultdict(set)

# from language elements
# lang has no script tag
_LANG_TO_SCRIPTS = collections.defaultdict(set)

# from territory elements
# values are lang-script, script is based on likely subtag data if not present
# in the territory element data.
# if lang has script tag, the script is also in lang_to_scripts.
_REGION_TO_LANG_SCRIPTS = collections.defaultdict(set)

_LOCALE_TO_PARENT = {}

def _parse_supplemental_data():
  if _LOCALE_TO_PARENT:
    return

  # _LIKELY_SUBTAGS data used directly below
  _parse_likely_subtags()

  data_file = path.join(
      CLDR_DIR, 'common', 'supplemental', 'supplementalData.xml')
  root = ElementTree.parse(data_file).getroot()

  for language_tag in root.iter('language'):
    attribs = language_tag.attrib

    if 'alt' in attribs:
      assert attribs['alt'] == 'secondary'

    lang = attribs['type']

    if 'territories' in attribs:
      territories = set(attribs['territories'].split(' '))
      _LANG_TO_REGIONS[lang].update(territories)

    if 'scripts' in attribs:
      scripts = set(attribs['scripts'].split(' '))
      _LANG_TO_SCRIPTS[lang].update(scripts)

  langs_missing_likely_subtag_data = []
  for tag in root.iter('territory'):
    territory = tag.get('type')
    for child in tag:
      assert child.tag == 'languagePopulation'
#     if 'officialStatus' not in child.attrib:
#       continue  # Skip non-official languages
      lang = child.get('type')
      if lang == 'und':
        # no point, this data is typically uninhabited small islands and
        # Antarctica
        continue
      ix = lang.find('_')
      if ix == -1:
        key = lang + '-' + territory
        try:
          likely_tuple = _LIKELY_SUBTAGS[key]
        except:
          try:
            likely_tuple = _LIKELY_SUBTAGS[lang]
          except:
            # hmmm, language tag for territory not in likely subtags data
            # filed bug with CLDR, for now patch fixes here
            if lang in ['bsc', 'mfv', 'snf', 'tnr']:
              script = 'Latn'
            elif lang in ['mey']:
              script = 'Arab'
            else:
              langs_missing_likely_subtag_data.append(key)
              likely_tuple = (lang, script, territory)
        script = likely_tuple[1]
      else:
        script = lang[ix + 1:]
        lang = lang[:ix]
      lang_script = lang + '-' + script
      _REGION_TO_LANG_SCRIPTS[territory].add(lang_script)
      _LANG_TO_REGIONS[lang].add(territory)
      _LANG_TO_SCRIPTS[lang].add(script)

  if langs_missing_likely_subtag_data:
    print 'cldr_data: %d keys not in likely subtags:' % len(
        langs_missing_likely_subtag_data)
    for k in sorted(langs_missing_likely_subtag_data):
      print ' ', k
    print 'cldr_data: defaulting script to Latn'
    # raise Exception('oops')

  # Use likely subtag data mapping script to lang to extend lang_to_scripts.
  known_scripts = set()
  for scripts in _LANG_TO_SCRIPTS.values():
    known_scripts |= scripts

  for script in known_scripts:
    und_scr = 'und-' + script
    if und_scr in _LIKELY_SUBTAGS:
      lang = _LIKELY_SUBTAGS[und_scr][0]
      if lang != 'und' and script not in _LANG_TO_SCRIPTS[lang]:
        if _DEBUG:
          print 'lang to scripts missing script %s for %s (from %s)' % (
              script, lang, ', '.join(_LANG_TO_SCRIPTS[lang]))
        _LANG_TO_SCRIPTS[lang].add(script)

  if _USE_EXTRA_LOCALE_DATA:
    # Supplement lang to script mapping with extra locale data
    for lang, scripts in extra_locale_data.LANG_TO_SCRIPTS.iteritems():
      _LANG_TO_SCRIPTS[lang] |= set(scripts)

    # Use extra locale data's likely subtag info to change the supplemental
    # data we got from the language and territory elements.
    # 1) Add the script to the scripts for the language
    # 2) Add the lang_script to the lang_scripts for the region
    for tags in extra_locale_data.LIKELY_SUBTAGS.values():
      lang = tags[0]
      script = tags[1]
      region = tags[2]
      lang_scripts = _LANG_TO_SCRIPTS[lang]
      if script not in lang_scripts:
        if _DEBUG:
          print ('extra likely subtags lang %s has script %s but supplemental '
                 'only has [%s]') % (
                     lang, script, ', '.join(sorted(lang_scripts)))
        if len(lang_scripts) == 1:
          replacement = set([script])
          if _DEBUG:
            print 'replacing %s with %s' % (lang_scripts, replacement)
          _LANG_TO_SCRIPTS[lang] = replacement
        else:
          _LANG_TO_SCRIPTS[lang].add(script)
      lang_script = lang + '-' + script
      # skip ZZ region
      if region != 'ZZ' and lang_script not in _REGION_TO_LANG_SCRIPTS[region]:
        if _DEBUG:
          print 'extra lang_script %s not in cldr for %s, adding' % (
              lang_script, region)
        _REGION_TO_LANG_SCRIPTS[region].add(lang_script)
        _LANG_TO_REGIONS[lang].add(region)

    for tup in extra_locale_data.REGION_TO_LANG_SCRIPTS.iteritems():
      territory, lang_scripts = tup
      _REGION_TO_LANG_SCRIPTS[territory] |= set(lang_scripts)
      for lang_script in lang_scripts:
        lang, script = lang_script.split('-')
        _LANG_TO_REGIONS[lang].add(territory)
        _LANG_TO_SCRIPTS[lang].add(script)

  for tag in root.iter('parentLocale'):
    parent = tag.get('parent')
    parent = parent.replace('_', '-')
    for locl in tag.get('locales').split(' '):
      locl = locl.replace('_', '-')
      _LOCALE_TO_PARENT[locl] = parent

  _LOCALE_TO_PARENT.update(extra_locale_data.PARENT_LOCALES)


def known_langs():
  _parse_supplemental_data()
  # Assume this is a superset of the keys in _LANG_TO_REGIONS
  return _LANG_TO_SCRIPTS.keys()


def known_regions():
  _parse_supplemental_data()
  return _REGION_TO_LANG_SCRIPTS.keys()


def lang_to_regions(lang):
  _parse_supplemental_data()
  try:
    return _LANG_TO_REGIONS[lang]
  except:
    return None


def lang_to_scripts(lang):
  _parse_supplemental_data()
  try:
    return _LANG_TO_SCRIPTS[lang]
  except:
    return None


def region_to_lang_scripts(region_tag):
  _parse_supplemental_data()
  try:
    return _REGION_TO_LANG_SCRIPTS[region_tag]
  except:
    return None


def get_likely_script(lang_tag):
  return get_likely_subtags(lang_tag)[1]


def get_likely_subtags(lang_tag):
  if not lang_tag:
    raise ValueError('empty lang tag')
  lang_tag = lang_tag.replace('_', '-')
  _parse_likely_subtags()
  tag = lang_tag
  while True:
    try:
      result = _LIKELY_SUBTAGS[tag]

      # supply provided parts
      m = LSRV_RE.match(lang_tag)
      if not m:
        if _DEBUG:
          print 'regex did not match locale \'%s\'' % loc_tag
        return result
      lang = m.group(1)
      script = m.group(2)
      region = m.group(3)
      variant = m.group(4)
      if script or region or variant:
        temp = list(result)
        if script:
          temp[1] = script
        if region:
          temp[2] = region
        if variant:
          temp.append(variant)
        result = tuple(temp)
      return result
    except KeyError:
      ix = tag.rfind('-')
      if ix == -1:
        break
      tag = tag[:ix]
      if tag == 'und':
        # stop default to 'en' for unknown scripts
        break

  if _DEBUG:
    print 'no likely subtag for %s' % lang_tag
  tags = lang_tag.split('-')
  return (tags[0], tags[1] if len(tags) > 1 else 'Zzzz',
          tags[2] if len(tags) > 2 else 'ZZ')


_SCRIPT_METADATA = {}

def _parse_script_metadata():
  global _SCRIPT_METADATA
  data = open(path.join(
      CLDR_DIR, 'common', 'properties', 'scriptMetadata.txt')).read()
  parsed_data = unicode_data._parse_semicolon_separated_data(data)
  _SCRIPT_METADATA = {line[0]:tuple(line[1:]) for line in parsed_data}


def is_script_rtl(script):
  if not _SCRIPT_METADATA:
    _parse_script_metadata()
  try:
    return _SCRIPT_METADATA[script][5] == 'YES'
  except KeyError:
    # special case a few codes and data we have that hasn't been
    # updated.  Also special case locale-script codes, we have some.
    if script == 'Adlm':
      return True
    if script in ['Zsym', 'Zsye', 'Hrkt', 'Jpan']:
      return False
    # we really should throw an exception
    if _DEBUG:
      print 'No script metadata for %s' % script
    return False


def is_rtl(lang_tag):
  tags = lang_tag.split('-')
  if len(tags) > 1:
    script = tags[1]
  else:
    script = get_likely_script(tags[0])
  return is_script_rtl(script)


_LANGUAGE_NAME_FROM_FILE_CACHE = {}

def _get_language_name_from_file(language, cldr_file_path):
  cache_key = (language, cldr_file_path)
  try:
    return _LANGUAGE_NAME_FROM_FILE_CACHE[cache_key]
  except KeyError:
    pass

  data_file = path.join(CLDR_DIR, cldr_file_path)
  try:
    root = ElementTree.parse(data_file).getroot()
  except IOError:
    _LANGUAGE_NAME_FROM_FILE_CACHE[cache_key] = None
    return None

  parent = root.find('.//languages')
  if parent is None:
    return None
  for tag in parent:
    assert tag.tag == 'language'
    if tag.get('type').replace('_', '-') == language:
      _LANGUAGE_NAME_FROM_FILE_CACHE[cache_key] = unicode(tag.text)
      return _LANGUAGE_NAME_FROM_FILE_CACHE[cache_key]
  return None


def parent_locale(locale):
  if not _LOCALE_TO_PARENT:
    _parse_supplemental_data()

  if locale in _LOCALE_TO_PARENT:
    return _LOCALE_TO_PARENT[locale]
  if '-' in locale:
    return locale[:locale.rindex('-')]
  if locale == 'root':
    return None
  return 'root'


def get_native_language_name(lang_scr, exclude_script=False):
    """Get the name of a language/script in its own locale."""

    if '-' in lang_scr:
      lang = lang_scr.split('-')[0]
    else:
      lang = lang_scr
      lang_scr = None

    if exclude_script or not lang_scr:
      langs = [lang]
    else:
      langs = [lang_scr, lang]  # lang_scr first since we want to try that first

    for lang in langs:
      try:
        return extra_locale_data.NATIVE_NAMES[lang]
      except KeyError:
        pass

    locale = lang_scr
    while locale != 'root':
      filename = locale.replace('-', '_') + '.xml'
      for subdir in ['common', 'seed']:
        cldr_file_path = path.join(subdir, 'main', filename)
        for lang in langs:
          native_name = _get_language_name_from_file(lang, cldr_file_path)
          if native_name:
            return native_name
      locale = parent_locale(locale)
    return None


def _xml_to_dict(element):
  result = {}
  for child in list(element):
    if 'alt' in child.attrib:
      continue
    key = child.get('type')
    key = key.replace('_', '-')
    result[key] = unicode(child.text)
  return result


_ENGLISH_LANGUAGE_NAMES = {}
_ENGLISH_SCRIPT_NAMES = {}
_ENGLISH_TERRITORY_NAMES = {}

def _parse_english_labels():
  global _ENGLISH_LANGUAGE_NAMES, _ENGLISH_SCRIPT_NAMES
  global _ENGLISH_TERRITORY_NAMES

  if _ENGLISH_LANGUAGE_NAMES:
    return

  data_file = path.join(CLDR_DIR, 'common', 'main', 'en.xml')
  root = ElementTree.parse(data_file).getroot()
  ldn = root.find('localeDisplayNames')

  _ENGLISH_LANGUAGE_NAMES = _xml_to_dict(ldn.find('languages'))
  _ENGLISH_SCRIPT_NAMES = _xml_to_dict(ldn.find('scripts'))
  _ENGLISH_TERRITORY_NAMES = _xml_to_dict(ldn.find('territories'))

  # Add languages used that miss names
  _ENGLISH_SCRIPT_NAMES.update(extra_locale_data.ENGLISH_SCRIPT_NAMES)
  _ENGLISH_LANGUAGE_NAMES.update(extra_locale_data.ENGLISH_LANGUAGE_NAMES)


def get_english_script_name(script):
  """Get the name of a script in the en-US locale."""
  _parse_english_labels()
  try:
    return _ENGLISH_SCRIPT_NAMES[script]
  except KeyError:
    return script


def get_english_language_name(lang_scr):
  """Get the name of a language/script in the en-US locale."""
  _parse_english_labels()

  try:
    return _ENGLISH_LANGUAGE_NAMES[lang_scr]
  except KeyError:
    if '-' in lang_scr:
      lang, script = lang_scr.split('-')
      try:
        langName = _ENGLISH_LANGUAGE_NAMES[lang]
        name = '%s (%s script)' % (langName, _ENGLISH_SCRIPT_NAMES[script])
        return name
      except KeyError:
        pass
  if _DEBUG:
    print 'No English name for \'%s\'' % lang_scr
  return None


def get_english_region_name(region):
  _parse_english_labels()
  try:
    return _ENGLISH_TERRITORY_NAMES[region]
  except KeyError:
    if _DEBUG:
      print 'No English name for region %s' % region
    return ''


def _read_character_at(source, pointer):
  """Reads a code point or a backslash-u-escaped code point."""
  while pointer < len(source) and source[pointer] == ' ':
    pointer += 1

  if pointer >= len(source):
    raise IndexError('pointer %d out of range 0-%d' % (pointer, len(source)))

  if source[pointer] == '\\':
    if source[pointer+1].upper() == 'U':
      end_of_hex = pointer+2
      while (end_of_hex < len(source)
           and source[end_of_hex].upper() in '0123456789ABCDEF'):
        end_of_hex += 1
      if end_of_hex-(pointer+2) not in {4, 5, 6, 8}:
        raise Exception(
            'cldr_data: parse of unicode escape failed at %d: %s' % (
                pointer, source[pointer:pointer + 10]))
      hex_code = source[pointer+2:end_of_hex]
      return end_of_hex, unichr(int(hex_code, 16))
    else:
      return pointer+2, source[pointer+1]
  else:
    return pointer+1, source[pointer]


def unicode_set_string_to_list(us_str):
  if us_str[0] == '[':
    assert us_str[-1] == ']'
    us_str = us_str[1:-1]

  result = []
  pointer = 0
  while pointer < len(us_str):
    if us_str[pointer] in ' ':
      pointer += 1
    elif us_str[pointer] == '{':
      multi_char = ''
      mc_ptr = pointer+1
      while us_str[mc_ptr] != '}':
        mc_ptr, char = _read_character_at(us_str, mc_ptr)
        multi_char += char
      result.append(multi_char)
      pointer = mc_ptr+1
    elif us_str[pointer] == '-':
      while pointer + 1 < len(us_str) and us_str[pointer + 1] == ' ':
        pointer += 1
        continue
      if pointer + 1 == len(us_str): # hyphen before ']' is special
        result.append('-')
        break
      previous = result[-1]
      assert len(previous) == 1  # can't have ranges with strings
      previous = ord(previous)

      pointer, last = _read_character_at(us_str, pointer+1)
      assert last not in [' ', '\\', '{', '}', '-']
      last = ord(last)
      result += [unichr(code) for code in range(previous+1, last+1)]
    else:
      pointer, char = _read_character_at(us_str, pointer)
      result.append(char)

  return result


_exemplar_from_file_cache = {}

def get_exemplar_from_file(cldr_file_path, types=['']):
  cache_key = cldr_file_path + '_'.join(sorted(types))
  try:
    return _exemplar_from_file_cache[cache_key]
  except KeyError:
    pass

  data_file = path.join(CLDR_DIR, cldr_file_path)
  try:
    root = ElementTree.parse(data_file).getroot()
  except IOError:
    _exemplar_from_file_cache[cldr_file_path] = None
    return None

  exemplars = []
  for tag in root.iter('exemplarCharacters'):
    if 'type' in tag.attrib:
      typeval = tag.attrib['type']
    else:
      typeval = ''
    if not typeval in types:
      continue
    # TODO(dougfelt): when multiple types are used, append in fixed order
    # and don't rely on order in the xml file?
    try:
      cat = frozenset(['L', 'M', 'N'])
      def accept(s):
        return len(s) > 1 or unicode_data.category(s)[0] in cat
      exemplar_list = [
          s for s in unicode_set_string_to_list(tag.text)
          if accept(s)]
      exemplars.extend(unicode_set_string_to_list(tag.text))
    except Exception as e:
      print 'failed parse of %s' % cldr_file_path
      raise e
    break

  _exemplar_from_file_cache[cldr_file_path] = exemplars
  return exemplars


_exemplar_from_extra_data_cache = {}

def get_exemplar_from_extra_data(loc_tag):
  try:
    return _exemplar_from_extra_data_cache[loc_tag]
  except KeyError:
    pass

  try:
    exemplar_string = extra_locale_data.EXEMPLARS[loc_tag]
    exemplars = unicode_set_string_to_list(exemplar_string)
  except KeyError:
    exemplars = None

  _exemplar_from_extra_data_cache[loc_tag] = exemplars
  return exemplars


# Technically, language tags are case-insensitive, but the CLDR data is cased,
# this leaves out lots of edge cases of course.  Sometimes we use lower case
# script tags so this allows that, but it requires the lang tag to be lower case
# and the region tag to be all upper case.
LSRV_RE = re.compile(r'^([a-z]{2,3})(?:[_-]([A-Za-z][a-z]{3}))?'
                     r'(?:[_-]([A-Z]{2}|\d{3}))?(?:[_-]([A-Z]{5,8}))?$')

def get_exemplar_and_source(loc_tag):
  # don't use exemplars encoded without script if the requested script is not
  # the default
  m = LSRV_RE.match(loc_tag)
  script = m.group(2) if m else None
  while loc_tag != 'root':
    for directory in ['common', 'seed', 'exemplars']:
      exemplar = get_exemplar_from_file(
          path.join(directory, 'main', loc_tag.replace('-', '_') + '.xml'),
          ['', 'auxiliary'])
      if exemplar:
        return exemplar, loc_tag + '_ex_' + directory
    exemplar = get_exemplar_from_extra_data(loc_tag)
    if exemplar:
      return exemplar, loc_tag + '_ex_extra'
    loc_tag = parent_locale(loc_tag)
    if loc_tag == 'root' or (
        script and get_likely_subtags(loc_tag)[1] != script):
      break
  return None, None


def loc_tag_to_lsrv(loc_tag):
  """Convert a locale tag to a tuple of lang, script, region, and variant.
  Supplies likely script if missing."""
  m = LSRV_RE.match(loc_tag)
  if not m:
    if _DEBUG:
      print 'regex did not match locale \'%s\'' % loc_tag
    return None
  lang = m.group(1)
  script = m.group(2)
  region = m.group(3)
  variant = m.group(4)

  if not script:
    tag = lang
    if region:
      tag += '-' + region
    try:
      script = get_likely_script(tag)
    except KeyError:
      try:
        script = get_likely_script(lang)
      except KeyError:
        pass
  return (lang, script, region, variant)


def lsrv_to_loc_tag(lsrv):
  return '-'.join([tag for tag in lsrv if tag])


_lang_scr_to_lit_pops = {}

def _init_lang_scr_to_lit_pops():
  data_file = path.join(
      CLDR_DIR, 'common', 'supplemental', 'supplementalData.xml')
  root = ElementTree.parse(data_file).getroot()

  tmp_map = collections.defaultdict(list)
  for territory in root.findall('territoryInfo/territory'):
    region = territory.attrib['type']
    population = int(territory.attrib['population'])
    lit_percent = float(territory.attrib['literacyPercent']) / 100.0
    for lang_pop in territory.findall('languagePopulation'):
      lang = lang_pop.attrib['type']
      pop_percent = float(lang_pop.attrib['populationPercent']) / 100.0
      if 'writingPercent' in lang_pop.attrib:
        lang_lit_percent = float(lang_pop.attrib['writingPercent']) / 100.0
      else:
        lang_lit_percent = lit_percent

      locale = loc_tag_to_lsrv(lang + '_' + region)
      lang_scr = '-'.join([locale[0], locale[1]])
      lit_pop = int(population * pop_percent * lang_lit_percent)
      tmp_map[lang_scr].append((region, lit_pop))

  # make it a bit more useful by sorting the value list in order of decreasing
  # population and converting the list to a tuple
  for lang_scr, values in tmp_map.iteritems():
    _lang_scr_to_lit_pops[lang_scr] = tuple(
        sorted(values, key=lambda (r, p): (-p, r)))


def get_lang_scr_to_lit_pops():
  """Return a mapping from lang_scr to a list of tuples of region and
  population sorted in descending order by population.
  """
  if not _lang_scr_to_lit_pops:
    _init_lang_scr_to_lit_pops()
  return _lang_scr_to_lit_pops;


def lang_scr_to_lit_pops(lang_scr):
  try:
    return get_lang_scr_to_lit_pops()[lang_scr]
  except KeyError:
    return None


def lang_scr_to_global_lit_pop(lang_scr):
  lit_pops = lang_scr_to_lit_pops(lang_scr)
  if not lit_pops:
    return 0
  return sum(p for _, p in lit_pops)


def get_lang_scrs_by_decreasing_global_lit_pop():
  lit_pops = get_lang_scr_to_lit_pops()
  result = []
  for lang_scr in lit_pops:
    global_pop = sum(p for _, p in lit_pops[lang_scr])
    result.append((global_pop, lang_scr))
  result.sort(reverse=True)
  return result


def main():
  global _DEBUG, _USE_EXTRA_LOCALE_DATA
  parser = argparse.ArgumentParser()
  parser.add_argument(
      '-rl', '--region_to_lang',  help='dump region to lang script info',
      metavar='region', nargs='*')
  parser.add_argument(
      '-lr', '--lang_to_region', help='dump lang to region info',
      metavar='lang', nargs='*')
  parser.add_argument(
      '-ls', '--lang_to_script', help='dump lang to script info',
      metavar='lang', nargs='*')
  parser.add_argument(
      '-d', '--debug', help='turn on debug flag when building data',
      action='store_true')
  parser.add_argument(
      '-nx', '--no_extra', help='turn off extra locale data',
      action='store_true')

  args = parser.parse_args();
  if args.debug:
    _DEBUG = True
  if args.no_extra:
    _USE_EXTRA_LOCALE_DATA = False

  if args.region_to_lang != None:
    print 'region to lang+script'
    regions = args.region_to_lang or sorted(known_regions())
    for r in regions:
      print '%s (%s):' % (r, get_english_region_name(r))
      for ls in sorted(region_to_lang_scripts(r)):
        print '  %s' % ls

  if args.lang_to_region != None:
    print 'lang to region'
    langs = args.lang_to_region or sorted(known_langs())
    for l in langs:
      print '%s (%s):' % (l, get_english_language_name(l))
      for r in sorted(lang_to_regions(l)):
        print '  %s' % r

  if args.lang_to_script != None:
    print 'lang to script'
    langs = args.lang_to_script or sorted(known_langs())
    for l in langs:
      print '%s (%s):' % (l, get_english_language_name(l))
      for s in sorted(lang_to_scripts(l)):
        print '  %s' % s


if __name__ == "__main__":
    main()
