#!/usr/bin/env python
#
# Copyright 2014 Google Inc. All rights reserved.
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

"""OpenType-related data."""

__author__ = 'roozbeh@google.com (Roozbeh Pournader)'


from nototools import unicode_data

OMPL = {}
def _set_ompl():
    """Set up OMPL.

    OMPL is defined to be the list of mirrored pairs in Unicode 5.1:
    http://www.microsoft.com/typography/otspec/ttochap1.htm#ltrrtl
    """

    global OMPL
    unicode_data.load_data()
    bmg_data = unicode_data._bidi_mirroring_glyph_data
    OMPL = {char:bmg for (char, bmg) in bmg_data.items()
            if float(unicode_data.age(char)) <= 5.1}


ZWSP = [0x200B]
JOINERS = [0x200C, 0x200D]
BIDI_MARKS = [0x200E, 0x200F]
DOTTED_CIRCLE = [0x25CC]

# From the various script-specific specs at
# http://www.microsoft.com/typography/SpecificationsOverview.mspx
SPECIAL_CHARACTERS_NEEDED = {
    'Arab': JOINERS + BIDI_MARKS + DOTTED_CIRCLE,
    'Beng': ZWSP + JOINERS + DOTTED_CIRCLE,
    'Bugi': ZWSP + JOINERS + DOTTED_CIRCLE,
    'Deva': ZWSP + JOINERS + DOTTED_CIRCLE,
    'Gujr': ZWSP + JOINERS + DOTTED_CIRCLE,
    'Guru': ZWSP + JOINERS + DOTTED_CIRCLE,
    # Hangul may not need the special characters:
    # https://code.google.com/p/noto/issues/detail?id=147#c2
    # 'Hang': ZWSP + JOINERS,
    'Hebr': BIDI_MARKS + DOTTED_CIRCLE,
    'Java': ZWSP + JOINERS + DOTTED_CIRCLE,
    'Khmr': ZWSP + JOINERS + DOTTED_CIRCLE,
    'Knda': ZWSP + JOINERS + DOTTED_CIRCLE,
    'Laoo': ZWSP + DOTTED_CIRCLE,
    'Mlym': ZWSP + JOINERS + DOTTED_CIRCLE,
    'Mymr': ZWSP + JOINERS + DOTTED_CIRCLE,
    'Orya': ZWSP + JOINERS + DOTTED_CIRCLE,
    'Sinh': ZWSP + JOINERS + DOTTED_CIRCLE,
    'Syrc': JOINERS + BIDI_MARKS + DOTTED_CIRCLE,
    'Taml': ZWSP + JOINERS + DOTTED_CIRCLE,
    'Telu': ZWSP + JOINERS + DOTTED_CIRCLE,
    'Thaa': BIDI_MARKS + DOTTED_CIRCLE,
    'Thai': ZWSP + DOTTED_CIRCLE,
    'Tibt': ZWSP + JOINERS + DOTTED_CIRCLE,
}

