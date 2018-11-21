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
import re

"""Generate samples from a description file."""

USAGE = """
'python generate_samples.py [options] description_file [output_file]'

This uses a description file containing character patterns to generate text
samples, writing them to output_file if it is provided and to the console if
not.

The description file is encoded in UTF-8, and contains two kinds of
definitions, groups and patterns.  Groups name lists of text sequences,
patterns name sequences of groups.  Group are specified first, then
patterns.

'#' is a comment character, anything after '#' on a line is ignored.

Names of groups and patterns use upper and lower case A-Z, digits, and
underscore.

Group names are followed by an equals sign and then a list of one or more
character sequences or ranges separated by comma (spaces around commas are
ignored).  In addition to the actual characters, unicode code point values
can be specified as hex escapes in either upper or lower case: use '\\x' for
two digits, '\\u' for four digits, and '\\U' for six digits.  For example,
'\\u200d' can be used to represent zero width joiner.  A backslash before a
comma, a space, pound sign ('#'), a hyphen (ASCII '-'), or another backslash
represents a comma, space, pound sign, hyphen, or backslash (unicode values
can also be used) and prevents the character from being interpreted in its
usual fashion.  Any other character following a backslash is rejected.
Out-of-range unicode values are also rejected. Ranges include all defined
characters between and including the one to the left and right of the hyphen.

Pattern names are followed by colon and then a list of one or more group
names enclosed in angle brackets, optionally separated by whitespace.  A
sequence from each group in the pattern is selected, and the sequences are
concatenated together.  Groups can also be enclosed in parentheses to
form virtual groups that are a union of all the sequences of the enclosed
groups.

For example:
-----
# comments are ignored
# groups
abc = a, b, c
d2f = d-\\x66
xy = x, y
ZWJ = \\u200d

# patterns
xy_zwj_xy: <xy><ZWJ><xy>
xy_abcxy: <xy>(<abc><xy>)
xy_d2f: <xy><d2f>
-----

By default samples are generated in order, one per line, ordered by the
sequence of patterns in the description file, groups within a pattern, and
sequences within an group.
"""

###
# options:
#
# --patterns <list of one or more pattern names, concatenated with comma>
#   only generate text using the named patterns
#
# --group
#   generate all output for a single pattern on one line, separated by sep
#
# --sep
#   define the separator to use when grouping, defaults to tab
#
# --sort
#   sorts within a group by unicode code point order instead of the order in
#   which the sequences in the group were defined.
#
# --label
#   write a line containing the name of the pattern before the samples that
#   each pattern generates, and separate each such group of samples with a
#   blank line.


# Some unicode utilities for working with python2 narrow builds.
# The python2 docs are abysmal in this respect, they tell you nothing
# about working with non-bmp unicode on narrow builds.

# constants
_LEAD_OFFSET = 0xD800 - (0x10000 >> 10);
_SURROGATE_OFFSET = 0x10000 - (0xD800 << 10) - 0xDC00;

def cp_to_str(cp):
  if cp < 0x10000:
    return unichr(cp)
  return unicode(r'\U%08X' % cp, encoding='unicode_escape')


def surrogate_pair_to_cp(low, high):
  # assumes low and high are proper surrogate values
  return (low << 10) + high + _SURROGATE_OFFSET;


def prev_cp(ustr, index):
  if index < 0:
    index += len(ustr)
  if index == 0:
    return None
  cp = ord(ustr[index - 1])
  if cp >= 0xdc00 and cp <= 0xe000 and index > 1:  # high surrogate
    pcp = ord(ustr[index - 2])
    if pcp >= 0xd800 and pcp < 0xdc00:  # low surrogate
      return index - 2, surrogate_pair_to_cp(pcp, cp)
  return index - 1, cp


def next_cp(ustr, index):
  limit = len(ustr)
  if index < 0:
    index += limit
  if index >= limit:
    return None
  cp = ord(ustr[index])
  if cp >= 0xd800 and cp < 0xdc00 and index < limit - 1:  # low surrogate
    ncp = ord(ustr[index + 1])
    if ncp >= 0xdc00 and ncp < 0xe000:  # high surrogate
      return index + 2, surrogate_pair_to_cp(cp, ncp)
  return index + 1, cp

### generator class

