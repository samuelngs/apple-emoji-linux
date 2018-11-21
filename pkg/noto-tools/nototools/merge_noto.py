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

"""Merges Noto fonts."""
import os.path
import tempfile

from fontTools import merge
from fontTools import ttLib
from fontTools.ttLib.tables import otTables


def make_font_name(script):
    if script:
        return 'Noto Sans %s' % script
    else:
        return 'Noto Sans'


def make_puncless_font_name(script):
    return make_font_name(script).replace(' ', '').replace('-', '')


def make_font_file_name(script, weight, directory='individual/unhinted'):
    filename = '%s/%s-%s.ttf' % (
        directory, make_puncless_font_name(script), weight)
    return filename


def add_ui_alternative(table, target):
    new_target = target + ' UI'
    sources = table[target]
    new_sources = [source + ' UI' for source in sources]
    table[new_target] = new_sources


def has_gsub_table(fontfile):
    font = ttLib.TTFont(fontfile)
    return 'GSUB' in font

SCRIPT_TO_OPENTYPE_SCRIPT_TAG = {
    'CypriotSyllabary': 'cprt',
    'Deseret': 'dsrt',
    'Glagolitic': 'glag',
    'Lisu': 'lisu',
    'Ogham': 'ogam',
    'OldItalic': 'ital',
    'Runic': 'runr',
    'Shavian': 'shaw',
    'Vai': 'vai ',
    'Carian': 'cari',
    'EgyptianHieroglyphs': 'egyp',
    'ImperialAramaic': 'armi',
    'LinearB': 'linb',
    'Lycian': 'lyci',
    'Lydian': 'lydi',
    'OldPersian': 'xpeo',
    'OldSouthArabian': 'sarb',
    'OldTurkic': 'orkh',
    'Osmanya': 'osma',
    'Phoenician': 'phnx',
    'SumeroAkkadianCuneiform': 'xsux',
    'Ugaritic': 'ugar',
    'OlChiki': 'olck',
    'TaiLe': 'tale',
    # Following keys are added to satisfy the use case in merge_fonts.py
    # Reference:
    # https://www.google.com/get/noto/#sans-xsux
    # https://www.google.com/get/noto/#sans-cprt
    # https://www.google.com/get/noto/#sans-yiii
    # https://www.microsoft.com/typography/otspec/scripttags.htm
    'Cuneiform': 'xsux',
    'Cypriot': 'cprt',
    'Yi': 'yi  ',
}


def get_opentype_script_tag(fontfile):
    fontfile = os.path.basename(fontfile)
    if fontfile.startswith('NotoSans'):
        fontfile = fontfile[8:]
    fontfile = fontfile[:fontfile.index('-')]
    return SCRIPT_TO_OPENTYPE_SCRIPT_TAG[fontfile]


def add_gsub_to_font(fontfile):
    """Adds an empty GSUB table to a font."""
    font = ttLib.TTFont(fontfile)
    gsub_table = ttLib.getTableClass('GSUB')('GSUB')
    gsub_table.table = otTables.GSUB()
    gsub_table.table.Version = 1.0
    gsub_table.table.ScriptList = otTables.ScriptList()
    gsub_table.table.ScriptCount = 1
    gsub_table.table.LookupList = otTables.LookupList()
    gsub_table.table.LookupList.LookupCount = 0
    gsub_table.table.LookupList.Lookup = []
    gsub_table.table.FeatureList = otTables.FeatureList()
    gsub_table.table.FeatureList.FeatureCount = 0
    gsub_table.table.LookupList.FeatureRecord = []

    script_record = otTables.ScriptRecord()
    script_record.ScriptTag = get_opentype_script_tag(fontfile)
    script_record.Script = otTables.Script()
    script_record.Script.LangSysCount = 0
    script_record.Script.LangSysRecord = []

    default_lang_sys = otTables.DefaultLangSys()
    default_lang_sys.FeatureIndex = []
    default_lang_sys.FeatureCount = 0
    default_lang_sys.LookupOrder = None
    default_lang_sys.ReqFeatureIndex = 65535
    script_record.Script.DefaultLangSys = default_lang_sys

    gsub_table.table.ScriptList.ScriptRecord = [script_record]

    font['GSUB'] = gsub_table

    target_file = tempfile.gettempdir() + '/' + os.path.basename(fontfile)
    font.save(target_file)
    return target_file


