#!/usr/bin/env python
# -*- coding: utf-8 -*-
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

"""Generate data files for the Noto website."""

from __future__ import division

__author__ = 'roozbeh@google.com (Roozbeh Pournader)'

import argparse
import codecs
import collections
import csv
import datetime
import glob
import json
import locale
import os
from os import path
import shutil
import subprocess
import xml.etree.cElementTree as ElementTree

from fontTools import ttLib

from nototools import cldr_data
from nototools import coverage
from nototools import create_image
from nototools import extra_locale_data
from nototools import lang_data
from nototools import notoconfig
from nototools import noto_fonts
from nototools import tool_utils
from nototools import unicode_data

TOOLS_DIR = notoconfig.noto_tools()
FONTS_DIR = notoconfig.noto_fonts()
CJK_DIR = notoconfig.noto_cjk()
EMOJI_DIR = notoconfig.noto_emoji()

CLDR_DIR = path.join(TOOLS_DIR, 'third_party', 'cldr')

LAT_LONG_DIR = path.join(TOOLS_DIR, 'third_party', 'dspl')
SAMPLE_TEXT_DIR = path.join(TOOLS_DIR, 'sample_texts')

# The Apache license is currently not used for our fonts, but leave
# this just in case this changes in the future.  We have a copy of
# the Apache license in the noto-emoji repo, since it covers the
# code there, so just use that.
APACHE_LICENSE_LOC = path.join(EMOJI_DIR, 'LICENSE')
SIL_LICENSE_LOC = path.join(CJK_DIR, 'LICENSE')

README_HEADER = """This package is part of the noto project.  Visit
google.com/get/noto for more information.

Built on %s from the following noto repositor%s:
-----
"""


def check_families(family_map):
  # ensure the count of fonts in a family is what we expect
  for family_id, family in sorted(family_map.iteritems()):
    hinted_members = family.hinted_members
    unhinted_members = family.unhinted_members

    if (hinted_members and unhinted_members and len(hinted_members) !=
        len(unhinted_members)):

      # Let's not consider this an error for now.  Just drop the members with
      # the higher number of fonts, assuming it's a superset of the fonts in the
      # smaller set, so that the fonts we provide and display are available to
      # all users.  This means website users will not be able to get these fonts
      # via the website.
      #
      # We'll keep the representative font and not try to change it.
      print 'Family %s has %d hinted members but %d unhinted memberts' % (
          family_id, len(hinted_members), len(unhinted_members))

      # The namedtuples are immutable, so we need to break them apart and reform
      # them
      name = family.name
      rep_member = family.rep_member
      charset = family.charset
      if len(hinted_members) < len(unhinted_members):
        unhinted_members = []
      else:
        hinted_members = []
      family_map[family_id] = noto_fonts.NotoFamily(
          name, family_id, rep_member, charset, hinted_members,
          unhinted_members)


def get_script_to_family_ids(family_map):
  """The keys in the returned map are all the supported scripts."""
  script_to_family_ids = collections.defaultdict(set)
  for key in family_map:
    script_key = family_map[key].rep_member.script
    for script in noto_fonts.script_key_to_scripts(script_key):
      script_to_family_ids[script].add(key)
  return script_to_family_ids


def get_family_id_to_lang_scrs(lang_scrs, script_to_family_ids):
  family_id_to_lang_scrs = collections.defaultdict(set)
  for lang_scr in lang_scrs:
    lang, script = lang_scr.split('-')
    family_ids = script_to_family_ids[script]
    for family_id in family_ids:
      family_id_to_lang_scrs[family_id].add(lang_scr)

  # Nastaliq patches:
  # Additionally map some languages in Arab script to Nastaliq ('Aran')
  if 'nastaliq-aran' in family_id_to_lang_scrs:
    nastaliq_lang_scrs = family_id_to_lang_scrs['nastaliq-aran']
    for lang_scr in ['bal-Arab', 'hnd-Arab', 'hno-Arab', 'ks-Arab', 'lah-Arab',
                     'pa-Arab', 'skr-Arab', 'ur-Arab']:
      if not lang_scr in lang_scrs:
        print 'Map nastaliq: %s not found' % lang_scr
      else:
        print 'added %s to nastaliq' % lang_scr
        nastaliq_lang_scrs.add(lang_scr)

  # Kufi patches:
  # - Kufi is broken for Urdu Heh goal (issue #34)
  # - Kufi doesn't support all characters needed for Khowar
  # - Kufi doesn't support all characters needed for Kashmiri
  if 'kufi-arab' in family_id_to_lang_scrs:
    kufi_lang_scrs = family_id_to_lang_scrs['kufi-arab']
    for lang_scr in ['ur-Arab', 'khw-Arab', 'ks-Arab']:
      if not lang_scr in lang_scrs:
        print 'Patch kufi: %s not found' % lang_scr
      else:
        kufi_lang_scrs.remove(lang_scr)
        print 'removed %s from kufi' % lang_scr
        if not kufi_lang_scrs:
          break

  # lad patches:
  # - lad is written in a style of Hebrew called Rashi, not sure
  #   if we support it so let's exclude it for now
  if 'sans-hebr' in family_id_to_lang_scrs:
    hebr_lang_scrs = family_id_to_lang_scrs['sans-hebr']
    for lang_scr in ['lad-Hebr']:
      if not lang_scr in lang_scrs:
        print 'Patch lad: %s not found' % lang_scr
      else:
        hebr_lang_scrs.remove(lang_scr)
        print 'removed %s from sans-hebr' % lang_scr
        if not hebr_lang_scrs:
          break;

  # ja patches:
  # - we generate all permutations of ja, including ja-Kana and
  #   ja-Hiri, but ja-Jpan subsumes these, so omit them.
  if 'sans-jpan' in family_id_to_lang_scrs:
    jpan_lang_scrs = family_id_to_lang_scrs['sans-jpan']
    for lang_scr in ['ja-Kana', 'ja-Hira']:
      if not lang_scr in lang_scrs:
        print 'Patch jpan: %s not found' % lang_scr
      else:
        jpan_lang_scrs.remove(lang_scr)
        print 'removed %s from sans-jpan' % lang_scr
        if not jpan_lang_scrs:
          break;

  for f, ls in sorted(family_id_to_lang_scrs.iteritems()):
    if not ls:
      print '!family %s has no lang' % f

  return family_id_to_lang_scrs


