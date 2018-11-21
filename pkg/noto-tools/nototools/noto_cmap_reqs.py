#!/usr/bin/env python
#
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

"""Build phase 3 cmap requirements data.

This starts with default assignments based on unicode property
script and script_extensions data, then applies a sequences of
operations to generate an allocation of cmaps to 'scripts' i.e.
font families.  The operations include assigning/removing common
characters in blocks, or entire blocks, to/from scripts,
assigning additional punctuation (based on reading the Unicode
8 standard and various L2 docs), and so on.

This uses pseudo script codes to represent the font families,
but this needs to be changed to some better representation.
for now, these are:

CJK: for all CJK scripts
EXCL: for excluded blocks (PUA, surrogates)
MONO: for blocks going into a monospace font
MUSIC: for blocks going into a music font
SYM2: for blocks going into a 'symbols 2' font with fewer masters
Zmth: for blocks going into a 'math' font
ZSym: for blocks going into the main symbols font (6 masters)
ZSye: for blocks going into the color emoji font
"""

import argparse
import collections
import sys

from nototools import cldr_data
from nototools import cmap_data
from nototools import compare_cmap_data
from nototools import collect_cldr_punct
from nototools import noto_data
from nototools import opentype_data
from nototools import tool_utils
from nototools import unicode_data

_MERGED_SCRIPTS_BY_TARGET = {
    'CJK': 'Bopo Hang Hani Hans Hant Hira Jpan Kana Kore'.split(),
    'LGC': 'Latn Grek Cyrl'.split(),
}

def _invert_script_to_chars(script_to_chars):
  """Convert script_to_chars to char_to_scripts and return."""
  char_to_scripts = collections.defaultdict(set)
  for script, cps in script_to_chars.iteritems():
    for cp in cps:
      char_to_scripts[cp].add(script)
  return char_to_scripts


class CmapOps(object):
  def __init__(self, script_to_chars=None, log_events=False, log_details=False,
               undefined_exceptions = None):
    if script_to_chars == None:
      self._script_to_chars = {}
    else:
      self._script_to_chars = {
          script: set(script_to_chars[script])
          for script in script_to_chars
      }
    self._log_events = log_events
    self._log_details = log_details
    self._suppressed_blocks = {
        'Hangul Jamo',
        'Kangxi Radicals',
        'Kanbun',
        'CJK Symbols and Punctuation',
        'Hangul Compatibility Jamo',
        'CJK Strokes',
        'Enclosed CJK Letters and Months',
        'CJK Compatibility',
        'CJK Compatibility Ideographs',
        'CJK Compatibility Ideographs Supplement',
        'CJK Unified Ideographs Extension A',
        'CJK Unified Ideographs Extension B',
        'CJK Unified Ideographs Extension C',
        'CJK Unified Ideographs Extension D',
        'CJK Unified Ideographs Extension E',
        'CJK Unified Ideographs',
        'CJK Radicals Supplement',
        'Hangul Jamo Extended-A',
        'Hangul Jamo Extended-B',
        'Hangul Syllables',
    }
    self._suppressed_scripts = {
        'EXCL',
    }
    self._block = None
    self._undefined_exceptions = undefined_exceptions or set()

  def _report(self, text):
    if self._log_events:
      print text

  def _finish_block(self):
    if self._block and self._log_events and not self._log_details:
      for text in sorted(self._block_count):
        print '%s: %s' % (
            text, tool_utils.write_int_ranges(
                self._block_count[text]))

  def _report_cp(self, cp, text, script):
    if not self._log_events:
      return
    cp_block = unicode_data.block(cp)
    if cp_block != self._block:
      self._finish_block()
      self._block = cp_block
      print '# block: ' + self._block
      self._block_count = collections.defaultdict(set)
    if self._log_details:
      if not (
          self._block in self._suppressed_blocks or
          script in self._suppressed_scripts):
        print self._cp_info(cp), text
    else:
      self._block_count[text].add(cp)

  def _error(self, text):
    print >> sys.stderr, text
    raise ValueError('failed')

  def _verify_script_exists(self, script):
    if script not in self._script_to_chars:
      self._error('script %s does not exist' % script)

  def _verify_script_does_not_exist(self, script):
    if script in self._script_to_chars:
      self._error('script %s already exists' % script)

  def _verify_scripts_exist(self, scripts):
    for script in scripts:
      self._verify_script_exists(script)
    return sorted(scripts)

  def _verify_script_empty(self, script):
    if len(self._script_to_chars[script]):
      self._error('script %s is not empty, cannot delete' % script)

  def _cp_info(self, cp):
    return '%04X (%s)' % (cp, unicode_data.name(cp, '<unnamed>'))

  def _script_ok_add(self, cp, script):
    if unicode_data.is_defined(cp) or cp in self._undefined_exceptions:
      self._script_cp_ok_add(cp, script)

  def _script_cp_ok_add(self, cp, script):
    if cp not in self._script_to_chars[script]:
      self._script_to_chars[script].add(cp)
      self._report_cp(cp, 'added to ' + script, script)

  def _script_ok_remove(self, cp, script):
    if unicode_data.is_defined(cp):
      self._script_cp_ok_remove(cp, script)

  def _script_cp_ok_remove(self, cp, script):
    if cp in self._script_to_chars[script]:
      self._report_cp(cp, 'removed from ' + script, script)
      self._script_to_chars[script].remove(cp)

  def _finish_phase(self):
    self._finish_block()
    self._block = None

  def phase(self, phase_name):
    self._finish_phase()
    self._report('\n# phase: ' + phase_name)

  def log(self, log_msg):
    self._report('# log: ' + log_msg)

  def ensure_script(self, script):
    if script in self._script_to_chars:
      return
    self.create_script(script)

  def create_script(self, script):
    self._verify_script_does_not_exist(script)
    self._script_to_chars[script] = set()
    self._report('# create script: ' + script)

  def delete_script(self, script):
    self._verify_script_exists(script)
    self._verify_script_empty(script)
    del self._script_to_chars[script]
    self._report('# delete script: ' + script)

  def add(self, cp, script):
    self._verify_script_exists(script)
    self._script_ok_add(cp, script)

  def add_all(self, cps, script):
    self._verify_script_exists(script)
    for cp in sorted(cps):
      self._script_ok_add(cp, script)

  def add_all_to_all(self, cps, scripts):
    scripts = self._verify_scripts_exist(scripts)
    for cp in sorted(cps):
      if unicode_data.is_defined(cp):
        for script in scripts:
          self._script_cp_ok_add(cp, script)

  def remove(self, cp, script):
    self._verify_script_exists(script)
    self._script_ok_remove(cp, script)

  def remove_all(self, cps, script):
    self._verify_script_exists(script)
    for cp in sorted(cps):
      self._script_ok_remove(cp, script)

  def remove_all_from_all(self, cps, scripts):
    scripts = self._verify_scripts_exist(scripts)
    for cp in sorted(cps):
      if unicode_data.is_defined(cp):
        for script in scripts:
          self._script_cp_ok_remove(cp, script)

  def remove_script_from(self, src_script, from_script):
    self._verify_script_exists(from_script)
    cps = self.script_chars(src_script)
    for cp in cps:
      self._script_ok_remove(cp, from_script)

  def move_to_from(self, cp, to_script, from_script):
    self._verify_script_exists(from_script)
    self._verify_script_exists(to_script)
    self._script_ok_add(cp, to_script)
    self._script_ok_remove(cp, from_script)

  def move_all_to_from(self, cps, to_script, from_script):
    """Combines add and remove."""
    self._verify_script_exists(from_script)
    self._verify_script_exists(to_script)
    sorted_cps = sorted(cps)
    for cp in sorted_cps:
      self._script_ok_add(cp, to_script)
    for cp in sorted_cps:
      self._script_ok_remove(cp, from_script)

  def all_scripts(self):
    return self._script_to_chars.keys()

  def create_char_to_scripts(self):
    return _invert_script_to_chars(self._script_to_chars)

  def script_chars(self, script):
    self._verify_script_exists(script)
    return sorted(self._script_to_chars[script])

  def create_script_to_chars(self):
    return {
        script: set(self._script_to_chars[script])
        for script in self._script_to_chars
    }

  def finish(self):
    self._finish_phase()


def _build_block_to_primary_script():
  """Create a map from block to the primary script in a block.
  If there are no characters defined in the block, it gets the script 'EXCL',
  for 'exclude.'  We don't define characters in this block.
  If the most common script accounts for less than 80% of the defined characters
  in the block, we use the primary from assigned_primaries, which might be None.
  It's an error if there's no default primary and it's not listed in
  assigned_primaries."""

  assigned_primaries = {
      'Basic Latin': 'Latn',
      'Latin-1 Supplement': 'Latn',
      'Vedic Extensions': 'Deva',
      'Superscripts and Subscripts': 'Latn',
      'Number Forms': 'Zyyy',
      'CJK Symbols and Punctuation': 'CJK',
      'Enclosed CJK Letters and Months': 'CJK',
      'CJK Compatibility': 'CJK',
      'Alphabetic Presentation Forms': None,
      'Halfwidth and Fullwidth Forms': 'CJK',
      'Kana Supplement': 'CJK',
  }

  inherited_primaries = {
      'Combining Diacritical Marks': 'Latn',
      'Combining Diacritical Marks Extended': 'Latn',
      'Combining Diacritical Marks Supplement': 'Latn',
      'Combining Diacritical Marks for Symbols': 'Zyyy',
      'Variation Selectors': 'EXCL',
      'Combining Half Marks': 'Latn',
      'Variation Selectors Supplement': 'EXCL',
  }

  block_to_script = {}
  for block in unicode_data.block_names():
    start, finish = unicode_data.block_range(block)
    script_counts = collections.defaultdict(int)
    num = 0
    for cp in range(start, finish + 1):
      script = unicode_data.script(cp)
      if script != 'Zzzz':
        script_counts[script] += 1
        num += 1
    max_script = None
    max_script_count = 0
    for script, count in script_counts.iteritems():
      if count > max_script_count:
        max_script = script
        max_script_count = count
    if num == 0:
      max_script = 'EXCL'  # exclude
    elif float(max_script_count) / num < 0.8:
      info = sorted(script_counts.iteritems(), key=lambda t: (-t[1], t[0]))
      block_info = '%s %s' % (block, ', '.join('%s/%d' % t for t in info))
      if block in assigned_primaries:
        max_script = assigned_primaries[block]
        # print 'assigning primary', block_info, '->', max_script
      else:
        print >> sys.stderr, 'ERROR: no primary', block, block_info
        max_script = None
    elif max_script == 'Zinh':
      if block in inherited_primaries:
        max_script = inherited_primaries[block]
      else:
        print >> sys.stderr, 'ERROR: no inherited primary', block, block_info
        max_script = None
    block_to_script[block] = max_script
  return block_to_script


_block_to_primary_script = None
def _primary_script_for_block(block):
  """Return the primary script for the block, or None if no primary script."""
  global _block_to_primary_script
  if not _block_to_primary_script:
    _block_to_primary_script = _build_block_to_primary_script()
  return _block_to_primary_script[block]


def _remove_unicode_assignments(cmap_ops):
  """The starting point is based on the script and script extensions data from
  Unicode.  Sometimes the assignments seem premature."""
  cmap_ops.phase('remove unicode assignments')

  # Jelle says A8F1 makes no sense for Bengali since other characters needed
  # for cantillation are not defined.  Unicode script extensions assign it to
  # Deva and Beng, leave it for Deva.
  cmap_ops.remove(0xa8f1, 'Beng')


def _unassign_inherited_and_common_with_extensions(cmap_ops):
  """Inherited and common characters with an extension that is neither of
  these get removed from inherited/common scripts."""

  def remove_cps_with_extensions(script):
    for cp in cmap_ops.script_chars(script):
      for s in unicode_data.script_extensions(cp):
        if s != 'Zinh' and s != 'Zyyy':
          cmap_ops.remove(cp, script)
          break

  cmap_ops.phase('unassign inherited with extensions')
  remove_cps_with_extensions('Zinh')
  cmap_ops.phase('unassign common with extensions')
  remove_cps_with_extensions('Zyyy')


def _reassign_inherited(cmap_ops):
  """Assign all 'Zinh' chars to the primary script in their block.
  Fail if there's no primary script.  'Zinh' is removed from script_to_chars."""
  cmap_ops.phase('reassign inherited')
  for cp in cmap_ops.script_chars('Zinh'):
    primary_script = _primary_script_for_block(unicode_data.block(cp))
    if not primary_script:
      print >> sys.stderr, 'Error: no primary script for %04X' % cp
    elif primary_script == 'Zinh':
      print >> sys.stderr, 'Error: primary script for %04X is Zinh' % cp
    else:
      cmap_ops.ensure_script(primary_script)
      cmap_ops.add(cp, primary_script)
      cmap_ops.remove(cp, 'Zinh')
  cmap_ops.delete_script('Zinh')


def _reassign_common(cmap_ops):
  """Move 'Zyyy' chars in blocks where 'Zyyy' is not primary to the primary
  script."""
  cmap_ops.phase('reassign common')
  for cp in cmap_ops.script_chars('Zyyy'):
    primary_script = _primary_script_for_block(unicode_data.block(cp))
    if primary_script != None and primary_script != 'Zyyy':
      cmap_ops.ensure_script(primary_script)
      cmap_ops.add(cp, primary_script)
      cmap_ops.remove(cp, 'Zyyy')


def _unassign_latin(cmap_ops):
  """Remove some characters that extensions assigns to Latin but which we don't
  need there."""
  unwanted_latn = tool_utils.parse_int_ranges("""
    0951 0952  # devanagari marks
    10FB  # Georgian paragraph separator
    """)
  cmap_ops.phase('unassign latin')
  cmap_ops.remove_all(unwanted_latn, 'Latn')


def _assign_cldr_punct(cmap_ops):
  """Assigns cldr punctuation to scripts."""
  for script, punct in collect_cldr_punct.script_to_punct().iteritems():
    if script != 'CURRENCY':
      cmap_ops.phase('assign cldr punct for ' + script)
      cmap_ops.ensure_script(script)
      for cp in punct:
        cmap_ops.add(ord(cp), script)


def _reassign_scripts(cmap_ops, scripts, new_script):
  """Reassign all chars in scripts to new_script."""
  assert new_script not in scripts

  cmap_ops.phase('reassign scripts')
  cmap_ops.ensure_script(new_script)
  for script in sorted(scripts):
    cmap_ops.phase('reassign %s to %s' % (script, new_script))
    for cp in cmap_ops.script_chars(script):
      cmap_ops.remove(cp, script)
      cmap_ops.add(cp, new_script)
    cmap_ops.delete_script(script)


