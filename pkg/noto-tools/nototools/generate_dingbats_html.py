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

import argparse
import codecs
import collections
import re
import string
import sys

from fontTools import ttLib
from fontTools.pens.boundsPen import BoundsPen

from os import path

from nototools import cmap_data
from nototools import font_data
from nototools import tool_utils
from nototools import unicode_data

"""Generate html comparison of codepoints in various fonts."""

_HTML_HEADER_TEMPLATE = """<!DOCTYPE html>
<html lang='en'>
<head>
  <meta charset="utf-8">
  <title>$title</title>
  <style>
    $styles
  </style>
  <style>
    table { background-color: #eee; font-size: 20pt; text-align: center }
    tr.head { font-weight: bold; font-size: 12pt;
        border-style: solid; border-width: 1px; border-color: black;
        border-collapse: separate }
    td:nth-of-type(1), td:nth-last-of-type(3) { font-size: 12pt; text-align:left }
    $mstyles
    td:nth-last-of-type(1), td:nth-last-of-type(2) {
        font-size: 10pt; text-align:left; max-width: 20em }
    .key { background-color: white; font-size: 12pt; border-collapse: separate;
        margin-top: 0; border-spacing: 10px 0; text-align: left }
    .line { font-size: 20pt; word-break: break-all }
    h3 { -webkit-margin-before: 1.75em; -webkit-margin-after: .25em }
    .ctx { font-family: $contextfont }
  </style>
</head>
<body>
  <h3>$title</h3>
"""

_METRICS_STYLES = (
    ', '.join('td:nth-last-of-type(%d)' % i for i in range(4, 9)) +
    ' { font-size: 10pt; text-align:right; font-family: sansserif }')

# hardcoded for now, this assumes 'noto' is one of the defined font names
_CONTEXT_FONT = 'noto'

_HTML_FOOTER = """
</body>
</html>
"""

def _cleanlines(textfile):
  """Strip comments and blank lines from textfile, return list of lines."""
  result = []
  with open(textfile, 'r') as f:
    for line in f:
      ix = line.find('#')
      if ix >= 0:
        line = line[:ix]
      line = line.strip()
      if line:
        result.append(line)
  return result


class CodeList(object):
  """An ordered list of code points (ints).  These might map to other (PUA) code
  points that the font knows how to display."""

  @staticmethod
  def fromfile(filename):
    if filename.endswith('_codes.txt'):
      return CodeList.frompairfile(filename)
    elif filename.endswith('_cmap.txt'):
      return CodeList.fromrangefile(filename)
    elif filename.endswith('.ttf') or filename.endswith('.otf'):
      return CodeList.fromfontcmap(filename)
    else:
      raise Exception(
          'unrecognized file type %s for CodeList.fromfile' % filename)

  @staticmethod
  def fromspec(spec):
    codelist_type, text = [t.strip() for t in spec.split(':')]
    return CodeList.fromtext(text, codelist_type)

  @staticmethod
  def fromtext(text, codelist_type):
    if codelist_type == 'cmap':
      return CodeList.fromrangetext(text)
    elif codelist_type == 'codes':
      return CodeList.frompairtext(text)
    elif codelist_type == 'list':
      return CodeList.fromlisttext(text)
    else:
      raise Exception('unknown codelist type "%s"' % codelist_type)

  @staticmethod
  def fromfontcmap(fontname):
    font = ttLib.TTFont(fontname)
    return CodeList.fromset(font_data.get_cmap(font))

  @staticmethod
  def fromset(cpset):
    return UnicodeCodeList(cpset)

  @staticmethod
  def fromrangetext(cpranges):
    return CodeList.fromset(
        tool_utils.parse_int_ranges(cpranges, allow_compressed=True))

  @staticmethod
  def fromrangefile(cprange_file):
    with open(cprange_file, 'r') as f:
      return CodeList.fromrangetext(f.read())

  @staticmethod
  def fromlist(cplist):
    return OrderedCodeList(cplist)

  @staticmethod
  def fromlisttext(cplist):
    codes = tool_utils.parse_int_ranges(
        cplist, allow_duplicates=True, return_set=False, allow_compressed=True)
    return CodeList.fromlist(codes)

  @staticmethod
  def fromlistfile(cplist_file):
    return CodeList.fromlisttext(_cleanlines(cplist_file))

  @staticmethod
  def frompairs(cppairs):
    return MappedCodeList(cppairs)

  @staticmethod
  def frompairtext(cppairs_text):
    # if no pairs, will treat as listtext.  cppairs must have only one item
    # or pair per line, however.
    pair_list = None
    single_list = []
    for line in cppairs_text.splitlines():
      parts = [int(s, 16) for s in line.split(';')]
      if pair_list:
        if len(parts) < 2:
          parts.append(parts[0])
        pair_list.append(tuple(parts)[:2])
      elif len(parts) > 1:
        pair_list = [(cp, cp) for cp in single_list]
        pair_list.append(tuple(parts[:2]))
      else:
        single_list.append(parts[0])

    if pair_list:
      return CodeList.frompairs(pair_list)
    return CodeList.fromlist(single_list)

  @staticmethod
  def frompairfile(cppairs_file):
    return CodeList.frompairtext('\n'.join(_cleanlines(cppairs_file)))

  def contains(self, cp):
    """Returns True if cp is in the code list."""
    raise NotImplementedError

  def codes(self):
    """Returns the codes in preferred order."""
    raise NotImplementedError

  def codeset(self):
    """Returns the frozenset of codes."""
    raise NotImplementedError

  def mapped_code(self, cp):
    """Returns the mapped code for this code point."""
    raise NotImplementedError