def get_family_id_to_lang_scr_to_sample_key(family_id_to_lang_scrs,
                                           families,
                                           lang_scr_to_sample_infos):

    """For each lang_scr + family combination, determine which sample to use
    from those available for the lang_scr.  If the family can't display any
    of the samples, report an error, the lang will not be added to those
    supported by the family.  If the family supports no languages, also
    report an error.

    The returned value is a tuple:
    - a map from family_id to another map, which is:
      - a map from lang_scr to sample_key
    - a map from sample_key to sample info

    """

    family_id_to_lang_scr_to_sample_key = {}
    sample_key_to_info = {}

    tested_keys = set()
    failed_keys = set()

    for family_id in sorted(family_id_to_lang_scrs):
      lang_scr_to_sample_key = {}
      for lang_scr in sorted(family_id_to_lang_scrs[family_id]):
        sample_infos = lang_scr_to_sample_infos[lang_scr]
        assert len(sample_infos) > 0

        sample_key_for_lang = None
        for info in sample_infos:
          sample, _, sample_key = info

          full_key = sample_key + '-' + family_id
          if full_key in tested_keys:
            if full_key in failed_keys:
              print 'family %s already rejected sample %s (lang %s)' % (
                  family_id, sample_key, lang_scr)
              continue
          else:
            failed_cps = set()
            tested_keys.add(full_key)
            charset = families[family_id].charset
            for cp in sample:
              if ord(cp) in [
                  0xa, 0x28, 0x29, 0x2c, 0x2d, 0x2e, 0x3b, 0x5b, 0x5d, 0x2010,
                  0x202e, 0xfe0e, 0xfe0f]:
                continue
              if ord(cp) not in charset:
                failed_cps.add(ord(cp))

            if failed_cps:
              print 'family %s rejects sample %s for lang %s:\n  %s' % (
                  family_id, sample_key, lang_scr,
                  '\n  '.join('%04x (%s)' % (
                      cp, unichr(cp)) for cp in sorted(failed_cps)))
              failed_keys.add(full_key)
              continue

          # print 'family %s accepts sample %s for lang %s' % (
          #    family_id, sample_key, lang_scr)

          sample_key_for_lang = sample_key
          if sample_key not in sample_key_to_info:
            sample_key_to_info[sample_key] = info
          break

        if not sample_key_for_lang:
          print '%s has no sample to display in %s' % (lang_scr, family_id)
        else:
          lang_scr_to_sample_key[lang_scr] = sample_key_for_lang

      if not lang_scr_to_sample_key:
        print '!%s can display no samples for any lang of %s' % (
            family_id, ', '.join(sorted(family_id_to_lang_scrs[family_id])))
      else:
        print '%s has samples for %s langs' % (
            family_id, len(lang_scr_to_sample_key))
        family_id_to_lang_scr_to_sample_key[family_id] = lang_scr_to_sample_key

    return (family_id_to_lang_scr_to_sample_key, sample_key_to_info)


def get_family_id_to_regions(family_id_to_lang_scr_to_sample_key):
  lang_scr_to_regions = collections.defaultdict(set)
  for region in sorted(cldr_data.known_regions()):
    if region == 'ZZ':
      continue
    if len(region) > 2: # e.g. world
      print 'skipping region %s' % region
      continue
    lang_scrs = cldr_data.region_to_lang_scripts(region)
    for lang_scr in lang_scrs:
      lang_scr_to_regions[lang_scr].add(region)

  family_id_to_regions = collections.defaultdict(set)
  warnings = set()
  for tup in family_id_to_lang_scr_to_sample_key.iteritems():
    family_id, lang_scr_to_sample_key = tup
    for lang_scr in lang_scr_to_sample_key:
      if lang_scr in lang_scr_to_regions:
        for region in lang_scr_to_regions[lang_scr]:
          family_id_to_regions[family_id].add(region)
      else:
        # don't warn about undefined languages
        if not lang_scr.startswith('und'):
          warnings.add(lang_scr)

  for lang_scr in sorted(warnings):
    print 'no mapping from %s to any region' % lang_scr

  return family_id_to_regions


def get_region_to_family_ids(family_id_to_regions):
  region_to_family_ids = collections.defaultdict(set)
  for family_id, regions in family_id_to_regions.iteritems():
    for region in regions:
      region_to_family_ids[region].add(family_id)
  return region_to_family_ids


def get_named_lang_scrs(family_id_to_lang_scr_to_sample_key):
  """Return the list of lang_scrs whose names appear in the UI."""
  named_lang_scrs = lang_data.lang_scripts()
  supported_lang_scrs = set()
  for family_id in family_id_to_lang_scr_to_sample_key:
    lang_scrs = [
        l for l in family_id_to_lang_scr_to_sample_key[family_id].keys()
        if l in named_lang_scrs]
    supported_lang_scrs.update(lang_scrs)
  return supported_lang_scrs


def get_lang_scr_sort_order(lang_scrs):
  """Return a sort order for lang_scrs based on the english name, but
  clustering related languages."""

  def lang_key(lang_scr):
    name = lang_data.lang_script_to_names(lang_scr)[0]
    if name.endswith (' script)'):
      ix = name.rfind('(') - 1
      script_sfx = ' ' + name[ix + 2: len(name) - 8]
      name = name[:ix]
    else:
      script_sfx = ''

    key = name
    for prefix in ['Ancient', 'Central', 'Eastern', 'Lower', 'Middle', 'North',
                   'Northern', 'Old', 'Southern', 'Southwestern', 'Upper',
                   'West', 'Western']:
      if name.startswith(prefix + ' '):
        key = name[len(prefix) + 1:] + ' ' + name[:len(prefix)]
        break

    for cluster in ['Arabic', 'French', 'Chinese', 'English', 'German', 'Hindi',
                    'Malay', 'Nahuatl', 'Tamazight', 'Thai']:
      if name.find(cluster) != -1:
        key = cluster + '-' + name
        break

    return key + script_sfx

  sorted_lang_scrs = list(lang_scrs)
  sorted_lang_scrs.sort(key=lang_key)
  n = 0
  tag_order = {}
  for lang_scr in sorted_lang_scrs:
    tag_order[lang_scr] = n
    n += 1
  return tag_order


def get_charset_info(charset):

  """Returns an encoding of the charset as pairs of lengths of runs of chars
  to skip and chars to include.  Each length is written as length - 1 in
  hex-- except when length == 1, which is written as the empty string-- and
  separated from the next length by a comma.  Thus successive commas
  indicate a length of 1, a 1 indicates a length of 2, and so on.  Since
  the minimum representable length is 1, the base is -1 so that the first
  run (a skip) of 1 can be output as a comma to then start the first
  included character at 0 if need be.  Only as many pairs of values as are
  needed to encode the last run of included characters."""

  ranges = coverage.convert_set_to_ranges(charset)
  prev = -1
  range_list = []
  for start, end in ranges:
    range_len = start - 1 - prev
    if range_len > 0:
      range_list.append('%x' % range_len)
    else:
      range_list.append('')
    range_len = end - start
    if range_len > 0:
      range_list.append('%x' % range_len)
    else:
      range_list.append('')
    prev = end + 1
  return ','.join(range_list)


_sample_names = []
def get_sample_names_for_lang_scr_typ(lang_scr, typ):
  """Sample names are of the form 'lang-scr(-var)*typ.txt', return
  names starting with lang-scr and ending with typ, stripping the extension,
  and sorted with lang-scr_typ first and the rest in alphabetical order."""
  global _sample_names

  if not _sample_names:
    _sample_names = [
        n[:-4] for n in os.listdir(SAMPLE_TEXT_DIR) if n.endswith('.txt')]

  names = [
      n for n in _sample_names if n.startswith(lang_scr) and n.endswith(typ)]

  preferred = lang_scr + typ
  names.sort(key=lambda s: '' if s == preferred else s)
  return names