def _reassign_merged_scripts(cmap_ops):
  """Reassign merged scripts."""
  for target, scripts in sorted(_MERGED_SCRIPTS_BY_TARGET.iteritems()):
    cmap_ops.phase('reassign to ' + target)
    _reassign_scripts(cmap_ops, scripts, target)


def _reassign_common_by_block(cmap_ops):
  """Reassign common chars to new scripts based on block."""
  block_assignments = {
    'Spacing Modifier Letters': 'LGC',
    'General Punctuation': 'LGC',
    'Currency Symbols': 'LGC',
    'Combining Diacritical Marks for Symbols': 'Zsym',
    'Letterlike Symbols': 'LGC',
    'Number Forms': 'Zsym',
    'Arrows': 'Zmth',
    'Mathematical Operators': 'Zmth',
    'Miscellaneous Technical': 'Zsym',
    'Control Pictures': 'SYM2',
    'Optical Character Recognition': 'SYM2',
    'Enclosed Alphanumerics': 'Zsym',
    'Box Drawing': 'MONO',
    'Block Elements': 'MONO',
    'Geometric Shapes': 'SYM2', # change
    'Miscellaneous Symbols': 'Zsym',
    'Dingbats': 'SYM2',
    'Miscellaneous Mathematical Symbols-A': 'Zmth',
    'Supplemental Arrows-A': 'Zmth',
    'Supplemental Arrows-B': 'Zmth',
    'Miscellaneous Mathematical Symbols-B': 'Zmth',
    'Supplemental Mathematical Operators': 'Zmth',
    'Miscellaneous Symbols and Arrows': 'SYM2',
    'Supplemental Punctuation': 'LGC',
    'Ideographic Description Characters': 'CJK',
    'Yijing Hexagram Symbols': 'SYM2',
    'Modifier Tone Letters': 'LGC',
    'Vertical Forms': 'CJK',
    'CJK Compatibility Forms': 'CJK',
    'Small Form Variants': 'CJK',
    'Specials': 'SYM2',
    'Ancient Symbols': 'SYM2',
    'Phaistos Disc': 'SYM2',
    'Byzantine Musical Symbols': 'MUSIC',
    'Musical Symbols': 'MUSIC',
    'Tai Xuan Jing Symbols': 'SYM2',
    'Mathematical Alphanumeric Symbols': 'Zmth',
    'Mahjong Tiles': 'SYM2',
    'Domino Tiles': 'SYM2',
    'Playing Cards': 'SYM2',
    'Enclosed Alphanumeric Supplement': 'Zsym',
    'Enclosed Ideographic Supplement': 'CJK',
    'Miscellaneous Symbols and Pictographs': 'SYM2',
    'Emoticons': 'SYM2',
    'Ornamental Dingbats': 'SYM2',
    'Transport and Map Symbols': 'SYM2',
    'Alchemical Symbols': 'Zsym',
    'Geometric Shapes Extended': 'SYM2',
    'Supplemental Arrows-C': 'SYM2',
    'Supplemental Symbols and Pictographs': 'SYM2',
    'Tags': 'EXCL',
  }

  cmap_ops.phase('reassign common by block')
  used_assignments = set()
  last_block = None
  for cp in cmap_ops.script_chars('Zyyy'):
    block = unicode_data.block(cp)
    if block != last_block:
      last_block = block
      if block not in block_assignments:
        print >> sys.stderr, 'ERROR: no assignment for block %s' % block
        new_script = None
      else:
        new_script = block_assignments[block]
        cmap_ops.ensure_script(new_script)
        used_assignments.add(block)
    if new_script:
      cmap_ops.remove(cp, 'Zyyy')
      cmap_ops.add(cp, new_script)
    else:
      print >> sys.stderr, '  could not assign %04x %s' % (
          cp, unicode_data.name(cp))

  if len(used_assignments) != len(block_assignments):
    print >> sys.stderr, 'ERROR: some block assignments unused'
    unused = set([block for block in block_assignments
        if block not in used_assignments])
    for block in unicode_data.block_names():
      if block in unused:
        print >> sys.stderr, '  %s' % block
        unused.remove(block)
    if unused:
      print >> sys.stderr, 'ERROR: unknown block names'
      for block in sorted(unused):
        print >> sys.stderr, '  %s' % block

  cmap_ops.delete_script('Zyyy')


def _block_cps(block):
  start, end = unicode_data.block_range(block)
  return frozenset([
      cp for cp in range(start, end + 1)
      if unicode_data.is_defined(cp)])


def _reassign_by_block(cmap_ops):
  """Reassign all chars in select blocks to designated scripts."""
  # block, from, to.  from '*' means from all scripts.
  block_assignments = [
      ('Number Forms', 'LGC', 'Zsym'),
      ('Halfwidth and Fullwidth Forms', 'LGC', 'CJK'),
      ('Aegean Numbers', '*', 'Linb'),
      ('Ancient Greek Numbers', '*', 'SYM2'),
      ('Ancient Symbols', 'LGC', 'SYM2'),
      ('Braille Patterns', 'Brai', 'SYM2'),
      ('Coptic Epact Numbers', '*', 'SYM2'),
      ('Rumi Numeral Symbols', '*', 'SYM2'),
      ('Ancient Greek Musical Notation', '*', 'MUSIC'),
      ('Counting Rod Numerals', 'CJK', 'SYM2'),
      ('Arabic Mathematical Alphabetic Symbols', '*', 'Zmth'),
      ('High Surrogates', '*', 'EXCL'),
      ('High Private Use Surrogates', '*', 'EXCL'),
      ('Low Surrogates', '*', 'EXCL'),
      ('Private Use Area', '*', 'EXCL'),
      ('Variation Selectors', '*', 'EXCL'),
      ('Tags', '*', 'EXCL'),
      ('Variation Selectors Supplement', '*', 'EXCL'),
      ('Supplementary Private Use Area-A', '*', 'EXCL'),
      ('Supplementary Private Use Area-B', '*', 'EXCL'),
  ]
  block_assignments = sorted(
      block_assignments, key=lambda k: unicode_data.block_range(k[0])[0])

  cmap_ops.phase('reassign by block')
  char_to_scripts = cmap_ops.create_char_to_scripts()
  for block, from_scripts, to_script in block_assignments:
    start, finish = unicode_data.block_range(block)
    if from_scripts == '*':
      all_scripts = True
    else:
      all_scripts = False
      from_scripts = from_scripts.split()
    for cp in range(start, finish + 1):
      if not unicode_data.is_defined(cp):
        continue
      if cp not in char_to_scripts and to_script != 'EXCL':
        print >> sys.stderr, 'reassign missing %04X %s' % (
            cp, unicode_data.name(cp, '<unnamed>'))
        continue
      if all_scripts:
        from_list = char_to_scripts[cp]
      else:
        from_list = from_scripts
      for from_script in from_list:
        if from_script == to_script:
          continue
        if not all_scripts and (from_script not in from_scripts):
          continue
        cmap_ops.remove(cp, from_script)
      cmap_ops.add(cp, to_script)


def _remove_empty(cmap_ops):
  """Remove any empty scripts (Braille should be one)."""
  cmap_ops.phase('remove empty')
  script_to_chars = cmap_ops.create_script_to_chars()
  for script, chars in script_to_chars.iteritems():
    if not chars:
      cmap_ops.delete_script(script)


def _reassign_symbols(cmap_ops):
  """Some symbols belong together but get split up when we assign by block."""
  cmap_ops.phase('reassign symbols')

  white_arrow_parts = tool_utils.parse_int_ranges(
      '2b00-2b04 1f8ac-1f8ad')
  cmap_ops.move_all_to_from(white_arrow_parts, 'Zsym', 'SYM2')

  tv_symbols = tool_utils.parse_int_ranges('23fb-23fe 2b58')
  cmap_ops.move_all_to_from(tv_symbols, 'SYM2', 'Zsym')

  # we want a copy in SYM2 for sizes, assume MATH will do its own thing
  # in context.
  math_circles = tool_utils.parse_int_ranges('2219 2299 22c5')
  cmap_ops.add_all(math_circles, 'SYM2')

  # keyboard symbols, user interface symbols, media play symbols
  misc_tech = tool_utils.parse_int_ranges(
      '2318 231a-231b 2324-2328 232b 237d 23ce-23cf 23e9-23fa 23fb-23fe')
  cmap_ops.move_all_to_from(misc_tech, 'SYM2', 'Zsym')

  # Split Miscellaneous Symbols into SYM2 and Zsym by related symbols.
  # mostly this is based on whether the group of symbols seems to have a use
  # in running text or is based on some alphabetic character.
  to_sym2 = tool_utils.parse_int_ranges(
      """2600-2609 # weather
      260e-2612 # ballot box
      2614 # umbrella with rain
      2615 # hot beverage
      2616-2617 # shogi pieces
      261a-261f # pointing hands
      2620-2623 # caution signs
      2626-262f 2638 # religious/political
      2630-2637 # chinese trigrams
      2668 # hot springs
      267f # wheelchair symbol
      2686-2689 # go markers
      268a-268f # yijing monograms/diagrms
      269e-269f # closed captioning
      26a1 # high voltage
      26aa-26ac # circles
      26bd-26be # sports
      26bf # squared key
      26c0-26c3 # checkers/draughts
      26c4-26c8 # weather
      26c9-26ca # more shogi
      26cb # game symbol
      """)
  to_zsym = tool_utils.parse_int_ranges(
      """260a-260d # alchemical symbols
      2613 # saltire
      2618-2619 # shamrock, floral bullet
      2624-2625 # medical, ankh
      2639-263b # smiley faces
      263c-2647 # astrological
      2648-2653 # western zodiac
      2654-265f # western chess
      2660-2667 # card suits
      2669-266f # music symbols
      2670-2671 # syriac cross
      2672-267d # recycling
      267e # paper
      2680-2685 # die faces
      2690-269b # dictionary and map symbols, go with Zsym since dictionary use
      269c # fleur-de-lis
      269d # outlined white star, a symbol of morocco
      26a0 # warning sign (exclamation point inside rounded triangle)
      26a2-26a9 # gender
      26ad-26b1 # genealogical
      26b2 # gender
      26b3-26bc # astrological
      26cc-26cd # traffic signs
      26ce # zodiac
      26cf-26e1 # traffic signs again
      26e2 # astronomical
      26e3 # map symbol
      26e4-26e7 # pentagrams
      26e8-26ff # more map symbols
      """)
  # sanity check
  duplicate_cps = to_sym2 & to_zsym
  if duplicate_cps:
    raise Exception(
        '%d cps in both from and to symbols: %s' % (
            len(duplicate_cps), tool_utils.write_int_ranges(duplicate_cps)))

  missing_cps = set(range(0x2600, 0x2700))
  missing_cps -= to_zsym
  missing_cps -= to_sym2
  if missing_cps:
    raise Exception(
        '%d cps from Misc. Symbols in neither from nor to symbols: %s' % (
            len(missing_cps), tool_utils.write_int_ranges(missing_cps)))

  cmap_ops.move_all_to_from(to_sym2, 'SYM2', 'Zsym')
  cmap_ops.move_all_to_from(to_zsym, 'Zsym', 'SYM2')

  # neutral face should go with smiley faces, which are in Zsym
  cmap_ops.move_to_from(0x1f610, 'Zsym', 'SYM2')

  # more math symbols that are geometric and might want dual treatment
  more_math = tool_utils.parse_int_ranges('2981 29bf 29eb')
  cmap_ops.add_all(more_math, 'SYM2')

  # let's put white arrows into Sym2
  white_arrows = tool_utils.parse_int_ranges(
      """21e6 21e8 21e7 21e9 21f3 2b04 2b00-2b03 1f8ac 1f8ad 21ea-21f0
      """)
  cmap_ops.move_all_to_from(white_arrows, 'SYM2', 'Zsym')

  # circled digits should all go into Symbols
  circled_digits = tool_utils.parse_int_ranges(
      """24ea # circled digit 0
      2460-2473 # circled digit 1-9, number 10-20
      24ff # negative circled digit 0
      1f10c # dingbat negative circled sans-serif digit 0
      2776-277f # dingbat negative circled digits 1-9, number 10
      2780-2789 # dingbat circled sans-serif digits 1-9, number 10
      278a-2793 # dingbat negative circled sans-serif digits 1-9, number 10
      24eb-24f4 # negative circled number 11-20
      1f10b # dingbat circled sans-serif digit 0
      """)
  cmap_ops.move_all_to_from(circled_digits, 'Zsym', 'SYM2')

  # hourglass with flowing sand is in a block that got assigned to Zsym by
  # default.  Looking at it and its neighbors, it seems really odd that these
  # are with 'technical symbols'
  emoji_symbols = tool_utils.parse_int_ranges('23f0-23f3')
  cmap_ops.add_all(emoji_symbols, 'SYM2')
  cmap_ops.remove_all(emoji_symbols, 'Zsym')

  # neutral face should go with white smiling/frowning face, which are in Zsym
  cmap_ops.add(0x1f610, 'Zsym')
  cmap_ops.remove(0x1f610, 'SYM2')

  # Zsym has combining marks, so add dotted circle.
  # Combining enclosing marks in Symbols need latin to combine with, so add
  # letters and digits, also dotted circle if not there already.
  alphanum = tool_utils.parse_int_ranges('30-39 41-5a 61-7a 25cc')
  cmap_ops.add_all(alphanum, 'Zsym')


def _reassign_emoji(cmap_ops):
  """Reassign all emoji to emoji-color. Then assign all emoji with default
  text presentation, plus those with variation selectors, plus select
  others, to SYM2."""

  cmap_ops.phase('reassign emoji')

  color_only_emoji = set(unicode_data.get_presentation_default_emoji())
  color_only_emoji.remove(0x1f004)  # mahjong tile red dragon
  color_only_emoji.remove(0x1f0cf)  # playing card black joker
  # remove emoji with a variation selector that allows a text presentation
  # include proposed variants from 2016/08/23
  color_only_emoji -= unicode_data.get_unicode_emoji_variants(
      'proposed_extra')

  all_emoji = unicode_data.get_emoji()
  cmap_ops.create_script('Zsye')
  cmap_ops.add_all(all_emoji, 'Zsye')

  cmap_ops.remove_all_from_all(color_only_emoji, ['Zsym', 'SYM2'])


