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

"""Custom configuration of lint for font instances."""

# The structure is a list of conditions and tests.  A condition says when to apply
# the following test.  These are processed in order and are cumulative, and
# where there is a conflict the last instructions win.

# Both conditions and tests can vary in specifity, a condition can for example simply
# indicate all fonts by a vendor, or indicate a particuar version of a particular font.

# At the end of the day, we have a particular font, and want to know which tests to
# run and which failures to ignore or report.  lint_config builds up a structure from
# a customization file that allows this api.

import argparse
import re


spec_format = """
A spec defines a list of conditions to be run in sequence.  A condition consists of
a filter, which determines whether a font matches the condition, and a list of tests, which
determines what tests to run on that font and what exceptions to make.  By default
all tests are run on all fonts.

Conditions are created by a list of filter and test instructions.  A new condition is
started either by the term 'condition' or by adding a filter after one or more tests
have been defined, there is an initial open condition at the start that accepts all
fonts.  Filters on the same property do not accumulate, instead the previous filter
for that property is replaced.  Similarly, tests on the same tag do not accumulate.

'#' starts a comment to the next '\\n'
'\\n' and ';' separate <instruction>

instruction:
  'condition' -- starts a new condition
  'filename | name | script | variant | weight | hinted | vendor | verson' <filter> -- adds a filter
  'enable | disable' <test_list> -- adds tests

filter:
  '*' -- reset filter
  <numeric_filter> <number>
  <string_filter> <string_value>
  'in' <string_list>
  <string> -- string equality test

numeric_filter:
  '< | <= | == | != | >= | >' -- compare decimal values

string_filter:
  'is' -- string equality
  'like' -- value is a regex, true if it matches target anywhere

string_list: -- one or more strings separated by comma
  <string>+

test_list: -- one or more tests separated by comma
  <test>+

test:
  <test_tag> | <test_tag> <relation> <value_type> <value_list>

test_tag: -- name of a test node (see tags)

relation:
  'except | only' -- whether to include or exclude values matched by the selector

value_type:
  'cp | gid' -- type of select values the tag takes, cp values are hex, gid are decimal

value_list: -- numbers or ranges separated by whitespace, no space around hyphen
  (<number> | <number>'-'<number>)+
"""

def parse_int_ranges(range_string, is_hex=True, sep=' '):
  """Returns a set of ints from a string of numbers or ranges separated by sep.
  A range is two values separated by hyphen with no intervening separator.
  Result can be empty if range_string is empty."""
  result = set()
  count = 0
  base = 16 if is_hex else 10
  range_string = range_string.strip()
  if not range_string:
    return set()
  value_list = range_string.split(sep)
  for val in value_list:
    if '-' in val: # assume range
      val_list = val.split('-')
      if len(val_list) != 2:
        raise ValueError('could not parse range from \'%s\'' % val)
      lo = int(val_list[0], base)
      hi = int(val_list[1], base)
      if lo >= hi:
        raise ValueError('val range must have high > low')
      result.update(range(lo, hi + 1))
      count += hi - lo + 1
    else:
      result.add(int(val, base))
      count += 1
  if len(result) != count:
    raise ValueError('duplicate values in %s, expected count is %d but result is %s' % (
        hexlist, count, result))
  return result


def write_int_ranges(int_values, in_hex=True, sep=' '):
  """From a set or list of ints, generate a string representation that can
  be parsed by parse_int_ranges to return the original values (not order_preserving)."""

  if not int_values:
    return ''

  num_list = []

  if type(int_values) is not list:
    int_values = [v for v in int_values]
  int_values.sort()
  start = prev = int_values[0]
  single_fmt = '%04x' if in_hex else '%d'
  pair_fmt = single_fmt + '-' + single_fmt

  def emit():
    if prev == start:
      num_list.append(single_fmt % prev)
    else:
      num_list.append(pair_fmt % (start, prev))

  for v in int_values[1:]:
    if v == prev + 1:
      prev += 1
      continue
    else:
      emit()
    start = prev = v
  emit()
  return sep.join(num_list)