def get_sample_from_sample_file(lang_scr_typ):
  filepath = path.join(SAMPLE_TEXT_DIR, lang_scr_typ + '.txt')
  if path.exists(filepath):
    return unicode(open(filepath).read().strip(), 'UTF-8')
  return None


ATTRIBUTION_DATA = {}

def get_attribution(lang_scr_typ):
  if not ATTRIBUTION_DATA:
    attribution_path = path.join(TOOLS_DIR, 'sample_texts', 'attributions.txt')
    with open(attribution_path, 'r') as f:
      data = f.readlines()
    for line in data:
      line = line.strip()
      if not line or line[0] == '#':
        continue
      tag, attrib = line.split(':')
      ATTRIBUTION_DATA[tag.strip()] = attrib.strip()
    print 'read %d lines of attribution data' % len(ATTRIBUTION_DATA)
  try:
    return ATTRIBUTION_DATA[lang_scr_typ + '.txt']
  except KeyError:
    if not lang_scr_typ.endswith('_chars'):
      print 'no attribution for %s' % lang_scr_typ
    return 'none'


EXEMPLAR_CUTOFF_SIZE = 60

def sample_text_from_exemplar(exemplar):
  exemplar = [c for c in exemplar
                if unicode_data.category(c[0])[0] in 'LNPS']
  exemplar = exemplar[:EXEMPLAR_CUTOFF_SIZE]
  return ' '.join(exemplar)


def get_sample_infos(lang_scr):
  """Return a list of tuples of:
  - a short sample text string
  - an attribution key, one of
    UN: official UN translation, needs attribution
    other: not an official UN translation, needs non-attribution
    original: public domain translation, does not need attribution
    none: we have no attribution info on this, does not need attribution
  - source key.
  The list is in order of priority: language texts, udhr samples, exemplars for
  the language, sample chars for the script, exemplars for the script."""

  assert '-' in lang_scr

  sample_infos = []

  def add_samples(lang_scr, typ):
    for src_key in get_sample_names_for_lang_scr_typ(lang_scr, typ):
      sample_text = get_sample_from_sample_file(src_key)
      if sample_text is not None:
        attr = get_attribution(src_key)
        sample_infos.append((sample_text, attr, src_key))

  def add_exemplars(lang_scr):
    exemplar, src_key = cldr_data.get_exemplar_and_source(lang_scr)
    if exemplar is not None:
      sample_infos.append(
          (sample_text_from_exemplar(exemplar), 'none', src_key))

  add_samples(lang_scr, '_text')

  add_samples(lang_scr, '_udhr')

  lang, script = lang_scr.split('-')
  if lang != 'und':
    add_exemplars(lang_scr)

  und_scr = 'und-' + script
  add_samples(und_scr, '_chars')

  add_exemplars(und_scr)

  if not sample_infos:
    print '!No sample info for %s' % lang_scr

  return sample_infos


def get_family_id_to_default_lang_scr(family_id_to_lang_scrs, families):
  """Return a mapping from family id to default lang tag, for families
  that have multiple lang tags.  This is based on likely subtags and
  the script of the family (Latn for LGC).
  """

  family_id_to_default_lang_scr = {}
  for family_id, lang_scrs in family_id_to_lang_scrs.iteritems():
    script_key = families[family_id].rep_member.script
    primary_script = noto_fonts.script_key_to_primary_script(script_key)

    if script_key == 'Aran':
      # patch for Nastaliq
      lang = 'ur'
    else:
      lang = lang_data.script_to_default_lang(primary_script)
    lang_scr = lang + '-' + primary_script

    if lang_scr not in lang_scrs:
      print 'default lang_scr \'%s\' not listed for family %s %s' % (
          lang_scr, family_id, lang_scrs)

    family_id_to_default_lang_scr[family_id] = lang_scr
  return family_id_to_default_lang_scr


lat_long_data = {}

def read_lat_long_data():
  with open(path.join(LAT_LONG_DIR, 'countries.csv')) as lat_long_file:
    for row in csv.reader(lat_long_file):
      region, latitude, longitude, _ = row
      if region == 'country':
          continue  # Skip the header
      if not latitude:
          continue  # Empty latitude
      latitude = float(latitude)
      longitude = float(longitude)
      lat_long_data[region] = (latitude, longitude)

  # From the English Wikipedia and The World Factbook at
  # https://www.cia.gov/library/publications/the-world-factbook/fields/2011.html
  lat_long_data.update({
      'AC': (-7-56/60, -14-22/60),  # Ascension Island
      'AX': (60+7/60, 19+54/60),  # Åland Islands
      'BL': (17+54/60, -62-50/60),  # Saint Barthélemy
      'BQ': (12+11/60, -68-14/60),  # Caribbean Netherlands
      'CP': (10+18/60, -109-13/60),  # Clipperton Island
      'CW': (12+11/60, -69),  # Curaçao
      'DG': (7+18/60+48/3600, 72+24/60+40/3600),  # Diego Garcia
       # Ceuta and Melilla, using Ceuta
      'EA': (35+53/60+18/3600, -5-18/60-56/3600),
      'IC': (28.1, -15.4),  # Canary Islands
      'MF': (18+4/60+31/3600, -63-3/60-36/3600),  # Saint Martin
      'SS': (8, 30),  # South Sudan
      'SX': (18+3/60, -63-3/60),  # Sint Maarten
      'TA': (-37-7/60, -12-17/60),  # Tristan da Cunha
       # U.S. Outlying Islands, using Johnston Atoll
      'UM': (16+45/60, -169-31/60),
  })


def get_region_lat_lng_data(regions):
  if not lat_long_data:
    read_lat_long_data()
  return lat_long_data


def get_css_generic_family(family):
    if family in {'Noto Naskh', 'Noto Serif', 'Tinos'}:
        return 'serif'
    if family in {'Arimo', 'Noto Kufi', 'Noto Sans'}:
        return 'sans-serif'
    if family == 'Cousine':
        return 'monospace'
    return None


def css_weight(weight_string):
    return noto_fonts.WEIGHTS[weight_string]


# mapping from stretch_name (font file name version) to
# tuple of css name, image file name abbreviation, sort order key
_STRETCH_DATA = {
    'UltraCondensed': ('ultra-condensed', 'ucon', 'a'),
    'ExtraCondensed': ('extra-condensed', 'xcon', 'b'),
    'Condensed': ('condensed', 'cond', 'c'),
    'SemiCondensed': ('semi-condensed', 'scon', 'd'),
    'Normal': ('normal', 'norm', 'e'),
    'SemiExpanded': ('semi-expanded', 'sexp', 'f'),
    'Expanded': ('expanded', 'expn', 'g'),
    'ExtraExpanded': ('extra-expanded', 'xexp', 'h'),
    'UltraExpanded': ('ultra-expanded', 'uexp', 'i'),
}


def css_stretch(stretch_name):
  return _STRETCH_DATA[stretch_name or 'Normal'][0]


def stretch_abbrev(stretch_name):
  return _STRETCH_DATA[stretch_name or 'Normal'][1]


def stretch_sort_key(stretch_name):
  return _STRETCH_DATA[stretch_name or 'Normal'][2]


