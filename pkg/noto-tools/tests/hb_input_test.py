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


from __future__ import print_function, unicode_literals

import unittest

from fontTools.agl import AGL2UV
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.misc import UnicodeIO
from fontTools import mtiLib
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import newTable, TTFont
from fontTools.ttLib.tables._c_m_a_p import cmap_format_4

from nototools.hb_input import HbInputGenerator


def make_font(feature_source, fea_type='fea'):
    """Return font with GSUB compiled from given source.

    Adds a bunch of filler tables so the font can be saved if needed, for
    debugging purposes.
    """

    # copied from fontTools' feaLib/builder_test.
    glyphs = """
        .notdef space slash fraction semicolon period comma ampersand
        quotedblleft quotedblright quoteleft quoteright
        zero one two three four five six seven eight nine
        zero.oldstyle one.oldstyle two.oldstyle three.oldstyle
        four.oldstyle five.oldstyle six.oldstyle seven.oldstyle
        eight.oldstyle nine.oldstyle onequarter onehalf threequarters
        onesuperior twosuperior threesuperior ordfeminine ordmasculine
        A B C D E F G H I J K L M N O P Q R S T U V W X Y Z
        a b c d e f g h i j k l m n o p q r s t u v w x y z
        A.sc B.sc C.sc D.sc E.sc F.sc G.sc H.sc I.sc J.sc K.sc L.sc M.sc
        N.sc O.sc P.sc Q.sc R.sc S.sc T.sc U.sc V.sc W.sc X.sc Y.sc Z.sc
        A.alt1 A.alt2 A.alt3 B.alt1 B.alt2 B.alt3 C.alt1 C.alt2 C.alt3
        a.alt1 a.alt2 a.alt3 a.end b.alt c.mid d.alt d.mid
        e.begin e.mid e.end m.begin n.end s.end z.end
        Eng Eng.alt1 Eng.alt2 Eng.alt3
        A.swash B.swash C.swash D.swash E.swash F.swash G.swash H.swash
        I.swash J.swash K.swash L.swash M.swash N.swash O.swash P.swash
        Q.swash R.swash S.swash T.swash U.swash V.swash W.swash X.swash
        Y.swash Z.swash
        f_l c_h c_k c_s c_t f_f f_f_i f_f_l f_i o_f_f_i s_t f_i.begin
        a_n_d T_h T_h.swash germandbls ydieresis yacute breve
        grave acute dieresis macron circumflex cedilla umlaut ogonek caron
        damma hamza sukun kasratan lam_meem_jeem noon.final noon.initial
        by feature lookup sub table
    """.split()
    font = TTFont()
    font.setGlyphOrder(glyphs)
    glyph_order = font.getGlyphOrder()

    font['cmap'] = cmap = newTable('cmap')
    table = cmap_format_4(4)
    table.platformID = 3
    table.platEncID = 1
    table.language = 0
    table.cmap = {AGL2UV[n]: n for n in glyph_order if n in AGL2UV}
    cmap.tableVersion = 0
    cmap.tables = [table]

    font['glyf'] = glyf = newTable('glyf')
    glyf.glyphs = {}
    glyf.glyphOrder = glyph_order
    for name in glyph_order:
        pen = TTGlyphPen(None)
        glyf[name] = pen.glyph()

    font['head'] = head = newTable('head')
    head.tableVersion = 1.0
    head.fontRevision = 1.0
    head.flags = head.checkSumAdjustment = head.magicNumber =\
        head.created = head.modified = head.macStyle = head.lowestRecPPEM =\
        head.fontDirectionHint = head.indexToLocFormat =\
        head.glyphDataFormat =\
        head.xMin = head.xMax = head.yMin = head.yMax = 0
    head.unitsPerEm = 1000

    font['hhea'] = hhea = newTable('hhea')
    hhea.tableVersion = 0x00010000
    hhea.ascent = hhea.descent = hhea.lineGap =\
        hhea.caretSlopeRise = hhea.caretSlopeRun = hhea.caretOffset =\
        hhea.reserved0 = hhea.reserved1 = hhea.reserved2 = hhea.reserved3 =\
        hhea.metricDataFormat = hhea.advanceWidthMax = hhea.xMaxExtent =\
        hhea.minLeftSideBearing = hhea.minRightSideBearing =\
        hhea.numberOfHMetrics = 0

    font['hmtx'] = hmtx = newTable('hmtx')
    hmtx.metrics = {}
    for name in glyph_order:
        hmtx[name] = (600, 50)

    font['loca'] = newTable('loca')

    font['maxp'] = maxp = newTable('maxp')
    maxp.tableVersion = 0x00005000
    maxp.numGlyphs = 0

    font['post'] = post = newTable('post')
    post.formatType = 2.0
    post.extraNames = []
    post.mapping = {}
    post.glyphOrder = glyph_order
    post.italicAngle = post.underlinePosition = post.underlineThickness =\
        post.isFixedPitch = post.minMemType42 = post.maxMemType42 =\
        post.minMemType1 = post.maxMemType1 = 0

    if fea_type == 'fea':
        addOpenTypeFeaturesFromString(font, feature_source)
    elif fea_type == 'mti':
        font['GSUB'] = mtiLib.build(UnicodeIO(feature_source), font)

    return font


