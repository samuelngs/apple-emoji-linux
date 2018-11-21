# Copyright 2016 Google Inc. All Rights Reserved.
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


"""Provides GposDiffFinder, which finds differences in ttxn feature output.

GposDiffFinder takes in two paths, to font binaries from which ttxn output is
made. It provides methods that compare the OpenType feature contents of these
files: `find_kerning_diffs`, `find_mark_class_diffs`, and
`find_positioning_diffs`.

Unlike ShapeDiffFinder, the methods don't have a `stats` argument and can't
accumulate a report between method calls (yet?). They simply report the
differences via a returned string.
"""


from collections import defaultdict
import re
import subprocess
import tempfile


class GposDiffFinder:
    """Provides methods to report diffs in GPOS content between ttxn outputs."""

    def __init__(self, file_a, file_b, error_bound, output_lines=6):
        ttxn_file_a = tempfile.NamedTemporaryFile()
        ttxn_file_b = tempfile.NamedTemporaryFile()
        subprocess.call(['ttxn', '-q', '-t', 'GPOS', '-o', ttxn_file_a.name,
                                                     '-f', file_a])
        subprocess.call(['ttxn', '-q', '-t', 'GPOS', '-o', ttxn_file_b.name,
                                                     '-f', file_b])
        self.text_a = ttxn_file_a.read()
        self.text_b = ttxn_file_b.read()
        self.err = error_bound
        self.out_lines = output_lines

    def find_kerning_diffs(self):
        """Report differences in kerning rules."""

        classes_a, classes_b = {}, {}
        rx = re.compile(r'(@[\w\d_.]+) = \[([\s\w\d_.]+)\];')
        self._parse_kerning_classes(rx, self.text_a, classes_a)
        self._parse_kerning_classes(rx, self.text_b, classes_b)

        unmatched = defaultdict(list)
        mismatched = defaultdict(list)
        rx = re.compile('pos \[?([\w\d@_.]+)\]? \[?([\w\d@_.]+)\]? (-?\d+);')
        self._parse_kerning(rx, '-', self.text_a, classes_a, unmatched)
        self._parse_kerning(rx, '+', self.text_b, classes_b, unmatched)
        self._organize_kerning_diffs(unmatched, mismatched)

        unmatched = [(k, v) for k, v in unmatched.iteritems() if v]
        res = ['%d differences in kerning pairs' % len(unmatched)]
        # (('+', 'a', 'b'), [-20, 10])
        # Sort order:
        # 1. Reverse absolute value of kerning
        # 2. Left-side glyph name
        # 3. Right-side glyph name
        unmatched.sort(key=lambda t:(-max(abs(v) for v in t[1]),
                                     t[0][1],
                                     t[0][2]))
        for (sign, left, right), vals in unmatched[:self.out_lines]:
            res.append('%s pos %s %s %s' % (sign, left, right, vals))
        res.append('')

        mismatched = [(k, v) for k, v in mismatched.iteritems() if any(v)]
        res.append('%d differences in kerning values' % len(mismatched))
        # (('V', 'A'), ([-4], [-17]))
        # Sort order:
        # 1. Reverse absolute difference between before and after kern values
        # 2. Left-side glyph name
        # 3. Right-side glyph name
        mismatched.sort(key=lambda t:(-sum(abs(v1-v2) for v1, v2 in
                                                        zip(t[1][0], t[1][1])),
                                      t[0][0],
                                      t[0][1]))
        for (left, right), (vals1, vals2) in mismatched[:self.out_lines]:
            if sum(abs(v1 - v2) for v1, v2 in zip(vals1, vals2)) > self.err:
                res.append('pos %s %s: %s vs %s' % (left, right, vals1, vals2))
        res.append('')
        return '\n'.join(res)

    def find_mark_class_diffs(self):
        """Report differences in mark class definitions."""

        unmatched = {}
        mismatched = {}
        rx = re.compile('mark \[([\w\d\s@_.]+)\] <anchor (-?\d+) (-?\d+)> '
                        '(@[\w\d_.]+);')
        self._parse_anchor_info(rx, '-', self.text_a, unmatched, mismatched)
        self._parse_anchor_info(rx, '+', self.text_b, unmatched, mismatched)

        res = ['%d differences in mark class definitions' % len(unmatched)]
        unmatched = unmatched.items()
        # (('+', 'uni0325', '@uni0323_6'), (0, -30))
        # Sort order:
        # 1. Glyph class
        # 2. Mark class
        unmatched.sort(key=lambda t: (t[0][1], t[0][2]))
        for (sign, member, mark_class), (x, y) in unmatched[:self.out_lines]:
            res.append('%s mark [%s] <anchor %d %d> %s;' %
                       (sign, member, x, y, mark_class))
        res.append('')

        res.append('%d differences in mark class values' % len(mismatched))
        mismatched = mismatched.items()
        # (('uni0300', '@uni0300_23'), ((0, 527), (300, 527)))
        # Sort order:
        # 1. Reverse absolute difference between position before and after
        # 2. Glyph class
        # 3. Mark class
        mismatched.sort(key=lambda t:(-(abs(t[1][0][0] - t[1][1][0])
                                      + abs(t[1][0][1] - t[1][1][1])),
                                      t[0][0],
                                      t[0][1]))
        for (member, cls), ((x1, y1), (x2, y2)) in mismatched[:self.out_lines]:
            if abs(x1 - x2) > self.err or abs(y1 - y2) > self.err:
                res.append('%s %s <%d %d> vs <%d %d>' %
                           (member, cls, x1, y1, x2, y2))
        res.append('')
        return '\n'.join(res)

    def find_positioning_diffs(self, mark_type='base'):
        """Report differences in positioning rules."""

        unmatched = {}
        mismatched = {}
        rx = re.compile('pos %s \[([\w\d\s@_.]+)\]\s+<anchor (-?\d+) (-?\d+)> '
                        'mark (@[\w\d_.]+);' % mark_type)
        self._parse_anchor_info(rx, '-', self.text_a, unmatched, mismatched)
        self._parse_anchor_info(rx, '+', self.text_b, unmatched, mismatched)

        res = ['%d differences in mark-to-%s positioning rule coverage' %
               (len(unmatched), mark_type)]
        unmatched = unmatched.items()
        # Sort order: same as 'mark class definitions'
        unmatched.sort(key=lambda t: (t[0][1], t[0][2]))
        for (sign, member, mark_class), (x, y) in unmatched[:self.out_lines]:
            res.append('%s pos %s [%s] <anchor %d %d> mark %s;' %
                       (sign, mark_type, member, x, y, mark_class))
        res.append('')

        res.append('%d differences in mark-to-%s positioning rule values' %
                   (len(mismatched), mark_type))
        mismatched = mismatched.items()
        # Sort order: same as 'mark class values'
        mismatched.sort(key=lambda t:(-(abs(t[1][0][0] - t[1][1][0])
                                      + abs(t[1][0][1] - t[1][1][1])),
                                      t[0][0],
                                      t[0][1]))
        for (member, cls), ((x1, y1), (x2, y2)) in mismatched[:self.out_lines]:
            if abs(x1 - x2) > self.err or abs(y1 - y2) > self.err:
                res.append('%s %s <%d %d> vs <%d %d>' %
                           (member, cls, x1, y1, x2, y2))
        res.append('')
        return '\n'.join(res)

    def _parse_kerning_classes(self, rx, text, classes):
        """Parse kerning class definitions."""

        for definition in rx.findall(text):
            name, members = definition
            classes[name] = members.split()

    def _parse_kerning(self, rx, sign, text, classes, unmatched):
        """Parse kerning rules."""

        for rule in rx.findall(text):
            left, right, val = rule
            val = int(val)
            if left in classes:
                left = classes[left]
            else:
                left = [left]
            if right in classes:
                right = classes[right]
            else:
                right = [right]

            for left_glyph in left:
                for right_glyph in right:
                    key = sign, left_glyph, right_glyph
                    key_match = (self._reverse_sign(sign), left_glyph,
                                 right_glyph)
                    if val in unmatched[key_match]:
                        unmatched[key_match].remove(val)
                    else:
                        unmatched[key].append(val)

    def _organize_kerning_diffs(self, unmatched, mismatched):
        """Move mismatched kerning rules into a separate dictionary."""

        keys = unmatched.keys()
        for key in keys:
            if key not in unmatched:  # already matched and removed
                continue
            sign, left, right = key
            key_match = self._reverse_sign(sign), left, right
            if (key_match in unmatched and
                unmatched[key] and unmatched[key_match]):
                if sign == '+':
                    key, key_match = key_match, key
                mismatched[left, right] = (
                    unmatched.pop(key), unmatched.pop(key_match))

    def _parse_anchor_info(self, rx, sign, text, unmatched, mismatched):
        """Parse unmatched and mismatched mark classes."""

        for members, x, y, mark_class in rx.findall(text):
            # hack to get around unexpected class naming differences (ttxn bug?)
            mark_class = '_'.join(mark_class.split('_', 2)[:2])
            for member in members.split():
                val = int(x), int(y)
                key_match = self._reverse_sign(sign), member, mark_class
                if key_match in unmatched:
                    if unmatched[key_match] != val:
                        mismatched[member, mark_class] = (
                            unmatched[key_match], val)
                    del unmatched[key_match]
                else:
                    unmatched[sign, member, mark_class] = val

    def _reverse_sign(self, sign):
        """Return the reverse of a sign contained in a string."""

        if sign == '-':
            return '+'
        elif sign == '+':
            return '-'
        else:
            raise ValueError('Bad sign "%s".' % sign)
