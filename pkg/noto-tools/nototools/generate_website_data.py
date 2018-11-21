#!/usr/bin/env python
# -*- coding: UTF-8 -*-
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

"""Generate data files for the Noto website."""

from __future__ import division

__author__ = 'roozbeh@google.com (Roozbeh Pournader)'

import argparse
import codecs
import collections
import csv
import json
import locale
import os
from os import path
import re
import shutil
import subprocess
import xml.etree.cElementTree as ElementTree

from fontTools import ttLib

from nototools import coverage
from nototools import create_image
from nototools import extra_locale_data
from nototools import font_data
from nototools import unicode_data
from nototools import tool_utils

# CJK_DIR is in newnoto/noto-cjk
# license is at this root
# FONT_DIR is in newnoto/noto-fonts, subdirs are alpha, hinted, unhinted
# license is at this root
# EMOJI is not here...

ROOT = path.abspath(path.join(path.dirname(__file__), os.pardir, os.pardir))

TOOLS_DIR = path.join(ROOT, 'nototools')
CJK_DIR = path.join(ROOT, 'noto-cjk')
FONT_DIR = path.join(ROOT, 'noto-fonts')

OUTPUT_DIR = path.join(ROOT, 'website_data')

CLDR_DIR = path.join(TOOLS_DIR, 'third_party', 'cldr')
LAT_LONG_DIR = path.join(TOOLS_DIR, 'third_party', 'dspl')
SAMPLE_TEXT_DIR = path.join(TOOLS_DIR, 'sample_texts')

APACHE_LICENSE_LOC = path.join(FONT_DIR, 'LICENSE')
SIL_LICENSE_LOC = path.join(CJK_DIR, 'LICENSE')

ODD_SCRIPTS = {
    'CJKjp': 'Jpan',
    'CJKkr': 'Kore',
    'CJKsc': 'Hans',
    'CJKtc': 'Hant',
    'NKo': 'Nkoo',
    'SumeroAkkadianCuneiform': 'Xsux',
    'Symbols': 'Zsym',
}

def convert_to_four_letter(script):
    """"Converts a script name from a Noto font file name to ISO 15924 code."""
    if script in ODD_SCRIPTS:
        script = ODD_SCRIPTS[script]
    elif script in unicode_data._script_long_name_to_code:
        script = unicode_data._script_long_name_to_code[script]
    else:
        for lname in unicode_data._script_long_name_to_code:
            if lname.replace('_', '').lower() == script.lower():
                script = unicode_data._script_long_name_to_code[lname]
    if len(script) != 4:
      raise ValueError("script code '%s' is not the right length." % script)
    return script


Font = collections.namedtuple(
    'Font',
    'filepath, hint_status, key, '
    'family, script, variant, weight, style, platform,'
    'charset, license_type')


all_fonts = []
supported_scripts = set()

def find_fonts():
    font_name_regexp = re.compile(
        '(NotoSans|NotoSerif|NotoNaskh|NotoKufi|Arimo|Cousine|Tinos)'
        '(Mono)?'
        '(.*?)'
        '(UI|Eastern|Estrangela|Western)?'
        '-'
        '(|Black|Bold|DemiLight|Light|Medium|Regular|Thin)'
        '(Italic)?'
        '(-Windows)?'
        '.[ot]t[cf]')

    unicode_data.load_data()

    for directory in [path.join(FONT_DIR, 'hinted'),
                      path.join(FONT_DIR, 'unhinted'),
                      path.join(FONT_DIR, 'alpha'),
                      CJK_DIR]:
        for filename in os.listdir(directory):
            match = font_name_regexp.match(filename)
            if match:
                family, mono, script, variant, weight, style, platform = match.groups()
            elif filename == 'NotoNastaliqUrduDraft.ttf':
                family = 'NotoNastaliq'
                script = 'Aran'  # Arabic Nastaliq
                weight = ''
                style = variant = platform = None
            else:
                if not (
                    filename == 'NotoSansCJK.ttc.zip' or  # All-comprehensive CJK
                    filename.endswith('.ttx') or
                    filename.endswith('.git') or
                    filename.startswith('README.') or
                    filename in ['COPYING', 'LICENSE', 'NEWS', 'HISTORY']):
                    raise ValueError("unexpected filename in %s: '%s'." %
                                     (directory, filename))
                continue

            if directory == CJK_DIR:
                license_type = 'sil'
            else:
                license_type = 'apache'

            if mono:
                # we don't provide the Mono CJK on the website
                continue
            if script == "Historic":
                # we don't provide this either
                continue

            if family in {'Arimo', 'Cousine', 'Tinos'}:
                continue  # Skip these three for the website

            if family.startswith('Noto'):
                family = family.replace('Noto', 'Noto ')

            if weight == '':
                weight = 'Regular'

            assert platform is None

            if script == '':  # LGC
                supported_scripts.update({'Latn', 'Grek', 'Cyrl'})
            elif script == 'Aran':
                supported_scripts.add(script)
            elif script in {'JP', 'KR', 'SC', 'TC', 'CJK'}:
                continue  # Skip unified or old CJK fonts
            else:
                script = convert_to_four_letter(script)
                supported_scripts.add(script)

            file_path = path.join(directory, filename)
            if filename.endswith('.ttf') or filename.endswith('.otf'):
                charset = coverage.character_set(file_path)
            else:
                charset = NotImplemented

            if directory == CJK_DIR:
                hint_status = 'hinted'
            elif directory.endswith('alpha'):
                hint_status = 'unhinted'
            else:
                hint_status = path.basename(directory)
            assert hint_status in ['hinted', 'unhinted']

            key = family.replace(' ', '-')
            if script:
                key += '-' + script
            if variant not in {None, 'UI'}:
                key += '-' + variant
            key = key.lower()

            font = Font(file_path, hint_status, key,
                        family, script, variant, weight, style, platform,
                        charset, license_type)
            all_fonts.append(font)