def _assign_nastaliq(cmap_ops):
  """Create Aran script based on requirements doc."""

  # Range spec matches "Noto Nastaliq requirements" doc, Tier 1.
  urdu_chars = tool_utils.parse_int_ranges("""
    0600-0604 060b-0614 061b 061c 061e-061f 0620 0621-063a
    0640-0659 065e-066d 0670-0673 0679 067a-067b 067c 067d
    067e 067f-0680 0681 0683-0684 0685-0686 0687 0688-0689
    068a 068b 068c-068d 068e 068f 0691 0693 0696 0698 0699
    069a 069e 06a6 06a9 06ab 06af-06b0 06b1 06b3 06b7 06ba
    06bb 06bc 06be 06c0-06c4 06cc-06cd 06d0 06d2-06d5
    06dd-06de 06e9 06ee-06ef 06f0-06f9 06ff 0759 075c 0763
    0767-0769 076b-077d 08ff fbb2-fbc1 fd3e-fd3f fdf2
    fdfa-fdfd""")
  cmap_ops.phase('assign nastaliq')
  cmap_ops.create_script('Aran')
  cmap_ops.add_all(urdu_chars, 'Aran')

  # These additional arabic were in phase 2 scripts.
  additional_arabic = tool_utils.parse_int_ranges("""
      0609  # ARABIC-INDIC PER MILLE SIGN
      060a  # ARABIC-INDIC PER TEN THOUSAND SIGN
      063b  # ARABIC LETTER KEHEH WITH TWO DOTS ABOVE
      063c  # ARABIC LETTER KEHEH WITH THREE DOTS BELOW
      063d  # ARABIC LETTER FARSI YEH WITH INVERTED V
      063e  # ARABIC LETTER FARSI YEH WITH TWO DOTS ABOVE
      063f  # ARABIC LETTER FARSI YEH WITH THREE DOTS ABOVE
      065d  # ARABIC REVERSED DAMMA
      066e  # ARABIC LETTER DOTLESS BEH
      066f  # ARABIC LETTER DOTLESS QAF
      06a1  # ARABIC LETTER DOTLESS FEH
      06a4  # ARABIC LETTER VEH
      06e0  # ARABIC SMALL HIGH UPRIGHT RECTANGULAR ZERO
      06e1  # ARABIC SMALL HIGH DOTLESS HEAD OF KHAH
      076a  # ARABIC LETTER LAM WITH BAR
  """)
  cmap_ops.add_all(additional_arabic, 'Aran')

  # noto-fonts#597 requests exclamation point
  # noto-fonts#449 requests european digits
  european_digits = tool_utils.parse_int_ranges('0021 0030-0039')
  cmap_ops.add_all(european_digits, 'Aran')

  # noto-fonts#368 requests these characters
  extra_arabic_1 = tool_utils.parse_int_ranges('067b  0684 068a 06b3 0759 0768')
  cmap_ops.add_all(extra_arabic_1, 'Aran')

  # noto-fonts#606 requests a few additional characters
  extra_arabic_2 = tool_utils.parse_int_ranges('06c6 06c7 06ca 06d5')
  cmap_ops.add_all(extra_arabic_2, 'Aran')


def _assign_complex_script_extra(cmap_ops):
  """Assigns Harfbuzz and USE characters to the corresponding scripts."""
  # Based on harfbuzz hb-ot-shape-complex-private
  # Removes Hang, Jungshik reports Behdad says it's not needed for Hang.
  hb_complex_scripts = """
    Arab Aran Bali Batk Beng Brah Bugi Buhd Cakm Cham Deva Dupl Egyp Gran
    Gujr Guru Hano Hebr Hmng Java Kali Khar Khmr Khoj Knda Kthi Lana Laoo
    Lepc Limb Mahj Mand Mani Mlym Modi Mong Mtei Mymr Nkoo Orya Phag Phlp
    Rjng Saur Shrd Sidd Sind Sinh Sund Sylo Syrc Tagb Takr Tale Talu Taml
    Tavt Telu Tfng Tglg Thai Tibt Tirh
    """.split()
  hb_extra = tool_utils.parse_int_ranges("""
      200c  # ZWNJ
      200d  # ZWJ
      25cc  # dotted circle""")

  # these scripts are based on github noto-fonts#576
  use_complex_scripts = """
    Bali Batk Brah Bugi Buhd Hano Kthi Khar Lepc Limb Mtei Rjng Saur Sund
    Sylo Tglg Tagb Tale Tavt
    """.split()
  # these characters are based on
  # https://www.microsoft.com/typography/OpenTypeDev/USE/intro.htm
  use_extra = tool_utils.parse_int_ranges("""
      200b  # ZWS
      200c  # ZWNJ
      200d  # ZWJ
      25cc  # dotted circle
      00a0  # NBS
      00d7  # multiplication sign
      2012  # figure dash
      2013  # en dash
      2014  # em dash
      2015  # horizontal bar
      2022  # bullet
      25fb  # white medium square
      25fc  # black medium square
      25fd  # white medium small square
      25fe  # black medium small square""")

  cmap_ops.phase('assign hb complex')
  cmap_ops.add_all_to_all(hb_extra, hb_complex_scripts)

  cmap_ops.phase('assign use complex')
  cmap_ops.add_all_to_all(use_extra, use_complex_scripts)


def _assign_hyphens_for_autohyphenation(cmap_ops):
  """Assign hyphens per Roozbeh's request."""
  hyphens = [
      0x002d,  # hyphen-minus
      0x2010   # hyphen
  ]
  # see github noto-fonts#524
  # Cyrl, Grek, Latn rolled into LGC
  # CJK not listed, these don't hyphenate, data is in CLDR for other reasons
  hyphen_scripts = """
      Arab Aran Armn Beng Copt Deva Ethi Geor Gujr Guru Hebr
      Khmr Knda LGC  Mlym Orya Taml Telu Thai Tibt
  """.split()
  cmap_ops.phase('assign hyphens')
  cmap_ops.add_all_to_all(hyphens, hyphen_scripts)


def _generate_script_extra(script_to_chars):
  """Generate script extra table."""
  for script in sorted(noto_data.P3_EXTRA_CHARACTERS_NEEDED):
    block = None
    cps = noto_data.P3_EXTRA_CHARACTERS_NEEDED[script]
    chars = script_to_chars[script]
    if script == 'Zsym':
      chars.update(script_to_chars['Zmth'])
      chars.update(script_to_chars['SYM2'])
      chars.update(script_to_chars['MUSIC'])
      chars.update(script_to_chars['MONO'])
    for cp in sorted(cps):
      if not unicode_data.is_defined(cp):
        continue
      name = unicode_data.name(cp, '<unnamed">')
      if cp not in chars:
        if block == None:
          print "'%s': tool_utils.parse_int_ranges(\"\"\"" % script
        cp_block = unicode_data.block(cp)
        if cp_block != block:
          block = cp_block
          print '  # %s' % block
        print '  %04X # %s' % (cp, name)
        chars.add(cp)
    if block != None:
      print '  """),'