class UnicodeCodeList(CodeList):
  """A codelist based on unicode code point order with no mapping."""
  def __init__(self, codeset):
    super(CodeList, self).__init__()
    self._codeset = frozenset(codeset)

  def contains(self, cp):
    return cp in self._codeset

  def codes(self):
    return sorted(self._codeset)

  def codeset(self):
    return self._codeset

  def mapped_code(self, cp):
    return cp if cp in self._codeset else None


class MappedCodeList(CodeList):
  def __init__ (self, codepairs):
    super(MappedCodeList, self).__init__()
    # hack, TODO: change the column order in the input files
    self._codemap = {v : k for k, v in codepairs}
    self._codes = tuple(p[1] for p in codepairs)

  def contains(self, cp):
    return cp in self._codemap

  def codes(self):
    return self._codes

  def codeset(self):
    return frozenset(self._codes)

  def mapped_code(self, cp):
    return self._codemap.get(cp)


class OrderedCodeList(CodeList):
  def __init__(self, codes):
    super(OrderedCodeList, self).__init__()
    self._codes = tuple(codes)
    self._codeset = frozenset(codes)

  def contains(self, cp):
    return cp in self._codeset

  def codes(self):
    return self._codes

  def codeset(self):
    return self._codeset

  def mapped_code(self, cp):
    return cp if cp in self._codeset else None


def _load_codelist(codelist_spec, data_dir, codelistfile_map):
  for codelist_type in ['file', 'cmap', 'codes', 'list', None]:
    if codelist_type and codelist_spec.startswith(codelist_type + ':'):
      codelist_spec = codelist_spec[len(codelist_type) + 1:].strip()
      break
  if not codelist_type:
    if codelist_spec.endswith('.txt'):
      codelist_type = 'file'
    else:
      raise Exception(
          'cannot determine type of codelist spec "%s"' % codelist_spec)
  if codelist_type != 'file':
    codelist = CodeList.fromtext(codelist_spec, codelist_type)
  else:
    fullpath = path.join(data_dir, codelist_spec)
    if not path.isfile(fullpath):
      raise Exception('codelist file "%s" not found' % codelist_spec)
    codelist = codelistfile_map.get(fullpath)
    if codelist == None:
      codelist = CodeList.fromfile(fullpath)
      codelistfile_map[codelist_spec] = codelist
  return codelist


class SequenceList(object):
  """A list of strings generated by a spec."""
  def __init__(self, codelists, suffix):
    self.codelists = codelists
    self.suffix = suffix

  def codes(self):
    codes = set()
    for codelist in self.codelists:
      codes |= codelist.codeset()
    codes |= set(ord(cp) for cp in self.suffix)
    return codes

  def __iter__(self):
    for codelist in self.codelists:
      chars = [unichr(cp) for cp in codelist.codes()]
      yield self.suffix.join(chars) + self.suffix


class Target(object):
  """A named collection of data that renders to html or text."""

  @staticmethod
  def from_table_data(name, codelist, used_fonts):
    return CodeTableTarget(name, codelist, used_fonts)

  @staticmethod
  def from_sequence_data(name, codelists, suffix, font):
    sequencelist = SequenceList(codelists, suffix)
    return SequenceListTarget(name, sequencelist, font)

  def __init__(self, name):
    self.name = name

  def name(self):
    return self.name

  def codes(self):
    """Returns the set of codepoints used in this target."""
    raise NotImplementedError

  def generate_text(self, metrics, flag_sets):
    raise NotImplementedError

  def generate_html(
      self, tindex, context, metrics, flag_sets, cp_to_targets):
    raise NotImplementedError


class SequenceListTarget(Target):
  def __init__(self, name, sequencelist, used_font):
    super(SequenceListTarget, self).__init__(name)
    self.sequencelist = sequencelist
    self.used_font = used_font

  def codes(self):
    return self.sequencelist.codes()

  def generate_text(self, metrics, flag_sets):
    raise NotImplementedError

  def generate_html(
      self, tindex, context, metrics, flag_sets, cp_to_targets):
    lines = ['<h3 id="target_%d">%s</h3>' % (tindex, self.name)]
    lines.append('<div class="%s line">' % self.used_font[0])
    for seq in self.sequencelist:
      lines.append(seq + '<br/>')
    lines.append('</div>')
    return '\n'.join(lines)