# www.microsoft.com/typography/otspec/os2.html#ur
# bit, block name, block range
_unicoderange_data = """0\tBasic Latin\t0000-007F
1\tLatin-1 Supplement\t0080-00FF
2\tLatin Extended-A\t0100-017F
3\tLatin Extended-B\t0180-024F
4\tIPA Extensions\t0250-02AF
\tPhonetic Extensions\t1D00-1D7F
\tPhonetic Extensions Supplement\t1D80-1DBF
5\tSpacing Modifier Letters\t02B0-02FF
\tModifier Tone Letters\tA700-A71F
6\tCombining Diacritical Marks\t0300-036F
\tCombining Diacritical Marks Supplement\t1DC0-1DFF
7\tGreek and Coptic\t0370-03FF
8\tCoptic\t2C80-2CFF
9\tCyrillic\t0400-04FF
\tCyrillic Supplement\t0500-052F
\tCyrillic Extended-A\t2DE0-2DFF
\tCyrillic Extended-B\tA640-A69F
10\tArmenian\t0530-058F
11\tHebrew\t0590-05FF
12\tVai\tA500-A63F
13\tArabic\t0600-06FF
\tArabic Supplement\t0750-077F
14\tNKo\t07C0-07FF
15\tDevanagari\t0900-097F
16\tBengali\t0980-09FF
17\tGurmukhi\t0A00-0A7F
18\tGujarati\t0A80-0AFF
19\tOriya\t0B00-0B7F
20\tTamil\t0B80-0BFF
21\tTelugu\t0C00-0C7F
22\tKannada\t0C80-0CFF
23\tMalayalam\t0D00-0D7F
24\tThai\t0E00-0E7F
25\tLao\t0E80-0EFF
26\tGeorgian\t10A0-10FF
\tGeorgian Supplement\t2D00-2D2F
27\tBalinese\t1B00-1B7F
28\tHangul Jamo\t1100-11FF
29\tLatin Extended Additional\t1E00-1EFF
\tLatin Extended-C\t2C60-2C7F
\tLatin Extended-D\tA720-A7FF
30\tGreek Extended\t1F00-1FFF
31\tGeneral Punctuation\t2000-206F
\tSupplemental Punctuation\t2E00-2E7F
32\tSuperscripts And Subscripts\t2070-209F
33\tCurrency Symbols\t20A0-20CF
34\tCombining Diacritical Marks For Symbols\t20D0-20FF
35\tLetterlike Symbols\t2100-214F
36\tNumber Forms\t2150-218F
37\tArrows\t2190-21FF
\tSupplemental Arrows-A\t27F0-27FF
\tSupplemental Arrows-B\t2900-297F
\tMiscellaneous Symbols and Arrows\t2B00-2BFF
38\tMathematical Operators\t2200-22FF
\tSupplemental Mathematical Operators\t2A00-2AFF
\tMiscellaneous Mathematical Symbols-A\t27C0-27EF
\tMiscellaneous Mathematical Symbols-B\t2980-29FF
39\tMiscellaneous Technical\t2300-23FF
40\tControl Pictures\t2400-243F
41\tOptical Character Recognition\t2440-245F
42\tEnclosed Alphanumerics\t2460-24FF
43\tBox Drawing\t2500-257F
44\tBlock Elements\t2580-259F
45\tGeometric Shapes\t25A0-25FF
46\tMiscellaneous Symbols\t2600-26FF
47\tDingbats\t2700-27BF
48\tCJK Symbols And Punctuation\t3000-303F
49\tHiragana\t3040-309F
50\tKatakana\t30A0-30FF
\tKatakana Phonetic Extensions\t31F0-31FF
51\tBopomofo\t3100-312F
\tBopomofo Extended\t31A0-31BF
52\tHangul Compatibility Jamo\t3130-318F
53\tPhags-pa\tA840-A87F
54\tEnclosed CJK Letters And Months\t3200-32FF
55\tCJK Compatibility\t3300-33FF
56\tHangul Syllables\tAC00-D7AF
57\tNon-Plane 0 *\tD800-DFFF
58\tPhoenician\t10900-1091F
59\tCJK Unified Ideographs\t4E00-9FFF
\tCJK Radicals Supplement\t2E80-2EFF
\tKangxi Radicals\t2F00-2FDF
\tIdeographic Description Characters\t2FF0-2FFF
\tCJK Unified Ideographs Extension A\t3400-4DBF
\tCJK Unified Ideographs Extension B\t20000-2A6DF
\tKanbun\t3190-319F
60\tPrivate Use Area (plane 0)\tE000-F8FF
61\tCJK Strokes\t31C0-31EF
\tCJK Compatibility Ideographs\tF900-FAFF
\tCJK Compatibility Ideographs Supplement\t2F800-2FA1F
62\tAlphabetic Presentation Forms\tFB00-FB4F
63\tArabic Presentation Forms-A\tFB50-FDFF
64\tCombining Half Marks\tFE20-FE2F
65\tVertical Forms\tFE10-FE1F
\tCJK Compatibility Forms\tFE30-FE4F
66\tSmall Form Variants\tFE50-FE6F
67\tArabic Presentation Forms-B\tFE70-FEFF
68\tHalfwidth And Fullwidth Forms\tFF00-FFEF
69\tSpecials\tFFF0-FFFF
70\tTibetan\t0F00-0FFF
71\tSyriac\t0700-074F
72\tThaana\t0780-07BF
73\tSinhala\t0D80-0DFF
74\tMyanmar\t1000-109F
75\tEthiopic\t1200-137F
\tEthiopic Supplement\t1380-139F
\tEthiopic Extended\t2D80-2DDF
76\tCherokee\t13A0-13FF
77\tUnified Canadian Aboriginal Syllabics\t1400-167F
78\tOgham\t1680-169F
79\tRunic\t16A0-16FF
80\tKhmer\t1780-17FF
\tKhmer Symbols\t19E0-19FF
81\tMongolian\t1800-18AF
82\tBraille Patterns\t2800-28FF
83\tYi Syllables\tA000-A48F
\tYi Radicals\tA490-A4CF
84\tTagalog\t1700-171F
\tHanunoo\t1720-173F
\tBuhid\t1740-175F
\tTagbanwa\t1760-177F
85\tOld Italic\t10300-1032F
86\tGothic\t10330-1034F
87\tDeseret\t10400-1044F
88\tByzantine Musical Symbols\t1D000-1D0FF
\tMusical Symbols\t1D100-1D1FF
\tAncient Greek Musical Notation\t1D200-1D24F
89\tMathematical Alphanumeric Symbols\t1D400-1D7FF
90\tPrivate Use (plane 15)\tFF000-FFFFD
\tPrivate Use (plane 16)\t100000-10FFFD
91\tVariation Selectors\tFE00-FE0F
\tVariation Selectors Supplement\tE0100-E01EF
92\tTags\tE0000-E007F
93\tLimbu\t1900-194F
94\tTai Le\t1950-197F
95\tNew Tai Lue\t1980-19DF
96\tBuginese\t1A00-1A1F
97\tGlagolitic\t2C00-2C5F
98\tTifinagh\t2D30-2D7F
99\tYijing Hexagram Symbols\t4DC0-4DFF
100\tSyloti Nagri\tA800-A82F
101\tLinear B Syllabary\t10000-1007F
\tLinear B Ideograms\t10080-100FF
\tAegean Numbers\t10100-1013F
102\tAncient Greek Numbers\t10140-1018F
103\tUgaritic\t10380-1039F
104\tOld Persian\t103A0-103DF
105\tShavian\t10450-1047F
106\tOsmanya\t10480-104AF
107\tCypriot Syllabary\t10800-1083F
108\tKharoshthi\t10A00-10A5F
109\tTai Xuan Jing Symbols\t1D300-1D35F
110\tCuneiform\t12000-123FF
\tCuneiform Numbers and Punctuation\t12400-1247F
111\tCounting Rod Numerals\t1D360-1D37F
112\tSundanese\t1B80-1BBF
113\tLepcha\t1C00-1C4F
114\tOl Chiki\t1C50-1C7F
115\tSaurashtra\tA880-A8DF
116\tKayah Li\tA900-A92F
117\tRejang\tA930-A95F
118\tCham\tAA00-AA5F
119\tAncient Symbols\t10190-101CF
120\tPhaistos Disc\t101D0-101FF
121\tCarian\t102A0-102DF
\tLycian\t10280-1029F
\tLydian\t10920-1093F
122\tDomino Tiles\t1F030-1F09F
\tMahjong Tiles\t1F000-1F02F
"""