# maintained using 'regen_script_required' fn
_SCRIPT_REQUIRED = [
  # Adlm - Adlm (Adlam)
  ('Adlm',
   # Comment
   """
   Additional characters recommended by Monotype.
   """,
   # Data
   """
   # Basic Latin
   0021  # EXCLAMATION MARK
   # Arabic
   061F  # ARABIC QUESTION MARK
   # General Punctuation
   204F  # REVERSED SEMICOLON
   # Supplemental Punctuation
   2E41  # REVERSED COMMA
   """),

  # Aghb - Caucasian Albanian
  ('Aghb',
   # Comment
   """
   From core specification.
   """,
   # Data
   """
   # Combining Diacritical Marks
   0304  # COMBINING MACRON
   0331  # COMBINING MACRON BELOW
   # Combining Half Marks
   FE20  # COMBINING LIGATURE LEFT HALF
   FE21  # COMBINING LIGATURE RIGHT HALF
   FE22  # COMBINING DOUBLE TILDE LEFT HALF
   FE23  # COMBINING DOUBLE TILDE RIGHT HALF
   FE24  # COMBINING MACRON LEFT HALF
   FE25  # COMBINING MACRON RIGHT HALF
   FE26  # COMBINING CONJOINING MACRON
   FE27  # COMBINING LIGATURE LEFT HALF BELOW
   FE28  # COMBINING LIGATURE RIGHT HALF BELOW
   FE29  # COMBINING TILDE LEFT HALF BELOW
   FE2A  # COMBINING TILDE RIGHT HALF BELOW
   FE2B  # COMBINING MACRON LEFT HALF BELOW
   FE2C  # COMBINING MACRON RIGHT HALF BELOW
   FE2D  # COMBINING CONJOINING MACRON BELOW
   FE2E  # COMBINING CYRILLIC TITLO LEFT HALF
   FE2F  # COMBINING CYRILLIC TITLO RIGHT HALF
   """),

  # Ahom - Ahom

  # Arab - Arabic
  ('Arab',
   # Comment
   """
   According to Roozbeh (and existing fonts) the following punctuation and
   digits are used with and interact with Arabic characters.  Hyphen and
   comma are to align with Aran.
   """,
   # Data
   """
   # Basic Latin
   0021  # EXCLAMATION MARK
   0028  # LEFT PARENTHESIS
   0029  # RIGHT PARENTHESIS
   002C  # COMMA
   002E  # FULL STOP
   0030  # DIGIT ZERO
   0031  # DIGIT ONE
   0032  # DIGIT TWO
   0033  # DIGIT THREE
   0034  # DIGIT FOUR
   0035  # DIGIT FIVE
   0036  # DIGIT SIX
   0037  # DIGIT SEVEN
   0038  # DIGIT EIGHT
   0039  # DIGIT NINE
   003A  # COLON
   # Latin-1 Supplement
   00A0  # NO-BREAK SPACE
   # Combining Diacritical Marks
   034F  # COMBINING GRAPHEME JOINER
   # General Punctuation
   200E  # LEFT-TO-RIGHT MARK
   200F  # RIGHT-TO-LEFT MARK
   2010  # HYPHEN
   2011  # NON-BREAKING HYPHEN
   204F  # REVERSED SEMICOLON
   # Supplemental Punctuation
   2E41  # REVERSED COMMA
   """),

  # Aran - Aran (Nastaliq)
  ('Aran',
   # Comment
   """
   Hyphens are required for Urdu from the Arabic
   Guillimets used for Persian according to Behdad
   Other punctuation was in phase2 fonts, so presumably from Kamal.
   """,
   # Data
   """
   # Basic Latin
   0021  # EXCLAMATION MARK
   002C  # COMMA
   002E  # FULL STOP
   003A  # COLON
   # Latin-1 Supplement
   00AB  # LEFT-POINTING DOUBLE ANGLE QUOTATION MARK
   00BB  # RIGHT-POINTING DOUBLE ANGLE QUOTATION MARK
   # Arabic
   061C  # ARABIC LETTER MARK
   # General Punctuation
   2010  # HYPHEN
   2011  # NON-BREAKING HYPHEN
   # Arabic Presentation Forms-A
   FDF4  # ARABIC LIGATURE MOHAMMAD ISOLATED FORM
   """),

  # Armi - Imperial Aramaic

  # Armn - Armenian
  ('Armn',
   # Comment
   """
   Characters referenced in Armenian encoding cross ref page
   see http://www.unicode.org/L2/L2010/10354-n3924-armeternity.pdf
   also see http://man7.org/linux/man-pages/man7/armscii-8.7.html
   also see core specification.
   """,
   # Data
   """
   # Basic Latin
   0028  # LEFT PARENTHESIS
   0029  # RIGHT PARENTHESIS
   002D  # HYPHEN-MINUS
   002E  # FULL STOP
   # Latin-1 Supplement
   00A0  # NO-BREAK SPACE
   00A7  # SECTION SIGN
   # Spacing Modifier Letters
   02BB  # MODIFIER LETTER TURNED COMMA
   # General Punctuation
   2010  # HYPHEN
   2014  # EM DASH
   2019  # RIGHT SINGLE QUOTATION MARK
   2024  # ONE DOT LEADER
   # Alphabetic Presentation Forms
   FB13  # ARMENIAN SMALL LIGATURE MEN NOW
   FB14  # ARMENIAN SMALL LIGATURE MEN ECH
   FB15  # ARMENIAN SMALL LIGATURE MEN INI
   FB16  # ARMENIAN SMALL LIGATURE VEW NOW
   FB17  # ARMENIAN SMALL LIGATURE MEN XEH
   """),

  # Avst - Avestan
  ('Avst',
   # Comment
   """
   From Core Specification and NamesList.txt
   www.unicode.org/L2/L2007/07006r-n3197r-avestan.pdf
   """,
   # Data
   """
   # Basic Latin
   002E  # FULL STOP
   # Latin-1 Supplement
   00B7  # MIDDLE DOT
   # General Punctuation
   200C  # ZERO WIDTH NON-JOINER
   # Supplemental Punctuation
   2E30  # RING POINT
   2E31  # WORD SEPARATOR MIDDLE DOT
   """),

  # Bali - Balinese

  # Bamu - Bamum

  # Bass - Bassa Vah
  ('Bass',
   # Comment
   """
   From core specification.
   """,
   # Data
   """
   # Basic Latin
   0022  # QUOTATION MARK
   002C  # COMMA
   002E  # FULL STOP
   # General Punctuation
   201C  # LEFT DOUBLE QUOTATION MARK
   201D  # RIGHT DOUBLE QUOTATION MARK
   """),

  # Batk - Batak

  # Beng - Bengali
  ('Beng',
   #Comment
   """
   Added by Monotype.
   """,
   # Data
   """
   # Spacing Modifier Letters
   02BC  # MODIFIER LETTER APOSTROPHE
   """),

  # Bhks - Bhks (Bhaiksuki)
  ('Bhks',
   # Comment
   """
   Reported by user on nototools#429
   """,
   # Data
   """
   # General Punctuation
   200B  # ZERO WIDTH SPACE
   # Geometric Shapes
   25CC  # DOTTED CIRCLE
   """),

  # Brah - Brahmi

  # Brai - Braille

  # Bugi - Buginese

  # Buhd - Buhid

  # CJK - (Bopo,Hang,Hani,Hans,Hant,Hira,Jpan,Kana,Kore)

  # Cakm - Chakma

  # Cans - Canadian Aboriginal
  ('Cans',
   # Comment
   """
   From core specification and web sites.
   """,
   # Data
   """
   # Basic Latin
   0022  # QUOTATION MARK
   0028  # LEFT PARENTHESIS
   0029  # RIGHT PARENTHESIS
   002C  # COMMA
   002D  # HYPHEN-MINUS
   002E  # FULL STOP
   # General Punctuation
   201C  # LEFT DOUBLE QUOTATION MARK
   201D  # RIGHT DOUBLE QUOTATION MARK
   """),

  # Cari - Carian
  ('Cari',
   # Comment
   """
   From core specification.
   """,
   # Data
   """
   # Latin-1 Supplement
   00B7  # MIDDLE DOT
   # General Punctuation
   205A  # TWO DOT PUNCTUATION
   205D  # TRICOLON
   # Supplemental Punctuation
   2E31  # WORD SEPARATOR MIDDLE DOT
   """),

  # Cham - Cham
  ('Cham',
   # Comment
   """
   From core specification.
   """,
   # Data
   """
   # Basic Latin
   002D  # HYPHEN-MINUS
   003A  # COLON
   003F  # QUESTION MARK
   # General Punctuation
   2010  # HYPHEN
   """),

  # Cher - Cherokee
  ('Cher',
   # Comment
   """
   From core specification and
   http://www.unicode.org/L2/L2014/14064r-n4537r-cherokee.pdf section 8.
   Core spec says 'uses latin punctuation', these are a subset of the latin-1
   punct because the intent of listing them is to ensure that use in running
   text works with the script.
   """,
   # Data
   """
   # Basic Latin
   0021  # EXCLAMATION MARK
   0022  # QUOTATION MARK
   0027  # APOSTROPHE
   0028  # LEFT PARENTHESIS
   0029  # RIGHT PARENTHESIS
   002C  # COMMA
   002D  # HYPHEN-MINUS
   002E  # FULL STOP
   002F  # SOLIDUS
   003A  # COLON
   003B  # SEMICOLON
   003F  # QUESTION MARK
   005B  # LEFT SQUARE BRACKET
   005D  # RIGHT SQUARE BRACKET
   007E  # TILDE
   # Combining Diacritical Marks
   0300  # COMBINING GRAVE ACCENT
   0301  # COMBINING ACUTE ACCENT
   0302  # COMBINING CIRCUMFLEX ACCENT
   0304  # COMBINING MACRON
   030B  # COMBINING DOUBLE ACUTE ACCENT
   030C  # COMBINING CARON
   0323  # COMBINING DOT BELOW
   0324  # COMBINING DIAERESIS BELOW
   0330  # COMBINING TILDE BELOW
   0331  # COMBINING MACRON BELOW
   # General Punctuation
   2010  # HYPHEN
   201C  # LEFT DOUBLE QUOTATION MARK
   201D  # RIGHT DOUBLE QUOTATION MARK
   """),

  # Copt - Coptic
  ('Copt',
   # Comment
   """
   From Core specification and
   http://std.dkuug.dk/JTC1/SC2/WG2/docs/n2636.pdf

   0323 referenced in the following according to Kamal:
   http://ucbclassics.dreamhosters.com/djm/coptic.html

   0361 and 1DCD resolve bug #748 according to MTI.  We
   originally intended to remove them since we didn't have
   a reference for their use.  We still don't, but they
   were re-added because of the bug.
   """,
   # Data
   """
   # Basic Latin
   002E  # FULL STOP
   003A  # COLON
   003B  # SEMICOLON
   # Latin-1 Supplement
   00B7  # MIDDLE DOT
   # Combining Diacritical Marks
   0300  # COMBINING GRAVE ACCENT
   0301  # COMBINING ACUTE ACCENT
   0302  # COMBINING CIRCUMFLEX ACCENT
   0304  # COMBINING MACRON
   0305  # COMBINING OVERLINE
   0307  # COMBINING DOT ABOVE
   0308  # COMBINING DIAERESIS
   0323  # COMBINING DOT BELOW
   033F  # COMBINING DOUBLE OVERLINE
   0361  # COMBINING DOUBLE INVERTED BREVE
   # Greek and Coptic
   0374  # GREEK NUMERAL SIGN
   0375  # GREEK LOWER NUMERAL SIGN
   # General Punctuation
   2019  # RIGHT SINGLE QUOTATION MARK
   # Supplemental Punctuation
   2E17  # DOUBLE OBLIQUE HYPHEN
   # Combining Half Marks
   FE24  # COMBINING MACRON LEFT HALF
   FE25  # COMBINING MACRON RIGHT HALF
   FE26  # COMBINING CONJOINING MACRON
   """),

  # Cprt - Cypriot

  # Deva - Devanagari
  ('Deva',
   # Comment
   """
   Email from Jelle, SHY was encoded as Macron by accident.
   """,
   # Data
   """
   # Latin-1 Supplement
   00AD  # SOFT HYPHEN
   """),

  # Dsrt - Deseret

  # Dupl - Duployan shorthand (Duployan)

  # Egyp - Egyptian hieroglyphs

  # Elba - Elbasan
  ('Elba',
   # Comment
   """
   see http://www.unicode.org/L2/L2011/11050-n3985-elbasan.pdf
   adds combining overbar and greek numerals for ones and tens, and
   both stigma/digamma for 6.
   """,
   # Data
   """
   # Latin-1 Supplement
   00B7  # MIDDLE DOT
   # Combining Diacritical Marks
   0305  # COMBINING OVERLINE
   # Greek and Coptic
   0391  # GREEK CAPITAL LETTER ALPHA
   0392  # GREEK CAPITAL LETTER BETA
   0393  # GREEK CAPITAL LETTER GAMMA
   0394  # GREEK CAPITAL LETTER DELTA
   0395  # GREEK CAPITAL LETTER EPSILON
   0396  # GREEK CAPITAL LETTER ZETA
   0397  # GREEK CAPITAL LETTER ETA
   0398  # GREEK CAPITAL LETTER THETA
   0399  # GREEK CAPITAL LETTER IOTA
   039A  # GREEK CAPITAL LETTER KAPPA
   039B  # GREEK CAPITAL LETTER LAMDA
   039C  # GREEK CAPITAL LETTER MU
   039D  # GREEK CAPITAL LETTER NU
   039E  # GREEK CAPITAL LETTER XI
   039F  # GREEK CAPITAL LETTER OMICRON
   03A0  # GREEK CAPITAL LETTER PI
   03DA  # GREEK LETTER STIGMA
   03DD  # GREEK SMALL LETTER DIGAMMA
   03DE  # GREEK LETTER KOPPA
   """),

  # Ethi - Ethiopic
  ('Ethi',
   # Comment
   """
   From core specification, also see
   http://abyssiniagateway.net/fidel/l10n/
   Recommends combining diaeresis 'for scholarly use', should look Ethiopian.
   Also claims hyphen is not used, but a wikipedia page in Amharic does use
   it, see
   https://am.wikipedia.org/wiki/1_%E1%8A%A5%E1%88%BD%E1%88%98-%E1%8B%B3%E1%8C%8B%E1%8A%95
   Western numerals and punctuation should look heavier to match the Ethiopic.
   A keyboard standard is here:
   See http://www.mcit.gov.et/documents/1268465/1282796/Keyboard+Layout+Standard/a8aa75ca-e125-4e25-872e-380e2a9b2313
   """,
   # Data
   """
   # Basic Latin
   0021  # EXCLAMATION MARK
   0028  # LEFT PARENTHESIS
   0029  # RIGHT PARENTHESIS
   002B  # PLUS SIGN
   002E  # FULL STOP
   002F  # SOLIDUS
   003D  # EQUALS SIGN
   # Combining Diacritical Marks
   0308  # COMBINING DIAERESIS
   030E  # COMBINING DOUBLE VERTICAL LINE ABOVE
   # Mathematical Operators
   22EE  # VERTICAL ELLIPSIS
   # Geometric Shapes
   25CC  # DOTTED CIRCLE
   """),

  # Geor - Georgian
  ('Geor',
   # Comment
   """
   From core specification (references unspecified additionl latin punct), also
   see example news article: http://www.civil.ge/geo/article.php?id=29970
   """,
   # Data
   """
   # Basic Latin
   0021  # EXCLAMATION MARK
   0025  # PERCENT SIGN
   0028  # LEFT PARENTHESIS
   0029  # RIGHT PARENTHESIS
   002E  # FULL STOP
   003A  # COLON
   003B  # SEMICOLON
   # Latin-1 Supplement
   00A0  # NO-BREAK SPACE
   00B7  # MIDDLE DOT
   # General Punctuation
   2014  # EM DASH
   2056  # THREE DOT PUNCTUATION
   2057  # QUADRUPLE PRIME
   2058  # FOUR DOT PUNCTUATION
   2059  # FIVE DOT PUNCTUATION
   205A  # TWO DOT PUNCTUATION
   205B  # FOUR DOT MARK
   205C  # DOTTED CROSS
   205D  # TRICOLON
   205E  # VERTICAL FOUR DOTS
   20BE  # LARI SIGN
   # Supplemental Punctuation
   2E2A  # TWO DOTS OVER ONE DOT PUNCTUATION
   2E2B  # ONE DOT OVER TWO DOTS PUNCTUATION
   2E2C  # SQUARED FOUR DOT PUNCTUATION
   2E2D  # FIVE DOT MARK
   2E31  # WORD SEPARATOR MIDDLE DOT
   """),

  # Glag - Glagolitic
  ('Glag',
   # Comment
   """
   See core specification.  It refers to 'numerous diacritical marks', these
   are not listed.
   """,
   # Data
   """
   # Basic Latin
   0022  # QUOTATION MARK
   002C  # COMMA
   002E  # FULL STOP
   003B  # SEMICOLON
   # Latin-1 Supplement
   00B7  # MIDDLE DOT
   # Combining Diacritical Marks
   0303  # COMBINING TILDE
   0305  # COMBINING OVERLINE
   # General Punctuation
   201C  # LEFT DOUBLE QUOTATION MARK
   201D  # RIGHT DOUBLE QUOTATION MARK
   2056  # THREE DOT PUNCTUATION
   2058  # FOUR DOT PUNCTUATION
   2059  # FIVE DOT PUNCTUATION
   """),

  # Goth - Gothic
  ('Goth',
   # Comment
   """
   From core specification.
   """,
   # Data
   """
   # Basic Latin
   003A  # COLON
   # Latin-1 Supplement
   00B7  # MIDDLE DOT
   # Combining Diacritical Marks
   0304  # COMBINING MACRON
   0305  # COMBINING OVERLINE
   0308  # COMBINING DIAERESIS
   0331  # COMBINING MACRON BELOW
   """),

  # Gran - Grantha
  ('Gran',
   # Comment
   """
   From core specification.
   """,
   # Data
   """
   # Devanagari
   0951  # DEVANAGARI STRESS SIGN UDATTA
   0952  # DEVANAGARI STRESS SIGN ANUDATTA
   # Vedic Extensions
   1CD0  # VEDIC TONE KARSHANA
   1CD2  # VEDIC TONE PRENKHA
   1CD3  # VEDIC SIGN NIHSHVASA
   1CF2  # VEDIC SIGN ARDHAVISARGA
   1CF3  # VEDIC SIGN ROTATED ARDHAVISARGA
   1CF4  # VEDIC TONE CANDRA ABOVE
   1CF8  # VEDIC TONE RING ABOVE
   1CF9  # VEDIC TONE DOUBLE RING ABOVE
   # Combining Diacritical Marks for Symbols
   20F0  # COMBINING ASTERISK ABOVE
   """),

  # Gujr - Gujarati

  # Guru - Gurmukhi
  ('Guru',
   # Comment
   """
   From core specification.
   """,
   # Data
   """
   # Miscellaneous Symbols
   262C  # ADI SHAKTI
   """),

  # Hano - Hanunoo

  # Hatr - Hatr (Hatran)
  ('Hatr',
   # Comment
   """
   See http://www.unicode.org/L2/L2012/12312-n4324-hatran.pdf (most info, but
   not latest assignment, which doesn't have all digits shown here)
   single and double vertical line, also ZWNJ in case ligatures need breaking
   might want to ligate hatran digit 1 forms 11 (2), 111 (3), 1111 (4) to
   look as the suggested (dropped) digits were represented in the doc.
   """,
   # Data
   """
   # Basic Latin
   007C  # VERTICAL LINE
   # General Punctuation
   200C  # ZERO WIDTH NON-JOINER
   2016  # DOUBLE VERTICAL LINE
   """),

  # Hebr - Hebrew
  ('Hebr',
   # Comment
   """
   From core specification, adds currency.
   """,
   # Data
   """
   # Basic Latin
   0028  # LEFT PARENTHESIS
   0029  # RIGHT PARENTHESIS
   # Combining Diacritical Marks
   0307  # COMBINING DOT ABOVE
   0308  # COMBINING DIAERESIS
   034F  # COMBINING GRAPHEME JOINER
   # General Punctuation
   200C  # ZERO WIDTH NON-JOINER
   200D  # ZERO WIDTH JOINER
   200E  # LEFT-TO-RIGHT MARK
   200F  # RIGHT-TO-LEFT MARK
   # Currency Symbols
   20AA  # NEW SHEQEL SIGN
   # Letterlike Symbols
   2135  # ALEF SYMBOL
   2136  # BET SYMBOL
   2137  # GIMEL SYMBOL
   2138  # DALET SYMBOL
   """),

  # Hluw - Anatolian Hieroglyphs
  ('Hluw',
   # Comment
   """
   see http://www.unicode.org/L2/L2012/12213-n4282-anatolian.pdf
   """,
   # Data
   """
   # General Punctuation
   200B  # ZERO WIDTH SPACE
   """),

  # Hmng - Pahawh Hmong

  # Hrkt - Japanese syllabaries (Katakana Or Hiragana)

  # Hung - Old Hungarian
  ('Hung',
   # Comment
   """
   see  http://www.unicode.org/L2/L2012/12168r-n4268r-oldhungarian.pdf
   letters with LTR override mirror reverse (!) "which has to be handled by
   the rendering engine"
   """,
   # Data
   """
   # Basic Latin
   0021  # EXCLAMATION MARK
   002C  # COMMA
   002D  # HYPHEN-MINUS
   002E  # FULL STOP
   003A  # COLON
   # General Punctuation
   200D  # ZERO WIDTH JOINER
   2010  # HYPHEN
   201F  # DOUBLE HIGH-REVERSED-9 QUOTATION MARK
   204F  # REVERSED SEMICOLON
   205A  # TWO DOT PUNCTUATION
   205D  # TRICOLON
   205E  # VERTICAL FOUR DOTS
   # Supplemental Punctuation
   2E2E  # REVERSED QUESTION MARK
   2E31  # WORD SEPARATOR MIDDLE DOT
   2E41  # REVERSED COMMA
   2E42  # DOUBLE LOW-REVERSED-9 QUOTATION MARK
   """),

  # Ital - Old Italic

  # Java - Javanese

  # Kali - Kayah Li
  ('Kali',
   # Comment
   """
   From core specification, also see
   http://www.unicode.org/L2/L2006/06073-n3038r-kayahli.pdf
   """,
   # Data
   """
   # Basic Latin
   0021  # EXCLAMATION MARK
   0022  # QUOTATION MARK
   0028  # LEFT PARENTHESIS
   0029  # RIGHT PARENTHESIS
   002C  # COMMA
   002D  # HYPHEN-MINUS
   003F  # QUESTION MARK
   # General Punctuation
   2010  # HYPHEN
   """),

  # Khar - Kharoshthi
  ('Khar',
   # Comment
   """
   From core specification.
   """,
   # Data
   """
   # Basic Latin
   002D  # HYPHEN-MINUS
   # General Punctuation
   2010  # HYPHEN
   """),

  # Khmr - Khmer
  ('Khmr',
   # Comment
   """
   Latin punct see web sites
   """,
   # Data
   """
   # Basic Latin
   0021  # EXCLAMATION MARK
   0028  # LEFT PARENTHESIS
   0029  # RIGHT PARENTHESIS
   """),

  # Khoj - Khojki
  ('Khoj',
   # Comment
   """
   From core specification, also see
   http://www.unicode.org/L2/L2011/11021-khojki.pdf
   """,
   # Data
   """
   # Basic Latin
   0028  # LEFT PARENTHESIS
   0029  # RIGHT PARENTHESIS
   002C  # COMMA
   002E  # FULL STOP
   003B  # SEMICOLON
   # General Punctuation
   2013  # EN DASH
   2026  # HORIZONTAL ELLIPSIS
   """),

  # Knda - Kannada

  # Kthi - Kaithi
  ('Kthi',
   # Comment
   """
   From core specification.
   """,
   # Data
   """
   # Basic Latin
   002B  # PLUS SIGN
   002D  # HYPHEN-MINUS
   # General Punctuation
   2010  # HYPHEN
   # Supplemental Punctuation
   2E31  # WORD SEPARATOR MIDDLE DOT
   """),

  # LGC - (Latn,Grek,Cyrl)
  ('LGC',
   # Comment
   """
   FE00 is for variant zero.
   """,
   # Data
   """
   # Spacing Modifier Letters
   02EA  # MODIFIER LETTER YIN DEPARTING TONE MARK
   02EB  # MODIFIER LETTER YANG DEPARTING TONE MARK
   # Letterlike Symbols
   2100  # ACCOUNT OF
   2101  # ADDRESSED TO THE SUBJECT
   2103  # DEGREE CELSIUS
   2105  # CARE OF
   2106  # CADA UNA
   2109  # DEGREE FAHRENHEIT
   2113  # SCRIPT SMALL L
   2116  # NUMERO SIGN
   2117  # SOUND RECORDING COPYRIGHT
   211E  # PRESCRIPTION TAKE
   2120  # SERVICE MARK
   2121  # TELEPHONE SIGN
   2122  # TRADE MARK SIGN
   2127  # INVERTED OHM SIGN
   2129  # TURNED GREEK SMALL LETTER IOTA
   212E  # ESTIMATED SYMBOL
   213B  # FACSIMILE SIGN
   214B  # TURNED AMPERSAND
   214D  # AKTIESELSKAB
   # Number Forms
   2150  # VULGAR FRACTION ONE SEVENTH
   2151  # VULGAR FRACTION ONE NINTH
   2152  # VULGAR FRACTION ONE TENTH
   2153  # VULGAR FRACTION ONE THIRD
   2154  # VULGAR FRACTION TWO THIRDS
   2155  # VULGAR FRACTION ONE FIFTH
   2156  # VULGAR FRACTION TWO FIFTHS
   2157  # VULGAR FRACTION THREE FIFTHS
   2158  # VULGAR FRACTION FOUR FIFTHS
   2159  # VULGAR FRACTION ONE SIXTH
   215A  # VULGAR FRACTION FIVE SIXTHS
   215B  # VULGAR FRACTION ONE EIGHTH
   215C  # VULGAR FRACTION THREE EIGHTHS
   215D  # VULGAR FRACTION FIVE EIGHTHS
   215E  # VULGAR FRACTION SEVEN EIGHTHS
   215F  # FRACTION NUMERATOR ONE
   2184  # LATIN SMALL LETTER REVERSED C
   2189  # VULGAR FRACTION ZERO THIRDS
   # Variation Selectors
   FE00  # VARIATION SELECTOR-1
   # Specials
   FFFC  # OBJECT REPLACEMENT CHARACTER
   FFFD  # REPLACEMENT CHARACTER
   """),

  # Lana - Lanna (Tai Tham)

  # Laoo - Lao
  ('Laoo',
   # Comment
   """
   For latin punct use see web sites, e.g. nuol.edu.la
   """,
   # Data
   """
   # Basic Latin
   0022  # QUOTATION MARK
   0028  # LEFT PARENTHESIS
   0029  # RIGHT PARENTHESIS
   002C  # COMMA
   002E  # FULL STOP
   003A  # COLON
   # General Punctuation
   201C  # LEFT DOUBLE QUOTATION MARK
   201D  # RIGHT DOUBLE QUOTATION MARK
   # Currency Symbols
   20AD  # KIP SIGN
   """),

  # Lepc - Lepcha
  ('Lepc',
   # Comment
   """
   From core specification, only the specificially mentioned punct.
   """,
   # Data
   """
   # Basic Latin
   002C  # COMMA
   002E  # FULL STOP
   003F  # QUESTION MARK
   """),

  # Limb - Limbu
  ('Limb',
   # Comment
   """
   From core specification.
   """,
   # Data
   """
   # Devanagari
   0965  # DEVANAGARI DOUBLE DANDA
   """),

  # Lina - Linear A

  # Linb - Linear B

  # Lisu - Fraser (Lisu)
  ('Lisu',
   # Comment
   """
   From core specification.
   """,
   # Data
   """
   # Basic Latin
   0021  # EXCLAMATION MARK
   0022  # QUOTATION MARK
   0028  # LEFT PARENTHESIS
   0029  # RIGHT PARENTHESIS
   002D  # HYPHEN-MINUS
   003A  # COLON
   003B  # SEMICOLON
   003F  # QUESTION MARK
   # Spacing Modifier Letters
   02BC  # MODIFIER LETTER APOSTROPHE
   02CD  # MODIFIER LETTER LOW MACRON
   # General Punctuation
   2010  # HYPHEN
   2026  # HORIZONTAL ELLIPSIS
   # CJK Symbols and Punctuation
   300A  # LEFT DOUBLE ANGLE BRACKET
   300B  # RIGHT DOUBLE ANGLE BRACKET
   """),

  # Lyci - Lycian
  ('Lyci',
   # Comment
   """
   From core specification.
   """,
   # Data
   """
   # General Punctuation
   205A  # TWO DOT PUNCTUATION
   """),

  # Lydi - Lydian
  ('Lydi',
   # Comment
   """
   From core specification.
   """,
   # Data
   """
   # Basic Latin
   003A  # COLON
   # Latin-1 Supplement
   00B7  # MIDDLE DOT
   # Supplemental Punctuation
   2E31  # WORD SEPARATOR MIDDLE DOT
   """),

  # MUSIC - MUSIC
  ('MUSIC',
   # Comment
   """
   Characters not in standard music blocks.
   """,
   # Data
   """
   # Miscellaneous Symbols
   2669  # QUARTER NOTE
   266A  # EIGHTH NOTE
   266B  # BEAMED EIGHTH NOTES
   266C  # BEAMED SIXTEENTH NOTES
   266D  # MUSIC FLAT SIGN
   266E  # MUSIC NATURAL SIGN
   266F  # MUSIC SHARP SIGN
   """),

  # Mahj - Mahajani
  ('Mahj',
   # Comment
   """
   From core specification.
   """,
   # Data
   """
   # Basic Latin
   002D  # HYPHEN-MINUS
   003A  # COLON
   # Latin-1 Supplement
   00B7  # MIDDLE DOT
   # Devanagari
   0964  # DEVANAGARI DANDA
   0965  # DEVANAGARI DOUBLE DANDA
   # General Punctuation
   2013  # EN DASH
   """),

  # Mand - Mandaean (Mandaic)
  ('Mand',
   # Comment
   """
   From core specification.
   """,
   # Data
   """
   # Arabic
   0640  # ARABIC TATWEEL
   """),

  # Mani - Manichaean

  # Marc - Marc (Marchen)

  # Mend - Mende (Mende Kikakui)

  # Merc - Meroitic Cursive
  ('Merc',
   # Comment
   """
   From core specification.
   also see http://www.unicode.org/L2/L2009/09188r-n3646-meroitic.pdf
   """,
   # Data
   """
   # Basic Latin
   003A  # COLON
   # General Punctuation
   2026  # HORIZONTAL ELLIPSIS
   205D  # TRICOLON
   """),

  # Mero - Meroitic (Meroitic Hieroglyphs)

  # Mlym - Malayalam

  # Modi - Modi
  ('Modi',
   # Comment
   """
   From core specification, also see
   http://www.unicode.org/L2/L2011/11212r2-n4034-modi.pdf
   """,
   # Data
   """
   # Basic Latin
   002C  # COMMA
   002E  # FULL STOP
   003B  # SEMICOLON
   """),

  # Mong - Mongolian
  ('Mong',
   # Comment
   """
   From core specification.
   """,
   # Data
   """
   # Basic Latin
   0021  # EXCLAMATION MARK
   0022  # QUOTATION MARK
   0028  # LEFT PARENTHESIS
   0029  # RIGHT PARENTHESIS
   003F  # QUESTION MARK
   # General Punctuation
   201C  # LEFT DOUBLE QUOTATION MARK
   201D  # RIGHT DOUBLE QUOTATION MARK
   2048  # QUESTION EXCLAMATION MARK
   2049  # EXCLAMATION QUESTION MARK
   """),

  # Mroo - Mro

  # Mtei - Meitei Mayek (Meetei Mayek)

  # Mult - Mult (Multani)

  # Mymr - Myanmar
  ('Mymr',
   # Comment
   """
   From core specification; FE00 is for dotted forms.
   """,
   # Data
   """
   # General Punctuation
   200B  # ZERO WIDTH SPACE
   # Variation Selectors
   FE00  # VARIATION SELECTOR-1
   """),

  # Narb - Old North Arabian

  # Nbat - Nabataean

  # Newa - Newa

  # Nkoo - N'Ko (N'Ko)
  ('Nkoo',
   # Comment
   """
   From core specification.
   """,
   # Data
   """
   # Arabic
   060C  # ARABIC COMMA
   061B  # ARABIC SEMICOLON
   061F  # ARABIC QUESTION MARK
   # Supplemental Punctuation
   2E1C  # LEFT LOW PARAPHRASE BRACKET
   2E1D  # RIGHT LOW PARAPHRASE BRACKET
   # Arabic Presentation Forms-A
   FD3E  # ORNATE LEFT PARENTHESIS
   FD3F  # ORNATE RIGHT PARENTHESIS
   """),

  # Ogam - Ogham

  # Olck - Ol Chiki
  ('Olck',
   # Comment
   """
   From core specification.
   """,
   # Data
   """
   # Basic Latin
   0021  # EXCLAMATION MARK
   002C  # COMMA
   003F  # QUESTION MARK
   # General Punctuation
   2014  # EM DASH
   2018  # LEFT SINGLE QUOTATION MARK
   2019  # RIGHT SINGLE QUOTATION MARK
   201C  # LEFT DOUBLE QUOTATION MARK
   201D  # RIGHT DOUBLE QUOTATION MARK
   """),

  # Orkh - Orkhon (Old Turkic)
  ('Orkh',
   # Comment
   """
   From core specification.
   """,
   # Data
   """
   # General Punctuation
   205A  # TWO DOT PUNCTUATION
   # Supplemental Punctuation
   2E30  # RING POINT
   """),

  # Orya - Oriya

  # Osge - Osge (Osage)
  ('Osge',
   # Comment
   """
   Added by Monotype.
   """,
   # Data
   """
   # Combining Diacritical Marks
   0301  # COMBINING ACUTE ACCENT
   0304  # COMBINING MACRON
   030B  # COMBINING DOUBLE ACUTE ACCENT
   0358  # COMBINING DOT ABOVE RIGHT
   # Geometric Shapes
   25CC  # DOTTED CIRCLE
   """),

  # Osma - Osmanya

  # Palm - Palmyrene

  # Pauc - Pau Cin Hau
  ('Pauc',
   # Comment
   """
   From core specification.
   """,
   # Data
   """
   # Basic Latin
   002E  # FULL STOP
   """),

  # Perm - Old Permic
  ('Perm',
   # Comment
   """
   From core specification.
   """,
   # Data
   """
   # Basic Latin
   0027  # APOSTROPHE
   003A  # COLON
   # Latin-1 Supplement
   00B7  # MIDDLE DOT
   # Combining Diacritical Marks
   0300  # COMBINING GRAVE ACCENT
   0306  # COMBINING BREVE
   0307  # COMBINING DOT ABOVE
   0308  # COMBINING DIAERESIS
   0313  # COMBINING COMMA ABOVE
   # Cyrillic
   0483  # COMBINING CYRILLIC TITLO
   # Combining Diacritical Marks for Symbols
   20DB  # COMBINING THREE DOTS ABOVE
   """),

  # Phag - Phags-pa

  # Phli - Inscriptional Pahlavi

  # Phlp - Psalter Pahlavi
  ('Phlp',
   # Comment
   """
   from core specification.
   """,
   # Data
   """
   # Arabic
   0640  # ARABIC TATWEEL
   """),

  # Phnx - Phoenician

  # Plrd - Pollard Phonetic (Miao)

  # Prti - Inscriptional Parthian

  # Rjng - Rejang
  ('Rjng',
   # Comment
   """
   From core specification.
   """,
   # Data
   """
   # Basic Latin
   002C  # COMMA
   002E  # FULL STOP
   003A  # COLON
   """),

  # Runr - Runic

  # Samr - Samaritan
  ('Samr',
   # Comment
   """
   From core specification.
   """,
   # Data
   """
   # Supplemental Punctuation
   2E31  # WORD SEPARATOR MIDDLE DOT
   """),

  # Sarb - Old South Arabian

  # Saur - Saurashtra
  ('Saur',
   # Comment
   """
   From core specification, only the specificially mentioned punct.
   """,
   # Data
   """
   # Basic Latin
   002C  # COMMA
   002E  # FULL STOP
   003F  # QUESTION MARK
   """),

  # Sgnw - SignWriting

  # Shaw - Shavian
  ('Shaw',
   # Comment
   """
   From core specification.
   """,
   # Data
   """
   # Latin-1 Supplement
   00B7  # MIDDLE DOT
   """),

  # Shrd - Sharada

  # Sidd - Siddham

  # Sind - Khudawadi
  ('Sind',
   # Comment
   """
   From core specification.
   """,
   # Data
   """
   # Basic Latin
   002E  # FULL STOP
   003A  # COLON
   003B  # SEMICOLON
   # Devanagari
   0964  # DEVANAGARI DANDA
   0965  # DEVANAGARI DOUBLE DANDA
   # General Punctuation
   2013  # EN DASH
   2014  # EM DASH
   """),

  # Sinh - Sinhala
  ('Sinh',
   # Comment
   """
   From core specification, plus unspecified latin punctuation seen on web
   sites.
   """,
   # Data
   """
   # Basic Latin
   0021  # EXCLAMATION MARK
   0028  # LEFT PARENTHESIS
   0029  # RIGHT PARENTHESIS
   002C  # COMMA
   002E  # FULL STOP
   # Devanagari
   0964  # DEVANAGARI DANDA
   """),

  # Sora - Sora Sompeng
  ('Sora',
   # Comment
   """
   From core specification and
   http://www.unicode.org/L2/L2009/09189r-n3647r-sora-sompeng.pdf
   """,
   # Data
   """
   # Basic Latin
   0021  # EXCLAMATION MARK
   0028  # LEFT PARENTHESIS
   0029  # RIGHT PARENTHESIS
   002C  # COMMA
   002D  # HYPHEN-MINUS
   002E  # FULL STOP
   003B  # SEMICOLON
   # General Punctuation
   2010  # HYPHEN
   """),

  # Sund - Sundanese
  ('Sund',
   # Comment
   """
   From core specification.
   """,
   # Data
   """
   # Basic Latin
   0022  # QUOTATION MARK
   002D  # HYPHEN-MINUS
   003C  # LESS-THAN SIGN
   003E  # GREATER-THAN SIGN
   003F  # QUESTION MARK
   # General Punctuation
   2010  # HYPHEN
   201C  # LEFT DOUBLE QUOTATION MARK
   201D  # RIGHT DOUBLE QUOTATION MARK
   """),

  # Sylo - Syloti Nagri
  ('Sylo',
   # Comment
   """
   From core specification.
   """,
   # Data
   """
   # Basic Latin
   002C  # COMMA
   002E  # FULL STOP
   003A  # COLON
   003B  # SEMICOLON
   # Devanagari
   0964  # DEVANAGARI DANDA
   0965  # DEVANAGARI DOUBLE DANDA
   # General Punctuation
   2055  # FLOWER PUNCTUATION MARK
   """),

  # Syrc - Syriac
  ('Syrc',
   # Comment
   """
   From core specification.  In it, the reference to 'arabic harakat' used with
   Garshuni is based on the Harakat section of the wikipedia page on Arabic
   diacritics.
   """,
   # Data
   """
   # Combining Diacritical Marks
   0303  # COMBINING TILDE
   0304  # COMBINING MACRON
   0307  # COMBINING DOT ABOVE
   0308  # COMBINING DIAERESIS
   030A  # COMBINING RING ABOVE
   0320  # COMBINING MINUS SIGN BELOW
   0323  # COMBINING DOT BELOW
   0324  # COMBINING DIAERESIS BELOW
   0325  # COMBINING RING BELOW
   032D  # COMBINING CIRCUMFLEX ACCENT BELOW
   032E  # COMBINING BREVE BELOW
   0330  # COMBINING TILDE BELOW
   # Arabic
   060C  # ARABIC COMMA
   061B  # ARABIC SEMICOLON
   061F  # ARABIC QUESTION MARK
   0640  # ARABIC TATWEEL
   064E  # ARABIC FATHA
   064F  # ARABIC DAMMA
   0650  # ARABIC KASRA
   0651  # ARABIC SHADDA
   0652  # ARABIC SUKUN
   0653  # ARABIC MADDAH ABOVE
   0670  # ARABIC LETTER SUPERSCRIPT ALEF
   0671  # ARABIC LETTER ALEF WASLA
   # General Punctuation
   200C  # ZERO WIDTH NON-JOINER
   """),

  # Tagb - Tagbanwa

  # Takr - Takri
  ('Takr',
   # Comment
   """
   From core specification.
   """,
   # Data
   """
   # Devanagari
   0964  # DEVANAGARI DANDA
   0965  # DEVANAGARI DOUBLE DANDA
   """),

  # Tale - Tai Le
  ('Tale',
   # Comment
   """
   From core specification & http://www.unicode.org/L2/L2001/01369-n2372.pdf
   Myanmar digits have glyphic variants according to the spec.
   """,
   # Data
   """
   # Basic Latin
   002C  # COMMA
   002E  # FULL STOP
   003A  # COLON
   003F  # QUESTION MARK
   # Combining Diacritical Marks
   0300  # COMBINING GRAVE ACCENT
   0301  # COMBINING ACUTE ACCENT
   0307  # COMBINING DOT ABOVE
   0308  # COMBINING DIAERESIS
   030C  # COMBINING CARON
   # Myanmar
   1040  # MYANMAR DIGIT ZERO
   1041  # MYANMAR DIGIT ONE
   1042  # MYANMAR DIGIT TWO
   1043  # MYANMAR DIGIT THREE
   1044  # MYANMAR DIGIT FOUR
   1045  # MYANMAR DIGIT FIVE
   1046  # MYANMAR DIGIT SIX
   1047  # MYANMAR DIGIT SEVEN
   1048  # MYANMAR DIGIT EIGHT
   1049  # MYANMAR DIGIT NINE
   # General Punctuation
   201C  # LEFT DOUBLE QUOTATION MARK
   201D  # RIGHT DOUBLE QUOTATION MARK
   # CJK Symbols and Punctuation
   3002  # IDEOGRAPHIC FULL STOP
   """),

  # Talu - New Tai Lue

  # Taml - Tamil
  ('Taml',
   # Comment
   """
   From core specificaion and
   http://www.unicode.org/L2/L2010/10407-ext-tamil-follow2.pdf
   """,
   # Data
   """
   # Latin-1 Supplement
   00B2  # SUPERSCRIPT TWO
   00B3  # SUPERSCRIPT THREE
   # Superscripts and Subscripts
   2074  # SUPERSCRIPT FOUR
   2082  # SUBSCRIPT TWO
   2083  # SUBSCRIPT THREE
   2084  # SUBSCRIPT FOUR
   """),

  # Tang - Tangut

  # Tavt - Tai Viet
  ('Tavt',
   # Comment
   """
   Used in SIL fonts.
   """,
   # Data
   """
   # Latin Extended-D
   A78B  # LATIN CAPITAL LETTER SALTILLO
   A78C  # LATIN SMALL LETTER SALTILLO
   """),

  # Telu - Telugu

  # Tfng - Tifinagh
  ('Tfng',
   # Comment
   """
   From core specification.
   """,
   # Data
   """
   # Combining Diacritical Marks
   0302  # COMBINING CIRCUMFLEX ACCENT
   0304  # COMBINING MACRON
   0307  # COMBINING DOT ABOVE
   0309  # COMBINING HOOK ABOVE
   # General Punctuation
   200D  # ZERO WIDTH JOINER
   """),

  # Tglg - Tagalog

  # Thaa - Thaana
  ('Thaa',
   # Comment
   """
   From core specification, parens from text sample.  Probably other punct
   as well but spec does not list.
   """,
   # Data
   """
   # Basic Latin
   0028  # LEFT PARENTHESIS
   0029  # RIGHT PARENTHESIS
   002E  # FULL STOP
   # Arabic
   060C  # ARABIC COMMA
   061B  # ARABIC SEMICOLON
   061F  # ARABIC QUESTION MARK
   """),

  # Thai - Thai
  ('Thai',
   # Comment
   """
   From core specification and
   http://www.unicode.org/L2/L2010/10451-patani-proposal.pdf
   for latin punct see web sites e.g. pandip.com, sanook.com
   Bhat already here, or should be
   """,
   # Data
   """
   # Basic Latin
   0021  # EXCLAMATION MARK
   0022  # QUOTATION MARK
   0028  # LEFT PARENTHESIS
   0029  # RIGHT PARENTHESIS
   002C  # COMMA
   002E  # FULL STOP
   003A  # COLON
   003F  # QUESTION MARK
   # Spacing Modifier Letters
   02BC  # MODIFIER LETTER APOSTROPHE
   02D7  # MODIFIER LETTER MINUS SIGN
   # Combining Diacritical Marks
   0303  # COMBINING TILDE
   0331  # COMBINING MACRON BELOW
   # General Punctuation
   200B  # ZERO WIDTH SPACE
   201C  # LEFT DOUBLE QUOTATION MARK
   201D  # RIGHT DOUBLE QUOTATION MARK
   2026  # HORIZONTAL ELLIPSIS
   """),

  # Tibt - Tibetan
  ('Tibt',
   # Comment
   """
   Wheel of Dharma from core specification, not sure of source for vertical
   line.
   """,
   # Data
   """
   # Basic Latin
   007C  # VERTICAL LINE
   # Miscellaneous Symbols
   2638  # WHEEL OF DHARMA
   """),

  # Tirh - Tirhuta
  ('Tirh',
   # Comment
   """
   From core specification.
   """,
   # Data
   """
   # Devanagari
   0964  # DEVANAGARI DANDA
   0965  # DEVANAGARI DOUBLE DANDA
   """),

  # Ugar - Ugaritic

  # Vaii - Vai
  ('Vaii',
   # Comment
   """
   From core specification.
   """,
   # Data
   """
   # Basic Latin
   002C  # COMMA
   002D  # HYPHEN-MINUS
   """),

  # Wara - Varang Kshiti (Warang Citi)
  ('Wara',
   # Comment
   """
   "Uses latin punctuation," so guess based on sample text from
   proposal doc, see
   http://www.unicode.org/L2/L2012/12118-n4259-warang-citi.pdf
   """,
   # Data
   """
   # Basic Latin
   0021  # EXCLAMATION MARK
   0028  # LEFT PARENTHESIS
   0029  # RIGHT PARENTHESIS
   002C  # COMMA
   002D  # HYPHEN-MINUS
   002E  # FULL STOP
   003A  # COLON
   003B  # SEMICOLON
   003F  # QUESTION MARK
   # General Punctuation
   2013  # EN DASH
   2014  # EM DASH
   201C  # LEFT DOUBLE QUOTATION MARK
   201D  # RIGHT DOUBLE QUOTATION MARK
   """),

  # Xpeo - Old Persian

  # Xsux - Sumero-Akkadian Cuneiform (Cuneiform)

  # Yiii - Yi
  ('Yiii',
   # Comment
   """
   From core specification.
   Fullwidth Comma is used in UDHR text for Yi.  Add standard comma
   so we have a 'halfwidth' form to match.
   """,
   # Data
   """
   # Latin-1
   002C  # COMMA
   # CJK Symbols and Punctuation
   3001  # IDEOGRAPHIC COMMA
   3002  # IDEOGRAPHIC FULL STOP
   # Halfwidth and Fullwidth Forms
   FF0C  # FULLWIDTH COMMA
   """),
]

