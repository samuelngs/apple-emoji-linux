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

"""Grab Universal Declaration of Human Rights data from unicode.org/udhr,
extract the text of Article 1 where it seems ok, and generate text files
using the bcp47 name (including script) for the language of that sample."""

import argparse
import codecs
import collections
import datetime
import difflib
import generate_website_data
import os
import re
import shutil
import unicode_data
import urllib
import xml.etree.ElementTree as ET
import zipfile

from nototools import cldr_data
from nototools import tool_utils

DIR_URL = 'http://unicode.org/udhr/d'
UDHR_XML_ZIP_NAME = 'udhr_xml.zip'
UDHR_XML_ZIP_URL = 'http://unicode.org/udhr/assemblies/' + UDHR_XML_ZIP_NAME

def fetch_udhr(fetch_dir):
  """Fetch UDHR xml bundle from unicode.org to fetch_dir."""
  fetch_dir = tool_utils.ensure_dir_exists(fetch_dir)
  dstfile = os.path.join(fetch_dir, UDHR_XML_ZIP_NAME)
  result = urllib.urlretrieve(UDHR_XML_ZIP_URL, dstfile)
  print 'Fetched: ' + result[0]


def update_udhr(udhr_dir, fetch_dir, in_repo):
  """Delete udhr_dir and rebuild with files extracted from udhr_xml.zip
  in fetch_dir. Stage if udhr_dir is in the repo."""

  zippath = os.path.join(fetch_dir, UDHR_XML_ZIP_NAME)
  tool_utils.check_file_exists(zippath)

  if in_repo and os.path.isdir(udhr_dir) and not tool_utils.git_is_clean(udhr_dir):
    raise ValueError('Please clean %s.' % udhr_dir)

  if os.path.isdir(udhr_dir):
    shutil.rmtree(udhr_dir)
  os.makedirs(udhr_dir)
  tool_utils.zip_extract_with_timestamp(zippath, udhr_dir)

  # dos line endings, sheesh
  tool_utils.dos2unix(udhr_dir, ['*.xml', '*.rnc', '*.rng'])

  if in_repo:
    tool_utils.git_add_all(udhr_dir)

  date = datetime.datetime.now().strftime('%Y-%m-%d')
  dst = 'in %s ' % udhr_dir if not in_repo else ''
  print 'Update UDHR files %sfrom %s as of %s.' % (dst, fetch_dir, date)


def parse_index(src_dir):
  """Parse the index.xml file in src_dir and return a map from bcp to a set of
  file codes, and a map from file code to ohchr code.

  Skip files at stages 1 (missing) or 2 (not started). Stage 3 files have
  article 1, which is what we want.  Stage 4 and 5 are ok, the vast majority are
  unreviewed (4).

  In some cases more than one file is mapped to the same bcp47 code, this gets
  dealt with in fix_index."""

  tree = ET.parse(os.path.join(src_dir, 'index.xml'))
  bcp_to_codes = collections.defaultdict(set)
  code_to_ohchr = {}

  for e in tree.getroot().iter('udhr'):
    s = int(e.attrib.get('stage'))
    if s < 3:
      continue

    code = e.attrib.get('f')

    bcp = e.attrib.get('bcp47')
    if not bcp:
      # don't know what to do with this, maybe we could supply a mapping.
      print 'no bcp for %s' % code
      continue

    script = e.attrib.get('iso15924')
    if script:
      # the bcp codes are minimized, and include scripts only if they are
      # not the default (for some version of default), however they will
      # include variants.
      # if the script code is not present in the bcp code, patch it in
      # after the lang.
      script = '-' + script
      if bcp.find(script) == -1:
        ix = bcp.find('-')
        if ix == -1:
          bcp += script
        else:
          bcp = bcp[:ix] + script + bcp[ix:]

    ohchr = e.attrib.get('ohchr')

    bcp_to_codes[bcp].add(code)

    # we use the ohchr code to identify an attribution
    if ohchr:
      code_to_ohchr[code] = ohchr

  return bcp_to_codes, code_to_ohchr