def read_character_at(source, pointer):
    assert source[pointer] not in ' -{}'
    if source[pointer] == '\\':
        if source[pointer+1] == 'u':
            end_of_hex = pointer+2
            while (end_of_hex < len(source)
                   and source[end_of_hex].upper() in '0123456789ABCDEF'):
                end_of_hex += 1
            assert end_of_hex-(pointer+2) in {4, 5, 6}
            hex_code = source[pointer+2:end_of_hex]
            return end_of_hex, unichr(int(hex_code, 16))
        else:
            return pointer+2, source[pointer+1]
    else:
        return pointer+1, source[pointer]


def exemplar_string_to_list(exstr):
    assert exstr[0] == '['
    exstr = exstr[1:]
    if exstr[-1] == ']':
        exstr = exstr[:-1]

    return_list = []
    pointer = 0
    while pointer < len(exstr):
        if exstr[pointer] in ' ':
            pointer += 1
        elif exstr[pointer] == '{':
            multi_char = ''
            mc_ptr = pointer+1
            while exstr[mc_ptr] != '}':
                mc_ptr, char = read_character_at(exstr, mc_ptr)
                multi_char += char
            return_list.append(multi_char)
            pointer = mc_ptr+1
        elif exstr[pointer] == '-':
            previous = return_list[-1]
            assert len(previous) == 1  # can't have ranges with strings
            previous = ord(previous)

            pointer, last = read_character_at(exstr, pointer+1)
            assert last not in [' ', '\\', '{', '}', '-']
            last = ord(last)
            return_list += [unichr(code) for code in range(previous+1, last+1)]
        else:
            pointer, char = read_character_at(exstr, pointer)
            return_list.append(char)

    return return_list


exemplar_from_file_cache = {}

def get_exemplar_from_file(cldr_file_path):
    try:
        return exemplar_from_file_cache[cldr_file_path]
    except KeyError:
        pass

    data_file = path.join(CLDR_DIR, cldr_file_path)
    try:
        root = ElementTree.parse(data_file).getroot()
    except IOError:
        exemplar_from_file_cache[cldr_file_path] = None
        return None
    for tag in root.iter('exemplarCharacters'):
        if 'type' in tag.attrib:
            continue
        exemplar_from_file_cache[cldr_file_path] = exemplar_string_to_list(
            tag.text)
        return exemplar_from_file_cache[cldr_file_path]
    return None


def find_parent_locale(locl):
    if locl in parent_locale:
        return parent_locale[locl]
    if '-' in locl:
        return locl[:locl.rindex('-')]
    if locale == 'root':
        return None
    return 'root'


def get_exemplar(language, script):
    locl = language + '-' + script
    while locl != 'root':
        for directory in ['common', 'seed', 'exemplars']:
            exemplar = get_exemplar_from_file(
                path.join(directory, 'main', locl.replace('-', '_')+'.xml'))
            if exemplar:
                return exemplar
        locl = find_parent_locale(locl)
    return None