class IntSetFilter(object):
  """Tests whether an int (glyph or code point) is in a set."""

  def __init__(self, accept_if_in, intset):
    self.accept_if_in = accept_if_in
    self.intset = intset
    # print 'IntSetFilter %s %s' % ('only' if accept_if_in else 'except', intset)

  def accept(self, cp):
    return self.accept_if_in == (cp in self.intset)


class FontInfo(object):
  def __init__(self, filename, name, style, script, variant, weight, monospace,
               hinted, vendor, version):
    self.filename = filename
    self.name = name
    self.style = style
    self.script = script
    self.variant = variant
    self.weight = weight
    self.monospace = monospace
    self.hinted = hinted
    self.vendor = vendor
    self.version = version

  def __repr__(self):
    return str(self.__dict__)


class FontCondition(object):

  def _init_fn_map():
    def test_lt(lhs, rhs):
      return float(lhs) < float(rhs)
    def test_le(lhs, rhs):
      return float(lhs) <= float(rhs)
    def test_eq(lhs, rhs):
      return float(lhs) == float(rhs)
    def test_ne(lhs, rhs):
      return float(lhs) != float(rhs)
    def test_ge(lhs, rhs):
      return float(lhs) >= float(rhs)
    def test_gt(lhs, rhs):
      return float(lhs) > float(rhs)
    def test_is(lhs, rhs):
      return lhs == rhs
    def test_in(lhs, rhs):
      return lhs in rhs
    def test_like(lhs, rhs):
      return rhs.search(lhs) != None
    def test_is_not(lhs, rhs):
      return lhs != rhs
    def test_not_in(lhs, rhs):
      return lhs not in rhs
    def test_not_like(lhs, rhs):
      return rhs.search(lhs) == None

    return {
      '<': test_lt,
      '<=': test_le,
      '==': test_eq,
      '!=': test_ne,
      '>=': test_ge,
      '>': test_gt,
      'is': test_is,
      'in': test_in,
      'like': test_like,
      'is not': test_is_not,
      'not in': test_not_in,
      'not like': test_not_like,
      }

  fn_map = _init_fn_map()


  def __init__(self, filename=None, name=None, style=None, script=None, variant=None, weight=None,
               hinted=None, vendor=None, version=None):
    """Each arg is either a string, or a pair of a fn of two args returning bool, and an object.
    When the arg is a pair, the target string is passed to the fn as the first arg and the
    second element of the pair is passed as the second arg."""

    self.filename = filename
    self.name = name
    self.style = style
    self.script = script
    self.variant = variant
    self.weight = weight
    self.hinted = hinted
    self.vendor = vendor
    self.version = version

  def modify(self, condition_name, fn_name, value):
    if not condition_name in self.__dict__:
      raise ValueError('FontCondition does not recognize: %s' % condition_name)

    if fn_name == '*':
      # no condition
      self.__dict__[condition_name] = None
      return

    if not value:
      # fn_name is value
      self.__dict__[condition_name] = fn_name
      return

    fn = self.fn_map[fn_name]
    if fn_name == 'in':
      value = set(value.split(','))
    elif fn_name == 'like':
      value = re.compile(value)
    self.__dict__[condition_name] = (fn, value)

  line_re = re.compile(r'([^ \t]+)\s+(is not|not like|not in|[^ \t]+)(.*)')
  def modify_line(self, line):
    line = line.strip()
    m = self.line_re.match(line)
    if not m:
      raise ValueError("FontCondition could not match '%s'" % line)
    condition_name = m.group(1)
    fn_name = m.group(2)
    value = m.group(3)
    if value:
      value = value.strip()
      if not value:
        value = None
    self.modify(condition_name, fn_name, value)

  def copy(self):
    return FontCondition(
        filename=self.filename, name=self.name, style=self.style, script=self.script,
        variant=self.variant, weight=self.weight, hinted=self.hinted, vendor=self.vendor,
        version=self.version)

  def accepts(self, fontinfo):
    for k in ['filename', 'name', 'style', 'script', 'variant', 'weight', 'hinted', 'vendor',
              'version']:
      test = getattr(self, k, None)
      if test:
        val = getattr(fontinfo, k, None)
        if isinstance(test, basestring):
          if test != val:
            return False
          continue
        if not test[0](val, test[1]):
          return False

    return True

  def __repr__(self):
    def value_str(value):
      if isinstance(value, basestring):
        cond_name = 'is'
        cond_value = value
      else:
        fn = value[0]
        val = value[1]
        cond_name = None
        for fn_text, fn_obj in FontCondition.fn_map.iteritems():
          if fn == fn_obj:
            cond_name = fn_text
            break
        if cond_name == 'like':
          cond_value = val.pattern
        else:
          if not cond_name:
            cond_name = str(fn)
          cond_value = str(val)
      return '%s %s' % (cond_name, cond_value)

    output = ['\n  %s: %s' % (k,value_str(v)) for k,v in self.__dict__.iteritems() if v]
    return 'condition:%s' % ''.join(output)