# These handle cases in which the unicode udhr data has multiple files with the
# same bcp47 code.
#
# In some cases, we pick just the one code to use, more or less arbitrarily.
# In other cases, we use multiple codes by adding a region or variant tag to the
# shared bcp47 code.
#
# This map contains all the bcp47 codes that we expect udhr assigns to multple
# files.  For each file we either assign a code, or None if we don't use that
# file.
#
# Possible errors are:
# 1) udhr has multiple files for a code, but we don't list the code.
# 2) udhr has multiple files for a code, but we have a different set of files
#    (in which case we might have ones they don't have, and they might have ones
#     we don't have)
# 3) udhr has a single file for a code, but we list the code
#
# We also need to make sure we don't assign a new code that udhr already uses.

BCP_FIXES = {
  'acu-Latn': {
      'acu': 'acu-Latn',
      'acu_1': None,
  },
  'ak': {
      'ak_asante': 'ak',
      'ak_fante': 'ak-fante',
  },
  'chr-Cher': {
      'chr_cased': 'chr-Cher-cased',
      'chr_uppercase': 'chr-Cher-monocase',
  },
  'cjk-Latn': {
      'cjk': 'cjk-Latn',
      'cjk_AO': 'cjk-Latn-AO',
  },
  'ht-Latn': {
      'hat_popular': 'ht-Latn-popular',
      'hat_kreyol': 'ht-Latn-kreyol',
  },
  'hus-Latn': {
      'hus': 'hus-Latn',
      'hva': None,
      'hsf': None,
  },
  'kg-Latn': {
      'kng': 'kg-Latn',
      'kng_AO': 'kg-Latn-AO',
  },
  'kmb-Latn': {
      '009': None,
      'kmb': 'kmb-Latn',
  },
  'la-Latn': {
      'lat': 'la-Latn',
      'lat_1': None,
  },
  'ln-Latn': {
      'lin_tones': 'ln-Latn',
      'lin': None,
  },
  'ny-Latn': {
      'nya_chinyanja': 'ny-Latn-chinyan',  # max 8 chars in bcp47
      'nya_chechewa': 'ny-Latn-chechewa',
  },
  'oc-Latn': {
      'lnc': 'oc-Latn',
      'auv': None,
      'oci_1': None,
      'oci_2': None,
      'oci_3': None,
      'oci_4': None,
      'prv': None,
  },
  'pov-Latn': {
      '008': None,
      'pov': 'pov-Latn',
  },
  'ro-Latn': {
      'ron_2006': 'ro-Latn',
      'ron_1993': None,
      'ron_1953': None,
  },
  'rom-Latn': {
      'rmn': 'rom-Latn',
      'rmn_1': None,
  },
  'th-Thai': {
      'tha': 'th-Thai',
      'tha2': None,
  },
  'ts-Latn': {
      'tso_MZ': 'ts-Latn-MZ',
      'tso_ZW': 'ts-Latn-ZW',
  },
  'umb-Latn': {
      '011': None,
      'umb': 'umb-Latn',
  },
  'ur-Arab': {
      'urd': 'ur-Arab',
      'urd_2': None,
  },

  }

def fix_index(bcp_to_codes):
  """Take a mapping from bcp47 to a set of file codes, and
  select the mappings we want using a whitelist.  We return
  a mapping from one bcp47 code to one file code.

  We use this opportunity to validate the whitelist, and if there are
  any errors, we fail once we're finished."""
  errors = []
  used_fixes = set()
  result = {}
  for k in sorted(bcp_to_codes):
    if k == 'und' or k.startswith('und-'):
      # we don't handle undefined languages
      continue

    v = bcp_to_codes[k]
    if len(v) == 1:
      udhr_code = next(iter(v))
      if k in result:
        errors.append('%s: udhr assigns %s but we already applied %' % (
            k, udhr_code, result[k]))
        continue

      if k in BCP_FIXES:
        errors.append(
            '%s: udhr assigns %s but we have fixes %s' % (
                k, result[k], ', '.join(BCP_FIXES[k].keys)))
        continue

      # normal case here
      result[k] = next(iter(v))
      continue

    if k not in BCP_FIXES:
      errors.append(
          '%s: no fixes for udhr multiple codes %s' % (
              k, ', '.join(sorted(v))))
      continue

    fixes = BCP_FIXES[k]
    fixes_keys = set(fixes.keys());
    unused_fixes = fixes_keys - v
    unknown_codes = v - fixes_keys
    if unused_fixes:
      errors.append(
          '%s: unused fixes %s' % (
              k, ', '.join(sorted(unused_fixes))))
    if unknown_codes:
      errors.append(
          '%s: unknown codes %s' % (
              k, ', '.join(sorted(unknown_codes))))
    if unused_fixes or unknown_codes:
      continue

    # apply all of our fixes
    for code, new_bcp in sorted(fixes.items()):
      if not new_bcp:
        continue

      if new_bcp in result:
        errors.append(
            '%s: fix defines %s as %s but already assigned %s' % (
                k, code, new_bcp, result[new_bcp]))
        continue

      # normal fix
      result[new_bcp] = code

  if errors:
    print 'fix_index had %d errors:' % len(errors)
    for e in errors:
      print ' ', e
    raise Exception('correct the fixes whitelist')

  return result


