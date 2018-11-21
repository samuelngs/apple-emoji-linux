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

"""
Functions to return information on scripts and langs, primarily for the
Noto website.

The data is generated based on information in cldr_data and unicode_data,
and cached in this module.  The primary functions return the primary
language for each script (sometimes 'und', e.g. for Dsrt), and the names
for each lang_script that has an English name (in English and in the script
when known).  Other functions return the set of scripts and the set of
lang_scripts (that have english names).
"""

import argparse
import collections
import os
from os import path
import re
import sys

from nototools import cldr_data
from nototools import unicode_data

# controls printing of debug/trace information
# normally disabled
def _log(msg):
  # print >> sys.stderr, '#lang_data: ' + msg
  pass

def is_excluded_script(script_code):
  return script_code in ['Zinh', 'Zyyy', 'Zzzz']


def script_includes(script_code):
  """Returns a set of script codes 'included' by the provided one.  Intended to
  deal with script codes like 'Jpan' used to describe writing systems that
  use/require multiple scripts.  The script code itself (and other subsets)
  are also included in the result."""
  if script_code not in scripts():
    raise ValueError('!not a script code: %s' % script_code)
  if script_code == 'Hrkt':
    return frozenset(['Hrkt', 'Hira', 'Kana'])
  if script_code == 'Jpan':
    return frozenset(['Jpan', 'Hrkt', 'Hani', 'Hira', 'Kana'])
  if script_code == 'Kore':
    return frozenset(['Kore', 'Hang'])
  return frozenset([script_code])


def _create_lang_data():
  """Generates language data from CLDR plus extensions.
  Returns a mapping from lang to a tuple of:
  - a set of scripts used in some region
  - a set of scripts not used in any region."""

  all_lang_scripts = collections.defaultdict(set)
  used_lang_scripts = collections.defaultdict(set)
  known_scripts = set()
  all_langs = set()
  for region in cldr_data.known_regions():
    lang_scripts = cldr_data.region_to_lang_scripts(region)
    for lang_script in lang_scripts:
      lang, script = lang_script.split('-')
      known_scripts.add(script)
      if lang == 'und':
        _log('used lang is und for script %s in region %s' % (script, region))
        continue
      used_lang_scripts[lang].add(script)
      all_lang_scripts[lang].add(script)
      all_langs.add(lang)

  for lang in cldr_data.known_langs():
    lang_scripts = cldr_data.lang_to_scripts(lang)
    all_lang_scripts[lang] |= lang_scripts
    known_scripts |= lang_scripts
    all_langs.add(lang)

  for lang in all_langs:
    script = cldr_data.get_likely_script(lang)
    if not is_excluded_script(script):
      all_lang_scripts[lang].add(script)

  for script in unicode_data.all_scripts():
    if is_excluded_script(script):
      continue
    lang = cldr_data.get_likely_subtags('und-' + script)[0]
    if lang != 'und':
      if script not in all_lang_scripts[lang]:
        _log('adding likely lang %s for script %s' % (lang, script))
      all_lang_scripts[lang].add(script)
    elif script not in known_scripts:
      _log('adding script with unknown language %s' % script)
      all_lang_scripts[lang].add(script)
    else:
      _log('script %s with unknown language already seen' % script)

  # Patch: ensure ryu-Jpan exists
  # - Okinawan can be written in either Kana or a combination of Hira
  #   and Kanji. Rather than take a strong position on this, add a
  #   mapping to Jpan.
  all_lang_scripts['ryu'].add('Jpan')

  # Patch: see noto-fonts#133 comment on June 8th.
  all_lang_scripts['tlh'] |= {'Latn', 'Piqd'}

  all_langs = used_lang_scripts.keys() + all_lang_scripts.keys()
  lang_data = {}
  for lang in all_langs:
    if lang in used_lang_scripts:
      if lang in all_lang_scripts:
        unused_set = all_lang_scripts[lang] - used_lang_scripts[lang]
        lang_data[lang] = (used_lang_scripts[lang].copy(),
                           unused_set if unused_set else set())
      else:
        lang_data[lang] = (used_lang_scripts[lang].copy(), set())
    else:
      lang_data[lang] = (set(), all_lang_scripts[lang].copy())

  return lang_data


def _langs_with_no_scripts(lang_script_data):
  """Return a set of langs with no scripts in lang_script_data."""
  return set([k for k in lang_script_data
              if not (lang_script_data[k][0] or lang_script_data[k][1])])


def _remove_keys_from_dict(keys, some_dict):
  for k in keys:
    some_dict.pop(k, None)