class TestSpec(object):
  data = """
  filename -- filename tests
    script
    name
  name -- name table tests
    unable_to_check
    copyright
    family
    subfamily
    unique_id
    full_name
    version
      match_head
      out_of_range
    postscript_name
    trademark
    manufacturer
    designer
    description
    vendor_url
    designer_url
    license
    license_url
    preferred_family
    preferred_subfamily
    wws_family
    wws_subfamily
    unused -- checks for unused entries in name table
  cmap -- cmap table tests
    tables
      missing
      unexpected
      format_12_has_bmp
      format_4_subset_of_12
      notaliased
    required
    script_required except|only cp
    private_use except|only cp
    non_characters
    disallowed_ascii
    variants
    unexpected
  head -- head table tests
    hhea
      ascent
      descent
      linegap
    vhea
      linegap
    os2
      fstype
      ascender
      descender
      linegap
      winascent
      windescent
      achvendid
      weight_class
      fsselection
      unicoderange
      panose
        family
        serif
        proportion
  bounds -- glyf limits etc
    glyph
      ui_ymax except|only gid
      ui_ymin except|only gid
      ymax except|only gid
      ymin except|only gid
    font
      ui_ymax
      ui_ymin
      ymax
      ymin
  paths -- outline tests
    extrema -- missing on-curve extrema
    intersection -- self-intersecting paths
  gdef -- gdef tests
    classdef
      not_present -- table is missing but there are mark glyphs
      unlisted except|only cp -- mark glyph is present and expected to be listed
      combining_mismatch except|only cp -- mark glyph is combining but not listed as combining
      not_combining_mismatch except|only cp -- mark glyph is not combining but listed as combining
    attachlist
      duplicates
      out_of_order
    ligcaretlist
      not_present -- table is missing but there are ligatures
      not_ligature -- listed but not a ligature
      unlisted -- is a ligature but no caret
  complex -- gpos and gsub tests
    gpos
      missing
      ui_name_id -- FeatureParamsStylisticSet.UINameID not in name table
    gsub
      missing
      ui_name_id -- FeatureParamsStylisticSet.UINameID not in name table
      variants -- expect standard variants to be supported in gsub
  bidi -- tests bidi pairs, properties
    rtlm_non_mirrored -- rtlm GSUB feature applied to private-use or non-mirrored character
    ompl_rtlm -- rtlm GSUB feature applied to ompl char
    ompl_missing_pair -- ompl sibling not in cmap
    rtlm_unlisted -- non-ompl bidi char does not have rtlm GSUB feature
  hints
    unexpected_tables -- unhinted fonts shouldn't have hint tables
    missing_bytecode except|only gid -- hinted tt fonts should have bytecodes
    unexpected_bytecode -- unhinted tt fonts should not have bytecodes
  advances
    digits -- checks that ASCII digits have same advance as digit zero
    comma_period -- checks that comma and period have same advance
    whitespace -- checks for expected advance relationships in whitespace
    spacing_marks -- checks that particular spacing marks have non-zero advances
  stem -- stem widths
    left_joining -- non-zero lsb
    right_joining -- rsb not -70
  reachable except|only gid
  """

  # fields are:
  # 0: zero or more spaces
  # 1: tag, lower case alphanumeric plus underscore
  # 2: optional relation regex, delimited by whitespace'
  # 3: optional (with relation) value type regex, delimited by whitespace'
  # 4: optional '--' followed by comment to end of line
  def _process_data(data):
    """data is a hierarchy of tags. any level down to root can be enabled or disabled.  this
    builds a representation of the tag hierarchy from the text description."""
    _data_line_re = re.compile(r'(\s*)([a-z0-9_]+)(?:\s+([^\s]+)\s+([^\s]+))?\s*(?:--\s*(.+)\s*)?$')
    tag_data = {}
    indent = (0, '', None)
    for line in data.splitlines():
      if not line.strip():
        continue
      m = _data_line_re.match(line)
      if not m:
        raise ValueError('failed to match line: \'%s\'' % line)
      line_indent = m.group(1)
      tag_part = m.group(2)
      relation = m.group(3)
      arg_type = m.group(4)
      comment = m.group(5)

      while line_indent <= indent[0]:
        if indent[2]:
          indent = indent[2]
        else:
          break
      tag = indent[1]
      if tag:
        tag += '/' + tag_part
      else:
        tag = tag_part
      tag_data[tag] = (relation, arg_type, comment)
      if line_indent > indent[0]:
        indent = (line_indent, tag, indent)
    return tag_data

  tag_data = _process_data(data)
  tag_set = frozenset(tag_data.keys())

  def __init__(self):
    self.touched_tags = set()
    self.enabled_tags = set()
    self.tag_options = {}

  def _get_single_tag(self, tag):
    """Resolve tag to a single node"""
    if not tag in self.tag_set:
      unique_tag = None
      # try to find a unique tag with this as a segment
      for t in TestSpec.tag_set:
        ix = t.find(tag)
        if ix != -1:
          if ix > 0 and t[ix-1] not in '/_':
            continue
          ix += len(tag)
          if ix < len(t) and t[ix] not in '/_':
            continue
          if unique_tag:
            raise ValueError('multiple matches for partial tag %s' % tag)
          unique_tag = t
      if not unique_tag:
        raise ValueError('unknown tag: %s' % tag)
      tag = unique_tag
    return tag

  def _get_tag_set(self, tag):
    """Resolve tag to a single node, and return it and all of its descendants."""
    if tag == '*':
      return TestSpec.tag_set
    tag = self._get_single_tag(tag)
    result = set()
    for candidate in self.tag_set:
      if candidate.startswith(tag):
        result.add(candidate)
    return result

  def _get_ancestor_tag_set(self, tag):
    """Resolve tag to a single node, and return all of its ancestors."""
    result = set()
    if tag != '*':
      tag = self._get_single_tag(tag)
      while tag:
        ix = tag.rfind('/')
        if ix == -1:
          break
        tag = tag[:ix]
        result.add(tag)
    return result

  def _set_enable_options(self, tag, relation, arg_type, arg):
    allowed_options = TestSpec.tag_data[tag]
    if not allowed_options[0]:
      raise ValueError('tag \'%s\' does not allow options' % tag)
    if not re.match(allowed_options[0], relation):
      raise ValueError('tag \'%s\' does not allow relation \'%s\'' % (tag, relation))
    if not re.match(allowed_options[1], arg_type):
      raise ValueError('tag \'%s\' and relation \'%s\' does not allow arg type %s' % (
          tag, relation, arg_type))

    if arg_type == 'cp' or arg_type == 'gid':
      is_hex = arg_type == 'cp'
      int_set = parse_int_ranges(arg, is_hex)
      self.tag_options[tag] = (arg_type, IntSetFilter(relation != 'except', int_set))
    else:
      raise ValueError('illegal state - unrecognized arg_type \'%s\'' % arg_type)

  def enable(self, tag, relation=None, arg_type=None, arg=None):
    tags = self._get_tag_set(tag)
    if relation != None:
      if len(tags) > 1:
        raise ValueError('options cannot be applied to multiple tags')
      tag = next(iter(tags))
      self._set_enable_options(tag, relation, arg_type, arg)
    self.touched_tags |= tags
    tags |= self._get_ancestor_tag_set(tag)
    self.enabled_tags |= tags

  tag_rx = re.compile(r'\s*([0-9a-z/_]+)(?:\s+(except|only)\s+(cp|gid)\s+(.*))?\s*$')
  def enable_tag(self, tag_seg):
    m = self.tag_rx.match(tag_seg)
    if not m:
      raise ValueError('TestSpec could not parse:\n  "%s"\n'
                       'expecting:\n  "<tag_name> except|only cp|gid <value>+"'% tag_seg)
    self.enable(m.group(1), relation=m.group(2), arg_type=m.group(3), arg=m.group(4))

  def disable(self, tag):
    tags = self._get_tag_set(tag)
    self.touched_tags |= tags
    self.enabled_tags -= tags

  def apply_spec(self, result, options):
    result -= self.touched_tags
    result |= self.enabled_tags
    for tag in self.touched_tags:
      options.pop(tag, None)
    for tag in self.enabled_tags:
      if tag in self.tag_options:
        options[tag] = self.tag_options[tag]


  # TODO(dougfelt): remove modify_line if no longer used
  line_rx = re.compile(r'\s*(enable|disable)\s+([0-9a-z/]+)(?:\s+(except|only)\s+(cp|gid)\s+(.*))?\s*')
  def modify_line(self, line):
    m = self.line_rx.match(line)
    if not m:
      raise ValueError('TestSpec could not parse ' + line)
    if m.group(1) == 'enable':
      self.enable(m.group(2), m.group(3), m.group(4), m.group(5))
    else:
      self.disable(m.group(2))

  def copy(self):
    result = TestSpec()
    result.touched_tags |= self.touched_tags
    result.enabled_tags |= self.enabled_tags
    return result

  def __repr__(self):
    enable_list = []
    disable_list = []
    for tag in self.touched_tags:
      if tag in self.enabled_tags:
        enable_list.append(tag)
      else:
        disable_list.append(tag)
    output = []
    if enable_list:
      output.append('enable:')
      output.extend('  %s' % item for item in sorted(enable_list))
    if disable_list:
      output.append('disable:')
      output.extend('  %s' % item for item in sorted(disable_list))
    return '\n'.join(output)