# The likely script data doesn't always match the samples, so we override it
# here.  Probably should always get the samples first and apply the script
# later, but for now we just check after the fact.

CODE_TO_BCP = {
  'evn': 'evn-Cyrl',
  'ojb': 'oj-Cans'}

def add_likely_scripts(bcp_to_code):
  """Add script subtags where they are not present in the bcp code.  If
  we don't know the script"""
  result= {}
  for bcp, code in bcp_to_code.iteritems():
    if code in CODE_TO_BCP:
      new_bcp = CODE_TO_BCP[code]
    else:
      new_bcp = bcp
      parts = bcp.split('-')
      try:
        script = generate_website_data.find_likely_script(parts[0])
        if len(parts) == 1:
          new_bcp = '%s-%s' % (bcp, script)
        elif len(parts[1]) != 4 or parts[1].isdigit():
          # assume a region or variant.  Some 4-char values are years, e.g. '1996'
          new_bcp = '%s-%s-%s' % (parts[0], script, '-'.join(parts[1:]))
        # otherwise, we assume the 4-char value is a script, and leave it alone.
      except KeyError:
        # if we can't provide a script, it's no use for a script sample, so exclude it
        print 'no likely subtag (script) data for %s, excluding' % parts[0]
        continue
    result[new_bcp] = code
  return result


# These have been fixed/changed in the noto repo.  We do not want to replace them
# with the UDHR samples, which (as of now, anyway) do not reflect these
# improvements. Our th-Thai is a more colloquial translation than the formal one
# in the UDHR repo.
EXCLUDE_BCP = frozenset([
  'fa-Arab', 'ar-Arab', 'th-Thai'])

# The data for these is bad.  The kwi.xml has no article 1 text (only '[?]')
# and the cbi.xml article 1 text has '. mitya, tsenr)1in ' in it, which just looks
# broken.
EXCLUDE_CODES = frozenset([
  'kwi', 'cbi'])

def filter_bcp_to_code(bcp_to_code):
  """Exclude entries for samples improved in noto/sample_texts and for bad samples."""
  return {k: v for k, v in bcp_to_code.iteritems()
          if k not in EXCLUDE_BCP and v not in EXCLUDE_CODES}


# Pick a default sample to use when only lang and script are provided.
OPTION_MAP = {
    'ak-Latn': 'ak-Latn-asante',
    'chr-Cher': 'chr-Cher-cased',
    'de-Latn': 'de-Latn-1996',
    'el-Grek': 'el-Grek-monoton',
    'ha-Latn': 'ha-Latn-NG',
    'ht-Latn': 'ht-Latn-kreyol',
    'ny-Latn': 'ny-Latn-chechewa',
    'pt-Latn': 'pt-Latn-BR',
    'ts-Latn': 'ts-Latn-MZ',  # arbitrarily select Mozambque
    'tw-Latn': 'tw-Latn-akuapem',  # 'prestige' dialect according to wikipedia
}

