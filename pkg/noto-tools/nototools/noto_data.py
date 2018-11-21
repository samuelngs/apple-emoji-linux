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

"""Noto-specific data about division of ranges between fonts.
"""

__author__ = "roozbeh@google.com (Roozbeh Pournader)"


CJK_RANGES_TXT = """
# Core
3400..4DBF; CJK Unified Ideographs Extension A
4E00..9FFF; CJK Unified Ideographs
F900..FAFF; CJK Compatibility Ideographs
20000..2A6DF; CJK Unified Ideographs Extension B
2A700..2B73F; CJK Unified Ideographs Extension C
2B740..2B81F; CJK Unified Ideographs Extension D
2F800..2FA1F; CJK Compatibility Ideographs Supplement
AC00..D7AF; Hangul Syllables
1100..11FF; Hangul Jamo
A960..A97F; Hangul Jamo Extended-A
D7B0..D7FF; Hangul Jamo Extended-B
3130..318F; Hangul Compatibility Jamo

3040..309F; Hiragana
1B000..1B0FF; Kana Supplement
30A0..30FF; Katakana
31F0..31FF; Katakana Phonetic Extensions

3100..312F; Bopomofo
31A0..31BF; Bopomofo Extended

# Others
3000..303F; CJK Symbols and Punctuation
3190..319F; Kanbun
31C0..31EF; CJK Strokes
3200..32FF; Enclosed CJK Letters and Months
FE10..FE1F; Vertical Forms
FE30..FE4F; CJK Compatibility Forms
FE50..FE6F; Small Form Variants
FF00..FFEF; Halfwidth and Fullwidth Forms

3300..33FF; CJK Compatibility
2FF0..2FFF; Ideographic Description Characters
2E80..2EFF; CJK Radicals Supplement
2F00..2FDF; Kangxi Radicals
"""

SYMBOL_RANGES_TXT = """
20A0..20CF; Currency Symbols
20D0..20FF; Combining Diacritical Marks for Symbols
2100..214F; Letterlike Symbols
2190..21FF; Arrows
2200..22FF; Mathematical Operators
2300..23FF; Miscellaneous Technical
2400..243F; Control Pictures
2440..245F; Optical Character Recognition
2460..24FF; Enclosed Alphanumerics
2500..257F; Box Drawing
2580..259F; Block Elements
25A0..25FF; Geometric Shapes
2600..26FF; Miscellaneous Symbols
2700..27BF; Dingbats
27C0..27EF; Miscellaneous Mathematical Symbols-A
27F0..27FF; Supplemental Arrows-A
2800..28FF; Braille Patterns
2900..297F; Supplemental Arrows-B
2980..29FF; Miscellaneous Mathematical Symbols-B
2A00..2AFF; Supplemental Mathematical Operators
2B00..2BFF; Miscellaneous Symbols and Arrows
2E00..2E7F; Supplemental Punctuation
4DC0..4DFF; Yijing Hexagram Symbols
A700..A71F; Modifier Tone Letters
FFF0..FFFF; Specials
10100..1013F; Aegean Numbers
10140..1018F; Ancient Greek Numbers
10190..101CF; Ancient Symbols
101D0..101FF; Phaistos Disc
1D000..1D0FF; Byzantine Musical Symbols
1D100..1D1FF; Musical Symbols
1D200..1D24F; Ancient Greek Musical Notation
1D300..1D35F; Tai Xuan Jing Symbols
1D360..1D37F; Counting Rod Numerals
1D400..1D7FF; Mathematical Alphanumeric Symbols
1F000..1F02F; Mahjong Tiles
1F030..1F09F; Domino Tiles
1F0A0..1F0FF; Playing Cards
1F100..1F1FF; Enclosed Alphanumeric Supplement
1F200..1F2FF; Enclosed Ideographic Supplement
1F700..1F77F; Alchemical Symbols
"""

UNDER_DEVELOPMENT_RANGES_TXT = """
0F00..0FFF; Tibetan
"""

