# Copyright 2017 Google Inc. All Rights Reserved.
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
import os.path
import unittest
import tempfile
import hashlib

from fontTools.ttLib import TTFont
import nototools.substitute_linemetrics

class LineMetricsTest(unittest.TestCase):
    def setUp(self):
        current_dir = os.path.abspath(os.path.dirname(
            os.path.realpath(__file__)))
        data_dir = os.path.join(current_dir, 'data')
        self.fontfile1 = data_dir + '/font1.ttf'
        self.fontfile2 = data_dir + '/font2.ttf'
        self.output_file = tempfile.gettempdir() + '/' + 'output.ttf'
        if os.path.isfile(self.output_file):
            os.remove(self.output_file)

    def test_basic(self):
        self.assertFalse(os.path.isfile(self.output_file))
        nototools.substitute_linemetrics.main([self.fontfile1, self.fontfile2, '-o',
            self.output_file])
        self.assertTrue(os.path.isfile(self.output_file))

        font1 = TTFont(self.fontfile1)
        font2 = TTFont(self.fontfile2)
        output = TTFont(self.output_file)

        assert dump_linemetrics(font1) != dump_linemetrics(font2),\
            'linemetrics for the two test fonts should be different.'

        self.assertEqual(dump_linemetrics(font2), dump_linemetrics(output))

        # checks other data in output should be the same as that in font1
        self.assertEqual(len(font1.__dict__), len(output.__dict__))
        cmap1 = font1['cmap']
        cmapo = output['cmap']
        self.assertEqual(len(cmap1.tables), len(cmapo.tables))
        t1 = cmap1.tables[0]
        to = cmapo.tables[0]
        self.assertEqual(t1.data, to.data)
        #FIXEME? Probably we need to check more tables to see if they are equal.
        # However, considering this is a fairly simple script, we shouldn't spend
        # much time on it so far.

        font1.close()
        font2.close()
        output.close()


def dump_linemetrics(font):
    metrics = {}
    metrics['ascent'] = font['hhea'].ascent
    metrics['descent'] = font['hhea'].descent
    metrics['usWinAscent'] = font['OS/2'].usWinAscent
    metrics['usWinDescent'] = font['OS/2'].usWinDescent
    metrics['sTypoAscender'] = font['OS/2'].sTypoAscender
    metrics['sTypoDescender'] = font['OS/2'].sTypoDescender
    metrics['sxHeight'] = font['OS/2'].sxHeight
    metrics['sCapHeight'] = font['OS/2'].sCapHeight
    metrics['sTypoLineGap'] = font['OS/2'].sTypoLineGap
    return metrics


if __name__ == '__main__':
    import sys
    sys.exit(unittest.main())