def add_default_lang_script(bcp_to_code_attrib_sample):
  """When we query this data, typically we have only language and
  script.  Some of the bcp codes have variants or regions as well, and in
  particular sometimes none of these has just a language and script.
  Select one of these to be used for that, and update the map."""

  errors = []
  options = collections.defaultdict(set)
  long_keys = {}
  for key in bcp_to_code_attrib_sample:
    tags = key.split('-')
    if len(tags) > 2:
      long_keys[key] = tags

  for key in sorted(long_keys):
    tags = long_keys[key]
    lang_scr = tags[0] + '-' + tags[1]
    options[lang_scr].add(key)

  for lang_scr in sorted(options):
    if lang_scr in bcp_to_code_attrib_sample:
      print '%s exists with variants %s' % (
          lang_scr, ', '.join(sorted(options[lang_scr])))
      del options[lang_scr]

  for lang_scr in sorted(options):
    print '%s options: %s' % (lang_scr, options[lang_scr])
    if not lang_scr in OPTION_MAP:
      errors.append('%s missing from option map' % lang_scr)
    elif not OPTION_MAP[lang_scr] in options[lang_scr]:
      errors.append('%s selected option for %s not available' % (
          lang_scr, OPTION_MAP[lang_scr]))
    else:
      alias = OPTION_MAP[lang_scr]
      print 'adding %s (from %s)' % (lang_scr, alias)
      bcp_to_code_attrib_sample[lang_scr] = bcp_to_code_attrib_sample[alias]

  if errors:
    print 'add_default_lang_script encountered %d errors:' % len(errors)
    for e in errors:
      print ' ', e
    raise Exception('oops')


def get_code_to_attrib(src_dir):
  code_to_attrib = {}
  code_file = 'attributions.tsv'
  with open(os.path.join(src_dir, code_file)) as f:
    for line in f.readlines():
      line = line.strip()
      if not line or line.startswith('#'):
        continue
      code, attrib_key, lang, attrib = line.split('\t')
      code_to_attrib[code] = attrib_key
  return code_to_attrib


def get_bcp_to_code_attrib_sample(src_dir, ohchr_dir):
  """Return a mapping from bcp47 to code (for debugging), attribution, and
  sample.  The process is:
  1) parse the index.xml file to determine a mapping from bcp47 to code.
     the bcp47 code has at least lang and script, and perhaps region/variant.
     Multiple codes might share the same bcp47 code.
  2) Use a whitelist to fix cases where a bcp47 code maps to multiple codes,
     either by selecting one code, or assigning a separate bcp47 value
     to other codes.
  3) Load samples for each bcp47 code using article 1 from the file
     identified by the code.  If there is no article 1, skip that bcp47 code.
  4) Do more checking on the samples to make sure they look legit and
     in particular contain only the scripts we expect them to have based
     on the script code in the bcp47 code.
  5) Add an attribution based on the code and the attributions file.
  6) Find cases where all the bcp47's sharing a lang and script have
     regions and/or variants, and select one of these to assign to
     the lang_script bcp47 code."""

  bcp_to_codes, code_to_ohchr = parse_index(src_dir)
  bcp_to_code = fix_index(bcp_to_codes)
  bcp_to_sample = get_bcp_to_sample(src_dir, bcp_to_code)
  check_bcp_to_sample(bcp_to_sample)

  code_to_attrib = get_code_to_attrib(ohchr_dir)

  bcp_to_code_attrib_sample = {}
  for bcp in bcp_to_sample:
    code = bcp_to_code[bcp]
    ohchr = code_to_ohchr.get(code)
    attr = code_to_attrib.get(ohchr)
    if not attr:
      attr = 'none'
      print '%s (%s) not in ohchr attribution data' % (code, ohchr)
    sample = bcp_to_sample[bcp]
    bcp_to_code_attrib_sample[bcp] = (code, attr, sample)

  add_default_lang_script(bcp_to_code_attrib_sample)

  return bcp_to_code_attrib_sample


def print_bcp_to_code_attrib_sample(bcp_to_code_attrib_sample):
  print 'index size: %s' % len(bcp_to_code_attrib_sample)
  for bcp, (code, attrib, sample) in sorted(
      bcp_to_code_attrib_sample.iteritems()):
    print '%s: %s, %s\n  "%s"' % (bcp, code, attrib, sample)


def extract_para(src_path):
  """Extract the text of article 1 from the sample, or None if we can't find
  it."""
  tree = ET.parse(src_path)
  root = tree.getroot()
  ns = {'udhr': 'http://www.unhchr.ch/udhr'}
  article = root.find('udhr:article[@number="1"]', ns)
  if article is None:
    # file kjh.xml is damaged, arrgh. Cyrillic small 'ie' looks just like 'e', and
    # the 'number' attribute is written with the Cyrillic e!
    article = root.find(u'udhr:article[@numb\u0435r="1"]', ns)
  if article is not None:
    text = '\n'.join([para.text for para in article.findall('udhr:para', ns)])
    return text.strip() + '\n'
  return None