DEEMED_UI_SCRIPTS_SET = frozenset({
  'Armn', # Armenian
  'Cher', # Cherokee
  'Ethi', # Ethiopic
  'Geor', # Georgian
  'Hebr', # Hebrew
  'Sinh', # Sinhala
  'Zsye', # Emoji
})

# A mapping from scripts to ttfautohint script ids.
# Most of the keys correspond to scripts we hinted for phase 2.
# Additions are 'Cher' (which we didn't hint in phase 2), and
# 'Latn', 'Grek', and 'Cyrl' (which we combine into LGC and don't
# break out into seprate scripts).
# A few scripts hinted in phase 2 are not listed by ttfautohint as
# supported: 'Cham', 'Orya', 'Thaa', and 'Tibt'; these map to None.
#
# ttfautohint supports two version of Georgian identified by 'geor'
# and 'geok', we assume 'geor'.
HINTED_SCRIPTS = {
    'Arab': 'arab',  # Arabic
    'Armn': 'armn',  # Armenian
    'Beng': 'beng',  # Bengali
    'Cham': None,    # Cham
    'Cher': 'cher',  # Cherokee (not hinted in phase2)
    'Cyrl': 'cyrl',  # Cyrillic (part of LGC)
    'Deva': 'deva',  # Devanagari
    'Ethi': 'ethi',  # Ethiopic
    'Geor': 'geor',  # Georgian (Mkhedruli, not Khutsuri)
    'Grek': 'grek',  # Greek (part of LGC)
    'Gujr': 'gujr',  # Gujarati
    'Guru': 'guru',  # Gurmukhi
    'Hebr': 'hebr',  # Hebrew
    'Khmr': 'khmr',  # Khmer
    'Knda': 'knda',  # Kannada
    'LGC': 'no-script',     # LGC, autohint but not to any particular script
    'Laoo': 'lao',   # Lao (only one 'o' for ttfautohint)
    'Latn': 'latn',  # Latin (part of LGC)
    'MONO': 'no-script',    # MONO, autohint like lgc
    'Mlym': 'mlym',  # Malayalam
    'Mymr': 'mymr',  # Myanmar
    'Orya': None,    # Oriya
    'Sinh': 'sinh',  # Sinhala
    'Taml': 'taml',  # Tamil
    'Telu': 'telu',  # Telugu
    'Thaa': None,    # Thaana
    'Thai': 'thai',  # Thai
    'Tibt': None,    # Tibetan
}


# Range spec matches "Noto Nastaliq requirements" doc, Tier 1.
URDU_RANGES = """
    0600..0604,060b..0614,061b,061c,061e..061f,0620,0621..063a,
    0640..0659,065e..066d,0670..0673,0679,067a..067b,067c,067d,
    067e,067f..0680,0681,0683..0684,0685..0686,0687,0688..0689,
    068a,068b,068c..068d,068e,068f,0691,0693,0696,0698,0699,
    069a,069e,06a6,06a9,06ab,06af..06b0,06b1,06b3,06b7,06ba,
    06bb,06bc,06be,06c0..06c4,06cc..06cd,06d0,06d2..06d5,
    06dd..06de,06e9,06ee..06ef,06f0..06f9,06ff,0759,075c,0763,
    0767..0769,076b..077d,08ff,fbb2..fbc1,fd3e..fd3f,fdf2,
    fdfa..fdfd"""

# Only these two characters are required for Urdu from the Arabic
# extra characters needed.
URDU_EXTRA = "2010..2011"

def _char_set(compact_set_text):
    result = set()
    prev = -1
    for part in compact_set_text.split(','):
        sep_index = part.find('..')
        if sep_index == -1:
            cp = int(part, base=16)
            assert cp > prev
            # print '%04x' % cp
            result.add(cp)
            prev = cp
        else:
          start = int(part[:sep_index], base=16)
          end = int(part[sep_index + 2:], base=16)
          # print '%04x..%04x' % (start, end)
          assert start > prev
          assert end > start
          for cp in range(start, end + 1):
              result.add(cp)
          prev = end
    return result