class CodeTableTarget(Target):
  def __init__(self, name, codelist, used_fonts):
    super(CodeTableTarget, self).__init__(name)
    self.codelist = codelist
    self.used_fonts = used_fonts

  def codes(self):
    return self.codelist.codes()

  def generate_text(self, metrics, flag_sets):
    lines = [self.name]
    header = ['idx  code']
    header.extend(f[0] for f in self.used_fonts)
    header.append('age name')
    lines.append(' '.join(header))
    for index, cp in enumerate(self.codelist.codes()):
      line = ['%3d' % index]
      line.append('%5s' % ('%04x' % cp))
      for rkey, keyinfos in self.used_fonts:
        match = any(codelist.contains(cp) for _, _, codelist in keyinfos)
        line.append(rkey if match else ('-' * len(rkey)))
      line.append(unicode_data.age(cp))
      line.append(_flagged_name(cp, flag_sets))
      lines.append(' '.join(line))
    return '\n'.join(lines)

  def generate_html(self, tindex, context, metrics, flag_sets, cp_to_targets):
    dump_metrics = False

    if dump_metrics:
      print '$ %s' % self.name

    def context_string(codelist, cp):
      cps = unichr(codelist.mapped_code(cp))
      return (context % cps) if context else cps

    def _target_line(cp, tindex, tinfo):
      info = []
      for ix, name in tinfo:
        if ix == tindex:
          continue
        info.append('<a href="#target_%d">%s</a>' % (ix, name))
      if not info:
        return '(no group)'
      return '; '.join(info)

    def _generate_header():
      header_parts = ['<tr class="head"><th>CP']
      for key, _ in self.used_fonts:
        header_parts.append('<th>' + key)
      if metrics != None:
        header_parts.append('<th>lsb<th>mid<th>rsb<th>wid<th>cy')
      header_parts.append('<th>Age<th>Name')
      return ''.join(header_parts)

    if metrics != None:
      # the metrics apply to the rightmost font
      fontname = self.used_fonts[-1][1][0][0]
      if fontname:
        metrics_font = _get_font(fontname)
      else:
        metrics_font = None
        print >> sys.stderr, 'no metrics font'

    lines = ['<h3 id="target_%d">%s</h3>' % (tindex, self.name)]
    char_line = _character_string_html(self.codelist, self.used_fonts[-1])
    if char_line:
      lines.append(char_line)
    lines.append('<table>')
    header = _generate_header()
    linecount = 0
    for cp in self.codelist.codes():
      if linecount % 20 == 0:
        lines.append(header)
      linecount += 1
      line = ['<tr>']
      line.append('<td>U+%04x' % cp)
      for rkey, keyinfos in self.used_fonts:
        cell_class = None
        cell_text = None
        index = 0
        for font, _, rcodelist in keyinfos:
          if rcodelist.contains(cp):
            if len(keyinfos) > 1:
              cell_class = '%s_%d' % (rkey, index)
            else:
              cell_class = rkey
            cell_class = replace_nonalpha(cell_class)
            if font:
              cell_text = context_string(rcodelist, cp)
            else:
              cell_text = ' * '
              cell_class += ' star'
            break
          index += 1
        if cell_class:
          line.append('<td class="%s">%s' % (cell_class, cell_text))
        else:
          line.append('<td>&nbsp;')
      name = _flagged_name(cp, flag_sets)
      if metrics != None:
        cp_metrics = _get_cp_metrics(metrics_font, cp) if metrics_font else None
        if cp_metrics:
          lsb, rsb, wid, adv, cy = cp_metrics
          if dump_metrics:
            print '%04x # %4d, %4d, %4d, %s' % (cp, lsb, adv, cy, name)

          if cp in metrics:
            nlsb, nadv, ncy = metrics[cp]
          else:
            nlsb, nadv, ncy = lsb, adv, cy
          nrsb = nadv - wid - nlsb

          line.append('<td>%d%s' % (
              lsb, '&rarr;<b>%d</b>' % nlsb if lsb != nlsb else ''))
          line.append('<td>%d' % wid)
          line.append('<td>%d%s' % (
              rsb, '&rarr;<b>%d</b>' % nrsb if rsb != nrsb else ''))
          line.append('<td>%d%s' % (
              adv, '&rarr;<b>%d</b>' % nadv if adv != nadv else ''))
          line.append('<td>%d%s' % (
              cy, '&rarr;<b>%d</b>' % ncy if cy != ncy else ''))
        else:
          line.append('<td><td><td><td><td>')
      line.append('<td>%s' % unicode_data.age(cp))
      line.append('<td>%s' % name)
      line.append('<td>%s' % _target_line(cp, tindex, cp_to_targets.get(cp)))
      lines.append(''.join(line))
    lines.append('</table>')
    return '\n'.join(lines)


def _load_fonts(data_list, data_dir, codelist_map):
  """data_list is a list of tuples of two to four items.  The first item is
  the key, the second is the name of the font file in data_dir.  The
  second can be None, otherwise it must exist.  The third item, if
  present, is the name to use for the font, otherwise it will be read
  from the font, it must be present where there is no font.  The
  fourth item, if present, is the name of a codelist file, it must be present
  where there is no font.  If present and None, the the unicode cmap from the
  font is used.  otherwise the font file name is stripped of its extension and
  try to find a file from which to create a codelist.
  Multiple tuples can share the same key, these form one column and the order
  of the files composing the tuple defines the order in which they are searched
  for a glyph.
  Returns a list of tuples of key, keyinfo, where keyinfo is
  a list of tuples of filepath, name, codelist."""

  def _load_font(data, codelist_map):
    if len(data) < 4:
      data = data + tuple([None] * (4 - len(data)))
    key, fname, name, codelistfile = data

    if not fname:
      if not name:
        raise Exception('must have name if no font provided')
      if not codelistfile:
        raise Exception('must have codelist file if no font provided')
      fontpath = None
    else:
      fontpath = path.join(data_dir, fname)
      if not path.isfile(fontpath):
        raise Exception('font "%s" not found' % fontpath)

    if codelistfile:
      codelist = _load_codelist(codelistfile, data_dir, codelist_map)

    if fname and (not codelistfile or not name):
      font = ttLib.TTFont(fontpath)
      if not name:
        names = font_data.get_name_records(font)
        name = names[16] if 16 in names else names[1] if 1 in names else None
        if not name:
          raise Exception('cannot read name from font "%s"' % fontpath)
      if not codelistfile:
        codelist = CodeList.fromset(font_data.get_cmap(font))

    return key, fontpath, name, codelist

  # group by key
  keyorder = []
  keyinfo = collections.defaultdict(list)
  for data in data_list:
    key, fontpath, name, codelist = _load_font(data, codelist_map)
    if key not in keyinfo:
      keyorder.append(key)
    keyinfo[key].append((fontpath, name, codelist))

  return [(key, keyinfo[key]) for key in keyorder]