def fix_sample(sample, bcp):
  """Fix samples that have known fixable issues."""
  new_sample = None
  if bcp == 'zh-Hans':
    new_sample = sample.replace(u',', u'\uff0c')
  elif bcp == 'hu-Latn':
    new_sample = sample.replace(u'Minden.', u'Minden')

  if not new_sample:
    return sample

  if new_sample == sample:
    print 'sample for %s was not changed by fix' % bcp
  else:
    print 'fixed sample for %s' % bcp
  return new_sample


def get_sample_for_code(udhr_dir, code):
  """Get a sample named for code."""
  src_file = 'udhr_%s.xml' % code
  src_path = os.path.join(udhr_dir, src_file)
  sample = extract_para(src_path)
  if not sample:
    print 'unable to get sample from %s' % src_file
    return None
  return sample


def get_bcp_to_sample(src_dir, bcp_to_code):
  """Return a map from bcp to sample, for codes that have a sample."""
  bcp_to_sample = {}
  for bcp in sorted(bcp_to_code):
    code = bcp_to_code[bcp]
    sample = get_sample_for_code(src_dir, code)
    if not sample:
      print 'bcp %s: no sample found (code %s)' % (bcp, code)
    else:
      bcp_to_sample[bcp] = sample
  return bcp_to_sample


bcp_script_re = re.compile(r'^(?:[A-Z][a-z]{3}|\d{3})$')
def get_bcp_script(bcp):
  """Return the script portion of the bcp tag if it exists, or None."""
  parts = bcp.split('-');
  if len(parts) == 1:
    return None
  return parts[1] if bcp_script_re.match(parts[1]) else None


def check_bcp_sample(bcp, sample):
  """Return error msg if fails, or 'OK'."""

  def info_str(script_data):
    v = {data[0]: script for script, data in script_data.items()}
    return ', '.join(
        '%2d: %s' % tup for tup in sorted(v.items(), reverse=True))

  def info_data(bad_scripts, script_data):
    errs = []
    for s in sorted(bad_scripts):
      count, chars = script_data[s]
      errs.append('%s (%d) %s' % (
          s, count, ','.join('%04x (%s)' % (ord(cp), cp) for cp in sorted(chars))))
    return '; '.join(errs)

  script_data = get_script_histogram(sample)

  if len(sample) < 5:
    return 'bcp %s: sample too short (%d): %s' % (
        bcp, len(sample), info_str(script_data))

  script = get_bcp_script(bcp) # can include non-unicode scripts like Jpan
  if not script:
    # formerly we were going to generate a script based on the sample if we
    # didn't alredy have one, but at the moment all the samples include a script
    # in index.xml.
    raise Exception('no script for %s' % bcp)

  required, accepted = accept_scripts(script) # unicode scripts
  allowed = set(['Zyyy']) # common is ok
  if required:
    allowed |= required
  if accepted:
    allowed |= accepted

  if required:
    if required & frozenset(script_data.keys()) != required:
      return 'bcp %s: required script %s but had (%s)' % (
          bcp, ', '.join(sorted(required)), info_str(script_data))
  elif not accepted:
    # my problem
    raise Exception('Script %s has neither required nor accepted' % script)

  disallowed = set(script_data.keys()) - allowed
  if disallowed:
    return 'bcp %s: script(s) {%s} not in allowed {%s}, %s' % (
        bcp, ', '.join(sorted(disallowed)), ', '.join(sorted(allowed)),
        info_data(disallowed, script_data))

  # ok, the sample passes.
  return 'OK'


def check_bcp_to_sample(bcp_to_sample):
  """For each bcp/sample pair, check the sample script histogram.  If
  anything looks funny (mismatching scripts, bcp script doesn't match
  histogram), delete the mapping, and if there are any rejects, at the
  end report them."""

  errors = []
  for bcp in sorted(bcp_to_sample):
    sample = bcp_to_sample[bcp]
    result = check_bcp_sample(bcp, sample)
    if result != 'OK':
      errors.append(result)
      del bcp_to_sample[bcp]

  if errors:
    print 'found %d errors in samples' % len(errors)
    for e in errors:
      print ' ', e