def urdu_set():
    return _char_set(URDU_RANGES) | _char_set(URDU_EXTRA)

def ascii_letters():
    return _char_set('0041..005a,0061..007a')

def char_range(start, end):
    return range(start, end+1)

COPTIC_EPACT = char_range(0x102E0, 0x102FB)
ARABIC_MATH = char_range(0x1EE00, 0x1EEF1)

P3_EXTRA_CHARACTERS_NEEDED = {
    # nothing additional outside block
    'Ahom': [ ],

    # According to Roozbeh (and existing fonts) the following punctuation and
    # digits are used with and interact with Arabic characters.
    'Arab': char_range(0x0030, 0x0039) + [
        # exclamation mark, comma, full stop, colon, NBS, guillimets
        0x0021, 0x002c, 0x002e, 0x003a, 0x00a0, 0x00ab, 0x00bb,
        0x06dd,           # Arabic end of Ayah
        0x2010, 0x2011,   # Hyphen and non-breaking hyphen need different shapes
        0x204F, 0x2E41,   # For Sindhi
        0xfd3e, 0xfd3f],  # ornate left and right paren (in Noto Naskh)

    # like Arabic, but Sindi is not written in Nastaliq so omitted.
    'Aran': char_range(0x0030, 0x0039) + [
        # exclamation mark, comma, full stop, colon, NBS, guillimets
        0x0021, 0x002c, 0x002e, 0x003a, 0x00a0, 0x00ab, 0x00bb,
        0x06dd,           # Arabic end of Ayah
        0x2010, 0x2011,   # Hyphen and non-breaking hyphen need different shapes
        0xfd3e, 0xfe3f],  # ornate left and right paren (in Noto Naskh)

    # Characters referenced in Armenian encoding cross ref page as shown in
    # see http://www.unicode.org/L2/L2010/10354-n3924-armeternity.pdf
    # also see http://man7.org/linux/man-pages/man7/armscii-8.7.html
    # left and right paren, comma, hyphen-minus, period, section,
    # no break space, left and right guillimet, hyphen, em dash, ellipsis
    # presentation forms FB13-FB17
    'Armn': [0x0028, 0x0029, 0x002C, 0x002D, 0x002E, 0x00A0,
             0x00A7, 0x00AB, 0x00BB, 0x2010, 0x2014, 0x2026],

    'Avst': [0x2E30, 0x2E31,  # From Core Specification and NamesList.txt
             0x200C],  # www.unicode.org/L2/L2007/07006r-n3197r-avestan.pdf

    # From http://www.unicode.org/L2/L2014/14064r-n4537r-cherokee.pdf section 8
    'Cher': [
        0x0300, 0x0301, 0x0302, 0x0304, 0x030B,
        0x030C, 0x0323, 0x0324, 0x0330, 0x0331],

    # From Core Specification:
    # period, colon, semicolon, middle dot
    # combining: grave, macron, overline, dot above, double overline
    # greek numeral sign, greek lower numeral sign, comb macrons (lh, rh, cj)
    # from http://std.dkuug.dk/JTC1/SC2/WG2/docs/n2636.pdf
    # oblique double hyphen, diaeresis, apostrophe, comb. circumflex, acute,
    # hyphen-minus, hyphen
    'Copt': [
        0x002E, 0x003A, 0x003B, 0x00B7,
        0x0300, 0x0304, 0x0305, 0x0307, 0x033F,
        0x0374, 0x0375, 0xFE24, 0xFE25, 0xFE26,
        0x2E17, 0x0308, 0x2019, 0x0302, 0x0301,
        0x002D, 0x2010,
        ],

    # Elbasan
    # see http://www.unicode.org/L2/L2011/11050-n3985-elbasan.pdf
    # adds combining overbar and greek numerals for ones and tens, and
    # both stigma/digamma for 6.
    # greek capital alpha beta gamma delta epsilon stigma/digamma zeta eta theta
    # iota kappa lambda mu nu xi omicron pi koppa
    'Elba': [0x00B7, 0x0305,
             0x0391, 0x0392, 0x0393, 0x0394, 0x0395,
             0x03DA, 0x03DD, 0x0396, 0x0397, 0x0398,
             0x0399, 0x039A, 0x039B, 0x039C, 0x039D,
             0x039E, 0x039F, 0x03A0, 0x03DE],

    # Ethiopic
    # See http://abyssiniagateway.net/fidel/l10n/
    # Recommends combining diaeresis 'for scholarly use', should look Ethiopian.
    # Also claims hyphen is not used, but a wikipedia page in Amharic does use
    # it, see
    # https://am.wikipedia.org/wiki/1_%E1%8A%A5%E1%88%BD%E1%88%98-%E1%8B%B3%E1%8C%8B%E1%8A%95
    # Western numerals and punctuation should look heavier to match the Ethiopic.
    # A keyboard standard is here:
    # See http://www.mcit.gov.et/documents/1268465/1282796/Keyboard+Layout+Standard/a8aa75ca-e125-4e25-872e-380e2a9b2313
    # digits
    # combining diaeresis (from abyssiniagateway site)
    # plus sign, comma, hyphen-minus, period, forward-slash
    # equals sign, question mark, left and right single and double curly quotes
    # left and right pointing double angle quotation marks, vertical three dot
    #   (plus sign to here all from keyboard doc)
    # exclamation point, left paren, right paren, ellipsis (web sites use them)
    # hyphen (used in hyphenated names in Amharaic, see wikipedia page)
    'Ethi': char_range(0x0030, 0x0039) + [
        0x0308,
        0x002B, 0x002C, 0x002D, 0x002E, 0x002F,
        0x003D, 0x003F, 0x2018, 0x2019, 0x201C, 0x201D,
        0x00AB, 0x00BB, 0x22EE,
        0x0021, 0x0028, 0x0029, 0x2026,
        0x2010],

    # Georgian
    # see example news article: http://www.civil.ge/geo/article.php?id=29970
    # ascii digits,
    # exclamation mark, percent, open/close paren, comma, hyphen-minus,
    # period, colon, semicolon, no break space (appears to be used in numbers)
    # em-dash, left double quotation mark, double low-9 quotation mark, ellipsis
    # see core standard:
    # middle dot, word separator middle dot, archaic punctuation (includes two
    # dot punctuation at 205A)
    'Geor': char_range(0x0030, 0x0039) + [
        0x0021, 0x0025, 0x0028, 0x0029, 0x002C, 0x002D,
        0x002E, 0x003A, 0x003B, 0x00A0,
        0x2014, 0x201C, 0x201E, 0x2026,
        0x00B7, 0x2E31] + char_range(0x2056, 0x205E) + char_range(0x2E2A, 0x2E2D),

    # Hatran
    # see http://www.unicode.org/L2/L2012/12312-n4324-hatran.pdf (most info, but
    # not latest assignment, which doesn't have all digits shown here)
    # single and double vertical line, also ZWNJ in case ligatures need breaking
    # might want to ligate hatran digit 1 forms 11 (2), 111 (3), 1111 (4) to
    # look as the suggested (dropped) digits were represented in the doc.
    'Hatr': [ 0x007C, 0x2016, 0x200C ],

    # Anatolian Hieroglyphs
    # see http://www.unicode.org/L2/L2012/12213-n4282-anatolian.pdf
    'Hluw': [0x200B],

    # Old Hungarian
    # see  http://www.unicode.org/L2/L2012/12168r-n4268r-oldhungarian.pdf
    # letters with LTR override mirror reverse (!) "which has to be handled by
    # the rendering engine"
    # ZWJ, middle dot, two dot punctuation, tricolon, vertical four dots
    # plus 'standard European punctuation:'
    # exclamation, comma, hyphen-minus, period, colon,
    # double high-reversed-9 quote, reversed semicolon, reversed question mark,
    #   reversed comma, double low-reversed-9 quote,
    # hyphen (the official one)
    'Hung': [ 0x200D, 0x2E31, 0x205A, 0x205D, 0x205E,
              0x0021, 0x002C, 0x002D, 0x002E, 0x003A,
              0x201F, 0x204F, 0x2E2E, 0x2E41, 0x2E42,
              0x2010,
            ],

    # latin 1 and 2
    'LGC': char_range(0x20, 0x7e) + char_range(0xa0, 0xff),

    'Lisu': [0x02BC, 0x02CD],  # From Core Specification

    # Meriotic Cursive
    # see http://www.unicode.org/L2/L2009/09188r-n3646-meroitic.pdf
    # colon, horizontal ellipsis, tricolon
    'Merc': [ 0x003A, 0x2026, 0x205D ],

    # Multani
    # see http://www.unicode.org/L2/L2012/12316-multani.pdf
    # Digits unified with Gurmukhi, but 6 and 7 look like Devanagari, it says.
    # Glyphic variant of section mark 0x112A9, but how would we represent it...
    'Mult': char_range(0x0A66, 0x0A6F),

    # Sharada
    # see http://www.unicode.org/L2/L2009/09074-sharada.pdf
    # also see http://www.unicode.org/L2/L2015/15255-sharada-vocalic-vs.pdf
    # which requests a change in the representative glyphs of 111ba and 111bb
    # (below vowel signs)
    # Seems self-contained, no other punctuation.
    'Shrd': [ ],

    # Siddham
    # see http://www.unicode.org/L2/L2012/12234r-n4294-siddham.pdf
    # most use in Aast Asia
    'Sidd': [ ],

    # Sign Writing
    # As with music notation, we can't lay this out.  Generative glyphs for lots
    # of hand positions...
    'Sgnw': [ ],

    'Sylo': [0x2055],  # From Core Specification

    # From Core Specification
    'Syrc': [
        0x0303, 0x0304, 0x0307, 0x0308, 0x030A, 0x0320,
        0x0323, 0x0324, 0x0325, 0x032D, 0x032E, 0x0330,
        0x060C, 0x061B, 0x061F, 0x0640] + char_range(0x064B, 0x0652),

    # From Core Specification & http://www.unicode.org/L2/L2001/01369-n2372.pdf
    'Tale': [0x0300, 0x0301, 0x0307, 0x0308, 0x030C],

    # From Core Specificaion and
    # http://www.unicode.org/L2/L2010/10407-ext-tamil-follow2.pdf
    'Taml': [0x00B2, 0x00B3, 0x2074, 0x2082, 0x2083, 0x2084],

    # From Core Specification and
    # http://www.unicode.org/L2/L2010/10451-patani-proposal.pdf
    'Thai': [0x02BC, 0x02D7, 0x0303, 0x0331],

    'Zmth': ARABIC_MATH,

    # Azerbaijani manat, Russian ruble, and Georgian Lari
    # Roozbeh says Coptic Epact doesn't belong in the Arabic fonts, though it's
    # used with Arabic.
    'Zsym': [0x20BC, 0x20BD, 0x20BE] + COPTIC_EPACT,
}