class SampleGen(object):
  def __init__(self, patterns, pattern_order):
    self.patterns = patterns
    self.pattern_order = pattern_order

  def generate(self, out_file, select_patterns, group, sep, label, sort):
    if not select_patterns:
      select_patterns = self.pattern_order
    else:
      ok_patterns = []
      for pattern in select_patterns:
        if pattern not in self.patterns:
          print 'No pattern named \'%s\' in %s' % (
              pattern, ', '.join(self.pattern_order))
          continue
        ok_patterns.append(pattern)
      select_patterns = ok_patterns

    output_lines = []
    for pattern in select_patterns:
      self._generate_output(output_lines, pattern, group, sep, label, sort)
    if not label:
      # force trailing newline, if we label we already have one
      output_lines.append('')
    output_text = '\n'.join(output_lines)

    if out_file:
      with codecs.open(out_file, 'w', 'utf-8') as f:
        f.write(output_text)
    else:
      print output_text


  def _generate_output(self, output_lines, pattern, group, sep, label, sort):
    pat_list = self.patterns[pattern]
    if label:
      output_lines.append(pattern)
    pat_output = []
    self._gen_results(pat_list, sort, '', pat_output)
    if group:
      output_lines.append(sep.join(pat_output))
    else:
      output_lines.extend(pat_output)
    if label:
      output_lines.append('')

  def _gen_results(self, pat_list, sort, prefix, samples):
    if not pat_list:
      samples.append(prefix)
      return
    items = self._get_items(pat_list[0], sort)
    for item in items:
      self._gen_results(pat_list[1:], sort, prefix + item, samples)


  def _get_items(self, group, sort):
    if type(group) == tuple:
      items = []
      for subgroup in group:
        for item in self._get_items(subgroup, False):
          # ensure no duplicates result from union of groups
          if item not in items:
            items.append(item)
    else:
      items = group
    return sorted(items) if sort else items


# parser utilities

def _strip_comments(definition_lines):
  """Not as straightforward as usual, because comments can be escaped
  by backslash, and backslash can escape space."""
  out_lines = []
  for line in definition_lines:
    pos = 0
    while True:
      x = line.find('#', pos)
      if x <= 0:
        if x == 0:
          line = ''
        break

      is_escaped = False
      if line[x - 1] == '\\':
        # see how many there are
        y = x - 2
        while y >= pos and line[y] == '\\':
          y -= 1
        is_escaped = (x - y) % 2 == 0

      if is_escaped:
        pos = x + 1
      else:
        line = line[:x]
        break
    out_lines.append(line)
  return out_lines


_ESCAPES = [
    # Must do backslash substitutions first.
    # (also note raw strings cannot end in a backslash).
    ('\\\\', r'\x5c'),
    (r'\ ', r'\x20'),
    (r'\#', r'\x23'),
    (r'\,', r'\x2c'),
    (r'\-', r'\x2d'),
    ]

def _canonicalize_escapes(definition_lines):
  """Replace each escape of a reserved character with a unicode escape."""
  out_lines = []
  for line in definition_lines:
    if '\\' in line:
      for old, new in _ESCAPES:
        line = line.replace(old, new)
    out_lines.append(line)
  return out_lines

_UNICODE_ESCAPE_RE = re.compile(r'\\([Uux])([0-9a-fA-F]{2,6})')
def _unescape(arg):
  # we only allow 6 hex digits after \U, 8 is too many, legacy cruft.
  def sub(esc_match):
    esc_type = esc_match.group(1)
    esc_val = esc_match.group(2)
    if esc_type == 'x':
      esc_len = 2
    elif esc_type == 'u':
      esc_len = 4
    elif esc_type == 'U':
      esc_len = 6
    else:
      raise ValueError('internal error')

    if len(esc_val) < esc_len:
      error = 'Unicode escape too short: "%s"' % (
          esc_match.group(0))
      raise ValueError(error)
    unival = int(esc_val[:esc_len], 16)
    if unival > 0x10ffff:
      error = 'Unicode escape value too large: "%X"' % unival
      raise ValueError(error)
    if unival < 0x10000:
      prefix = unichr(unival)
    else:
      prefix = unicode(
          '\\U%08X' % unival, encoding='unicode_escape', errors='strict')
    return prefix + esc_val[esc_len:]

  return _UNICODE_ESCAPE_RE.sub(sub, arg)


def _convert_to_segments(arg):
  """Return a list of strings and/or range tuples."""

  # First we split on hyphen
  chunks = arg.split('-')
  # If you want a literal hyphen, escape it.
  # A hyphen with no value before or after (including two
  # hyphens in succession) is an error.
  for part in chunks:
    if not part:
      raise ValueError('bad range in "%s"' % arg)

  # Once we've done this, we can replace unicode escapes
  # (otherwise one might expand to hyphen).
  chunks = [_unescape(arg) for arg in chunks]

  # if no hyphen, we just have the string, so return it
  if len(chunks) == 1:
    return chunks

  result = []
  prev = chunks[0]
  for i in range(1, len(chunks)):
    index, pcp = prev_cp(prev, len(prev))
    if index != 0:
      result.append(prev[:index])
    next = chunks[i]
    index, ncp = next_cp(next, 0)
    if ncp <= pcp:
      raise ValueError('illegal range from %0x to %0x in "%s"' % (
          pcp, ncp, arg))
    result.append((pcp, ncp))
    prev = next[index:]
  if prev:
    result.append(prev)
  return result


def _segments_to_strings(segments, prefix, result):
  """Recursive utility function to expand segments into a list of strings."""
  if len(segments) == 0:
    result.append(prefix)
    return
  segment = segments[0]
  segments = segments[1:]
  if type(segment) == tuple:
    for cp in range(segment[0], segment[1] + 1):
      _segments_to_strings(segments, prefix + cp_to_str(cp), result)
  else:
    _segments_to_strings(segments, prefix + segment, result)