def _select_used_fonts(codelist, fonts, prefer_fonts, omit_fonts):
  """Return the fonts we want to use to display the codelist, in order.
  If not None, prefer_fonts is a key or list of keys for fonts to order
  at the end.  If not None, omit_fonts is key or list of keys to omit
  even if they would otherwise be used by default, however prefer_fonts
  takes precedence over omit_fonts if the same key is in both."""

  if prefer_fonts is not None:
    if isinstance(prefer_fonts, basestring):
      prefer_fonts = [prefer_fonts]
    preferred = [None] * len(prefer_fonts)
  else:
    prefer_fonts = []
    preferred = []

  if omit_fonts is not None:
    if '_all_' in omit_fonts:
      omit_fonts = [k for k, _ in fonts]
    else:
      omit_fonts = [omit_fonts]
    if prefer_fonts:
      omit_fonts = [k for k in omit_fonts if k not in prefer_fonts]
  else:
    omit_fonts = []

  regular = []
  codes = codelist.codes()
  for f in fonts:
    key, keyinfo = f
    if key in omit_fonts:
      continue
    for name, _, cl in keyinfo:
      if any(cl.contains(cp) for cp in codes):
        is_preferred = False
        for i, k in enumerate(prefer_fonts):
          if key == k:
            preferred[i] = f
            is_preferred = True
            break
        if not is_preferred:
          regular.append(f)
        break
  return tuple(regular + filter(None, preferred))


def _load_targets(target_data, fonts, data_dir, codelist_map):
  """Target data is a list of tuples of target names, codelist files, an
  optional preferred font key or list of keys, and an optional omitted font
  key or list of keys. All files should be in data_dir.  Codelist_map is a
  cache in case the codelist file has already been read.  Returns a list of
  tuples of target name, codelist, and fontlist."""

  def _create_suffix(charlist):
    return charlist.decode('unicode-escape')

  def _select_font(fonts, font_id):
    for f in fonts:
      if f[0] == font_id:
        return f
    raise Exception('no font with id "%s"' % font_id)

  result = []
  for target in target_data:
    target_type, name, codelist_spec = target[:3]
    if target_type == 'table':
      codelist = _load_codelist(codelist_spec, data_dir, codelist_map)
      prefer_fonts = target[3] if len(target) > 3 else None
      omit_fonts = target[4] if len(target) > 4 else None
      used_fonts = _select_used_fonts(codelist, fonts, prefer_fonts, omit_fonts)
      if not used_fonts:
        raise Exception('no fonts used by target %s' % name)
      result.append(Target.from_table_data(name, codelist, used_fonts))
    elif target_type == 'sequence':
      if len(target) < 5:
        raise Exception('sequence target too short')
      lists = codelist_spec.split(',')
      codelists = [CodeList.fromlisttext(cl) for cl in lists]
      suffix = _create_suffix(target[3])
      font_tuple = _select_font(fonts, target[4])
      result.append(
          Target.from_sequence_data(name, codelists, suffix, font_tuple))
  return tuple(result)


def _create_codeset_from_expr(expr_list, flag_sets, data_dir, codelist_map):
  """Processes expr_list in order, building a codeset.
  See _read_flag_data_from_file for information on expr_list.
  This can modify flag_sets and codelist_map."""

  result = ()
  for op, exp in expr_list:
    if exp not in flag_sets:
      # its a codelist
      codes = _load_codelist(exp, data_dir, codelist_map).codeset()
    else:
      codes_or_spec = flag_sets[exp]
      if isinstance(codes_or_spec, (set, frozenset)):
        codes = codes_or_spec
      else:
        # replace the spec with the actual codes
        if codes_or_spec == None:
          # we only know about '_emoji_' and '_math_'
          if exp == '_emoji_':
            codes = (
                unicode_data.get_emoji() -
                unicode_data.get_unicode_emoji_variants('proposed_extra'))
          elif exp == '_math_':
            codes = unicode_data.chars_with_property('Math')
          else:
            raise Exception('unknown special codeset "%s"' % exp)
        else:
          codes = _load_codelist(
              codes_or_spec, data_dir, codelist_map).codeset()
        flag_sets[exp] = codes
    if op == '|':
      if not result:
        # it appers that python 'optimizes' |= by replacing the lhs by rhs if
        # lhs is an empty set, but this changes the type of lhs to frozenset...
        result = set(codes)
      else:
        result |= codes
    elif op == '&':
      result &= codes
    elif op == '-':
      result -= codes
    else:
      raise Exception('unknown op "%s"' % op)

  return result