class LintTests(object):
  def __init__(self, tag_set, tag_filters):
    self.tag_set = tag_set
    self.tag_filters = tag_filters
    self.run_log = set()
    self.skip_log = set()

  def get_filter(self, tag):
    if tag not in TestSpec.tag_set:
      raise ValueError('unrecognized tag ' + tag)
    return self.tag_filters.get(tag, None)

  def check(self, tag):
    if tag not in TestSpec.tag_set:
      raise ValueError('unrecognized tag ' + tag)
    run = tag in self.tag_set
    if run:
      self.run_log.add(tag)
    else:
      self.skip_log.add(tag)
    return run

  def valuetype(self, tag):
    """If the tag filters values, return the type of the value ('gid' or 'cp')
    being filtered, or None."""
    if tag in self.tag_filters:
      return self.tag_filters[tag][0]
    return None

  def checkvalue(self, tag, value):
    run = self.check(tag)
    if run and tag in self.tag_filters:
      run = self.tag_filters[tag][1].accept(value)
    return run

  def runlog(self):
    return self.run_log

  def skiplog(self):
    return self.skip_log

  def __repr__(self):
    lines = []
    if not (self.run_log or self.skip_log):
      for tag in sorted(self.tag_set):
        tag_filter = self.tag_filters.get(tag, None)
        if tag_filter:
          lines.append('%s %s' % (tag, tag_filter))
        else:
          lines.append(tag)
    if self.run_log:
      lines.add('run:')
      lines.append('  ' + t for t in self.run_log)
    if self.skip_log:
      lines.add('skipped:')
      lines.append('  ' + t for t in self.skip_log)
    return '\n'.join(lines)