class HbInputGeneratorTest(unittest.TestCase):
    def _make_generator(self, feature_source, fea_type='fea'):
        """Return input generator for GSUB compiled from given source."""

        font = make_font(feature_source, fea_type)
        return HbInputGenerator(font)

    def test_no_gsub(self):
        g = self._make_generator('')
        self.assertEqual(g.input_from_name('a'), ((), 'a'))
        self.assertEqual(g.input_from_name('acute', pad=True), ((), ' \u00b4'))

    def test_input_not_found(self):
        g = self._make_generator('')
        self.assertEqual(g.input_from_name('A.sc'), None)

    def test_cyclic_rules_not_followed(self):
        g = self._make_generator('''
            feature onum {
                sub zero by zero.oldstyle;
            } onum;

            feature lnum {
                sub zero.oldstyle by zero;
            } lnum;
        ''')
        self.assertEqual(g.input_from_name('zero.oldstyle'), (('onum',), '0'))

    def test_onum_after_lnum(self):
        g = self._make_generator('''
            feature onum {
                sub zero by zero.oldstyle;
            } onum;
        ''')
        self.assertEqual(g.input_from_name('zero'), ((), '0'))
        self.assertEqual(g.input_from_name('zero.oldstyle'), (('onum',), '0'))
        g = self._make_generator('''
            feature onum {
                sub zero by zero.oldstyle;
            } onum;

            feature lnum {
                sub zero.oldstyle by zero;
            } lnum;
        ''')
        self.assertEqual(g.input_from_name('zero'), ((), '0'))
        self.assertEqual(g.input_from_name('zero.oldstyle'), (('onum',), '0'))

    def test_lnum_after_onum(self):
        g = self._make_generator('''
            feature onum {
                sub zero by zero.oldstyle;
            } onum;
        ''')
        self.assertEqual(g.input_from_name('zero.oldstyle'), (('onum',), '0'))
        self.assertEqual(g.input_from_name('zero'), ((), '0'))

    def test_contextual_substitution_type1(self):
        g = self._make_generator('''
            FontDame GSUB table

            feature table begin
            0\ttest\ttest-lookup-ctx
            feature table end

            lookup\ttest-lookup-ctx\tcontext
            glyph\tb,a\t1,test-lookup-sub
            lookup end

            lookup\ttest-lookup-sub\tsingle
            a\tA.sc
            lookup end
        ''', fea_type='mti')
        self.assertEqual(g.input_from_name('A.sc'), (('test',), 'ba'))

    def test_contextual_substitution_type2(self):
        g = self._make_generator('''
            FontDame GSUB table

            feature table begin
            0\ttest\ttest-lookup-ctx
            feature table end

            lookup\ttest-lookup-ctx\tcontext
            class definition begin
            a\t1
            b\t2
            c\t3
            d\t1
            class definition end
            class\t1,2,3,1\t1,test-lookup-sub
            lookup end

            lookup\ttest-lookup-sub\tligature
            A.sc\ta\tb\tc
            D.sc\td\tb\tc
            lookup end
        ''', fea_type='mti')
        self.assertEqual(g.input_from_name('A.sc'), (('test',), 'abca'))
        self.assertEqual(g.input_from_name('D.sc'), (('test',), 'dbca'))

    def test_chaining_substitution_type1(self):
        g = self._make_generator('''
            FontDame GSUB table

            feature table begin
            0\ttest\ttest-lookup-ctx
            feature table end

            lookup\ttest-lookup-ctx\tchained
            glyph\tb\ta\tc\t1,test-lookup-sub
            lookup end

            lookup\ttest-lookup-sub\tsingle
            a\tA.sc
            lookup end
        ''', fea_type='mti')
        self.assertEqual(g.input_from_name('A.sc'), (('test',), 'bac'))

    def test_chaining_substitution_type3(self):
        g = self._make_generator('''
            lookup CNTXT_LIGS {
                substitute f i by f_i;
                substitute c t by c_t;
            } CNTXT_LIGS;

            lookup CNTXT_SUB {
                substitute n by n.end;
                substitute s by s.end;
            } CNTXT_SUB;

            feature test {
                substitute [a e i o u]
                    f' lookup CNTXT_LIGS i' n' lookup CNTXT_SUB;
                substitute [a e i o u]
                    c' lookup CNTXT_LIGS t' s' lookup CNTXT_SUB;
            } test;
        ''')
        self.assertEqual(g.input_from_name('f_i'), (('test',), 'afin'))
        self.assertEqual(g.input_from_name('c_t'), (('test',), 'acts'))
        self.assertEqual(g.input_from_name('n.end'), (('test',), 'afin'))
        self.assertEqual(g.input_from_name('s.end'), (('test',), 'acts'))

        g = self._make_generator('''
            feature test {
                substitute [a e n] d' by d.alt;
            } test;
        ''')
        self.assertEqual(g.input_from_name('d.alt'), (('test',), 'ad'))

    def test_no_feature_rule_takes_precedence(self):
        g = self._make_generator('''
            feature test {
                substitute [A-Z] [A.sc-Z.sc]' by [a-z];
            } test;
        ''')
        self.assertEqual(g.input_from_name('a'), ((), 'a'))

        g = self._make_generator('''
            feature test {
                substitute [e e.begin]' t' c by ampersand;
            } test;
        ''')
        self.assertEqual(g.input_from_name('ampersand'), ((), '&'))

    def test_chaining_substitution_backtrack_reversed(self):
        g = self._make_generator('''
            feature test {
                substitute [b e] [c f] a' [d g] by A.sc;
            } test;
        ''')
        self.assertEqual(g.input_from_name('A.sc'), (('test',), 'bcad'))

    def test_is_sublist(self):
        g = self._make_generator('')
        self.assertTrue(g._is_sublist([], []))
        self.assertFalse(g._is_sublist([], [1]))
        self.assertTrue(g._is_sublist([1, 2, 3], [2, 3]))
        self.assertFalse(g._is_sublist([1, 2, 3], [1, 3]))

    def test_min_permutation(self):
        g = self._make_generator('')
        self.assertEqual(g._min_permutation(
            [[1, 2], [3, 4], [5, 6]], [2, 3]), [2, 3, 5])
        self.assertEqual(g._min_permutation(
            [[1, 2], [3, 4], [5, 6]], [3, 6]), [1, 3, 6])
        self.assertEqual(g._min_permutation(
            [[1, 2], [3, 4], [5, 6]], [1, 4, 5]), [1, 4, 5])
        self.assertEqual(g._min_permutation(
            [[1], [], [2]], [1]), [])

if __name__ == '__main__':
    unittest.main()