def css_style(style_value):
    if style_value is None:
        return 'normal'
    else:
        assert style_value == 'Italic'
        return 'italic'


_DEBUG_KEYS = frozenset([
  'families', 'script_to_family_ids', 'lang_scr_to_sample_infos',
  'family_id_to_lang_scrs', 'family_id_to_lang_scr_to_sample_key',
  'sample_key_to_info', 'family_id_to_regions', 'region_to_family_ids',
  'family_id_to_default_lang_scr',
    ])

def check_debug(debug):
  if debug == None:
    return frozenset()
  elif not debug:
    return _DEBUG_KEYS

  for key in debug:
    if not key in _DEBUG_KEYS:
      print 'Bad debug key(s) found.  Keys are:\n  %s' % (
        '\n  '.join(sorted(_DEBUG_KEYS)))
      raise ValueError()

  return frozenset(debug)


class WebGen(object):

  def __init__(
      self, target, clean, repo_info, pretty_json, no_zips=False,
      no_images=False, no_css=False, no_data=False, no_build=False, debug=None):
    self.target = target
    self.clean = clean
    self.repo_info = repo_info
    self.pretty_json = pretty_json
    self.no_zips = no_zips
    self.no_images = no_images
    self.no_css = no_css
    self.no_data = no_data
    self.no_build = no_build or (no_zips and no_images and no_css and no_data)
    self.debug = check_debug(debug)

    self.pkgs = path.join(target, 'pkgs')
    self.fonts = path.join(target, 'fonts')
    self.css = path.join(target, 'css')
    self.samples = path.join(target, 'samples')
    self.data = path.join(target, 'data')

  def clean_target_dir(self):
    if path.exists(self.target):
        print 'Removing the old website directory from %s...' % self.target
        shutil.rmtree(self.target)

  def write_json(self, obj, name):
    filepath = path.join(self.data, name + '.json')
    with codecs.open(filepath, 'w', encoding='UTF-8') as f:
      json.dump(obj, f, ensure_ascii=False, separators=(',', ':'))

    if self.pretty_json:
      filepath = path.join(self.data, 'pretty', name + '-pretty.json')
      with codecs.open(filepath, 'w', encoding='UTF-8') as f:
        json.dump(obj, f, ensure_ascii=False, separators=(',', ': '),
                       indent=4)

  def ensure_target_dirs_exist(self):
    def mkdirs(p):
      if not path.exists(p):
        os.makedirs(p)
    mkdirs(self.target)
    mkdirs(self.pkgs)
    mkdirs(self.css)
    mkdirs(self.fonts)
    mkdirs(self.samples)
    mkdirs(self.data)
    if self.pretty_json:
      mkdirs(path.join(self.data, 'pretty'))

  def create_zip(self, name, fonts, readme_path):
    zipname = name + '.zip'
    zippath = path.join(self.pkgs, zipname)
    if path.isfile(zippath):
      print('Assuming %s is valid.' % zipname)
    else:
      pairs = [(readme_path, path.basename(readme_path))]
      license_types = set(font.license_type for font in fonts)
      if 'apache' in license_types:
        pairs.append((APACHE_LICENSE_LOC, 'LICENSE_APACHE.txt'))
      if 'sil' in license_types:
        pairs.append((SIL_LICENSE_LOC, 'LICENSE_OFL.txt'))
      for font in fonts:
        pairs.append((font.filepath, path.basename(font.filepath)))
      tool_utils.generate_zip_with_7za_from_filepairs(pairs, zippath)
      print 'Created zip %s' % zippath
    return os.stat(zippath).st_size

  def get_readme_keys(self):
    return 'fonts cjk emoji all'.split()

  def get_readme_key_for_filepath(self, filepath):
    abs_filepath = tool_utils.resolve_path(filepath)
    for key in self.get_readme_keys()[:-1]:
      key_path = tool_utils.resolve_path('[%s]/' % key)
      if abs_filepath.startswith(key_path):
        return key
    raise Exception('no key for path %s' % abs_filepath)

  def get_readme_path(self, readme_key):
    return '/tmp/readmes/%s/README' % readme_key

  def build_readmes(self):
    """Create README files for the zips.  These are named README
    and are put into /tmp/readmes/{fonts|cjk|emoji|all} before
    being copied to zip files."""

    date_str = str(datetime.date.today())
    names = self.get_readme_keys()
    for name in names:
      fname = self.get_readme_path(name)
      tool_utils.ensure_dir_exists(path.dirname(fname))
      with open(fname, 'w') as f:
        if name == 'all':
          f.write(README_HEADER % (date_str, 'ies'))
          for i, n in enumerate(names[:-1]):
            if i > 0:
              f.write('-----\n')
            f.write(self.repo_info[n])
            f.write('\n')
        else:
          f.write(README_HEADER % (date_str, 'y'))
          f.write(self.repo_info[name])
          f.write('\n')

  def build_family_zips(self, key, family):
    readme_key = self.get_readme_key_for_filepath(family.rep_member.filepath)
    readme_path = self.get_readme_path(readme_key)

    zip_name = noto_fonts.get_family_filename(family)
    hinted_size = 0
    unhinted_size = 0
    if family.hinted_members:
      hinted_size = self.create_zip(
          zip_name + '-hinted', family.hinted_members, readme_path)
    if family.unhinted_members:
      unhinted_size = self.create_zip(
          zip_name + '-unhinted', family.unhinted_members, readme_path)
    return zip_name, hinted_size, unhinted_size

  def build_zips(self, families):
    zip_info = {}
    for key, family_data in families.iteritems():
      zip_info[key] = self.build_family_zips(key, family_data)
    return zip_info

  def build_universal_zips(self, families):
    hinted_fonts = []
    unhinted_fonts = []
    readme_path = self.get_readme_path('all')
    for family_data in families.values():
      hinted_fonts.extend(
          family_data.hinted_members or family_data.unhinted_members)
      unhinted_fonts.extend(
          family_data.unhinted_members or family_data.hinted_members)
    hinted_size = self.create_zip(
        'Noto-hinted', hinted_fonts, readme_path)
    unhinted_size = self.create_zip(
        'Noto-unhinted', unhinted_fonts, readme_path)
    return 'Noto', hinted_size, unhinted_size

  def copy_font(self, fontpath):
    basename = path.basename(fontpath)
    dst = path.join(self.fonts, basename)
    shutil.copy(fontpath, dst)
    return basename

  def build_family_css(self, key, family):
    fonts = [m for m in (family.hinted_members or family.unhinted_members)
             if not m.is_UI]
    fonts.sort(
        key=lambda f: (
            f.is_mono, css_weight(f.weight), css_style(f.slope) == 'italic'))

    css_name = key + '.css'
    css_path = path.join(self.css, css_name)
    max_font_size = 0
    with open(css_path, 'w') as css_file:
      for font in fonts:
        font_path = self.copy_font(font.filepath)
        max_font_size = max(max_font_size, os.stat(font.filepath).st_size)
        # Make it possible to access Mono cjk variants and those with irregular
        # css values by assigning them other names.
        css_family = family.name
        if font.is_cjk and font.is_mono:
          css_family += ' ' + 'Mono'
        weight = css_weight(font.weight)
        if weight % 100 != 0:
          css_family += ' ' + str(weight)
          # prevent auto-bolding of this font by describing it as bold
          weight = 700
        slope = css_style(font.slope)
        stretch = css_stretch(font.width)
        css_file.write(
          '@font-face {\n'
          '  font-family: "%s";\n'
          '  font-stretch: %s;\n'
          '  font-weight: %d;\n'
          '  font-style: %s;\n'
          '  src: url(../fonts/%s) format("truetype");\n'
          '}\n' % (css_family, stretch, weight, slope, font_path))
    return max_font_size

  def build_css(self, families):
    css_info = {}
    for key, family_data in families.iteritems():
      css_info[key] = self.build_family_css(key, family_data)
    return css_info

  def build_data_json(self, family_id_to_lang_scr_to_sample_key,
                      families, family_zip_info, universal_zip_info,
                      family_id_to_regions, region_to_family_ids):

    data_obj = collections.OrderedDict()
    families_obj = collections.OrderedDict()

    # Sort families by English name, except Noto Sans/Serif/Mono come first.
    initial_ids = [
        'sans-lgc', 'serif-lgc', 'sans-lgc-display', 'serif-lgc-display',
        'mono-mono']
    family_ids = [family_id for family_id
                  in family_id_to_lang_scr_to_sample_key
                  if family_id not in initial_ids]
    family_ids = sorted(family_ids, key=lambda f: families[f].name)
    sorted_ids = [fid for fid in initial_ids
                  if fid in family_id_to_lang_scr_to_sample_key]
    sorted_ids.extend(family_ids)

    fail = False
    for k in sorted_ids:
      family = families[k]
      family_obj = {}
      family_obj['name'] = family.name

      name, hinted_size, unhinted_size = family_zip_info[k]
      pkg_obj = collections.OrderedDict()
      if hinted_size:
        pkg_obj['hinted'] = hinted_size
      if unhinted_size:
        pkg_obj['unhinted'] = unhinted_size
      family_obj['pkgSize'] = pkg_obj

      # special case number of fonts for CJK
      if family.rep_member.is_cjk:
        num_fonts = 7 #ignore mono
      else:
        num_fonts = sum(
            1 for f in (family.hinted_members or family.unhinted_members)
            if not f.is_UI)
        if num_fonts not in [1, 2, 4, 9, 36, 72]:
          print 'family %s (%s) has %d fonts' % (k, family.name, num_fonts)
          print '\n'.join(f.filepath for f in sorted(family.hinted_members or family.unhinted_members))
          fail = True

      family_obj['fonts'] = num_fonts
      # only displayed langs -- see build_family_json lang_scrs
      lang_scrs_map = family_id_to_lang_scr_to_sample_key[k]
      family_obj['langs'] = sum(
          [1 for l in lang_scrs_map if not l.startswith('und-')])
      family_obj['regions'] = len(family_id_to_regions[k])

      families_obj[k] = family_obj

    if fail:
      raise Exception("some fonts had bad counts")
    data_obj['family'] = families_obj

    data_obj['familyOrder'] = sorted_ids

    # get inverse map from lang_scr to family_id
    lang_scr_to_family_ids = collections.defaultdict(set)
    for family_id, lang_scrs in family_id_to_lang_scr_to_sample_key.iteritems():
      for lang_scr in lang_scrs:
        lang_scr_to_family_ids[lang_scr].add(family_id)

    # Dont list 'und-' lang tags, these are for default samples and not
    # listed in the UI
    lang_scrs = [l for l in lang_scr_to_family_ids if not l.startswith('und-')]

    langs_obj = collections.OrderedDict()
    # sort by english name
    for lang_scr in sorted(lang_scrs,
                           key=lambda l: lang_data.lang_script_to_names(l)[0]):
      lang_obj = collections.OrderedDict()
      names = lang_data.lang_script_to_names(lang_scr)
      english_name = names[0]
      lang_obj['name'] = english_name
      if cldr_data.is_rtl(lang_scr):
        lang_obj['rtl'] = True
      lang_obj['families'] = sorted(lang_scr_to_family_ids[lang_scr])
      native_names = [n for n in names[1:] if n != english_name]
      if native_names:
        lang_obj['keywords'] = native_names
      langs_obj[lang_scr] = lang_obj
    data_obj['lang'] = langs_obj

    regions_obj = collections.OrderedDict()
    for region in sorted(region_to_family_ids,
                         key=lambda r: cldr_data.get_english_region_name(r)):
      region_obj = collections.OrderedDict()
      region_obj['families'] = sorted(region_to_family_ids[region])
      region_obj['keywords'] = [cldr_data.get_english_region_name(region)]
      regions_obj[region] = region_obj
    data_obj['region'] = regions_obj

    pkg_obj = collections.OrderedDict()
    pkg_obj['hinted'] = universal_zip_info[1]
    pkg_obj['unhinted'] = universal_zip_info[2]
    data_obj['pkgSize'] = pkg_obj

    self.write_json(data_obj, 'data')

  def _sorted_displayed_members(self, family):
    members = [m for m in (family.hinted_members or family.unhinted_members)
               if not (m.is_UI or (m.is_cjk and m.is_mono))]
    # sort stretch, then weight, then italic
    # sort non-italic before italic
    return sorted(members,
                  key=lambda f: (stretch_sort_key(f.width) + '-' +
                  str(css_weight(f.weight)) + '-' +
                  ('b' if css_style(f.slope) == 'italic' else 'a')))

  def build_family_json(
      self, family_id, family, lang_scrs_map, lang_scr_sort_order, regions,
      css_info, default_lang_scr):

    family_obj = collections.OrderedDict()
    category = get_css_generic_family(family.name)
    if category:
      family_obj['category'] = category
    if lang_scrs_map:
      # The map includes all samples, but some samples have no language.
      # These are not listed.
      lang_scrs = [l for l in lang_scrs_map.keys() if not l.startswith('und-')]
      lang_scrs.sort(key=lambda l: lang_scr_sort_order[l])
      family_obj['langs'] = lang_scrs
      # The mapping from sample to sample id includes all samples.
      samples_obj = collections.OrderedDict()
      for lang_scr in sorted(lang_scrs_map.keys()):
        samples_obj[lang_scr] = lang_scrs_map[lang_scr]
      family_obj['samples'] = samples_obj
    if default_lang_scr:
      family_obj['defaultLang'] = default_lang_scr
      if lang_scrs_map:
        assert default_lang_scr in lang_scrs_map
    if regions:
      family_obj['regions'] = sorted(regions)
    if family.charset:
      family_obj['ranges'] = get_charset_info(family.charset)
    promo = None
    if family_id == 'emoji-zsye-color':
      promo = ('Explore all emojis in Noto Color Emoji', './help/emoji')
    elif family_id in [
        'sans-jpan', 'sans-kore', 'sans-hans', 'sans-hant',
        'serif-jpan', 'serif-kore', 'serif-hans', 'serif-hant']:
      promo = ('Learn more about Noto Serif/Sans CJK', './help/cjk')
    if promo:
      promo_obj = collections.OrderedDict()
      promo_obj['text'] = promo[0]
      promo_obj['link'] = promo[1]
      family_obj['promo'] = promo_obj
    fonts_obj = []
    displayed_members = self._sorted_displayed_members(family)
    for font in displayed_members:
      weight_style = collections.OrderedDict()
      weight_style['weight'] = css_weight(font.weight)
      style = css_style(font.slope)
      if style != 'normal':
        weight_style['style'] = style
      stretch = css_stretch(font.width)
      if stretch != 'normal':
        weight_style['stretch'] = stretch
      fonts_obj.append(weight_style)
    family_obj['fonts'] = fonts_obj
    family_obj['fontSize'] = css_info
    self.write_json(family_obj, family_id)

  def build_families_json(self, family_id_to_lang_scr_to_sample_key,
                          families, family_id_to_default_lang_scr,
                          family_id_to_regions, family_css_info,
                          lang_scr_sort_order):
    for family_id, lang_scrs_map in sorted(
        family_id_to_lang_scr_to_sample_key.iteritems()):
      family = families[family_id]
      regions = family_id_to_regions[family_id]
      css_info = family_css_info[family_id]
      default_lang_scr = family_id_to_default_lang_scr[family_id]
      self.build_family_json(
          family_id, family, lang_scrs_map, lang_scr_sort_order,
          regions, css_info, default_lang_scr)

  def build_misc_json(self, sample_key_to_info, region_data):
    meta_obj = collections.OrderedDict()

    samples_obj = collections.OrderedDict()
    for sample_key in sorted(sample_key_to_info):
      text, attrib, _ = sample_key_to_info[sample_key]
      sample_obj = collections.OrderedDict()
      sample_obj['text'] = text
      sample_obj['attrib'] = attrib
      samples_obj[sample_key] = sample_obj
    meta_obj['samples'] = samples_obj

    # don't need much accuracy for our map UI use case
    def trim_decimals(num):
      return float('%1.2f' % num)

    regions_obj = collections.OrderedDict()
    for region in sorted(region_data):
      lat, lng = region_data[region]
      lat = trim_decimals(lat)
      lng = trim_decimals(lng)
      region_obj = collections.OrderedDict()
      region_obj['lat'] = lat
      region_obj['lng'] = lng
      regions_obj[region] = region_obj

    meta_obj['region'] = regions_obj

    self.write_json(meta_obj, 'meta')


  def build_family_images(
      self, family, lang_scr, sample_text, attrib, sample_key):
    family_id = family.family_id
    is_cjk = family.rep_member.is_cjk
    is_rtl = cldr_data.is_rtl(lang_scr)
    displayed_members = self._sorted_displayed_members(family)
    for font in displayed_members:
      weight = css_weight(font.weight)
      style = css_style(font.slope)
      stretch = css_stretch(font.width)
      stretch_seg = stretch_abbrev(font.width)
      maxheight = 0
      horiz_margin = 0
      if font.variant == 'color':
        imgtype = 'png'
        fsize = 36
        lspc = 44
      elif font.is_display:
        imgtype = 'svg'
        fsize = 80
        lspc = 96  # 1.2
        maxheight = -2  # lines
        horiz_margin = 16  # lgc serif display italic
      else:
        imgtype = 'svg'
        fsize = 20
        lspc = 32
        horiz_margin = 10
      image_file_name = '%s_%s_%s_%d_%s.%s' % (
          family_id, lang_scr, stretch_seg, weight, style, imgtype)
      if is_cjk and family.name.find('Serif') < 0:
        # The sans and serif cjk's are named differently, and it confuses
        # fontconfig.  Sans includes 'Regular' and 'Bold' in the standard
        # font names, but serif doesn't.  Fontconfig registers two names
        # for these in the sans (with and without the weight), but only
        # the name without weight for the serif.  So if you ask pango/cairo
        # for the serif font and include the weight name, it fails and
        # falls back to some non-noto font.
        family_name = family.name + ' ' + font.weight
      else:
        family_name = family.name
      image_location = path.join(self.samples, image_file_name)
      if path.isfile(image_location):
        # Don't rebuild images when continuing.
        print "Continue: assuming image file '%s' is valid." % image_location
        continue
      print 'create %s' % image_file_name
      create_image.create_img(
          sample_text,
          image_location,
          family=family_name,
          language=lang_scr,
          rtl=is_rtl,
          width=685,
          # text is coming out bigger than we expect, perhaps this is why?
          font_size=int(fsize * (72.0/96.0)),
          line_spacing=int(lspc * (72.0/96.0)),
          weight=weight,
          style=style,
          stretch=stretch,
          maxheight=maxheight,
          horiz_margin=horiz_margin)

  def build_images(self, family_id_to_lang_scr_to_sample_key,
                   families, family_id_to_default_lang_scr,
                   sample_key_to_info):
    for family_id in sorted(family_id_to_lang_scr_to_sample_key):
      family = families[family_id]
      print 'Generating images for %s...' % family.name
      default_lang = family_id_to_default_lang_scr[family_id]
      lang_scr_to_sample_key = family_id_to_lang_scr_to_sample_key[family_id]

      # We don't know that rendering the same sample text with different
      # languages is the same, so we have to generate all the samples and
      # name them based on the language.  But most of the samples with the
      # same font and text will be the same, because the fonts generally
      # only customize for a few language tags.  Sad!
      for lang_scr, sample_key in sorted(lang_scr_to_sample_key.iteritems()):
        sample_text, attrib, _ = sample_key_to_info[sample_key]
        self.build_family_images(
            family, lang_scr, sample_text, attrib, sample_key)

  def build_ttc_zips(self):
    """Generate zipped versions of the ttc files and put in pkgs directory."""

    # The font family code skips the ttc files, but we want them in the
    # package directory. Instead of mucking with the family code to add the ttcs
    # and then exclude them from the other handling, we'll just handle them
    # separately.
    # For now at least, the only .ttc fonts are the CJK fonts

    readme_path = self.get_readme_path('cjk')
    readme_pair = (readme_path, path.basename(readme_path))
    filenames = [path.basename(f) for f in os.listdir(CJK_DIR)
                 if f.endswith('.ttc')]
    for filename in filenames:
      zip_basename = filename + '.zip'
      zip_path = path.join(self.pkgs, zip_basename)
      if path.isfile(zip_path):
          print("Assuming built %s is valid." % zip_basename)
          continue
      oldsize = os.stat(path.join(CJK_DIR, filename)).st_size
      pairs = [
          readme_pair,
          (SIL_LICENSE_LOC, 'LICENSE_OFL.txt'),
          (path.join(CJK_DIR, filename), filename)]
      tool_utils.generate_zip_with_7za_from_filepairs(pairs, zip_path)
      newsize = os.stat(zip_path).st_size
      print "Wrote " + zip_path
      print 'Compressed from {0:,}B to {1:,}B.'.format(oldsize, newsize)

    # NotoSans/SerifCJK.ttc.zip already has been zipped for size reasons
    # because git doesn't like very large files. So it wasn't in the above
    # files. For our purposes ideally it would have the license file in it,
    # but it doesn't.  So we have to copy the zip and add the license to
    # the copy.
    # The Serif ttc is so big github won't let us push it.  In fact, I can't
    # even commit it to my repo because then I can't push anything.  So
    # the serif ttc might not be here.  We want to provide it, but we don't
    # have it in git so the README doesn't apply.  Not sure what to do about
    # this, for now don't include a README for it.  There's no git repo for
    # people to trace this file back to.
    for filename in ['NotoSansCJK.ttc.zip', 'NotoSerifCJK.ttc.zip']:
      src_zip = path.join(CJK_DIR, filename)
      if not path.isfile(src_zip):
        print 'Warning: %s does not exist' % filename
        continue
      pairs = [(SIL_LICENSE_LOC, 'LICENSE_OFL.txt')]
      if os.stat(src_zip).st_size < 100000000:  # lower than 100MB
        pairs.append(readme_pair)
      dst_zip = path.join(self.pkgs, filename)
      shutil.copy2(src_zip, dst_zip)
      tool_utils.generate_zip_with_7za_from_filepairs(pairs, dst_zip)


  def build_subset_zips(self):
    """Generate zipped versions of the CJK subset families for access via
    the link on the cjk help page."""

    # The font family code skips the subset files, but we want them in the
    # package directory. Like the ttcs, we handle them separately.

    readme_path = self.get_readme_path('cjk')
    readme_pair = (readme_path, path.basename(readme_path))
    for style in ['Sans', 'Serif']:
      for subset in ['KR', 'JP', 'SC', 'TC']:
        base_name = 'Noto%s%s' % (style, subset)
        zip_name = '%s.zip' % base_name
        zip_path = path.join(self.pkgs, zip_name)
        if path.isfile(zip_path):
          print("Assuming built %s is valid." % zip_name)
          continue

        filenames = glob.glob(path.join(CJK_DIR, base_name + '-*.otf'))
        if not filenames:
          raise Exception('no file in %s matched "%s"' % (CJK_DIR, family_pat))

        oldsize = sum(os.stat(f).st_size for f in filenames)
        pairs = [
            readme_pair,
            (SIL_LICENSE_LOC, 'LICENSE_OFL.txt')]
        pairs.extend((f, path.basename(f)) for f in filenames)

        tool_utils.generate_zip_with_7za_from_filepairs(pairs, zip_path)
        newsize = os.stat(zip_path).st_size
        print "Wrote " + zip_path
        print 'Compressed from {0:,}B to {1:,}B.'.format(oldsize, newsize)

  def generate(self):
    if self.clean:
      self.clean_target_dir()

    if not self.no_build:
      self.ensure_target_dirs_exist()

    def use_in_web(font):
      return (not font.subset and
              not font.fmt == 'ttc' and
              not font.script in {'CJK', 'HST'} and
              not font.family in {'Arimo', 'Cousine', 'Tinos'})
    fonts = filter(use_in_web, noto_fonts.get_noto_fonts())
    families = noto_fonts.get_families(fonts)

    check_families(families)

    if 'families' in self.debug:
      print '\n#debug families'
      print '%d found' % len(families)
      for i, (family_id, family) in enumerate(sorted(families.iteritems())):
        print '%2d] %s (%s, %s)' % (
            i, family_id, family.name, noto_fonts.get_family_filename(family))
        if family.hinted_members:
          print '  hinted: %s' % ', '.join(sorted(
              [path.basename(m.filepath) for m in family.hinted_members]))
        if family.unhinted_members:
          print '  unhinted: %s' % ', '.join(sorted(
              [path.basename(m.filepath) for m in family.unhinted_members]))

    script_to_family_ids = get_script_to_family_ids(families)
    if 'script_to_family_ids' in self.debug:
      print '\n#debug script to family ids'
      print '%d found' % len(script_to_family_ids)
      for i, (script, family_ids) in enumerate(
          sorted(script_to_family_ids.iteritems())):
        print '%2d] %s: %s' % (i, script, ', '.join(sorted(family_ids)))

    all_lang_scrs = set(['und-' + script for script in script_to_family_ids])
    all_lang_scrs.update(lang_data.lang_scripts())
    lang_scr_to_sample_infos = {}
    for lang_scr in sorted(all_lang_scrs):
      lang, script = lang_scr.split('-')
      if not script in script_to_family_ids:
        print 'no family supports script in %s' % lang_scr
        continue

      sample_infos = get_sample_infos(lang_scr)
      if not sample_infos:
        continue

      lang_scr_to_sample_infos[lang_scr] = sample_infos

    if 'lang_scr_to_sample_infos' in self.debug:
      print '\n#debug lang+script to sample infos'
      print '%d found' % len(lang_scr_to_sample_infos)
      for lang_scr, info_list in sorted(lang_scr_to_sample_infos.iteritems()):
        for info in info_list:
          print '%s: %s, %s, len %d' % (
              lang_scr, info[2], info[1], len(info[0]))

    family_id_to_lang_scrs = get_family_id_to_lang_scrs(
        lang_scr_to_sample_infos.keys(), script_to_family_ids)
    if 'family_id_to_lang_scrs' in self.debug:
      print '\n#debug family id to list of lang+script'
      print '%d found' % len(family_id_to_lang_scrs)
      for i, (family_id, lang_scrs) in enumerate(
          sorted(family_id_to_lang_scrs.iteritems())):
        print '%3d] %s: (%d) %s' % (
            i, family_id, len(lang_scrs), ' '.join(sorted(lang_scrs)))

    family_id_to_lang_scr_to_sample_key, sample_key_to_info = (
        get_family_id_to_lang_scr_to_sample_key(
            family_id_to_lang_scrs, families, lang_scr_to_sample_infos))
    if 'family_id_to_lang_scr_to_sample_key' in self.debug:
      print '\n#debug family id to map from lang+script to sample key'
      print '%d found' % len(family_id_to_lang_scr_to_sample_key)
      for i, (family_id, lang_scr_to_sample_key) in enumerate(
          sorted(family_id_to_lang_scr_to_sample_key.iteritems())):
        print '%2d] %s (%d):' % (i, family_id, len(lang_scr_to_sample_key))
        for j, (lang_scr, sample_key) in enumerate(
            sorted(lang_scr_to_sample_key.iteritems())):
          print '  [%2d] %s: %s' % (j, lang_scr, sample_key)
    if 'sample_key_to_info' in self.debug:
      print '\n#debug sample key to sample info'
      print '%d found' % len(sample_key_to_info)
      for i, (sample_key, info) in enumerate(
          sorted(sample_key_to_info.iteritems())):
        print '%2d] %s: %s, len %d' % (
            i, sample_key, info[1], len(info[0]))

    family_id_to_regions = get_family_id_to_regions(
        family_id_to_lang_scr_to_sample_key)
    if 'family_id_to_regions' in self.debug:
      print '\n#debug family id to regions'
      print '%d found' % len(family_id_to_regions)
      for i, (family_id, regions) in enumerate(
          sorted(family_id_to_regions.iteritems())):
        print '%2d] %s: (%d) %s' % (
            i, family_id, len(regions), ', '.join(sorted(regions)))

    region_to_family_ids = get_region_to_family_ids(family_id_to_regions)
    if 'region_to_family_ids' in self.debug:
      print '\n#debug region to family ids'
      print '%d found' % len(region_to_family_ids)
      for i, (region, family_ids) in enumerate(
          sorted(region_to_family_ids.iteritems())):
        print '%2d] %s: (%d) %s' % (
            i, region, len(family_ids), ', '.join(sorted(family_ids)))

    family_id_to_default_lang_scr = get_family_id_to_default_lang_scr(
        family_id_to_lang_scrs, families)
    if 'family_id_to_default_lang_scr' in self.debug:
      print '\n#debug family id to default lang scr'
      print '%d found' % len(family_id_to_default_lang_scr)
      for i, (family_id, lang_scr) in enumerate(
          sorted(family_id_to_default_lang_scr.iteritems())):
        print '%2d] %s: %s' % (i, family_id, lang_scr)

    region_data = get_region_lat_lng_data(region_to_family_ids.keys())

    lang_scrs = get_named_lang_scrs(family_id_to_lang_scr_to_sample_key)
    lang_scr_sort_order = get_lang_scr_sort_order(lang_scrs)

    # sanity checks
    # all families have languages, and all those have samples.
    # all families have a default language, and that is in the sample list
    error_list = []
    for family in sorted(families.values()):
      family_id = family.family_id
      if not family_id in family_id_to_lang_scr_to_sample_key:
        error_list.append('no entry for family %s' % family_id)
        continue

      lang_scr_to_sample_key = family_id_to_lang_scr_to_sample_key[family_id]
      if not lang_scr_to_sample_key:
        error_list.append('no langs for family %s' % family_id)
        continue

      for lang_scr in sorted(lang_scr_to_sample_key):
        sample_key = lang_scr_to_sample_key[lang_scr]
        if not sample_key:
          error_list.append(
              'no sample key for lang %s in family %s' % (lang_scr, sample_key))
          continue
        if not sample_key in sample_key_to_info:
          error_list.append('no sample for sample key: %s' % sample_key)

      if not family_id in family_id_to_default_lang_scr:
        error_list.append('no default lang for family %s' % family_id)
        continue
      default_lang_scr = family_id_to_default_lang_scr[family_id]
      if not default_lang_scr in lang_scr_to_sample_key:
        error_list.append('default lang %s not in samples for family %s' %
                          (default_lang_scr, family_id))

    if error_list:
      print 'Errors:\n' + '\n  '.join(error_list)

    if error_list or self.no_build:
      print 'skipping build output'
      return

    # build outputs
    # zips are required for data
    if self.no_zips and self.no_data:
      print 'skipping zip output'
    else:
      self.build_readmes()

      family_zip_info = self.build_zips(families)
      universal_zip_info = self.build_universal_zips(families)

      # build outputs not used by the json but linked to from the web page
      if not self.no_zips:
        self.build_ttc_zips()
        self.build_subset_zips()

    if self.no_css:
      print 'skipping css output'
    else:
      family_css_info = self.build_css(families)

    if self.no_data:
      print 'skipping data output'
    else:
      self.build_data_json(family_id_to_lang_scr_to_sample_key,
                           families, family_zip_info, universal_zip_info,
                           family_id_to_regions, region_to_family_ids)

      self.build_families_json(family_id_to_lang_scr_to_sample_key,
                               families, family_id_to_default_lang_scr,
                               family_id_to_regions, family_css_info,
                               lang_scr_sort_order)

      self.build_misc_json(sample_key_to_info, region_data)

    if self.no_images:
      print 'skipping image output'
    else:
      self.build_images(family_id_to_lang_scr_to_sample_key,
                        families,  family_id_to_default_lang_scr,
                        sample_key_to_info)