EXTRA_CHARACTERS_NEEDED = {
    'Arab': [
        0x2010, 0x2011,   # Hyphen and non-breaking hyphen need different shapes
        0x204F, 0x2E41],  # For Sindhi

    'Avst': [0x2E30, 0x2E31],  # From Core Specification and NamesList.txt

    # From http://www.unicode.org/L2/L2014/14064r-n4537r-cherokee.pdf section 8
    'Cher': [
        0x0300, 0x0301, 0x0302, 0x0304, 0x030B,
        0x030C, 0x0323, 0x0324, 0x0330, 0x0331],

    # From Core Specification
    'Copt': [
        0x0300, 0x0304, 0x0305, 0x0307, 0x033F,
        0x0374, 0x0375, 0xFE24, 0xFE25, 0xFE26],

    # latin 1 and 2
    'LGC': char_range(0x20, 0x7e) + char_range(0xa0, 0xff),

    'Lisu': [0x02BC, 0x02CD],  # From Core Specification

    'Sylo': [0x2055],  # From Core Specification

    # From Core Specification
    'Syrc': [
        0x0303, 0x0304, 0x0307, 0x0308, 0x030A, 0x0320,
        0x0323, 0x0324, 0x0325, 0x032D, 0x032E, 0x0330,
        0x060C, 0x061B, 0x061F, 0x0640] + char_range(0x064B, 0x0652),

    # From Core Specification & http://www.unicode.org/L2/L2001/01369-n2372.pdf
    'Tale': [0x0300, 0x0301, 0x0307, 0x0308, 0x030C],

    # From Core Specificaion and
    # http://www.unicode.org/L2/L2010/10407-ext-tamil-follow2.pdf
    'Taml': [0x00B2, 0x00B3, 0x2074, 0x2082, 0x2083, 0x2084],

    # From Core Specification and
    # http://www.unicode.org/L2/L2010/10451-patani-proposal.pdf
    'Thai': [0x02BC, 0x02D7, 0x0303, 0x0331],

    # Azerbaijani manat, Russian ruble, and Georgian Lari
    'Zsym': [0x20BC, 0x20BD, 0x20BE],
}