def main():
    merge_table = {
        'Historic': [
            'Avestan',
            'Carian',
            'Egyptian Hieroglyphs',
            'Imperial Aramaic',
            'Pahlavi',  # Should be 'Inscriptional Pahlavi',
            'Parthian',  # Should be 'Inscriptional Parthian',
            'Linear B',
            'Lycian',
            'Lydian',
            'Mandaic',
            'Old Persian',
            'Old South Arabian',
            'Old Turkic',
            'Osmanya',
            'Phags-Pa',
            'Phoenician',
            'Samaritan',
            'Sumero-Akkadian Cuneiform',
            'Ugaritic',
        ],
        'South Asian': [
            'Devanagari',
            'Bengali',
            'Gurmukhi',
            'Gujarati',
            'Oriya',
            'Tamil',
            'Telugu',
            'Kannada',
            'Malayalam',
            'Sinhala',
            'Thaana',
            'Brahmi',
            'Kaithi',
            'Kharoshthi',  # Move to Historic?
            'Lepcha',
            'Limbu',
            'Meetei Mayek',
            'Ol Chiki',
            'Saurashtra',
            'Syloti Nagri',
        ],
        'Southeast Asian': [
            'Thai',
            'Lao',
            'Khmer',
            'Batak',
            'Buginese',
            'Buhid',
            'Cham',
            'Hanunoo',
            'Javanese',
            'Kayah Li',
            'New Tai Lue',
            'Rejang',
            'Sundanese',
            'Tagalog',
            'Tagbanwa',
            'Tai Le',
            'Tai Tham',
            'Tai Viet',
        ],
        '': [  # LGC,
            'Armenian',
            'Bamum',
            'Canadian Aboriginal',
            'Cherokee',
            'Coptic',
            'Cypriot Syllabary',
            'Deseret',
            'Ethiopic',
            'Georgian',
            'Glagolitic',
            'Gothic',
            'Hebrew',
            'Lisu',
            'NKo',
            'Ogham',
            'Old Italic',
            'Runic',
            'Shavian',
            'Tifinagh',
            'Vai',
        ],
    }

    add_ui_alternative(merge_table, 'South Asian')
    add_ui_alternative(merge_table, 'Southeast Asian')

    for merge_target in sorted(merge_table):
        for weight in ['Regular', 'Bold']:
            merger = merge.Merger()
            source_fonts = merge_table[merge_target]
            if '' not in source_fonts:
                source_fonts = [''] + source_fonts  # The LGC font
            regular_sources = [make_font_file_name(script, weight)
                               for script in source_fonts]
            regular_sources = [font
                               for font in regular_sources
                               if os.path.isfile(font)]

            if len(regular_sources) <= 1:
                continue

            print('Merging Noto Sans %s %s' % (merge_target, weight))

            for index, fontfile in enumerate(regular_sources):
                if not has_gsub_table(fontfile):
                    regular_sources[index] = add_gsub_to_font(fontfile)

            font = merger.merge(regular_sources)

            first_font = source_fonts[0]
            if first_font != merge_target:
                for name_record in font['name'].names:
                    name = unicode(name_record.string, 'UTF-16BE')
                    name = name.replace(make_font_name(first_font),
                                        make_font_name(merge_target))
                    name = name.replace(make_puncless_font_name(first_font),
                                        make_puncless_font_name(merge_target))
                    name_record.string = name.encode('UTF-16BE')

            font.save(make_font_file_name(
                merge_target,
                weight,
                directory='combined/unhinted'))


if __name__ == '__main__':
    main()