def _load_flags(flag_data, data_dir, codelist_map):
  """Flag data is a list of tuples of defined sets or flags and expressions, see
  _read_flag_data_from_file for more info.
  This returns a map from set name to a tuple of (cp_set, bool) where True
  means the flag is set for a cp if it is in the cp_set, and false means the
  flag is set if the cp is not in the cp_set.

  This can fail since the code processing the flag_data does not actually try
  to load the codelists."""

  flag_sets = {}
  flag_map = {}
  for flag_info in flag_data:
    t0, t1, t2 = flag_info
    if t0 == '!define':
      set_name = t1
      if set_name in ['_emoji_', '_math_']:
        set_codes = None  # gets created by _create_codeset_from_expr
      else:
        set_codes = _load_codelist(t2, data_dir, codelist_map).codeset()
      flag_sets[set_name] = set_codes
    else:
      flag_name = t0
      flag_in = t1
      flag_set = _create_codeset_from_expr(
          t2, flag_sets, data_dir, codelist_map)
      flag_map[flag_name] = (flag_set, flag_in)
  return flag_map


def _load_fonts_targets_flags(font_data, target_data, flag_data, data_dir):
  # we cache the codelists to avoid building them twice if they're referenced by
  # both fonts and targets, not a big deal but...
  codelist_map = {}
  fonts = _load_fonts(font_data, data_dir, codelist_map)
  targets = _load_targets(target_data, fonts, data_dir, codelist_map)
  flags = _load_flags(flag_data, data_dir, codelist_map)
  return fonts, targets, flags


def strip_comments_from_file(filename):
  with open(filename, 'r') as f:
    for line in f:
      ix = line.find('#')
      if ix >= 0:
        line = line[:ix]
      line = line.strip()
      if not line:
        continue
      yield line


def _read_font_data_from_file(filename):
  font_data = []
  for line in strip_comments_from_file(filename):
    info = line.split(';')
    while len(info) < 4:
      info.append(None)
    font_data.append(tuple(info))
  return font_data


def _read_target_data_from_file(filename):
  """Target data uses # to indicate a comment to end of line.
  Comments are stripped, then an empty or blank line is ignored.

  Targets are either tables or sequences, the default
  is a table.

  Each line in a table target defines a tuple of four values:
  target name, codelist, preferred font ids, and omitted font
  ids.  Each line in a sequence target defines a tuple of
  four values: target name, codelist, suffix, and font id.
  A line can also start with one of tree directives,
  !define, !default, or !type.

  If a line starts with '!define ' we expect a key followed
  by '=' and then one or more names separated by space. The
  names are turned into a list, and entered into a dictionary
  for the key.  Once defined a key cannot be redefined.

  If a line starts with '!default ' we expect a key of either
  'prefer' or 'omit' optionally followed by '=' and a list of
  names to prefer or omit; these will become the default
  values until the next '!default ' directive.  If there is
  no '=' the value is reset.  An omitted or empty prefer or
  omit field will get the fallback, to explicitly request None
  and override the fallback the field should contain 'None'.

  If a line starts with '!type ' we expect either 'table' or
  'sequence' to follow.  This will become the type of the
  following lines until the next '!type ' directive.

  Normally, a line consists of 2-4 fields separated by ';'.
  The first two are a target name and a codelist spec.

  For table targets, the third is the preferred font ids
  separated by space, previously !defined keys can be used
  here instead of this list and the list defined for that key
  will be used.  The fourth is the omitted font ids separated
  by space, they are treated similarly.  If the preferred or
  omit field is missing or empty and a default value for it
  has been set, that value is used.

  For sequence targets, the third is a hex sequence indicating
  the suffix string to apply after each codepoint, and the
  fourth is the font id; these must both be present.

  This returns a list of the tuples of the type name followed
  by the data for that type.
  """

  def add_index_list_or_defined(info, index, fallback, defines):
    """Extend or update info[index], possibly using defines"""
    if len(info) <= index:
      info.append(fallback)
    elif info[index] != None:
      item = info[index]
      if item in defines:
        items = defines[item]
      elif item == 'None':
        items = None
      elif item:
        items = item.split()
      else:
        items = fallback
      info[index] = items

  prefer_fallback = None
  omit_fallback = None
  target_type = 'table'
  defines = {}
  target_data = []
  kDefineDirective = '!define '
  kDefaultDirective = '!default '
  kTypeDirective = '!type '

  for line in strip_comments_from_file(filename):
    if line.startswith(kDefineDirective):
      # !define key=val val...
      name, rest = line[len(kDefineDirective):].split('=')
      name = name.strip()
      if name in defines:
        raise Exception('name %s already defined in %s' % (name, filename))
      rest = rest.strip().split()
      defines[name] = tuple(rest)
      continue
    if line.startswith(kDefaultDirective):
      # !default prefer|omit=val val...
      values = line[len(kDefaultDirective):].split('=')
      name = values[0].strip()
      rest = values[1].strip().split() if len(values) > 1 else None
      if not rest:
        rest = None
      if name == 'prefer':
        prefer_fallback = rest
      elif name == 'omit':
        omit_fallback = rest
      else:
        raise Exception('default only understands \'prefer\' or \'omit\'')
      continue
    if line.startswith(kTypeDirective):
      # !type table|sequence
      value = line[len(kTypeDirective):]
      if value in {'table', 'sequence'}:
        target_type = value
      else:
        raise Exception('type only understands \'table\' or \'sequence\'')
      continue
    info = [k.strip() for k in line.split(';')]
    if len(info) < 2:
      raise Exception('need at least two fields in "%s"' % line)
    if target_type == 'table':
      # name;character spec or filename;prefer_id... or empty;omit_id... or empty
      add_index_list_or_defined(info, 2, prefer_fallback, defines)  # preferred
      add_index_list_or_defined(info, 3, omit_fallback, defines)  # omitted
      target_data.append(tuple(['table'] + info))
    elif target_type == 'sequence':
      if len(info) < 4:
        raise Exception('need four fields in sequence data in "%s"' % line)
      target_data.append(tuple(['sequence'] + info))

  return target_data