ur_data = []
ur_bucket_info = [[] for i in range(128)]

def _setup_unicoderange_data():
    """The unicoderange data used in the os/2 table consists of slightly under
    128 'buckets', each of which consists of one or more 'ranges' of codepoints.
    Each range has a name, start, and end.  Bucket 57 is special, it consists of
    all non-BMP codepoints and overlaps the other ranges, though in the data it
    corresponds to the high and low UTF-16 surrogate code units.  The other ranges
    are all disjoint.

    We build two tables.  ur_data is a list of the ranges, consisting of the
    start, end, bucket index, and name.  It is sorted by range start.  ur_bucket_info
    is a list of buckets in bucket index order; each entry is a list of the tuples
    in ur_data that belong to that bucket.

    This is called by functions that require these tables.  On first use it builds
    ur_data and ur_bucket_info, which should remain unchanged thereafter."""

    if ur_data:
        return
    index = 0
    for line in _unicoderange_data.splitlines():
        index_str, name, urange = line.split('\t')
        range_start_str, range_end_str = urange.split('-')
        range_start = int(range_start_str, 16)
        range_end = int(range_end_str, 16)
        if index_str:
            index = int(index_str)
        tup = (range_start, range_end, index, name)
        ur_data.append(tup)
        ur_bucket_info[index].append(tup)
    ur_data.sort()


def collect_unicoderange_info(cmap):
    """Return a list of 2-tuples, the first element a count of the characters in a
    range, the second element the 4-tuple of information about that range: start,
    end, bucket number, and name.  Only ranges for which the cmap has a character
    are included."""

    _setup_unicoderange_data()
    range_count = 0
    index = 0
    limit = len(ur_data)
    result = []
    for cp in sorted(cmap):
        while index < limit:
            tup = ur_data[index]
            if cp <= tup[1]:
                # the ranges are disjoint and some characters fall into no
                # range, e.g. Javanese.
                if cp >= tup[0]:
                    range_count += 1
                break
            if range_count:
                result.append((range_count, ur_data[index]))
                range_count = 0
            index += 1
    if range_count:
        result.append((range_count, ur_data[index]))
    return result


def unicoderange_bucket_info_name(bucket_info):
    return ', '.join(t[3] for t in bucket_info)


def unicoderange_bucket_info_size(bucket_info):
    return sum(t[1] - t[0] + 1 for t in bucket_info)


def unicoderange_bucket_index_to_info(bucket_index):
    if bucket_index < 0 or bucket_index >= 128:
        raise ValueError('bucket_index %s out of range' % bucket_index)
    _setup_unicoderange_data()
    return ur_bucket_info[bucket_index]


def unicoderange_bucket_index_to_name(bucket_index):
    return unicoderange_bucket_info_name(unicoderange_bucket_index_to_info(bucket_index))


if not OMPL:
    _set_ompl()