def get_sample_from_sample_file(language, script):
    filepath = path.join(SAMPLE_TEXT_DIR, language+'-'+script+'.txt')
    if path.exists(filepath):
        return unicode(open(filepath).read().strip(), 'UTF-8')
    return None


language_name_from_file_cache = {}

def get_language_name_from_file(language, cldr_file_path):
    cache_key = (language, cldr_file_path)
    try:
        return language_name_from_file_cache[cache_key]
    except KeyError:
        pass

    data_file = path.join(CLDR_DIR, cldr_file_path)
    try:
        root = ElementTree.parse(data_file).getroot()
    except IOError:
        language_name_from_file_cache[cache_key] = None
        return None

    parent = root.find('.//languages')
    if parent is None:
        return None
    for tag in parent:
        assert tag.tag == 'language'
        if tag.get('type').replace('_', '-') == language:
            language_name_from_file_cache[cache_key] = tag.text
            return language_name_from_file_cache[cache_key]
    return None


def get_native_language_name(lang_scr):
    """Get the name of a language in its own locale."""
    try:
        return extra_locale_data.NATIVE_NAMES[lang_scr]
    except KeyError:
        pass

    if '-' in lang_scr:
        language = lang_scr.split('-')[0]
    else:
        language = lang_scr

    locl = lang_scr
    while locl != 'root':
        for directory in ['common', 'seed']:
            file_path = path.join(
                directory, 'main', locl.replace('-', '_')+'.xml')
            for name_to_find in [lang_scr, language]:
                native_name = get_language_name_from_file(
                    name_to_find, file_path)
                if native_name:
                    return native_name
        locl = find_parent_locale(locl)
    return None


EXEMPLAR_CUTOFF_SIZE = 50

def sample_text_from_exemplar(exemplar):
    exemplar = [c for c in exemplar
                  if unicode_data.category(c[0])[0] in 'LNPS']
    exemplar = exemplar[:EXEMPLAR_CUTOFF_SIZE]
    return ' '.join(exemplar)


def get_sample_text(language, script):
    """Returns a sample text string for a given language and script."""

    sample_text = get_sample_from_sample_file(language, script)
    if sample_text is not None:
        return sample_text

    exemplar = get_exemplar(language, script)
    if exemplar is not None:
        return sample_text_from_exemplar(exemplar)

    sample_text = get_sample_from_sample_file('und', script)
    if sample_text is not None:
        return sample_text

    raise ValueError, 'language=%s script=%s' % (language, script)


def xml_to_dict(element):
    return_dict = {}
    for child in list(element):
        if 'alt' in child.attrib:
            continue
        key = child.get('type')
        key = key.replace('_', '-')
        return_dict[key] = child.text
    return return_dict


english_language_name = {}
english_script_name = {}
english_territory_name = {}

def parse_english_labels():
    global english_language_name, english_script_name, english_territory_name

    data_file = path.join(
        CLDR_DIR, 'common', 'main', 'en.xml')
    root = ElementTree.parse(data_file).getroot()
    ldn = root.find('localeDisplayNames')

    english_language_name = xml_to_dict(ldn.find('languages'))
    english_script_name = xml_to_dict(ldn.find('scripts'))
    english_territory_name = xml_to_dict(ldn.find('territories'))

    # Add langauges used that miss names
    english_language_name.update(extra_locale_data.ENGLISH_LANGUAGE_NAMES)

def get_english_language_name(lang_scr):
    try:
        return english_language_name[lang_scr]
    except KeyError:
        lang, script = lang_scr.split('-')
        name = '%s (%s script)' % (
            english_language_name[lang],
            english_script_name[script])
        print "Constructing name '%s' for %s." % (name, lang_scr)
        return name

used_in_regions = collections.defaultdict(set)
written_in_scripts = collections.defaultdict(set)
territory_info = collections.defaultdict(set)
parent_locale = {}

def parse_supplemental_data():
    data_file = path.join(
        CLDR_DIR, 'common', 'supplemental', 'supplementalData.xml')
    root = ElementTree.parse(data_file).getroot()

    for language_tag in root.iter('language'):
        attribs = language_tag.attrib

        if 'alt' in attribs:
            assert attribs['alt'] == 'secondary'

        lang = attribs['type']
        if lang == 'mru':  # CLDR bug: http://unicode.org/cldr/trac/ticket/7709
            continue

        if 'territories' in attribs:
            territories = set(attribs['territories'].split(' '))
            used_in_regions[lang].update(territories)

        if 'scripts' in attribs:
            scripts = set(attribs['scripts'].split(' '))
            written_in_scripts[lang].update(scripts)

    for tag in root.iter('territory'):
        territory = tag.get('type')
        for child in tag:
            assert child.tag == 'languagePopulation'