def get_repo_info(skip_checks):
  """Looks at the three noto fonts repos (fonts, cjk, emoji) and
  gets information about the current state of each.  Returns
  a mapping from 'fonts', 'cjk', and 'emoji' to the corresponding
  info.

  If skip_checks is not set, checks that the repos are in a good
  state (at a known annotated tag and there are no pending commits),
  otherwise an exception is raised."""

  repo_info = {}
  errors = []
  for repo_name in 'fonts cjk emoji'.split():
    msg_lines = []
    repo = tool_utils.resolve_path('[%s]' % repo_name)
    repo_head_commit = tool_utils.git_head_commit(repo)
    repo_branch = tool_utils.git_get_branch(repo)
    if not (skip_checks or tool_utils.git_is_clean(repo)):
      errors.append('noto-%s is not clean' % repo_name)
      continue
    repo_tag = None
    for tag in tool_utils.git_tags(repo):
      if tag[0] == repo_head_commit[0]: # matching commits
        repo_tag = tag
        break
    if repo_tag:
      commit, tag_name, date = tag
      subject = tool_utils.git_tag_info(repo, tag_name)
      mtype, minfo = 'Tag', tag_name
    elif skip_checks:
      commit, date, subject = repo_head_commit
      body = None
      mtype, minfo = 'Branch', repo_branch
    else:
      errors.append('noto-%s is not at a release tag' % repo_name)
      continue

    msg_lines.append('Repo: noto-%s' % repo_name)
    msg_lines.append('%s: %s' % (mtype, minfo))
    msg_lines.append('Date: %s' % date)
    msg_lines.append('Commit: %s'% commit)
    msg_lines.append('\n%s' % subject)
    message = '\n'.join(msg_lines)
    repo_info[repo_name] = message

  for rname, v in sorted(repo_info.iteritems()):
    print '--%s--\n%s' % (rname, v)
  if errors:
    raise Exception('Some repos are not clean\n' + '\n'.join(errors))
  return repo_info