def update_samples(
    sample_dir, udhr_dir, bcp_to_code_attrib_sample, in_repo, no_stage):
  """Create samples in sample_dir based on the bcp to c_a_s map.  Stage
  if sample_dir is in the repo.  If sample_dir is in the repo, don't
  overwrite samples whose most recent log entry does not start with
  'Updated by tool'."""

  tool_utils.check_dir_exists(udhr_dir)

  if (in_repo and not no_stage and os.path.isdir(sample_dir) and
      not tool_utils.git_is_clean(sample_dir)):
    raise ValueError('Please clean %s.' % sample_dir)

  if in_repo:
    repo, subdir = os.path.split(sample_dir)
    tool_samples = frozenset(tool_utils.get_tool_generated(repo, subdir))
    print 'allowing overwrite of %d files:\n  %s' % (
        len(tool_samples), ', '.join(sorted(tool_samples)))

  comments = [
    '# Attributions for sample excerpts:',
    '#   original - in the public domain, no attribution',
    '#   UN - UN, OHCHR, or affiliate, attribute to UN',
    '#   other - not a UN translation',
    '#   none - not on ohchr, not a UN translation'
  ]
  sample_attrib_list = []
  sample_dir = tool_utils.ensure_dir_exists(sample_dir)
  count = 0
  for bcp, (code, attrib, sample) in bcp_to_code_attrib_sample.iteritems():
    dst_file = '%s_udhr.txt' % bcp
    dst_path = os.path.join(sample_dir, dst_file)
    if in_repo and os.path.isfile(dst_path) and dst_file not in tool_samples:
      print 'Not overwriting modified file %s' % dst_file
    else:
      with codecs.open(dst_path, 'w', 'utf8') as f:
        f.write(sample)
      count += 1
    sample_attrib_list.append('%s: %s' % (dst_file, attrib))
  print 'Created %d samples' % count

  # Some existing samples that we don't overwrite are not in
  # bcp_to_code_attrib_sample, so they're not listed.  Readers of the
  # attributions.txt file will need to default these to 'none'.
  attrib_data = '\n'.join(comments + sorted(sample_attrib_list)) + '\n'
  with open(os.path.join(sample_dir, 'attributions.txt'), 'w') as f:
    f.write(attrib_data)

  if in_repo and not no_stage:
    tool_utils.git_add_all(sample_dir)

  date = datetime.datetime.now().strftime('%Y-%m-%d')
  dst = 'in %s ' % sample_dir if not in_repo else ''
  noto_ix = udhr_dir.find('nototools')
  src = udhr_dir if noto_ix == -1 else udhr_dir[noto_ix:]

  # prefix of this sample commit message indicates that these were
  # tool-generated
  print 'Updated by tool - sample files %sfrom %s as of %s.' % (dst, src, date)


def get_scripts(text):
  """Return the set of scripts in this text.  Excludes
  some common chars."""
  # ignore these chars, we assume they are ok in any script
  exclusions = {0x00, 0x0A, 0x0D, 0x20, 0xA0, 0xFEFF}
  zyyy_chars = set()
  scripts = set()
  ustr = unicode(text, 'utf8')
  for cp in ustr:
    if ord(cp) in exclusions:
      continue
    script = unicode_data.script(cp)
    if script == 'Zyyy': # common/undetermined
      zyyy_chars.add(cp if cp < '\u00fe' else ord(cp))
    elif not script == 'Zinh': # inherited
      scripts.add(script)
  return scripts, zyyy_chars


def get_script_histogram(utext):
  """Return a map from script to character count + chars, excluding some common
  whitespace, and inherited characters.  utext is a unicode string."""
  exclusions = {0x00, 0x0A, 0x0D, 0x20, 0xA0, 0xFEFF}
  result = {}
  for cp in utext:
    if ord(cp) in exclusions:
      continue
    script = unicode_data.script(cp)
    if script == 'Zinh':
      continue
    if script not in result:
      result[script] = [1, set([cp])]
    else:
      r = result[script]
      r[0] += 1
      r[1].add(cp)
  return result


# required, allowed sets
SCRIPT_MAP = {
    'Kore':(None, frozenset(['Hang'])),
    'Jpan':(None, frozenset(['Hani', 'Hira'])),
    'Hant':(None, frozenset(['Hani'])),
    'Hans':(None, frozenset(['Hani']))}

def accept_scripts(script):
  if script in SCRIPT_MAP:
    required, allowed = SCRIPT_MAP.get(script)
  else:
    required, allowed = frozenset([script]), None
  return required, allowed