def _flagged_name(cp, flag_sets):
  """Prepend any flags to cp's unicode name, and return.  Flag_sets
  is a map from flag name to a tuple of cp set and boolean.
  True means add flag if cp in set, False means add flag if it is
  not in the set."""
  try:
    name = unicode_data.name(cp)
  except:
    raise Exception('no name for %04X' % cp)
  flags = []
  for k, v in sorted(flag_sets.iteritems()):
    if (cp in v[0]) == v[1]:
      flags.append(k)
  if flags:
    name = '(%s) %s' % (', '.join(flags),  name)
  return name


def generate_text(outfile, title, fonts, targets, flag_sets, metrics, data_dir):
  print >> outfile, title
  print >> outfile
  print >> outfile, 'Fonts:'
  max_keylen = max(len(key) for key, _ in fonts)
  fmt = '  %%%ds: %%s (%%s)' % max_keylen
  for key, keyinfos in fonts:
    for font, name, _ in keyinfos:
      rel_font = path.relpath(font, data_dir) if font else '(no font)'
      print >> outfile, fmt % (key, name, rel_font)
  print >> outfile

  for target in targets:
    print >> outfile
    print >> outfile, target.generate_text(flag_sets, metrics)


def _generate_fontkey(fonts, targets, data_dir):
  lines = ['<p style="margin-bottom:5px"><b>Targets</b>']
  lines.append('<div style="margin-left:20px"><table class="key">')
  for tid, target in enumerate(targets):
    lines.append(
        '<tr><th><a href="#target_%s">%s</a>' % (tid, target.name))
  lines.append('</table></div>')

  lines.append('<p style="margin-bottom:5px"><b>Fonts</b>')
  lines.append('<div style="margin-left:20px"><table class="key">')
  for key, keyinfos in fonts:
    for font, name, _ in keyinfos:
      rel_font = path.relpath(font, data_dir) if font else '(no font)'
      lines.append('<tr><th>%s<td>%s<td>%s' % (key, name, rel_font))
  lines.append('</table></div>')

  return '\n'.join(lines)


_nonalpha_re = re.compile(r'\W')
def replace_nonalpha(key):
  return _nonalpha_re.sub('_', key)


def _generate_styles(fonts, relpath):
  face_pat = """@font-face {
      font-family: "%s"; src:url("%s")
    }"""

  facelines = []
  classlines = []
  for key, keyinfos in fonts:
    index = 0
    for font, _, _ in keyinfos:
      if len(keyinfos) > 1:
        kname = '%s_%d' % (replace_nonalpha(key), index)
      else:
        kname = replace_nonalpha(key)
      index += 1
      if not font:
        classlines.append('.%s { font-size: 12pt }' % kname)
      else:
        if relpath is None:
          font = 'file://' + font
        else:
          font = path.join(relpath, path.basename(font))
        facelines.append(face_pat % (kname, font))
        classlines.append(
            '.%s { font-family: "%s", "noto_0" }' % (kname, kname))

  lines = []
  lines.extend(facelines)
  lines.append('')
  lines.extend(classlines)
  return '\n    '.join(lines)



def _character_string_html(codelist, used_font):
  C0_controls = frozenset(range(0, 0x20))
  rkey, rinfo = used_font
  _, _, f_codelist = rinfo[0]
  f_codeset = frozenset(f_codelist.codeset() - C0_controls)
  cps = [cp for cp in codelist.codes() if cp in f_codeset]
  if not cps:
    return None
  line = ['<bdo class="', rkey, ' line" dir="ltr">']
  line.extend(unichr(cp) for cp in cps)
  line.append('</bdo>')
  return ''.join(line)


_FONT_CACHE = {}
def _get_font(fontname):
  font = _FONT_CACHE.get(fontname)
  if not font:
    font = ttLib.TTFont(fontname)
    _FONT_CACHE[fontname] = font
  return font


GMetrics = collections.namedtuple('GMetrics', 'lsb, rsb, wid, adv, cy')


def _get_cp_metrics(font, cp):
    # returns metrics for nominal glyph for cp, or None if cp not in font
    cmap = font_data.get_cmap(font)
    if cp not in cmap:
      return None
    glyphs = font.getGlyphSet()
    g = glyphs[cmap[cp]]
    pen = BoundsPen(glyphs)
    g.draw(pen)
    if not pen.bounds:
      return None
    xmin, ymin, xmax, ymax = pen.bounds
    return GMetrics(
        xmin, g.width - xmax, xmax - xmin, g.width, (ymin + ymax) / 2)


_expr_re = re.compile(r'(\||&|(?<![0-9a-fA-F])-(?![0-9a-fA-F]))')