# This is a utility function that parses the _script_required data
# and spits it out again in the above format.  When editing the
# above data, just type in the hex values, then run this to regenerate
# the source in sorted order with block labels and codepoint names.
def _regen_script_required():
  """Rerun after editing script required to check/reformat."""
  script_to_comment_and_data = {
      script: (comment, data)
      for script, comment, data in _SCRIPT_REQUIRED
  }
  scripts = set(unicode_data.all_scripts())
  for to_script, from_scripts in _MERGED_SCRIPTS_BY_TARGET.iteritems():
    scripts.add(to_script)
    scripts -= set(from_scripts)
  # keep extra script data, e.g. 'Aran'
  scripts.update(set(script_to_comment_and_data.keys()))
  scripts -= set(['Zinh', 'Zyyy', 'Zzzz'])

  for script in sorted(scripts):
    if script in _MERGED_SCRIPTS_BY_TARGET:
      script_name = '(%s)' % ','.join(_MERGED_SCRIPTS_BY_TARGET[script])
    else:
      script_name = cldr_data.get_english_script_name(script)
      try:
        unicode_script_name = unicode_data.human_readable_script_name(script)
        if script_name.lower() != unicode_script_name.lower():
          script_name += ' (%s)' % unicode_script_name
      except KeyError:
        pass
      script_name = script_name.replace(unichr(0x2019), "'")
    print '  # %s - %s' % (script, script_name)
    if script in script_to_comment_and_data:
      print "  ('%s'," % script
      lines = []
      comment, data = script_to_comment_and_data[script]
      lines.append('   # Comment')
      lines.append('"""')
      for line in comment.strip().splitlines():
        lines.append(line.strip())
      lines.append('""",')

      lines.append('# Data')
      lines.append('"""')
      cps = tool_utils.parse_int_ranges(data)
      block = None
      for cp in sorted(cps):
        cp_block = unicode_data.block(cp)
        if cp_block != block:
          block = cp_block
          lines.append('# ' + block)
        cp_name = unicode_data.name(cp, '<unnamed>')
        lines.append('%04X  # %s' % (cp, cp_name))
      lines.append('"""),')
      print '\n   '.join(lines)
    print