#            if 'officialStatus' not in child.attrib:
#                continue  # Skip non-official languages
            lang = child.get('type').replace('_', '-')
            territory_info[territory].add(lang)

    for tag in root.iter('parentLocale'):
        parent = tag.get('parent')
        parent = parent.replace('_', '-')
        for locl in tag.get('locales').split(' '):
            locl = locl.replace('_', '-')
            parent_locale[locl] = parent

    parent_locale.update(extra_locale_data.PARENT_LOCALES)


likely_subtag_data = {}

def parse_likely_subtags():
    data_file = path.join(
        CLDR_DIR, 'common', 'supplemental', 'likelySubtags.xml')
    tree = ElementTree.parse(data_file)

    for tag in tree.findall('likelySubtags/likelySubtag'):
        from_tag = tag.get('from').replace('_', '-')
        to_tag = tag.get('to').split('_')
        likely_subtag_data[from_tag] = to_tag

    likely_subtag_data.update(extra_locale_data.LIKELY_SUBTAGS)


def find_likely_script(language):
    if not likely_subtag_data:
        parse_likely_subtags()
    return likely_subtag_data[language][1]


script_metadata = {}

def parse_script_metadata():
    global script_metadata
    data = open(path.join(
        CLDR_DIR, 'common', 'properties', 'scriptMetadata.txt')).read()
    parsed_data = unicode_data._parse_semicolon_separated_data(data)
    script_metadata = {line[0]:tuple(line[1:]) for line in parsed_data}


def is_script_rtl(script):
    if not script_metadata:
        parse_script_metadata()
    return script_metadata[script][5] == 'YES'


lat_long_data = {}

def read_lat_long_data():
    with open(path.join(LAT_LONG_DIR, 'countries.csv')) as lat_long_file:
        for row in csv.reader(lat_long_file):
            region, latitude, longitude, _ = row
            if region == 'country':
                continue  # Skip the header
            if not latitude:
                continue  # Empty latitude
            latitude = float(latitude)
            longitude = float(longitude)
            lat_long_data[region] = (latitude, longitude)

    # From the English Wikipedia and The World Factbook at
    # https://www.cia.gov/library/publications/the-world-factbook/fields/2011.html
    lat_long_data.update({
        'AC': (-7-56/60, -14-22/60),  # Ascension Island
        'AX': (60+7/60, 19+54/60),  # Åland Islands
        'BL': (17+54/60, -62-50/60),  # Saint Barthélemy
        'BQ': (12+11/60, -68-14/60),  # Caribbean Netherlands
        'CP': (10+18/60, -109-13/60),  # Clipperton Island
        'CW': (12+11/60, -69),  # Curaçao
        'DG': (7+18/60+48/3600, 72+24/60+40/3600),  # Diego Garcia
         # Ceuta and Melilla, using Ceuta
        'EA': (35+53/60+18/3600, -5-18/60-56/3600),
        'IC': (28.1, -15.4),  # Canary Islands
        'MF': (18+4/60+31/3600, -63-3/60-36/3600),  # Saint Martin
        'SS': (8, 30),  # South Sudan
        'SX': (18+3/60, -63-3/60),  # Sint Maarten
        'TA': (-37-7/60, -12-17/60),  # Tristan da Cunha
         # U.S. Outlying Islands, using Johnston Atoll
        'UM': (16+45/60, -169-31/60),
    })


def sorted_langs(langs):
    return sorted(
        set(langs),
        key=lambda code: locale.strxfrm(
            get_english_language_name(code).encode('UTF-8')))


all_used_lang_scrs = set()

def create_regions_object():
    if not lat_long_data:
        read_lat_long_data()
    regions = {}
    for territory in territory_info:
        region_obj = {}
        region_obj['name'] = english_territory_name[territory]
        region_obj['lat'], region_obj['lng'] = lat_long_data[territory]
        region_obj['langs'] = sorted_langs(territory_info[territory])
        all_used_lang_scrs.update(territory_info[territory])
        regions[territory] = region_obj

    return regions


def charset_supports_text(charset, text):
    if charset is NotImplemented:
        return False
    needed_codepoints = {ord(char) for char in set(text)}
    return needed_codepoints <= charset