def main():
    """Outputs data files for the noto website."""

    default_dest = '/tmp/website2'

    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--clean',  help='clean target directory',
                        action='store_true')
    parser.add_argument('-d', '--dest', help='target dir, default %s' %
                        default_dest, default=default_dest, metavar='dir')
    parser.add_argument('-pj', '--pretty_json',
                        help='generate additional pretty json',
                        action='store_true')
    parser.add_argument('-nr', '--no_repo_check',
                        help='do not check that repos are in a good state',
                        action='store_true')
    parser.add_argument('-nz', '--no_zips', help='skip zip generation',
                        action='store_true')
    parser.add_argument('-ni', '--no_images', help='skip image generation',
                        action='store_true')
    parser.add_argument('-nd', '--no_data', help='skip data generation',
                        action='store_true')
    parser.add_argument('-nc', '--no_css', help='skip css generation',
                        action='store_true')
    parser.add_argument('-n', '--no_build',
                        help='skip build of zip, image, data, and css',
                        action='store_true')
    parser.add_argument('--debug',
                        help='types of information to dump during build',
                        nargs='*')
    args = parser.parse_args();

    repo_info = get_repo_info(args.no_repo_check)

    webgen = WebGen(args.dest, args.clean, repo_info, args.pretty_json,
                    no_zips=args.no_zips, no_images=args.no_images,
                    no_css=args.no_css, no_data=args.no_data,
                    no_build=args.no_build, debug=args.debug)
    webgen.generate()


if __name__ == '__main__':
    locale.setlocale(locale.LC_COLLATE, 'en_US.UTF-8')
    main()