def _assign_script_required(cmap_ops):
  """Assign extra characters for various scripts."""

  for script, _, data in _SCRIPT_REQUIRED:
    extra = tool_utils.parse_int_ranges(data)
    cmap_ops.phase('assign script required for ' + script)
    cmap_ops.add_all(extra, script)

  # Because of a miscommunication the Coptic EPACT numbers, which had
  # been assigned to SYM2, were also added to the Coptic font because
  # they were listed in a bug from two years ago.  So we'll now put them
  # in the Coptic requirements just so we know they're supposed to be there.
  epact = tool_utils.parse_int_ranges('102e0-102fb')
  cmap_ops.add_all(epact, 'Copt')


def _assign_script_special_chars(cmap_ops):
  """Assign special characters listed in opentype_data."""
  cmap_ops.phase('assign special chars')
  for script, chars in opentype_data.SPECIAL_CHARACTERS_NEEDED.iteritems():
    cmap_ops.add_all(frozenset(chars), script)


def _assign_legacy_phase2(cmap_ops):
  """Assign legacy chars in some scripts, excluding some blocks."""
  legacy_data = cmap_data.read_cmap_data_file('data/noto_cmap_phase2.xml')
  legacy_map = cmap_data.create_map_from_table(legacy_data.table)
  legacy_script_to_chars = {
      script: tool_utils.parse_int_ranges(row.ranges)
      for script, row in legacy_map.iteritems()}

  # The default is to include all legacy characters, except for the chars
  # listed for these scripts, for some default chars, and for some scripts.

  # Find out why these were included in the phase two fonts.
  # This excludes lots of punctuation and digits from Cham, Khmer, and Lao
  # but leaves some common latin characters like quotes, parens, comma/period,
  # and so on.
  exclude_script_ranges = {
    'Cham': '23-26 2A-2B 30-39 3C-3E 40 5B-60 7B-7E 037E',
    'Deva': '00AF', # Jelle says this was encoded by accident, should be 00AD
    'Kthi': '0030-0039',
    'Khmr': '23-26 2A-2B 30-39 3C-3E 40 5B-60 7B-7E 037E',
    'LGC': '03E2',
    'Lana': '2219',
    'Laoo': '23-26 2A-2B 30-39 3C-3E 40 5B-60 7B-7E 037E',
    'Limb': '0964', # I think double-danda was intended
    'Mlym': '0307 0323',
    'Syrc': '250C 2510', # box drawing?
    'Tavt': 'A78C',
  }

  # mono temporarily
  ignore_legacy = frozenset('LGC Zsye Zsym MONO'.split())
  ignore_cps = frozenset([0x0, 0xd, 0x20, 0xa0, 0xfeff])

  cmap_ops.phase('assign legacy phase 2')
  script_to_chars = cmap_ops.create_script_to_chars()
  for script in sorted(legacy_script_to_chars):
    if script not in script_to_chars:
      cmap_ops.log('skipping script %s' % script)
      continue
    if script in ignore_legacy:
      cmap_ops.log('ignoring %s' % script)
      continue

    script_chars = script_to_chars[script]
    legacy_chars = legacy_script_to_chars[script]
    missing_legacy = set(legacy_chars) - set(script_chars) - ignore_cps
    if script in exclude_script_ranges:
      ranges = exclude_script_ranges[script]
      missing_legacy -= set(tool_utils.parse_int_ranges(ranges))
    if missing_legacy:
      cmap_ops.phase('assign legacy %s' % script)
      cmap_ops.add_all(missing_legacy, script)


