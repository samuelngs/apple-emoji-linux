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


import tempfile
import unittest

from nototools.gpos_diff import GposDiffFinder
from hb_input_test import make_font


class GposDiffFinderText(unittest.TestCase):
    def _expect_kerning_diffs(self, source_a, source_b, pairs, values):
        font_a = make_font('feature kern {\n%s\n} kern;' % source_a)
        font_b = make_font('feature kern {\n%s\n} kern;' % source_b)
        file_a = tempfile.NamedTemporaryFile()
        file_b = tempfile.NamedTemporaryFile()
        font_a.save(file_a.name)
        font_b.save(file_b.name)
        finder = GposDiffFinder(file_a.name, file_b.name, 0, 100)

        diffs = finder.find_kerning_diffs()
        self.assertIn('%d differences in kerning pairs' % len(pairs), diffs)
        for pair_diff in pairs:
            self.assertIn('%s pos %s %s %s' % pair_diff, diffs)
        self.assertIn('%d differences in kerning values' % len(values), diffs)
        for value_diff in values:
            self.assertIn('pos %s %s: %s vs %s' % value_diff, diffs)

    def test_simple(self):
        self._expect_kerning_diffs('''
                pos a b -10;
                pos a c -20;
            ''', '''
                pos a b -30;
                pos a d -40;
            ''',
            [('-', 'a', 'c', [-20]), ('+', 'a', 'd', [-40])],
            [('a', 'b', [-10], [-30])])

    def test_multiple_rules(self):
        self._expect_kerning_diffs('''
                @a_b = [a b];
                pos a d -10;
                pos @a_b d -20;
            ''', '''
                pos a d -30;
            ''',
            [('-', 'b', 'd', [-20])],
            [('a', 'd', [-10, -20], [-30])])

    def test_single_vs_class(self):
        self._expect_kerning_diffs('''
                pos a d -10;
            ''', '''
                @a_b = [a b];
                pos @a_b d -20;
            ''',
            [('+', 'b', 'd', [-20])],
            [('a', 'd', [-10], [-20])])


if __name__ == '__main__':
    unittest.main()