def _scan_expr(expr, def_names, used_names):
  """Scans the expression, building a list of operation tuples."""
  result = []
  op_str = '|'
  while expr:
    op = op_str
    m = _expr_re.search(expr)
    if not m:
      exp = expr.strip()
      expr = None
      op_str = None
    else:
      exp = expr[:m.start()].strip()
      expr = expr[m.end():]
      op_str = m.group(1)
    if not exp:
      raise Exception('empty expression after op %s' % op)
    result.append((op, exp))
    if exp in def_names:
      used_names.add(exp)
  return result


def _read_flag_data_from_file(filename):
  """Read flag data file and generate a list of tuples for creating
  the flag data map.  If filename is None, returns an empty list.

  Lines in the file either define a set used by a flag, or define
  a flag.  Define lines start with '!define ' followed by the name
  of the set (_0-9A-Za-z), '=', and the definition (a codelist).

  Definition lines have three fields separated by semicolon,
  the name of the flag, 'in' or 'not in', and the definition
  which can either be a codelist or an expression formed from
  names of !defined sets joined with '&' (intersection), '|'
  (union), or '-' (set difference).  These operations are performed
  in order left to right, there's no predecence.

  Predefined sets are '_emoji_', the unicode extended emoji values,
  and '_math_', codepoints with the 'Math' property.

  '#' is a comment to end-of line.  Blank lines are ignored.

  It's an error if there are multiple defined sets
  with the same name or multiple flags with the same name.

  This returns a list of 3-tuples, one for each set used by a
  flag, then one for each flag.  Tuple for defined sets are
    ('!define', set_name, set_spec),
  there set_spec is None if the set_name is special, like '_emoji_'.
  Tuples for flags are
    (flag_name, True/False, [(op,expr)]),
  where the list of op, expr tuples has the op character
  ('|' '&', '-') and a define name or a codelist."""

  if not filename:
    return []

  predefined = ['_emoji_', '_math_']

  def_names = set(predefined)

  def_re = re.compile(r'!define ([a-zA-Z][a-zA-Z0-9_]*)\s*=\s*(.*)\s*')
  flag_re = re.compile(r'([^;]+);\s*(in|not in)\s*;\s*(.*)\s*')

  def_info = [('!define', item, None) for item in predefined]
  flag_info = []
  with open(filename, 'r') as f:
    for line in f.readlines():
      ix = line.find('#')
      if ix > -1:
        line = line[:ix]
      line = line.strip()
      if not line:
        continue
      if line.startswith('!'):
        m = def_re.match(line)
        if not m:
          raise Exception('could not match definition line "%s"' % line)
        def_name = m.group(1)
        def_codelist = m.group(2)
        if def_name in def_names:
          raise Exception('more than one flag definition named "%s"' % def_name)
        def_names.add(def_name)
        def_info.append(('!define', def_name, def_codelist))
      else:
        m = flag_re.match(line)
        if not m:
          raise Exception('could not match set definition line "%s"' % line)
        flag_name = m.group(1)
        flag_in_str = m.group(2)
        if flag_in_str == 'in':
          flag_in = True
        elif flag_in_str == 'not in':
          flag_in = False
        else:
          raise Exceeption(
              'found "%s" but expected \'in\' or \'not in\'' % flag_in_str)
        flag_expr = m.group(3)
        flag_info.append([flag_name, flag_in, flag_expr])

  used_names = set()
  flag_expr_info = []
  for flag_name, flag_in, flag_expr in flag_info:
    expr_list = _scan_expr(flag_expr, def_names, used_names)
    flag_expr_info.append((flag_name, flag_in, expr_list))
  used_defs = [t for t in def_info if t[1] in used_names]
  return used_defs + flag_expr_info

"""
def _generate_html_lines(outfile, fontkey):
  ascii_chars = u'#*0123456789 '
  epact_chars = u''.join(unichr(cp) for cp in range(0x102e1, 0x102fb + 1)) + ' '
  phaistos_chars = u''.join(unichr(cp) for cp in range(0x101d0, 0x101fc + 1)) + ' '
  stringlist = [
     ascii_chars,
     u''.join(u'%s\u20e3' % c for c in ascii_chars),
     epact_chars,
     u''.join(u'%s\U000102e0' % c for c in epact_chars),
     phaistos_chars,
     u''.join(u'%s\U000101fd' % c for c in phaistos_chars),
  ]

  lines = ['<h3>Sequences</h3>']
  lines.append('<div class="%s line">' % fontkey)
  for string in stringlist:
    lines.append(string + '<br/>')
  lines.append('</div>')

  print >> outfile, '\n'.join(lines)
"""

def generate_html(
    outfile, title, fonts, targets, flag_sets, context, metrics,
    cp_to_targets, data_dir, relpath):
  """If not None, relpath is the relative path from the outfile to
  the datadir, for use when generating font paths."""

  template = string.Template(_HTML_HEADER_TEMPLATE)
  styles = _generate_styles(fonts, relpath)
  mstyles = _METRICS_STYLES if metrics != None else ''
  contextfont = _CONTEXT_FONT if context else 'sansserif'
  print >> outfile, template.substitute(
      title=title, styles=styles, mstyles=mstyles, contextfont=contextfont)

  print >> outfile, _generate_fontkey(fonts, targets, data_dir)

  # hardcode font key for now
  # _generate_html_lines(outfile, 'sym4')

  for index, target in enumerate(targets):
    print >> outfile, target.generate_html(
        index, context, metrics, flag_sets, cp_to_targets)

  print >> outfile, _HTML_FOOTER