class LintSpec(object):

  def __init__(self):
    self.specs = []

  def add_spec(self, font_condition, test_spec):
    self.specs.append((font_condition, test_spec))

  def get_tests(self, font_info):
    result = set()
    options = {}
    result |= TestSpec.tag_set
    for condition, spec in self.specs:
      if condition.accepts(font_info):
        spec.apply_spec(result, options)

    return LintTests(frozenset(result), options)

  def __repr__(self):
    return '--- spec ---\n' + '\n--- spec ---\n'.join('%s\n%s' % spec for spec in self.specs)


def parse_spec(spec, lint_spec=None):
  if not lint_spec:
    lint_spec = LintSpec()
  if not spec:
    return lint_spec

  cur_condition = FontCondition()
  cur_test_spec = TestSpec()
  have_test = False
  for line in spec.splitlines():
    ix = line.find('#')
    if ix > -1:
      line = line[:ix]
    line = line.strip()
    if not line:
      continue
    for segment in line.split(';'):
      segment = segment.strip()
      if segment == 'condition':
        if have_test:
          lint_spec.add_spec(cur_condition.copy(), cur_test_spec)
          cur_test_spec = TestSpec()
          have_test = False
        cur_condition = FontCondition()
      elif segment.startswith('enable '):
        segment = segment[len('enable '):]
        for seg in segment.split(','):
          cur_test_spec.enable_tag(seg.strip())
        have_test = True
      elif segment.startswith('disable '):
        segment = segment[len('disable '):]
        for seg in segment.split(','):
          cur_test_spec.disable(seg.strip())
        have_test = True
      else:
        if have_test:
          lint_spec.add_spec(cur_condition.copy(), cur_test_spec)
          cur_test_spec = TestSpec()
          have_test = False
        cur_condition.modify_line(segment)
  if have_test:
    lint_spec.add_spec(cur_condition, cur_test_spec)

  return lint_spec


def parse_spec_file(filename):
  with open(filename) as f:
    return parse_spec(f.read())


def main():
  parser = argparse.ArgumentParser()
  parser.add_argument('--tags', help='list all tags supported by the parser', action='store_true')
  parser.add_argument('--comments', help='list tags with comments when present', action='store_true')
  parser.add_argument('--filters', help='list tags with filters when present', action='store_true')
  parser.add_argument('--spec', help='prints the syntax', action='store_true')
  parser.add_argument('--parsefile', help='prints the parsed spec', metavar='spec')
  args = parser.parse_args()

  if not (args.tags or args.comments or args.filters or args.spec or args.parsefile):
    print 'nothing to do.'
    return

  if args.spec:
    print spec_format
    return

  for tag in sorted(TestSpec.tag_set):
    data = TestSpec.tag_data[tag]
    comment = args.comments and data[2]
    if args.filters and (data[0] or data[1]):
      filter = ' '.join(data[:2])
    else:
      filter = None
    show_tag = args.tags or comment or filter
    if show_tag:
      print tag
      if filter:
        print '  ' + filter
      if comment:
        print '  -- ' + comment

  if args.parsefile:
    print parse_spec_file(args.parsefile)


if __name__ == '__main__':
    main()
