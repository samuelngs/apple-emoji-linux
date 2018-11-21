#!/usr/bin/env python
# Copyright 2015 Google Inc. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Generates script-specific samples (collections of chars) using cldr
exemplar data for languages written in a script."""

import argparse
import codecs
import collections
import locale
import os
from os import path
import re
import shutil
import xml.etree.cElementTree as ElementTree

from nototools import cldr_data
from nototools import create_image
from nototools import extra_locale_data
from nototools import notoconfig
from nototools import tool_utils
from nototools import unicode_data


try:
  from icu import Locale, Collator
  print 'will use icu locale-specific order'
  _HAVE_ICU = True
except ImportError as e:
  print 'will use default locale sort order'
  _HAVE_ICU = False

NOTO_TOOLS = path.abspath(path.join(path.dirname(__file__), os.pardir))

CLDR_DIR = path.join(NOTO_TOOLS, 'third_party', 'cldr')

_VERBOSE = False

def get_script_to_exemplar_data_map():
  """Return a map from script to 3-tuples of:
    - locale tuple (lang, script, region, variant)
    - cldr_relative path to src of exemplar data
    - tuple of the exemplar chars"""

  script_map = collections.defaultdict(dict)
  for directory in ['common', 'seed', 'exemplars']:
    data_dir = path.join(directory, 'main')
    for filename in os.listdir(path.join(CLDR_DIR, data_dir)):
      if not filename.endswith('.xml'):
        continue

      exemplar_list = cldr_data.get_exemplar_from_file(path.join(data_dir, filename))
      if not exemplar_list:
        if _VERBOSE:
          print '  no exemplar list for %s' % path.join(data_dir, filename)
        continue

      lsrv = cldr_data.loc_tag_to_lsrv(filename[:-4])
      if not lsrv:
        if _VERBOSE:
          print '  no lsrv for %s' % path.join(data_dir, filename)
        continue
      src = path.join(directory, filename)
      script = lsrv[1]
      if not script:
        if _VERBOSE:
          print '  no script for %s' % path.join(data_dir, filename)
        continue

      loc_tag = cldr_data.lsrv_to_loc_tag(lsrv)
      loc_to_exemplar_info = script_map[script]
      if loc_tag in loc_to_exemplar_info:
        if _VERBOSE:
          print 'skipping %s, already have exemplars for %s from %s' % (
              src, loc_tag, loc_to_exemplar_info[loc_tag][1])
        continue

      # fix exemplars that look incorrect
      if script == 'Arab' and 'd' in exemplar_list:
        if _VERBOSE:
          print 'found \'d\' in %s for %s' % (src, lsrv)
        no_latin = True
      else:
        no_latin = False
      # exclude exemplar strings, and restrict to letters and digits
      def accept_cp(cp):
        if len(cp) != 1:
          return False
        cat = unicode_data.category(cp)
        if cat[0] != 'L' and cat != 'Nd':
          return False
        if no_latin and cp in 'df':
          return False
        return True
      filtered_exemplar_list = filter(accept_cp, exemplar_list)

      # some exemplar lists don't surround strings with curly braces, and end up
      # with duplicate characters.  Flag these
      exemplar_chars = set()
      dup_chars = set()
      fixed_exemplar_list = []
      for cp in filtered_exemplar_list:
        if cp in exemplar_chars:
          dup_chars.add(cp)
        else:
          exemplar_chars.add(cp)
          fixed_exemplar_list.append(cp)
      if len(dup_chars) > 0 and _VERBOSE:
        print 'duplicate exemplars in %s: %s' % (
            src, ', '.join([u'\u200e%s\u200e (%x)' % (cp, ord(cp)) for cp in dup_chars]))
      loc_to_exemplar_info[loc_tag] = (lsrv, src, tuple(fixed_exemplar_list))

  # supplement with extra locale data
  for loc_tag in extra_locale_data.EXEMPLARS:
    exemplar_list = cldr_data.get_exemplar_from_extra_data(loc_tag)
    lang, script = loc_tag.split('-')
    lsrv = (lang, script, None, None)
    loc_to_exemplar_info = script_map[script]
    src = '[extra locale data]/%s' % loc_tag
    if loc_tag in loc_to_exemplar_info:
      if _VERBOSE:
        print 'skipping %s, already have exemplars for %s from %s' % (
            src, loc_tag, loc_to_exemplar_info[loc_tag][1])
      continue

    # restrict to letters, except for zsym
    def accept_cp(cp):
      cat = unicode_data.category(cp)
      return cat[0] == 'L' or cat == 'Nd'

    if 'Zsym' not in loc_tag:
      filtered_exemplar_list = filter(accept_cp, exemplar_list)
      if len(filtered_exemplar_list) != len(exemplar_list) and _VERBOSE:
        print 'filtered some characters from %s' % src
    else:
      filtered_exemplar_list = exemplar_list
    loc_to_exemplar_info[loc_tag] = (lsrv, src, tuple(filtered_exemplar_list))

  return script_map


def show_rarely_used_char_info(script, loc_map, char_to_lang_map):
  # let's list chars unique to each language
  for loc_tag in sorted(loc_map):
    unique_chars = []
    dual_chars = []
    dual_shared_with = set()
    triple_chars = []
    triple_shared_with = set()
    info = loc_map[loc_tag]
    exemplars = info[2]
    for cp in exemplars:
      num_common_langs = len(char_to_lang_map[cp])
      if num_common_langs == 1:
        unique_chars.append(cp)
      elif num_common_langs == 2:
        dual_chars.append(cp)
        for shared_loc_tag in char_to_lang_map[cp]:
          if shared_loc_tag != loc_tag:
            dual_shared_with.add(shared_loc_tag)
      elif num_common_langs == 3:
        triple_chars.append(cp)
        for shared_loc_tag in char_to_lang_map[cp]:
          if shared_loc_tag != loc_tag:
            triple_shared_with.add(shared_loc_tag)

    script_tag = '-' + script
    if unique_chars:
      print '%s has %d unique chars: %s%s' % (
          loc_tag, len(unique_chars), ' '.join(unique_chars[:100]),
          '...' if len(unique_chars) > 100 else '')
    if dual_chars:
      print '%s shares %d chars (%s%s) with 1 other lang: %s' % (
          loc_tag, len(dual_chars), ' '.join(dual_chars[:20]),
          '...' if len(dual_chars) > 20 else '',
          ', '.join(sorted([loc.replace(script_tag, '') for loc in dual_shared_with])))
    if triple_chars:
      print '%s shares %d chars (%s%s) with 2 other langs: %s' % (
          loc_tag, len(triple_chars), ' '.join(triple_chars[:20]),
          '...' if len(triple_chars) > 20 else '',
          ', '.join(sorted([loc.replace(script_tag, '') for loc in triple_shared_with])))
    if not (unique_chars or dual_chars or triple_chars):
      print '%s shares all chars with 3+ other langs' % loc_tag


def get_char_to_lang_map(loc_map):
  char_to_lang_map = collections.defaultdict(list)
  for loc_tag in sorted(loc_map):
    info = loc_map[loc_tag]
    exemplars = info[2]
    for cp in exemplars:
      if loc_tag in char_to_lang_map[cp]:
        print 'loc %s (from %s) already in char_to_lang_map for %s (%x)' % (
            loc_tag, info[1], cp, ord(cp))
      else:
        char_to_lang_map[cp].append(loc_tag)
  return char_to_lang_map


def char_lang_info(num_locales, char_to_lang_map):
  """Returns a tuple containing
  - characters ordered by the number of langs that use them
  - a list mapping number of shared langs to number of chars shared by those langs"""

  freq_list = []
  hist = [0] * (num_locales + 1)
  for cp in char_to_lang_map:
    num_shared_langs = len(char_to_lang_map[cp])
    if num_shared_langs >= len(hist):
      for shared_lang in char_to_lang_map[cp]:
        if shared_lang not in loc_map:
          print 'loc map does not have \'%s\'!' % shared_lang

    freq_list.append((num_shared_langs, cp))
    if num_shared_langs >= len(hist):
      print 'num shared langs is %d but size of hist is %d' % (num_shared_langs, len(hist))
    hist[num_shared_langs] += 1
  freq_list.sort()
  return [cp for nl, cp in freq_list], hist


def show_char_use_info(script, chars_by_num_langs, char_to_lang_map):
  script_tag = '-' + script
  for cp in chars_by_num_langs:
    langs = char_to_lang_map[cp]
    count = len(langs)
    limit = 12
    without_script = [loc.replace(script_tag, '') for loc in langs[:limit]]
    without_script_str = ', '.join(sorted(without_script))
    if count > limit:
      without_script_str += '...'
    print u'char %s\u200e (%x): %d %s' % (cp, ord(cp), count, without_script_str)
  print 'total chars listed: %d' % len(char_to_lang_map)


def show_shared_langs_hist(hist):
  # histogram - number of chars per number of shared languages
  for i in range(1, len(hist)):
    print '[%3d] %3d %s' % (i, hist[i], 'x' * hist[i])


def get_upper_case_list(char_list):
  """Return the upper case versions where they differ.
  If no char in the list is a lower case variant, the result is empty."""
  # keep in same order as input list.
  upper_case_chars = []
  for cp in char_list:
    upcp = unicode_data.to_upper(cp)
    if upcp != cp:
      upper_case_chars.append(upcp)
  return upper_case_chars


def show_tiers(char_list, num_tiers, tier_size):
  for tier in range(1, num_tiers + 1):
    if tier == 1:
      subset = char_list[-tier_size:]
    else:
      subset = char_list[tier * -tier_size:(tier-1) * -tier_size]
    if not subset:
      break
    tier_chars = sorted(subset)
    print 'tier %d: %s' % (tier, ' '.join(tier_chars))

    upper_case_chars = get_upper_case_list(tier_chars)
    if upper_case_chars:
      print ' upper: ' + ' '.join(upper_case_chars)


def get_rare_char_info(char_to_lang_map, shared_lang_threshold):
  """Returns a tuple of:
  - a set of 'rare_chars' (those used threshold langs or fewer),
  - a mapping from each locale with rare chars to a set of its rare chars"""

  rare_chars = set()
  locs_with_rare_chars = collections.defaultdict(set)
  for cp in char_to_lang_map:
    num_shared_langs = len(char_to_lang_map[cp])
    if num_shared_langs <= shared_lang_threshold:
      rare_chars.add(cp)
      for lang_tag in char_to_lang_map[cp]:
        locs_with_rare_chars[lang_tag].add(cp)
  return rare_chars, locs_with_rare_chars


_lang_for_script_map = {}

def _init_lang_for_script_map():
  locs_by_lit_pop = [loc for _, loc in cldr_data.get_lang_scrs_by_decreasing_global_lit_pop()]
  for t in locs_by_lit_pop:
    lsrv = cldr_data.loc_tag_to_lsrv(t)
    script = lsrv[1]
    if script not in _lang_for_script_map:
      lang = lsrv[0]
      # print '%s lang => %s' % (script, lang)
      _lang_for_script_map[script] = lang


def lang_for_script(script):
  """Return the most common language for a script based on literate population."""
  # should use likely subtag data for this.
  # the current code assumes all we want is lang -> script, I'd have to change
  # it to map locale->locale. Right now I dont' get Hant -> zh_Hant, only
  # Hant -> zh, which isn't good enough I think.
  if not _lang_for_script_map:
    _init_lang_for_script_map()
  return _lang_for_script_map.get(script)


def select_rare_chars_for_loc(script, locs_with_rare_chars, shared_lang_threshold,
                              char_to_lang_map):
  """Return a list of 2-tuples of loc and selected rare chars,
  ordered by decreasing literate population of the locale."""

  rarity_threshold_map = {}
  for lang_tag in locs_with_rare_chars:
    rarity_threshold_map[lang_tag] = shared_lang_threshold

  selected = []
  locs_by_lit_pop = [loc for _, loc in cldr_data.get_lang_scrs_by_decreasing_global_lit_pop()]
  # examine locales in decreasing order of literate population
  for loc_tag in locs_by_lit_pop:
    if script not in loc_tag:
      continue
    loc_tag = loc_tag.replace('_', '-')
    if loc_tag not in locs_with_rare_chars:
      continue
    most_specific_chars = set()
    most_specific_chars_count = rarity_threshold_map[loc_tag]
    # From the rare chars for this locale, select those that
    # are most specific to this language. In most cases they
    # are unique to this language.
    for cp in locs_with_rare_chars[loc_tag]:
      num_chars = len(char_to_lang_map[cp])
      if num_chars <= most_specific_chars_count:
        if num_chars < most_specific_chars_count:
          most_specific_chars = set()
        most_specific_chars.add(cp)
        most_specific_chars_count = num_chars
    if most_specific_chars:
      selected.append((loc_tag, most_specific_chars))
      for cp in most_specific_chars:
        for tag in char_to_lang_map[cp]:
          if rarity_threshold_map[tag] > most_specific_chars_count:
            rarity_threshold_map[tag] = most_specific_chars_count
  return selected


def show_selected_rare_chars(selected):
  print 'langs with rare chars by lang pop:'
  for lang_tag, chars in selected:
    print '%10s: %s' % (lang_tag, ', '.join(sorted(chars)))


def sort_for_script(cp_list, script):
  lang = lang_for_script(script)
  if not lang:
    print 'cannot sort for script, no lang for %s' % script
    return cp_list
  if _HAVE_ICU:
    from icu import Locale, Collator
    loc = Locale(lang + '_' + script)
    col = Collator.createInstance(loc)
    return sorted(cp_list, cmp=col.compare)
  else:
    import locale
    return sorted(cp_list, cmp=locale.strcoll)


def addcase(sample, script):
  cased_sample = []
  for cp in sample:
    ucp = unicode_data.to_upper(cp)
    if ucp != cp and ucp not in sample: # Copt has cased chars paired in the block
      cased_sample.append(ucp)
  if cased_sample:
    cased_sample = ' '.join(cased_sample)
    if _VERBOSE:
      print 'add case for %s' % script
    return sample + '\n' + cased_sample
  return sample


def _generate_excluded_characters():
  # Some of these exclusions are desired, and some are reluctantly applied because
  # Noto currently does not support some characters.  We use the generated
  # data as fallback samples on a per-script and not per-font basis, which is also
  # a problem.

  # Religious characters
  # deva OM, Arabic pbuh, bismillah
  codepoints = [0x950, 0xfdfa, 0xfdfd]

  # Cyrillic characters not in sans or serif
  codepoints.append(0x2e2f)
  for cp in range(0xa640, 0xa680):
    codepoints.append(cp)

  # Arabic character not in kufi
  codepoints.append(0x08a0)

  chars = set()
  for cp in codepoints:
    chars.add(unichr(cp))
  return frozenset(chars)

_EXCLUDE_CHARS = _generate_excluded_characters()


def generate_sample_for_script(script, loc_map):
  num_locales = len(loc_map)

  if num_locales == 1:
    tag, info = loc_map.iteritems().next()
    exemplars = info[2]
    ex_len = len(exemplars)
    info = '%s (1 locale)\nfrom exemplars for %s (%s%d chars)' % (
        script, tag, 'first 60 of ' if ex_len > 60 else '', ex_len)
    # don't sort, rely on exemplar order
    sample = ' '.join(exemplars[:60])
    sample = addcase(sample, script)
    return sample, info

  script_tag = '-' + script

  char_to_lang_map = get_char_to_lang_map(loc_map)
  if len(char_to_lang_map) <= 60:
    info = '%s (%d locales)\nfrom merged exemplars (%d chars) from %s' % (
        script, num_locales, len(char_to_lang_map),
        ', '.join([loc.replace(script_tag, '') for loc in loc_map]))
    sample = ' '.join(sort_for_script(list(char_to_lang_map), script))
    sample = addcase(sample, script)
    return sample, info

  # show_rarely_used_char_info(script, loc_map, char_to_lang_map)

  chars_by_num_langs, num_langs_to_num_chars = char_lang_info(
      num_locales, char_to_lang_map)

  # show_char_use_info(chars_by_num_langs, char_to_lang_map)

  # show_shared_langs_hist(num_langs_to_num_chars)

  # show_tiers(chars_by_num_langs, 3, 40)

  shared_lang_threshold = min(7, num_locales)
  rare_chars, locs_with_rare_chars = get_rare_char_info(
      char_to_lang_map, shared_lang_threshold)

  selected = select_rare_chars_for_loc(script,
      locs_with_rare_chars, shared_lang_threshold, char_to_lang_map)

  # show_selected_rare_chars(selected)
  chars_by_num_langs = [cp for cp in chars_by_num_langs if cp not in _EXCLUDE_CHARS]

  chosen_chars = list(chars_by_num_langs)[-60:]
  rare_extension = []
  for _, chars in selected:
    avail_chars = [cp for cp in chars if cp not in chosen_chars and
                   cp not in rare_extension and cp not in _EXCLUDE_CHARS]
    rare_extension.extend(sorted(avail_chars)[:4]) # vietnamese dominates latin otherwise
    if len(rare_extension) > 20:
      break
  chosen_chars = chosen_chars[:60 - len(rare_extension)]
  chosen_chars.extend(rare_extension)
  info = ('%s (%d locales)\n'
         'from most common exemplars plus chars specific to most-read languages' % (
             script, num_locales))
  sample = ' '.join(sort_for_script(chosen_chars, script))
  sample = addcase(sample, script)
  return sample, info


def generate_samples(dstdir, imgdir, summary):
  if imgdir:
    imgdir = tool_utils.ensure_dir_exists(imgdir)
    print 'writing images to %s' % imgdir

  if dstdir:
    dstdir = tool_utils.ensure_dir_exists(dstdir)
    print 'writing files to %s' % dstdir

  verbose = summary
  script_map = get_script_to_exemplar_data_map()
  for script in sorted(script_map):
    sample, info = generate_sample_for_script(script, script_map[script])
    if summary:
      print
      print info
      print sample

    if imgdir:
      path = os.path.join(imgdir, 'und-%s_chars.png' % script)
      print 'writing image %s.png' % script
      rtl = script in ['Adlm', 'Arab', 'Hebr', 'Nkoo', 'Syrc', 'Tfng', 'Thaa']
      create_image.create_png(
          sample, path, font_size=34, line_spacing=40, width=800, rtl=rtl)

    if dstdir:
      filename = 'und-%s_chars.txt' % script
      print 'writing data %s' % filename
      filepath = os.path.join(dstdir, filename)
      with codecs.open(filepath, 'w', 'utf-8') as f:
        f.write(sample + '\n')


def main():
  default_dstdir = os.path.join(NOTO_TOOLS, 'sample_texts')

  parser = argparse.ArgumentParser()
  parser.add_argument('--dstdir', help='where to write samples (default %s)' %
                      default_dstdir, default=default_dstdir, metavar='dir')
  parser.add_argument('--imgdir', help='if defined, generate images in this dir',
                      metavar='dir')
  parser.add_argument('--save', help='write sample files in dstdir', action='store_true')
  parser.add_argument('--summary', help='output list of samples and how they were generated',
                      action='store_true')
  parser.add_argument('--verbose', help='print warnings and extra info', action='store_true')
  args = parser.parse_args()

  if not args.save and not args.imgdir and not args.summary:
    print 'nothing to do.'
    return

  if args.verbose:
    global _VERBOSE
    _VERBOSE = True

  generate_samples(args.dstdir if args.save else None, args.imgdir, args.summary)


if __name__ == '__main__':
  locale.setlocale(locale.LC_COLLATE, 'en_US.UTF-8')
  main()