family_to_langs = collections.defaultdict(set)

def create_langs_object():
    langs = {}
    for lang_scr in sorted(set(written_in_scripts) | all_used_lang_scrs):
        lang_object = {}
        if '-' in lang_scr:
            language, script = lang_scr.split('-')
        else:
            language = lang_scr
            try:
                script = find_likely_script(language)
            except KeyError:
                print "no likely script for %s" % language
                continue

        lang_object['name'] = get_english_language_name(lang_scr)
        native_name = get_native_language_name(lang_scr)
        if native_name is not None:
            lang_object['nameNative'] = native_name

        lang_object['rtl'] = is_script_rtl(script)

        if script == 'Kana':
            script = 'Jpan'

        if script not in supported_scripts:
            # Scripts we don't have fonts for yet
            print('No font supports the %s script (%s) needed for the %s language.'
                  % (english_script_name[script], script, lang_object['name']))
            assert script in {
                'Bass',  # Bassa Vah
                'Lina',  # Linear A
                'Mani',  # Manichaean
                'Merc',  # Meroitic Cursive
                'Mroo',  # Mro
                'Narb',  # Old North Arabian
                'Orya',  # Oriya
                'Plrd',  # Miao
                'Sora',  # Sora Sompeng
                'Thaa',  # Thaana
                'Tibt',  # Tibetan
            }

            lang_object['families'] = []
        else:
            sample_text = get_sample_text(language, script)
            lang_object['sample'] = sample_text

            if script in {'Latn', 'Grek', 'Cyrl'}:
                query_script = ''
            else:
                query_script = script

            # FIXME(roozbeh): Figure out if the language is actually supported
            # by the font + Noto LGC. If it's not, don't claim support.
            fonts = [font for font in all_fonts if font.script == query_script]

            # For certain languages of Pakistan, add Nastaliq font
            if lang_scr in {'bal', 'hnd', 'hno', 'ks-Arab', 'lah',
                            'pa-Arab', 'skr', 'ur'}:
                fonts += [font for font in all_fonts if font.script == 'Aran']

            family_keys = set([font.key for font in fonts])

            lang_object['families'] = sorted(family_keys)
            for family in family_keys:
                family_to_langs[family].add(lang_scr)

        langs[lang_scr] = lang_object
    return langs


def get_font_family_name(font_file):
    font = ttLib.TTFont(font_file)
    name_record = font_data.get_name_records(font)
    return name_record[1]


def charset_to_ranges(font_charset):
    # Ignore basic common characters
    charset = font_charset - {0x00, 0x0D, 0x20, 0xA0, 0xFEFF}
    ranges = coverage.convert_set_to_ranges(charset)

    output_list = []
    for start, end in ranges:
        output_list.append(('%04X' % start, '%04X' % end))
    return output_list


def get_css_generic_family(family):
    if family in {'Noto Naskh', 'Noto Serif', 'Tinos'}:
        return 'serif'
    if family in {'Arimo', 'Noto Kufi', 'Noto Sans'}:
        return 'sans-serif'
    if family == 'Cousine':
        return 'monospace'
    return None


CSS_WEIGHT_MAPPING = {
    'Thin': 250,
    'Light': 300,
    'DemiLight': 350,
    'Regular': 400,
    'Medium': 500,
    'Bold': 700,
    'Black': 900,
}

def css_weight(weight_string):
    return CSS_WEIGHT_MAPPING[weight_string]


CSS_WEIGHT_TO_STRING = {s:w for w, s in CSS_WEIGHT_MAPPING.items()}

def css_weight_to_string(weight):
    return CSS_WEIGHT_TO_STRING[weight]


def css_style(style_value):
    if style_value is None:
        return 'normal'
    else:
        assert style_value == 'Italic'
        return 'italic'


def fonts_are_basically_the_same(font1, font2):
    """Returns true if the fonts are the same, except perhaps hint or platform.
    """
    return (font1.family == font2.family and
            font1.script == font2.script and
            font1.variant == font2.variant and
            font1.weight == font2.weight and
            font1.style == font2.style)


def compress_png(pngpath):
    subprocess.call(['optipng', '-o7', '-quiet', pngpath])


def compress(filepath, compress_function):
    print 'Compressing %s.' % filepath
    oldsize = os.stat(filepath).st_size
    compress_function(filepath)
    newsize = os.stat(filepath).st_size
    print 'Compressed from {0:,}B to {1:,}B.'.format(oldsize, newsize)