def _check_CJK():
  # not used
  # check CJK
  cmap_ops.log('check cjk legacy')
  legacy_cjk_chars = set()
  for script in _MERGED_SCRIPTS_BY_TARGET['CJK']:
    if script in legacy_script_to_chars:
      legacy_cjk_chars |= legacy_script_to_chars[script]

  cjk_chars = script_to_chars['CJK']
  not_in_legacy = cjk_chars - legacy_cjk_chars
  # ignore plane 2 and above
  not_in_legacy -= set(range(0x20000, 0x120000))
  if not_in_legacy:
    print 'not in legacy (%d):' % len(not_in_legacy)
    compare_cmap_data._print_detailed(not_in_legacy)
  not_in_new = legacy_cjk_chars - cjk_chars
  if not_in_new:
    print 'not in new (%d):' % len(not_in_new)
    compare_cmap_data._print_detailed(not_in_new)


def _assign_bidi_mirroring(cmap_ops):
  """Ensure that if a bidi mirroring char is in a font, its mirrored char
  is too."""
  cmap_ops.phase('bidi mirroring')
  script_to_chars = cmap_ops.create_script_to_chars()
  mirrored = unicode_data.mirrored_chars()
  for script, cps in sorted(script_to_chars.iteritems()):
    mirrored_in_script = cps & mirrored
    if not mirrored_in_script:
      continue
    sibs = set(unicode_data.bidi_mirroring_glyph(cp)
               for cp in mirrored_in_script)
    missing_sibs = sibs - mirrored_in_script
    if missing_sibs:
      cmap_ops.log('adding %d missing bidi chars' % len(missing_sibs))
      cmap_ops.add_all(missing_sibs, script)


def _unassign_lgc_from_symbols(cmap_ops):
  """Characters in LGC don't need to be in Symbols or Sym2."""
  cmap_ops.phase('unassign lgc from symbols')
  lgc_set = frozenset(cmap_ops.script_chars('LGC'))
  sym_set = frozenset(cmap_ops.script_chars('Zsym'))
  sym2_set = frozenset(cmap_ops.script_chars('SYM2'))
  sym_set_to_remove = sym_set & lgc_set
  sym2_set_to_remove = sym2_set & lgc_set

  # Combining enclosing marks in Symbols need latin to combine with, so add
  # letters and digits, also dotted circle if not there already.
  alphanum = tool_utils.parse_int_ranges('30-39 41-5a 61-7a 25cc')
  sym_set_to_remove -= alphanum

  cmap_ops.remove_all(sym_set_to_remove, 'Zsym')
  cmap_ops.remove_all(sym2_set_to_remove, 'SYM2')



def _assign_programming_lang_symbols(cmap_ops):
  """Assign characters used in programming languages, which generally
  should be in MONO and in some cases need to be compatible with math
  in general."""

  def add_mirrored(cps):
    mirrored_cps = set()
    for cp in cps:
      if unicode_data.mirrored(cp):
        mirrored_glyph = unicode_data.bidi_mirroring_glyph(cp)
        if mirrored_glyph != None:
          mirrored_cps.add(mirrored_glyph)
    cps |= (mirrored_cps)

  # some characters we want to preserve in symbols despite adding them
  # to math.
  preserve_symbols_cps = tool_utils.parse_int_ranges(
      """
      2190 # LEFTWARDS ARROW
      2191 # UPWARDS ARROW
      2192 # RIGHTWARDS ARROW
      2193 # DOWNWARDS ARROW
      2194 # LEFT RIGHT ARROW
      2195 # UP DOWN ARROW
      2474 # PARENTHESIZED DIGIT ONE
      2475 # PARENTHESIZED DIGIT TWO
      266d # MUSIC FLAT SIGN
      266e # MUSIC NATURAL SIGN
      266f # MUSIC SHARP SIGN
      27f6 # LONG RIGHTWARDS ARROW
      """)

  # similarly, preserve some in symbols2
  preserve_symbols2_cps = tool_utils.parse_int_ranges(
      """
      21e8 # RIGHTWARDS WHITE ARROW
      2219 # BULLET OPERATOR
      2299 # CIRCLED DOT OPERATOR
      25a1 # WHITE SQUARE
      25b7 # WHITE RIGHT-POINTING TRIANGLE
      25bb # WHITE RIGHT-POINTING POINTER
      25c2 # BLACK LEFT-POINTING SMALL TRIANGLE
      25c3 # WHITE LEFT-POINTING SMALL TRIANGLE
      25c5 # WHITE LEFT-POINTING POINTER
      25c7 # WHITE DIAMOND
      25c8 # WHITE DIAMOND CONTAINING BLACK SMALL DIAMOND
      25cb # WHITE CIRCLE
      2736 # SIX POINTED BLACK STAR
      """)

  cmap_ops.phase('programming - haskell')
  # see noto-fonts#669 agda non-ascii character list
  haskell_cps = tool_utils.parse_int_ranges(
      """
      00a0 00ac 00b2 00b7 00b9 00bd 00d7 00e0 00e9 00f3 00f6-00f7 019b
      02b0 02b3 02e1-02e2 0307 0393 0398 03a0 03a3 03b5 03b7 03bb-03be
      03c1 03c3-03c4 03c6 03c8-03c9 2022 2026 2032-2033 203c 203f
      2045-2046 2070 207a-207b 207f-2089 2113 2115 211a 2124 2190-2194
      219d-219e 21a0 21a2-21a3 21a6 21d0-21d4 21db 21e8 2200-2201
      2203-2205 2208-2209 220b 220e 2218-2219 221e 2223 2227-222a
      2236-2238 223c 2241 2243 2245 2247-224b 2254 2257 225f 2261-2262
      2264-2265 226c 226e-2273 2275 227a-227b 2286-2288 228e 2291-229c
      22a4-22a5 22b4 22b8 22c2-22c3 22c6 22c9-22ca 22ce 22d0 22e2
      2308-230b 236e 2474-2475 25a1 25b7 25bb 25c2-25c3 25c5 25c7-25c8
      266d 266f 2736 27e6-27eb 27f6 2987-2988 2a00 2a05-2a06 ff5b ff5d
      """)

  # add extra not in the set above:
  # (from github.com/adobe-fonts/source-code-pro/issues/114)
  haskell_cps |= tool_utils.parse_int_ranges(
      """2202 2210 2220 2234 2235 2284 2285 2289""")

  # see comment from joeyaiello on noto-fonts/issues/669
  # others mentioned in that comment are already in haskell
  haskell_cps.add(0x2195)

  # add mirrored cps to this set
  add_mirrored(haskell_cps)

  # add 'leftwards' variants (not mirrored) and a few other variants
  # because it seems odd to split these groups even if there's no use for
  # them in haskell.
  leftwards_variants = tool_utils.parse_int_ranges(
      """
    # Arrows
      219c # LEFTWARDS WAVE ARROW (ref 219d)
      21a4 # LEFTWARDS ARROW FROM BAR (ref 21a6)
      21da # LEFTWARDS TRIPLE ARROW (ref 21db)
      21e6 # LEFTWARDS WHITE ARROW (ref 21e8)
    # Miscellaneous Technical
      2310 # REVERSED NOT SIGN (ref 00ac)
      2319 # TURNED NOT SIGN (ref 00ac)
    # Miscellaneous Symbols
      266e # MUSIC NATURAL SIGN (ref 266d)
    # Supplemental Arrows-A
      27f5 # LONG LEFTWARDS ARROW (ref 27f6)
      """)
  haskell_cps |= leftwards_variants

  cmap_ops.add_all_to_all(haskell_cps, ['Zmth', 'MONO'])
  cmap_ops.remove_all(haskell_cps - preserve_symbols_cps, 'Zsym')
  cmap_ops.remove_all(haskell_cps - preserve_symbols2_cps, 'SYM2')

  cmap_ops.phase('programming - APL')
  # For the below APL sets, see noto-fonts#751
  apl_cps = tool_utils.parse_int_ranges(
      """
      0021 0024 0027-0029 002b-002c 002e-002f 003a-003f 005b-005d 005f
      007b 007d 00a8 00af 00d7 00f7 2190-2193 2205-2207 220a 2212 2218
      2223 2227-222a 2235 223c 2260-2262 2264-2265 2282-2283 2286-2287
      2296 22a2-22a5 22c4 22c6 2308 230a 2336-237a 2395 25cb
      """)

  # do not use circled uppercase letters as a substitute for APL underscored
  # letters.  Dyalog APL does this and hacks a font to make them to render as
  # underscored. Also apl385 does this and renders these as underscored.  This
  # is contrary to Unicode (which should just have gone ahead and encoded these,
  # but I guess balked since they were already kind of deprecated by that time).
  # apl_cps |= tool_utils.parse_int_ranges('24B6-24CF')

  # additionally requested relational algebra symbols
  apl_cps |= tool_utils.parse_int_ranges('22c8-22ca 25b7 27d5-27d7')

  # additionally requested NARS symbols
  apl_cps |= tool_utils.parse_int_ranges('00a7 03c0 221a 221e 2299')

  add_mirrored(apl_cps)

  # Android doesn't want MONO as a fallback, so no codepoint should be added
  # only to MONO and not to any other Noto font.
  cmap_ops.add_all_to_all(apl_cps, ['MONO', 'Zmth'])


def _assign_symbols_from_groups(cmap_ops):
  """Use 'group data' to assign various symbols to Zmth, Zsym, SYM2,
  MONO, MUSIC' based on character groups.  This fine-tunes the block
  assignments (some related symbols are scattered across blocks,
  and symbols blocks are themselves mixed)."""

  cmap_ops.phase('assign symbols from groups')
  with open('codepoint_groups.txt', 'r') as f:
    for lineix, line in enumerate(f):
      ix = line.find('#')
      if ix >= 0:
        line = line[:ix]
      line = line.strip()
      if not line:
        continue

      cols = [s.strip() for s in line.split(';')]
      if not len(cols) == 3:
        print ('incorrect cols on line %d "%s"' % (lineix, line))
      if cols[0] == '':
        # no assignments for this line
        continue

      add, remove = [], []
      for s in cols[0].split():
        if s.startswith('-'):
          remove.append(s[1:])
        else:
          add.append(s)
      name = cols[1]

      # We use parens to delimit parts of the ranges that are 'for
      # reference' but should not impact codepoint assignment.
      # since parse_int_ranges doesn't understand these, strip
      # out the parenthesized sections. These don't nest but we
      # don't check for this, only that open ranges are closed.
      ranges = cols[2]
      parts = None
      ix = 0
      while ix < len(ranges):
        open_p = ranges.find('(', ix)
        if open_p < 0:
          if parts != None:
            parts.append(ranges[ix:].strip())
          break
        close_p = ranges.find(')', open_p+1)
        if close_p < 0:
          raise Exception(
              'unclosed paren in ranges on line %d "%s"' % (lineix, line))
        if parts == None:
          parts = []
        parts.append(ranges[ix:open_p])
        ix = close_p + 1
      if parts:
        ranges = ' '.join(parts)

      try:
        cps = tool_utils.parse_int_ranges(ranges)
      except Exception as err:
        print >> sys.stderr, err
        print >> sys.stderr, cols[2]
        print >> sys.stderr, 'problem on %d "%s"' % (lineix, line)
        raise err
      if len(cps) > 50:
        print >> sys.stderr, 'large range (%d) on %d "%s"' % (
            len(cps), lineix, line)

      cmap_ops.log('group: %s (%d)' % (name, len(cps)))
      if add:
        cmap_ops.add_all_to_all(cps, add)
      if remove:
        cmap_ops.remove_all_from_all(cps, remove)