def _expand_ranges(arg):
  """Return a list of args, expanding ranges in arg if present."""
  segments = _convert_to_segments(arg)
  result = []
  _segments_to_strings(segments, '', result)
  return result


def _parse_group(value):
  args = []
  try:
    for arg in value.split(','):
      for expanded_arg in _expand_ranges(arg.strip()):
        if expanded_arg in args:
          print 'The sequence "%s" is already in this group, ignoring it' % (
              'U+%04X' % cp for cp in expanded_arg)
          continue
        args.append(expanded_arg)
  except ValueError as e:
    print str(e)
    return None

  if not args[-1]:
    # special case trailing comma, ignore args after it
    args = args[:-1]
  return args


def _check_balanced_parens(text):
  count = 0
  for i in range(len(text)):
    if text[i] == '(':
      count += 1
    elif text[i] == ')':
      count -= 1
      if count < 0:
        print 'Unmatched close paren.'
        return None
  if count > 0:
    print 'Unmatched open paren.'
    return None
  return text


def _find_matching_close_paren(text, pos):
  count = 0
  for i in range(pos, len(text)):
    if text[i] == '(':
      count += 1
    elif text[i] == ')':
      count -= 1
      if count == 0:
        return i
  return -1


_PAT_RE = re.compile(r'\s*(?:<([a-zA-Z0-9_]+)>|\()')
def _parse_pattern(value, groups):
  """Return a list of lists (groups) or tuples of lists
  (parenthesized groups)."""
  pat_list = []
  while value:
    m = _PAT_RE.match(value)
    if not m:
      return None
    name = m.group(1)
    if name:
      # angle brackets
      if name not in groups:
        print 'Could not find "%s" in groups (%s)' % (
            name, ', '.join(sorted(groups)))
        return None
      pat_list.append(groups[name])
      value = value[m.end():].strip()
    else:
      # open paren
      y = _find_matching_close_paren(value, 0)
      if y < 0:
        raise ValueError("internal error")
      pat = _parse_pattern(value[1 : y], groups)
      if not pat:
        return None
      pat_list.append(tuple(pat))
      value = value[y + 1:].strip()
  return pat_list


_LINE_RE = re.compile(r'^\s*([a-zA-Z0-9_]+)\s*([:=])\s*(.*)$')
def parse_sample_gen(definition):
  original_lines = definition.splitlines()
  definition_lines = _strip_comments(original_lines)
  definition_lines = _canonicalize_escapes(definition_lines)

  groups = {}
  patterns = {}
  pattern_order = []

  for n in range(len(definition_lines)):
    line = definition_lines[n]
    if not line:
      continue
    m = _LINE_RE.match(line)
    if not m:
      print 'Could not parse "%s"' % original_lines[n]
      return None
    name = m.group(1)
    is_group = m.group(2) == '='
    value = m.group(3)
    if is_group:
      value = _parse_group(value)
    else:
      if not _check_balanced_parens(value):
        return None
      value = _parse_pattern(value, groups)
    if not value:
      print 'Could not parse values in "%s"' % original_lines[n]
      return None
    if is_group:
      if name in groups:
        print 'The group "%s" has already been defined' % name
        return None
      groups[name] = value
    else:
      if name in patterns:
        print 'The pattern "%s" has already been defined' % name
        return None
      pattern_order.append(name)
      patterns[name] = value

  return SampleGen(patterns, pattern_order)


def generate_samples(
    defs_file, out_file, patterns=None, group=False, sep='\t',
    label=False, sort=False):

  with codecs.open(defs_file, 'r', 'utf-8') as f:
    sample_gen = parse_sample_gen(f.read())
  if sample_gen:
    sample_gen.generate(out_file, patterns, group, sep, label, sort)


def main():
    parser = argparse.ArgumentParser(
        epilog=USAGE, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        '-p', '--patterns', help='only output the named patterns, to name '
        'more than one, join them with comma', metavar='pat')
    parser.add_argument(
        '-g', '--group', help='group output from a pattern on a single line',
        action='store_true')
    parser.add_argument(
        '-s', '--sep', help='separator to use when grouping, default tab',
        metavar='sep', default='\t')
    parser.add_argument(
        '--sort', help='sort sequences within a group by unicode code point',
        action='store_true')
    parser.add_argument(
        '-l', '--label', help='include the name of a pattern before the '
        'samples it generates, separate groups with blank lines',
        action='store_true')
    parser.add_argument(
        'defs', help='the name of the definitions file',
        metavar='definition_file')
    parser.add_argument(
        'out', help='the name of the output file',
        metavar='output_file', nargs='?')
    args = parser.parse_args()

    generate_samples(
        args.defs, args.out, patterns=args.patterns, group=args.group,
        sep=args.sep, label=args.label, sort=args.sort)

if __name__ == '__main__':
    main()