zip_contents_cache = {}

def create_zip(major_name, target_platform, fonts):
    # Make sure no file name repeats
    assert len({path.basename(font.filepath) for font in fonts}) == len(fonts)

    all_hint_statuses = {font.hint_status for font in fonts}
    if len(all_hint_statuses) == 1:
        hint_status = list(all_hint_statuses)[0]
    else:
        hint_status = 'various'

    if target_platform == 'other':
        if hint_status == 'various':
            # This may only be the comprehensive package
            assert len(fonts) > 50
            suffix = ''
        elif hint_status == 'unhinted':
            suffix = '-unhinted'
        else:  # hint_status == 'hinted'
            suffix = '-hinted'
    elif target_platform == 'windows':
        if hint_status in ['various', 'hinted']:
            if 'windows' in {font.platform for font in fonts}:
                suffix = '-windows'
            else:
                suffix = '-hinted'
        else:  # hint_status == 'unhinted':
            suffix = '-unhinted'
    else:  # target_platform == 'linux'
        if len(fonts) > 50 or hint_status in ['various', 'hinted']:
            suffix = '-hinted'
        else:
            suffix = '-unhinted'

    zip_basename = '%s%s.zip' % (major_name, suffix)

    zippath = path.join(OUTPUT_DIR, 'pkgs', zip_basename)
    frozen_fonts = frozenset(fonts)
    if path.isfile(zippath):  # Skip if the file already exists
        # When continuing, we assume that if it exists, it is good
        if zip_basename not in zip_contents_cache:
            print("Continue: assuming built %s is valid" % zip_basename)
            zip_contents_cache[zip_basename] = frozen_fonts
        else:
            assert zip_contents_cache[zip_basename] == frozen_fonts
        return zip_basename
    else:
        assert frozen_fonts not in zip_contents_cache.values()
        zip_contents_cache[zip_basename] = frozen_fonts
        pairs = []
        license_types = set()
        for font in fonts:
            pairs.append((font.filepath, path.basename(font.filepath)))
            license_types.add(font.license_type)
        if 'apache' in license_types:
            pairs.append((APACHE_LICENSE_LOC, 'LICENSE.txt'))
        if 'sil' in license_types:
            pairs.append((SIL_LICENSE_LOC, 'LICENSE_CJK.txt'))
        tool_utils.generate_zip_with_7za_from_filepairs(pairs, zippath)
    return zip_basename


def copy_font(source_file):
    source_dir, source_basename = path.split(source_file)
    target_dir = path.join(OUTPUT_DIR, 'fonts')
    if source_dir.endswith('/hinted'):
        target_dir = path.join(target_dir, 'hinted')
    shutil.copy(source_file, path.join(OUTPUT_DIR, target_dir))
    return '../fonts/' + source_basename


def create_css(key, family_name, fonts):
    csspath = path.join(OUTPUT_DIR, 'css', 'fonts', key + '.css')
    with open(csspath, 'w') as css_file:
        for font in fonts:
            font_url = copy_font(font.filepath)
            css_file.write(
                '@font-face {\n'
                '  font-family: "%s";\n'
                '  font-weight: %d;\n'
                '  font-style: %s;\n'
                '  src: url(%s) format("truetype");\n'
                '}\n' % (
                    family_name,
                    css_weight(font.weight),
                    css_style(font.style),
                    font_url)
            )
    return '%s.css' % key