def _create_script_to_default_lang(lang_script_data):
  """Iterates over all the scripts in lang_script_data, and returns a map
  from each script to the default language code, generally based on cldr
  likely subtag data.  This assigns 'en' to Latn by fiat (cldr defaults to
  'und').  Some other scripts (e.g. Dsrt) just get 'und'.

  This checks that the default lang for a script actually uses that script
  in lang_script_data, when the default lang is not 'und'.
  """

  script_to_default_lang = {}
  all_scripts = set()
  script_to_used = collections.defaultdict(set)
  script_to_unused = collections.defaultdict(set)
  for lang in lang_script_data:
    used, unused = lang_script_data[lang]
    all_scripts |= used
    all_scripts |= unused
    for script in used:
      script_to_used[script].add(lang)
    for script in unused:
      script_to_unused[script].add(lang)

  # Add scripts without langs.
  all_scripts.add('Zsym')
  all_scripts.add('Zsye')

  # Patch Klingon as default lang for (unused) script pIqaD
  script_to_used['Piqd'].add('tlh')

  for script in sorted(all_scripts):
    default_lang = cldr_data.get_likely_subtags('und-' + script)[0]

    if default_lang == 'und':
      if script == 'Latn':
        default_lang = 'en' # cultural bias...
      else:
        _log('no default lang for script %s' % script)
        langs = script_to_used[script]
        if langs:
          default_lang = iter(langs).next()
          _log('using used lang %s from %s' % (default_lang, langs))
        else:
          langs = script_to_unused[script]
          if langs:
            default_lang = iter(langs).next()
            _log('using unused lang %s from %s' % (default_lang, langs))
          else:
            _log('defaulting to \'und\'')
    else:
      used, unused = lang_script_data[default_lang]
      assert script in used or script in unused

    script_to_default_lang[script] = default_lang

  return script_to_default_lang


def _create_lang_script_to_names(lang_script_data):
  """Generate a map from lang-script to English (and possibly native) names.
  Whether the script is included in the name depends on the number of used
  and unused scripts.  If there's one used script, that script is omitted.
  Else if there's no used script and one unused script, that script is
  omitted.  Else the script is included.  If there's no English name for
  the lang_script, it is excluded.
  """

  lang_to_names = {}
  for lang in lang_script_data:
    used, unused = lang_script_data[lang]
    if len(used) == 1:
      exclude_script = iter(used).next()
    elif not used and len(unused) == 1:
      exclude_script = iter(unused).next()
    else:
      exclude_script = ''

    for script in (used | unused):
      lang_script = lang + '-' + script
      target = lang if script == exclude_script else lang_script
      # special case, not generally useful
      if target.startswith('und-'):
        en_name =  cldr_data.get_english_script_name(target[4:]) + ' script'
      else:
        en_name = cldr_data.get_english_language_name(target)
      if not en_name:
        # Easier than patching the cldr_data, not sure I want to go there.
        if lang_script == 'tlh-Piqd':
          en_name = u'Klingon'
        else:
          _log('No english name for %s' % lang_script)
          continue
      native_name = cldr_data.get_native_language_name(
          lang_script, exclude_script)
      if native_name == en_name:
        native_name = None
      lang_to_names[lang_script] = (
          [en_name, native_name] if native_name else [en_name])

  return lang_to_names


_LANG_DATA = None
def _get_lang_data():
  global _LANG_DATA
  if not _LANG_DATA:
    _LANG_DATA = _create_lang_data()
  return _LANG_DATA


_SCRIPT_TO_DEFAULT_LANG = None
def _get_script_to_default_lang():
  global _SCRIPT_TO_DEFAULT_LANG
  if not _SCRIPT_TO_DEFAULT_LANG:
    _SCRIPT_TO_DEFAULT_LANG = _create_script_to_default_lang(_get_lang_data())
  return _SCRIPT_TO_DEFAULT_LANG


_LANG_SCRIPT_TO_NAMES = None
def _get_lang_script_to_names():
  global _LANG_SCRIPT_TO_NAMES
  if not _LANG_SCRIPT_TO_NAMES:
    _LANG_SCRIPT_TO_NAMES = _create_lang_script_to_names(_get_lang_data())
  return _LANG_SCRIPT_TO_NAMES


def scripts():
  return _get_script_to_default_lang().keys()


def script_to_default_lang(script):
  return _get_script_to_default_lang()[script]


def lang_scripts():
  return _get_lang_script_to_names().keys()


def lang_script_to_names(lang_script):
  return _get_lang_script_to_names()[lang_script]


def main():
  lang_data = _get_lang_data()
  print
  print '--------'

  langs_without_scripts = _langs_with_no_scripts(lang_data)
  if langs_without_scripts:
    print 'langs without scripts: ' + ', '.join(sorted(langs_without_scripts))
    _remove_keys_from_dict(langs_without_scripts, lang_data)
    print

  print 'lang data'
  for k in sorted(lang_data):
    used, unused = lang_data[k]
    used_msg = 'used: ' + ', '.join(sorted(used)) if used else None
    unused_msg = 'unused: ' + ', '.join(sorted(unused)) if unused else None
    msg = '; '.join([m for m in (used_msg, unused_msg) if m])
    print k, msg

  print
  print 'lang_script to names'
  lang_script_to_names = _get_lang_script_to_names()
  for t in sorted(lang_script_to_names.iteritems()):
    print '%s: %s' % t

  print
  print 'script to default lang'
  script_to_default_lang = _get_script_to_default_lang()
  for t in sorted(script_to_default_lang.iteritems()):
    print '%s: %s' % t


if __name__ == '__main__':
    main()