def _assign_mono(cmap_ops):
  """Monospace should be similar to LGC, with the addition of box drawing
  and block elements.  It should also include all CP437 codepoints."""

  cmap_ops.phase('assign mono')
  lgc_chars = cmap_ops.script_chars('LGC')
  cmap_ops.add_all(lgc_chars, 'MONO')

  cp437_cps = unicode_data.codeset('cp437')
  cmap_ops.phase('assign cp437 to mono')
  assert cp437_cps != None
  cmap_ops.add_all(cp437_cps, 'MONO')

  # for variant zero
  cmap_ops.add(0xfe00, 'MONO')

  # geometric shapes should be in MONO too, many are but they're scattered
  cmap_ops.add_all(_block_cps('Geometric Shapes'), 'MONO')


def _assign_sym2(cmap_ops):
  """SYM2 should support enclosing keycaps, used to be in B/W Emoji."""
  cmap_ops.phase('assign sym2')
  keycap_chars = tool_utils.parse_int_ranges("""
      0023      # Number Sign
      002A      # Asterisk
      0030-0039 # Digits
      20E3      # Combining Enclosing Keycap""")
  cmap_ops.add_all(keycap_chars, 'SYM2')


def _assign_math(cmap_ops):
  """No longer use STIX character set, we will just fallback for characters
  not in math. However, we want much of math to work without fallback, for
  instance we need character ranges for the combining marks, and want a serif
  form of the ASCII, so we duplicate more than usual."""

  cmap_ops.phase('assign math')

  # We keep this here for awhile for reference, but no longer use it.
  STIX_CPS = tool_utils.parse_int_ranges(
      """
      0020-007e 00a0-0180 0188 0190 0192 0195 0199-019b 019e 01a0-01a1 01a5
      01aa-01ab 01ad 01af-01b0 01b5 01ba-01bb 01be 01c0-01c3 01f0 01fa-01ff
      0221 0234-0237 02b0-02e9 02ec-02ed 0300-033f 0346 034c 0359 035c
      0360-0362 037e 0384-038a 038c 038e-03a1 03a3-03ce 03d0-03d2 03d5-03d6
      03d8-03e1 03f0-03f1 03f4-03f6 0401-040c 040e-044f 0451-045c 045e-045f
      0462-0463 046a-046b 0472-0475 0490-0491 1d00 1d07 1d1c 1d84-1d85 1d8a
      1d8d-1d8e 1e80-1e85 1ef2-1ef3 2010-2022 2025-2026 2030-203c 203e 2040
      2043-2044 2047 204e-2052 2057 205f 207f 20a3-20a4 20a7 20ac 20d0-20d2
      20d6-20d7 20db-20df 20e1 20e4-20f0 2102 2105 2107 210a-2113 2115-211e
      2122 2124-2129 212b-2138 213c-214b 2153-215e 2190-21ea 21f4-22ff 2302
      2305-2306 2308-2313 2315-231a 231c-2323 2329-232a 232c-232e 2332 2336
      233d 233f-2340 2353 2370 237c 2393-2394 239b-23b9 23ce 23d0 23dc-23e7
      2423 2460-2468 24b6-24ea 2500 2502 2506 2508 250a 250c 2510 2514 2518
      251c 2524 252c 2534 253c 2550-256c 2571-2572 2584 2588 258c 2590-2593
      25a1-25ff 2606 2609 260c 260e 2612 2621 2639-2644 2646-2649 2660-2667
      2669-266b 266d-266f 267e 2680-2689 26a0 26a5 26aa-26ac 26b2 2709 2713
      2720 272a 2736 273d 2772-2773 2780-2793 279b 27c1-27c9 27cc 27d0-27ef
      27f1-27ff 2901-2aff 2b13-2b41 2b43-2b4c 2b50-2b54 3030 fb00-fb04
      1d401-1d454 1d456-1d49c 1d49e-1d49f 1d4a2 1d4a5-1d4a6 1d4a9-1d4ac
      1d4ae-1d4b9 1d4bb 1d4bd-1d4c3 1d4c5-1d505 1d507-1d50a 1d50d-1d514
      1d516-1d51c 1d51e-1d539 1d53b-1d53e 1d540-1d544 1d546 1d54a-1d550
      1d552-1d6a5 1d6a8-1d7c9 1d7ce-1d7ff
      """)

  # Assume fallback will work for these in general, but...
  cmap_ops.remove_all(cmap_ops.script_chars('LGC'), 'Zmth')
  cmap_ops.remove_all(cmap_ops.script_chars('SYM2'), 'Zmth')

  # Add all printable ASCII.  We're not going to rely on fallback for these
  # after all.
  printable_ascii = tool_utils.parse_int_ranges('0020-007e')
  cmap_ops.add_all(printable_ascii, 'Zmth')

  # Add back blocks that get split up too arbitrarily
  cmap_ops.add_all(_block_cps('Mathematical Operators'), 'Zmth')
  cmap_ops.add_all(_block_cps('Miscellaneous Mathematical Symbols-B'), 'Zmth')

  # Add back some symbols for math/logic
  math_geom = tool_utils.parse_int_ranges(
      '25af/b3/b7/bd/c1/ca/fb', allow_compressed=True)
  cmap_ops.add_all(math_geom, 'Zmth')

  # Add dotted circle, we have combining marks
  cmap_ops.add(0x25cc, 'Zmth')

  # Add misc latin ops
  # plus/minus, multiply, divide, logical not
  # a7 is used in a variant of APL
  latin_misc = tool_utils.parse_int_ranges('b1 d7 f7 a7 ac')
  cmap_ops.add_all(latin_misc, 'Zmth')

  # Fill holes in math alpha blocks, again we don't fallback here after all.
  math_holes = tool_utils.parse_int_ranges(
      """
      2102/0a-0e/10-12/15/19-1d/24/28/2c-2d/2f-31/33-38/3c-40/45-49
      """, allow_compressed=True)
  cmap_ops.add_all(math_holes, 'Zmth')

  # Add hebrew alef, bet, gimel, dalet
  cmap_ops.add_all(tool_utils.parse_int_ranges('2135-2138'), 'Zmth')

  # Add greek regular, we can have combining marks on them too
  # These correspond to the math greek alpha ranges
  greek_math_regular = tool_utils.parse_int_ranges(
      '391-3a1 3f4 3a3-3a9 2207 3b1-3c9 2202 3f5 3d1 3f0 3d5 3f1 3d6')
  cmap_ops.add_all(greek_math_regular, 'Zmth')

  # Add primes
  cmap_ops.add_all(tool_utils.parse_int_ranges('2032-2037 2057'), 'Zmth')

  # Duplicate some combining marks from LGC so they can apply to math chars
  more_combining_marks = tool_utils.parse_int_ranges('302-303 305 307-308 330')
  cmap_ops.add_all(more_combining_marks, 'Zmth')


def _assign_dotted_circle(cmap_ops):
  """All scripts with combining marks should provide dotted circle (and provide
  an appropriate rendering of the mark in combination with it)."""
  cmap_ops.phase('assign dotted circle')

  def is_combining(cp):
    return unicode_data.category(cp) == 'Mn'

  # Note wikipedia shows Arabic marks placed w.r.t. tatweel, not the dotted
  # circle, but as using dotted circle is the convention used by Unicode in
  # their code charts we'll require it for Arabic too.
  script_to_chars = cmap_ops.create_script_to_chars()
  for script, charset in sorted(script_to_chars.iteritems()):
    if script == 'EXCL':
      continue
    nsm = frozenset(cp for cp in charset if is_combining(cp))
    if nsm:
      count = len(nsm)
      range_str = tool_utils.write_int_ranges(sorted(nsm)[:8])
      msg = '%s has %d marks: %s' % (
          script, count, range_str if count < 8 else range_str + '...')
      cmap_ops.log(msg)
      cmap_ops.add(0x25CC, script)


def _remove_unwanted(cmap_ops):
  """Remove characters we know we don't want in any font."""
  # Chars we never want.
  unwanted_chars = tool_utils.parse_int_ranges("""
      0000-001f  # C0 controls
      007F       # DEL
      0080-009f  # C1 controls
      FEFF       # BOM""")

  # Chars we don't want, but perhaps a bit more provisionally than the
  # above.
  excluded_chars = tool_utils.parse_int_ranges("""
      332c         # Jungshik says excluded on purpose
      fa70-fad9    # Jungshik says Ken regards DPRK compatibility chars as
                   # outside of scope, like most of plane 2.
      1b000-1b001  # Ken says these are controversial.""")
  cmap_ops.phase('remove unwanted')
  cmap_ops.remove_all_from_all(unwanted_chars, cmap_ops.all_scripts())
  cmap_ops.add_all(unwanted_chars, 'EXCL')

  cmap_ops.phase('remove excluded')
  cmap_ops.remove_all_from_all(excluded_chars, cmap_ops.all_scripts())
  cmap_ops.add_all(excluded_chars, 'EXCL')


def _assign_wanted(cmap_ops):
  """After we remove the characters we 'never want', add exceptions back in
  to particular fonts."""
  wanted_chars = {
      'LGC': '20bf feff', # Bitcoin (not in Unicode 9 data yet), BOM
      'MONO': 'feff',  # BOM
      'SYM2': '0000-001f 007f 0080-009f', # show as question mark char
      'Zsye': 'fe4e5-fe4ee fe82c fe82e-fe837', # legacy PUA for android
  }
  cmap_ops.phase('assign wanted')
  for script in sorted(wanted_chars.keys()):
    chars = tool_utils.parse_int_ranges(wanted_chars[script])
    cmap_ops.add_all(chars, script)


def _assign_basic(cmap_ops):
  """Add NUL, CR, Space, NBS to all scripts."""
  basic_chars = frozenset([0x0, 0x0D, 0x20, 0xA0])
  cmap_ops.phase('assign basic')
  scripts_to_add = set(cmap_ops.all_scripts()) - set(['EXCL'])
  cmap_ops.add_all_to_all(basic_chars, scripts_to_add)


def build_script_to_chars(log_level):
  if log_level == 0:
    log_events = False
    log_details = False
  else:
    log_events = True
    log_details = log_level > 1

  script_to_chars = unicode_data.create_script_to_chars()

  # Bitcoin is not in our unicode 9 data yet, allow it to be set anyway.
  temp_defined = set([0x20bf])

  cmap_ops = CmapOps(
      script_to_chars, log_events=log_events, log_details=log_details,
      undefined_exceptions=temp_defined)

  _remove_unicode_assignments(cmap_ops)
  _unassign_inherited_and_common_with_extensions(cmap_ops)
  _reassign_inherited(cmap_ops)
  _reassign_common(cmap_ops)
  _unassign_latin(cmap_ops)
  _assign_cldr_punct(cmap_ops)
  _reassign_merged_scripts(cmap_ops)
  _reassign_common_by_block(cmap_ops)
  _reassign_by_block(cmap_ops)
  _remove_empty(cmap_ops)
  _reassign_symbols(cmap_ops)
  _reassign_emoji(cmap_ops)
  _assign_nastaliq(cmap_ops)
  _assign_complex_script_extra(cmap_ops)
  _assign_hyphens_for_autohyphenation(cmap_ops)
  _assign_script_required(cmap_ops)
  _assign_script_special_chars(cmap_ops)
  _assign_legacy_phase2(cmap_ops)
  _assign_bidi_mirroring(cmap_ops)
  _unassign_lgc_from_symbols(cmap_ops)
  _assign_programming_lang_symbols(cmap_ops)
  _assign_symbols_from_groups(cmap_ops)
  _assign_mono(cmap_ops) # after LGC is defined except for basics
  _assign_sym2(cmap_ops) # after LGC removed, add back for enclosing keycaps
  _assign_math(cmap_ops)
  _assign_dotted_circle(cmap_ops) # for all fonts with combining marks
  _remove_unwanted(cmap_ops)  # comes before assign_basic, assign_wanted
  _assign_wanted(cmap_ops)
  _assign_basic(cmap_ops)
  cmap_ops.finish()  # so we can clean up log

  return cmap_ops.create_script_to_chars()


def _merge_fallback_chars(script_to_chars, srcfile):
  xtra_cmap_data = cmap_data.read_cmap_data_file(srcfile)
  xtra_rowdata = cmap_data.create_map_from_table(xtra_cmap_data.table)
  merged_cmap = {}
  for script in sorted(script_to_chars):
    cmap = script_to_chars[script]
    xcmap = None
    if script in xtra_rowdata:
      rowdata = xtra_rowdata[script]
      xcount = int(getattr(rowdata, 'xcount', -1))
      if xcount != -1:
        xcmap = tool_utils.parse_int_ranges(rowdata.xranges)
        cmap -= xcmap
      else:
        xcmap = None  # not a tuple, so probably no fallback data
    else:
      print >> sys.stderr, 'no script %s found in %s' % (script, srcfile)
    merged_cmap[script] = (cmap, xcmap)
  return merged_cmap


def _get_cmap_data(script_to_chars, metadata):
  tabledata = cmap_data.create_table_from_map(script_to_chars)
  return cmap_data.CmapData(metadata, tabledata)


### debug

def _dump_primaries():
  for block in unicode_data.block_names():
    block_range = unicode_data.block_range(block)
    primary_script = _primary_script_for_block(block)
    print '%13s %6s %s' % (
      '%04X-%04X' % block_range,
      '\'%s\'' % primary_script if primary_script else '------',
      block)


def main():
  DEFAULT_OUTFILE = 'noto_cmap_phase3_temp.xml'
  parser = argparse.ArgumentParser()
  parser.add_argument(
      '-o', '--outfile', help='name of cmap file to output ("%s" if name '
      'omitted)' % DEFAULT_OUTFILE, metavar='file', nargs='?', default=None,
      const=DEFAULT_OUTFILE)
  parser.add_argument(
      '-m', '--merge', help='merge excluded/fallback data from file',
      metavar='file')
  parser.add_argument(
      '-l', '--loglevel', help='log detail 0-2',
      metavar='level', nargs='?', type=int, const=1, default=0)
  parser.add_argument(
      '--regen', help='reformat script required data, no cmap generation',
      action='store_true')

  args = parser.parse_args()
  if args.regen:
    _regen_script_required()
    return

  script_to_chars = build_script_to_chars(args.loglevel)
  meta_params = []
  if args.merge:
    script_to_chars = _merge_fallback_chars(script_to_chars, args.merge)
    meta_params.append(('mergefile', args.merge))
  metadata = cmap_data.create_metadata('noto_cmap_reqs', meta_params)

  cmapdata = _get_cmap_data(script_to_chars, metadata)
  if args.outfile:
    cmap_data.write_cmap_data_file(cmapdata, args.outfile, pretty=True)
    print 'wrote %s' % args.outfile
  else:
    print cmap_data.write_cmap_data(cmapdata, pretty=True)


if __name__ == "__main__":
  main()