def create_families_object(target_platform):
    all_keys = set([font.key for font in all_fonts])
    families = {}
    all_font_files = set()
    for key in all_keys:
        family_object = {}
        members = {font for font in all_fonts
                   if font.key == key and font.variant != 'UI'
                                      and font.filepath.endswith('tf')}

        if not members:
            mbrs = {font for font in all_fonts if font.key == key}
            raise ValueError("no members for %s from %s" % (key, [f.filepath for f in mbrs]))

        members_to_drop = set()
        for font in members:
            if font.platform == target_platform:
                # If there are any members matching the target platform, they
                # take priority: drop alternatives
                members_to_drop.update(
                    {alt for alt in members
                     if fonts_are_basically_the_same(font, alt) and
                        font.platform != alt.platform})
            elif font.platform is not None:
                # This is a font for another platform
                members_to_drop.add(font)
        members -= members_to_drop

        if target_platform in ['windows', 'linux']:
            desired_hint_status = 'hinted'
        else:
            desired_hint_status = 'unhinted'

        # If there are any members matching the desired hint status, they take
        # priority: drop alternatives
        members_to_drop = set()
        for font in members:
            if font.hint_status == desired_hint_status:
                members_to_drop.update(
                    {alt for alt in members
                     if fonts_are_basically_the_same(font, alt) and
                        font.hint_status != alt.hint_status})
        members -= members_to_drop

        all_font_files |= members

        repr_members = {font for font in members
                        if font.weight == 'Regular' and font.style is None}

        if len(repr_members) != 1:
            raise ValueError("Do not have a single regular font (%s) for key: %s (from %s)." %
                             (len(repr_members), key, [f.filepath for f in members]))
        repr_member = repr_members.pop()

        font_family_name = get_font_family_name(repr_member.filepath)
        if font_family_name.endswith('Regular'):
            font_family_name = font_family_name.rsplit(' ', 1)[0]
        family_object['name'] = font_family_name

        family_object['pkg'] = create_zip(
            font_family_name.replace(' ', ''), target_platform, members)

        family_object['langs'] = sorted_langs(family_to_langs[repr_member.key])

        family_object['category'] = get_css_generic_family(repr_member.family)
        family_object['css'] = create_css(key, font_family_name, members)
        family_object['ranges'] = charset_to_ranges(repr_member.charset)

        font_list = []
        for font in members:
            font_list.append({
                'style': css_style(font.style),
                'weight': css_weight(font.weight),
            })
        if len(font_list) not in [1, 2, 4, 7]:
            print key, font_list
        assert len(font_list) in [1, 2, 4, 7]
        family_object['fonts'] = font_list

        families[key] = family_object
    return families, all_font_files


def generate_ttc_zips_with_7za():
    """Generate zipped versions of the ttc files and put in pkgs directory."""

    # The font family code skips the ttc files, but we want them in the
    # package directory. Instead of mucking with the family code to add the ttcs
    # and then exclude them from the other handling, we'll just handle them
    # separately.
    # For now at least, the only .ttc fonts are the CJK fonts

    pkg_dir = path.join(OUTPUT_DIR, 'pkgs')
    tool_utils.ensure_dir_exists(pkg_dir)
    filenames = [path.basename(f) for f in os.listdir(CJK_DIR) if f.endswith('.ttc')]
    for filename in filenames:
        zip_basename = filename + '.zip'
        zip_path = path.join(pkg_dir, zip_basename)
        if path.isfile(zip_path):
            print("Continue: assuming built %s is valid." % zip_basename)
            continue
        oldsize = os.stat(path.join(CJK_DIR, filename)).st_size
        pairs = [(path.join(CJK_DIR, filename), filename),
                 (SIL_LICENSE_LOC, 'LICENSE_CJK.txt')]
        tool_utils.generate_zip_with_7za_from_filepairs(pairs, zip_path)
        newsize = os.stat(zip_path).st_size
        print "Wrote " + zip_path
        print 'Compressed from {0:,}B to {1:,}B.'.format(oldsize, newsize)
    shutil.copy2(path.join(CJK_DIR, 'NotoSansCJK.ttc.zip'),
                 path.join(pkg_dir, 'NotoSansCJK.ttc.zip'))


def generate_sample_images(data_object):
    image_dir = path.join(OUTPUT_DIR, 'images', 'samples')
    for family_key in data_object['family']:
        family_obj = data_object['family'][family_key]
        font_family_name = family_obj['name']
        print 'Generating images for %s...' % font_family_name
        is_cjk_family = (
            family_key.endswith('-hans') or
            family_key.endswith('-hant') or
            family_key.endswith('-jpan') or
            family_key.endswith('-kore'))
        for lang_scr in family_obj['langs']:
            lang_obj = data_object['lang'][lang_scr]
            sample_text = lang_obj['sample']
            is_rtl = lang_obj['rtl']
            for instance in family_obj['fonts']:
                weight, style = instance['weight'], instance['style']
                image_file_name = path.join(
                    image_dir,
                    '%s_%s_%d_%s.png' % (family_key, lang_scr, weight, style))
                if is_cjk_family:
                    family_suffix = ' ' + css_weight_to_string(weight)
                else:
                    family_suffix = ''
                image_location = path.join(image_dir, image_file_name)
                if path.isfile(image_location):
                    # Don't rebuild images when continuing.
                    print "Continue: assuming image file '%s' is valid." % image_location
                    continue
                create_image.create_png(
                    sample_text,
                    image_location,
                    family=font_family_name+family_suffix,
                    language=lang_scr,
                    rtl=is_rtl,
                    weight=weight, style=style)
                compress(image_location, compress_png)


