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


"""Provides GsubDiffFinder, which finds differences in GSUB tables.

GsubDiffFinder takes in two paths, to font binaries from which ttxn output is
made. It provides `find_gsub_diffs` which compares the OpenType substitution
rules in these files, reporting the differences via a returned string.
"""


import re
import subprocess
import tempfile


class GsubDiffFinder(object):
    """Provides methods to report diffs in GSUB content between ttxn outputs."""

    def __init__(self, file_a, file_b, output_lines=20):
        ttxn_file_a = tempfile.NamedTemporaryFile()
        ttxn_file_b = tempfile.NamedTemporaryFile()
        subprocess.call(['ttxn', '-q', '-t', 'GSUB', '-o', ttxn_file_a.name,
                                                     '-f', file_a])
        subprocess.call(['ttxn', '-q', '-t', 'GSUB', '-o', ttxn_file_b.name,
                                                     '-f', file_b])
        self.text_a = ttxn_file_a.read()
        self.text_b = ttxn_file_b.read()
        self.file_a = file_a
        self.file_b = file_b
        self.output_lines = output_lines

    def find_gsub_diffs(self):
        """Report differences in substitution rules."""

        rules_a = self._get_gsub_rules(self.text_a, self.file_a)
        rules_b = self._get_gsub_rules(self.text_b, self.file_b)

        diffs = []
        report = ['']  # first line replaced by difference count
        for rule in rules_a:
            if rule not in rules_b:
                diffs.append(('-',) + rule)
        for rule in rules_b:
            if rule not in rules_a:
                diffs.append(('+',) + rule)
        # ('+', 'smcp', 'Q', 'Q.sc')
        # Sort order:
        # 1. Feature tag
        # 2. Glyph name before substitution
        # 3. Glyph name after substitution
        diffs.sort(key=lambda t:(t[1], t[2], t[3]))
        report = ['%d differences in GSUB rules' % len(diffs)]
        report.extend(' '.join(diff) for diff in diffs)
        return '\n'.join(report[:self.output_lines + 1])

    def _get_gsub_rules(self, text, filename):
        """Get substitution rules in this ttxn output."""

        feature_name_rx = r'feature (\w+) {'
        contents_rx = r'feature %s {(.*?)} %s;'
        rule_rx = r'sub ([\w.]+) by ([\w.]+);'

        rules = set()
        for name in re.findall(feature_name_rx, text):
            contents = re.findall(contents_rx % (name, name), text, re.S)
            assert len(contents) == 1, 'Multiple %s features in %s' % (
                name, filename)
            contents = contents[0]
            for lhs, rhs in re.findall(rule_rx, contents):
                rules.add((name, lhs, rhs))
        return rules