LGC_CHARACTERS_NOT_NEEDED = frozenset(
        char_range(0x0370, 0x0373) +
        [0x0376, 0x0377, 0x03CF, 0x0951, 0x0952, 0x1E9C, 0x1E9D, 0x1E9F] +
        char_range(0x1EFA, 0x1EFF) +
        [0x2071] +
        char_range(0x2095, 0x209C) +
        char_range(0x2160, 0x2183) +
        char_range(0x2185, 0x2188) +
        char_range(0x2C6E, 0x2C70) +
        char_range(0x2C78, 0x2C7F) +
        char_range(0x2DE0, 0x2DFF) +
        char_range(0xA640, 0xA673) +
        char_range(0xA67C, 0xA697) +
        char_range(0xA722, 0xA787) +
        [0xA78D, 0xA78E, 0xA790, 0xA791] +
        char_range(0xA7A0, 0xA7A9) +
        char_range(0xA7FA, 0xA7FF) +
        [0xA92E, 0xFB00, 0xFB05, 0xFB06])

P3_CHARACTERS_NOT_NEEDED = {
    'Arab': char_range(0x10E60, 0x10E7E) + COPTIC_EPACT + ARABIC_MATH,
    'Latn': LGC_CHARACTERS_NOT_NEEDED,
    'LGC': LGC_CHARACTERS_NOT_NEEDED,
}

CHARACTERS_NOT_NEEDED = {
    'Arab': char_range(0x10E60, 0x10E7E),
    'Latn': LGC_CHARACTERS_NOT_NEEDED,
    'LGC': LGC_CHARACTERS_NOT_NEEDED,
}

ACCEPTABLE_AS_COMBINING = {
    0x02DE,  # MODIFIER LETTER RHOTIC HOOK
}


def get_extra_characters_needed(script, phase):
  try:
    if phase == 2:
      return set(EXTRA_CHARACTERS_NEEDED[script])
    if phase == 3:
      return set(P3_EXTRA_CHARACTERS_NEEDED[script])
  except KeyError:
    pass
  return set()


def get_characters_not_needed(script, phase):
  try:
    if phase == 2:
      return set(CHARACTERS_NOT_NEEDED[script])
    if phase == 3:
      return set(P3_CHARACTERS_NOT_NEEDED[script])
  except KeyError:
    pass
  return set()