def create_package_object(fonts, target_platform):
    CLOUD_LOC = 'http://storage.googleapis.com/noto-website/pkgs/'
    comp_zip_file = create_zip('Noto', target_platform, fonts)
    package = {}
    package['url'] = CLOUD_LOC + comp_zip_file
    package['size'] = os.stat(
        path.join(OUTPUT_DIR, 'pkgs', comp_zip_file)).st_size
    return package


def main():
    """Outputs data files for the noto website."""

    parser = argparse.ArgumentParser()
    parser.add_argument('--continue', help="continue with existing built objects",
                        action='store_true', dest='continuing')
    args = parser.parse_args();

    # 'continue' is useful for debugging the build process.  some zips take a
    # long time to build, and this lets the process be restarted and catch up
    # quickly.
    #
    # The run for the actual deploy should be a clean one from scratch.
    if not args.continuing:
        if path.exists(OUTPUT_DIR):
            assert path.isdir(OUTPUT_DIR)
            print 'Removing the old website directory...'
            shutil.rmtree(OUTPUT_DIR)
        os.mkdir(OUTPUT_DIR)
        os.mkdir(path.join(OUTPUT_DIR, 'pkgs'))
        os.mkdir(path.join(OUTPUT_DIR, 'fonts'))
        os.mkdir(path.join(OUTPUT_DIR, 'fonts', 'hinted'))
        os.mkdir(path.join(OUTPUT_DIR, 'css'))
        os.mkdir(path.join(OUTPUT_DIR, 'css', 'fonts'))
        os.mkdir(path.join(OUTPUT_DIR, 'images'))
        os.mkdir(path.join(OUTPUT_DIR, 'images', 'samples'))
        os.mkdir(path.join(OUTPUT_DIR, 'js'))

    print 'Finding all fonts...'
    find_fonts()

    print 'Parsing CLDR data...'
    parse_english_labels()
    parse_supplemental_data()

    for target_platform in ['windows', 'linux', 'other']:
        print 'Target platform %s:' % target_platform

        output_object = {}
        print 'Generating data objects and CSS...'
        output_object['region'] = create_regions_object()
        output_object['lang'] = create_langs_object()

        output_object['family'], all_font_files = create_families_object(
            target_platform)

        print 'Creating comprehensive zip file...'
        output_object['pkg'] = create_package_object(
            all_font_files, target_platform)

        ############### Hot patches ###############
        # Kufi is broken for Urdu Heh goal
        # See issue #34
        output_object['lang']['ur']['families'].remove('noto-kufi-arab')
        output_object['family']['noto-kufi-arab']['langs'].remove('ur')

        # Kufi doesn't support all characters needed for Khowar
        output_object['lang']['khw']['families'].remove('noto-kufi-arab')
        output_object['family']['noto-kufi-arab']['langs'].remove('khw')

        # Kufi doesn't support all characters needed for Kashmiri
        output_object['lang']['ks-Arab']['families'].remove('noto-kufi-arab')
        output_object['family']['noto-kufi-arab']['langs'].remove('ks-Arab')
        ############### End of hot patches ########

        if target_platform == 'linux':
            generate_sample_images(output_object)

        # Drop presently unused features
        for family in output_object['family'].itervalues():
            del family['category']
            del family['css']
            del family['ranges']
        for language in output_object['lang'].itervalues():
            del language['rtl']
            if 'sample' in language:
                del language['sample']

        if target_platform == 'other':
            json_file_name = 'data.json'
        else:
            json_file_name = 'data-%s.json' % target_platform
        json_path = path.join(OUTPUT_DIR, 'js', json_file_name)
        with codecs.open(json_path, 'w', encoding='UTF-8') as json_file:
            json.dump(output_object, json_file,
                      ensure_ascii=False, separators=(',', ':'))

    # Compress the ttc files.  Requires 7za on the build machine.
    generate_ttc_zips_with_7za()

    # Keep presently unused directories so we can continue after first success
    #    if not args.continuing:
    #        shutil.rmtree(path.join(OUTPUT_DIR, 'fonts'))
    #        shutil.rmtree(path.join(OUTPUT_DIR, 'css'))


if __name__ == '__main__':
    locale.setlocale(locale.LC_COLLATE, 'en_US.UTF-8')
    main()