def test_sample_scripts(sample_dir):
  tested = 0
  errors = 0
  for filename in os.listdir(sample_dir):
    filepath = os.path.join(sample_dir, filename)
    if not (os.path.isfile(filepath) and filename.endswith('_udhr.txt')):
      continue
    tested += 1
    with open(filepath, 'rb') as f:
      textbytes = f.read()
      scripts, zyyy = get_scripts(textbytes)
      bcp = filename[:-len('_udhr.txt')] # trim off extension
      expected_script = bcp.split('-')[1]
      required, allowed = accept_scripts(expected_script)
      if required and required - scripts:
        required_name = ', '.join(sorted([s for s in required]))
        scripts_name = ', '.join(sorted([s for s in scripts]))
        print '%s requires %s but contains only %s' % (filename, required_name, scripts_name)
        errors += 1
      else:
        remainder = scripts
        if allowed:
          remainder -= allowed
        if required:
          remainder -= required
        if remainder:
          allowed_name = '<none>' if not allowed else ', '.join(
              sorted([s for s in allowed]))
          scripts_name = ', '.join(sorted([s for s in scripts]))
          print '%s allows %s but contains %s' % (filename, allowed_name, scripts_name)
          errors += 1
  print 'Found %d errors in %d files tested.' % (errors, tested)


def compare_samples(base_dir, trg_dir, trg_to_base_name=lambda x: x, opts=None):
  """Report on differences between samples in base and target directories.
  The trg_to_base_name fn takes a target file name and returns the source
  file name to use in the comparisons."""

  if not os.path.isdir(base_dir):
    print 'Original sample dir \'%s\' does not exist' % base_dir
    return
  if not os.path.isdir(trg_dir):
    print 'New sample dir \'%s\' does not exist' % trg_dir
    return

  print 'Base (current) dir: %s' % base_dir
  print 'Target (new) dir: %s' % trg_dir
  print '[a/b] means "a" in base is replaced with "b" in target'

  show_missing = opts and 'missing' in opts
  show_diffs = opts and 'diffs' in opts

  for trg_name in os.listdir(trg_dir):
    if trg_name == 'attributions.txt':
      continue

    trg_path = os.path.join(trg_dir, trg_name)
    if not (os.path.isfile(trg_path) and trg_name.endswith('.txt')):
      continue

    base_name = trg_to_base_name(trg_name)
    base_path = os.path.join(base_dir, base_name)
    if not os.path.exists(base_path):
      if show_missing:
        print 'base does not exist: %s' % base_name
      continue

    base_text = None
    dst_text = None
    with codecs.open(base_path, 'r', 'utf8') as f:
      base_text = f.read()
    with codecs.open(trg_path, 'r', 'utf8') as f:
      trg_text = f.read()
    if not base_text:
      print 'base text (%s) is empty' % k
      continue
    if not trg_text:
      print 'target text is empty: %s' % trg_path
      continue
    if base_text.find(trg_text) == -1:
      print 'target (%s) text not in base (%s)' % (base_name, trg_name)
      if show_diffs:
        # In scripts that use space for word break it might be better to compare
        # word by word, but this suffices.
        sm = difflib.SequenceMatcher(None, base_text, trg_text, autojunk=False)
        lines = []
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
          if tag == 'delete':
            lines.append('[%s/]' % base_text[i1:i2])
          elif tag == 'equal':
            lines.append(base_text[i1:i2])
          elif tag == 'insert':
            lines.append('[/%s]' % trg_text[j1:j2])
          else:
            lines.append('[%s/%s]' % (base_text[i1:i2], trg_text[j1:j2]))
        print ''.join(lines)


def update_repo(repo_samples, new_samples):
  # Verify directory is clean.
  if not tool_utils.git_is_clean(new_samples):
    print 'Please fix.'
    return

  # Copy samples into git repo
  for filename in os.listdir(new_samples):
    filepath = os.path.join(new_samples, filename)
    if not os.path.isfile(filepath):
      continue
    shutil.copy2(filename, repo_samples)

  # Stage changes.
  tool_utils.git_add_all(new_samples)

  # Sample commit message.
  print 'Update UDHR sample data.'