def _build_cp_to_targets(targets):
  """Return a map from cp to a list of pairs of target group index and
  name."""
  cp_to_targets = collections.defaultdict(list)
  #  for i, (name, codelist, _) in enumerate(targets):
  for i, target in enumerate(targets):
    tinfo = (i, target.name)
    for cp in target.codes():
      cp_to_targets[cp].append(tinfo)
  return cp_to_targets


def generate(
    outfile, fmt, data_dir, font_spec, target_spec, flag_spec, title=None,
    context=None, metrics=False, relpath=None):
  if not path.isdir(data_dir):
    raise Exception('data dir "%s" does not exist' % data_dir)

  font_data = _read_font_data_from_file(path.join(data_dir, font_spec))
  target_data = _read_target_data_from_file(
      path.join(data_dir, target_spec))
  flag_data = _read_flag_data_from_file(
      None if not flag_spec else path.join(data_dir, flag_spec))
  fonts, targets, flag_sets = _load_fonts_targets_flags(
      font_data, target_data, flag_data, data_dir)

  if fmt == 'txt':
    generate_text(outfile, title, fonts, targets, flag_sets, metrics, data_dir)
  elif fmt == 'html':
    cp_to_targets = _build_cp_to_targets(targets)
    generate_html(
        outfile, title, fonts, targets, flag_sets, context, metrics,
        cp_to_targets, data_dir, relpath)
  else:
    raise Exception('unrecognized format "%s"' % fmt)


def _parse_metrics_file(filename):
  """format is 'cp;lsb;adv' with cp in hex."""
  metrics = {}
  with open(filename, 'r') as f:
    for line in f:
      ix = line.find('#')
      if ix >= 0:
        line = line[:ix]
      line = line.strip()
      if not line:
        continue
      cp, lsb, adv, cy = line.split(';')
      cp = int(cp, 16)
      lsb = int(lsb)
      adv = int(adv)
      cy = int(cy)
      if cp in metrics:
        raise Exception('cp %04x listed twice in %s' % (cp, filename))
      metrics[cp] = (lsb, adv, cy)
  return metrics


def _call_generate(
    outfile, fmt, data_dir, font_spec, target_spec, flag_spec, title=None,
    context=None, metrics=None):
  data_dir = path.realpath(path.abspath(data_dir))
  if metrics != None:
    if metrics == '-':
      metrics = {}
    else:
      metrics = _parse_metrics_file(path.join(data_dir, metrics))
  if outfile:
    outfile = path.realpath(path.abspath(outfile))
    base, ext = path.splitext(outfile)
    if ext:
      ext = ext[1:]
    if not ext:
      if not fmt:
        fmt = 'txt'
        ext = 'txt'
      else:
        ext = fmt
    elif not fmt:
      if ext not in ['html', 'txt']:
        raise Exception('don\'t understand "%s" format' % ext)
      fmt = ext
    elif ext != fmt:
      raise Exception('mismatching format "%s" and output extension "%s"' % (
          fmt, ext))
    outfile = base + '.' + ext
    outdir = path.dirname(outfile)
    if data_dir == outdir:
      relpath = ''
    elif data_dir.startswith(outdir):
      relpath = data_dir[len(outdir) + 1:]
    else:
      relpath = None
    with codecs.open(outfile, 'w', 'utf-8') as f:
      generate(
          f, fmt, data_dir, font_spec, target_spec, flag_spec, title, context,
          metrics, relpath)
  else:
    if not fmt:
      fmt = 'txt'
    generate(
        sys.stdout, fmt, data_dir, font_spec, target_spec, flag_spec, title,
        context, metrics)


def main():
  DEFAULT_OUT = 'dingbats_compare'

  parser = argparse.ArgumentParser()
  parser.add_argument(
      '-o', '--outfile', help='Path to output file (will use %s)' % DEFAULT_OUT,
      const=DEFAULT_OUT, metavar='file', nargs='?')
  parser.add_argument(
      '-t', '--output_type', help='output format (defaults based on outfile '
      'extension, else "txt")', choices=['txt', 'html'])
  parser.add_argument(
      '-d', '--data_dir', help='Path to directory containing fonts '
      'and data', metavar='dir', required=True)
  parser.add_argument(
      '--font_spec', help='Name of font spec file relative to data dir '
      '(default \'font_data.txt\')', metavar='file', default='font_data.txt')
  parser.add_argument(
      '--target_spec', help='Name of target spec file relative to data dir '
      '(default \'target_data.txt\')', metavar='file',
      default='target_data.txt')
  parser.add_argument(
      '--flag_spec', help='Name of flag spec file relative to data dir '
      '(uses \'flag_data.txt\' with no arg)', metavar='file', nargs='?',
      const = 'flag_data.txt')
  parser.add_argument(
      '--title', help='Title on html page', metavar='title',
      default='Character and Font Comparison')
  parser.add_argument(
      '--context', help='Context pattern for glyphs (e.g. \'O%%sg\')',
      metavar='ctx', nargs='?',
      const='<span class="ctx">O</span>%s<span class="ctx">g</span>')
  parser.add_argument(
      '-m', '--metrics', help='Report metrics of target font, optionally '
      'with preferred metrics file', metavar='file', nargs='?', const='-')
  args = parser.parse_args()

  _call_generate(
      args.outfile, args.output_type, args.data_dir, args.font_spec,
      args.target_spec, args.flag_spec, args.title, args.context,
      args.metrics)

if __name__ == '__main__':
  main()