def main():
  fetch = '/tmp/udhr/zip'
  udhr = '[tools]/third_party/udhr'
  samples = '[tools]/sample_texts'

  epilog = """The general flow is as follows:
  1) ensure attributions.tsv is in [tools]/third_party/ohchr, using
     extract_ohchr_attributions.py.
  2) use -uu to fetch and stage changes to [tools]/third_party/udhr
  3) use -us --sample_dir=/tmp/foo to generate samples
  4) use -c --sample_dir=/tmp/foo to compare the staged samples
  5) tweak the mapping, use -m to see that it's doing what we want
  6) use --us to generate the samples and stage them to [tools]/sample_texts

  This will not overwrite samples whose most recent log entry does
  not start with 'Updated by tool'.
  """

  parser = argparse.ArgumentParser(epilog=epilog,
    formatter_class=argparse.RawTextHelpFormatter)
  parser.add_argument('--fetch_dir', help='directory into which to fetch xml.zip '
                      '(default %s)' % fetch, metavar='dir', default=fetch)
  parser.add_argument('--udhr_dir', help='location into which to unpack udhr files '
                      '(default %s)' % udhr, metavar='dir', default=udhr)
  parser.add_argument('--sample_dir', help='directory into which to extract samples '
                      '(default %s)' % samples, metavar='dir', default=samples)
  parser.add_argument('-f', '--fetch', help='fetch files from unicode.org/udhr to fetch dir',
                      action='store_true')
  parser.add_argument('-uu', '--update_udhr', help='unpack from fetched files to clean udhr dir\n'
                      '(will stage if in repo and not no_stage)', action='store_true')
  parser.add_argument('-us', '--update_sample', help='extract samples from udhr to sample dir, '
                      'using the bcp to code mapping\n(will stage if in repo and not no_stage)',
                      action='store_true')
  parser.add_argument('-m', '--mapping', help='print the bcp to code mapping generated from the '
                      'udhr dir', action='store_true')
  parser.add_argument('-c', '--compare', help='compare sample changes from base dir '
                      '(default %s)\nto sample dir' % samples,
                      metavar='base_dir',  nargs='?', const=samples,
                      dest='base_sample_dir')
  parser.add_argument('-co', '--compare_opts', help='options for comparison, provide any of:\n'
                      '  \'missing\' to show samples files not in base, and/or\n'
                      '  \'diffs\' to show full diffs of samples',
                      metavar='opt', nargs='+')
  parser.add_argument('-ts', '--test_script', help='test script of samples in sample dir',
                      action='store_true')
  parser.add_argument('-n', '--no_stage', help='do not stage changes in repo', action='store_true')

  args = parser.parse_args()

  # Check arguments

  if not (args.fetch or args.update_udhr or args.update_sample or args.mapping
          or args.base_sample_dir or args.test_script):
    print 'nothing to do.'
    return

  def fix_noto_prefix(argname):
    newval = tool_utils.resolve_path(getattr(args, argname))
    setattr(args, argname, newval)

  if args.update_udhr or args.update_sample or args.mapping:
    fix_noto_prefix('udhr_dir')

  if args.update_sample or args.base_sample_dir or args.test_script:
    fix_noto_prefix('sample_dir')

  if args.base_sample_dir:
    fix_noto_prefix('base_sample_dir')

  if args.sample_dir == args.base_sample_dir:
    parser.error('Compare is no-op when base and target sample dirs are the same.')

  # Perform operations.  Some might still fail despite arg checks.
  try:
    if args.fetch:
      fetch_udhr(args.fetch_dir)

    if args.update_udhr:
      in_repo = args.udhr_dir == tool_utils.resolve_path(udhr)
      update_udhr(args.udhr_dir, args.fetch_dir, in_repo and not args.no_stage)

    if args.update_sample or args.mapping:
      ohchr_dir = tool_utils.resolve_path('[tools]/third_party/ohchr')
      bcp_to_code_attrib_sample = get_bcp_to_code_attrib_sample(
          args.udhr_dir, ohchr_dir)

    if args.update_sample:
      in_repo = args.sample_dir == tool_utils.resolve_path(samples)
      update_samples(
          args.sample_dir, args.udhr_dir, bcp_to_code_attrib_sample,
          in_repo, args.no_stage)

    if args.mapping:
      print_bcp_to_code_attrib(bcp_to_code_attrib)

    if args.base_sample_dir:
      compare_samples(
          args.base_sample_dir, args.sample_dir, opts=args.compare_opts)

    if args.test_script:
      test_sample_scripts(args.sample_dir)
  except ValueError as e:
      print 'Error:', e

if __name__ == '__main__':
    main()
