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

"""Fix some issues in Noto fonts before releasing them."""

__author__ = 'roozbeh@google.com (Roozbeh Pournader)'

import argparse
import array
import os
from os import path
import re
import sys

from fontTools import ttLib

from nototools import font_data
from nototools import notoconfig


NOTO_URL = "http://www.google.com/get/noto/"

_LICENSE_ID = 13
_LICENSE_URL_ID = 14

_SIL_LICENSE = (
    'This Font Software is licensed under the SIL Open Font License, '
    'Version 1.1. This Font Software is distributed on an "AS IS" '
    'BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express '
    'or implied. See the SIL Open Font License for the specific language, '
    'permissions and limitations governing your use of this Font Software.')

_SIL_LICENSE_URL = "http://scripts.sil.org/OFL"


def fix_revision(font):
    """Fix the revision of the font to match its version."""
    version = font_data.font_version(font)
    match = re.match(r'Version (\d{1,5})\.(\d{1,5})', version)
    major_version = match.group(1)
    minor_version = match.group(2)

    accuracy = len(minor_version)
    font_revision = font_data.printable_font_revision(font, accuracy)
    expected_font_revision = major_version+'.'+minor_version
    if font_revision != expected_font_revision:
        font['head'].fontRevision = float(expected_font_revision)
        print 'Fixed fontRevision to %s' % expected_font_revision
        return True

    return False


def fix_fstype(font):
    """Fix the fsType of the font."""
    if font['OS/2'].fsType != 0:
        font['OS/2'].fsType = 0
        print 'Updated fsType to 0'
        return True
    return False


def fix_vendor_id(font):
    """Fix the vendor ID of the font."""
    if font['OS/2'].achVendID != 'GOOG':
        font['OS/2'].achVendID = 'GOOG'
        print 'Changed font vendor ID to GOOG'
        return True
    return False


# Reversed name records in Khmer and Lao fonts
NAME_CORRECTIONS = {
    'Sans Kufi': 'Kufi',
    'SansKufi': 'Kufi',
    'UI Khmer': 'Khmer UI',
    'UIKhmer': 'KhmerUI',
    'UI Lao': 'Lao UI',
    'UILao': 'LaoUI',
    'SansEmoji': 'Emoji',
    'Sans Emoji': 'Emoji',
}

TRADEMARK_TEMPLATE = u'%s is a trademark of Google Inc.'

def fix_name_table(font):
    """Fix copyright and reversed values in the 'name' table."""
    modified = False
    name_records = font_data.get_name_records(font)

    copyright_data = name_records[0]
    years = re.findall('20[0-9][0-9]', copyright_data)
    year = min(years)
    copyright_data = u'Copyright %s Google Inc. All Rights Reserved.' % year

    if copyright_data != name_records[0]:
        print 'Updated copyright message to "%s"' % copyright_data
        font_data.set_name_record(font, 0, copyright_data)
        modified = True

    for name_id in [1, 3, 4, 6]:
        record = name_records[name_id]
        for source in NAME_CORRECTIONS:
            if source in record:
                oldrecord = record
                record = record.replace(source, NAME_CORRECTIONS[source])
                break
        if record != name_records[name_id]:
            font_data.set_name_record(font, name_id, record)
            print 'Updated name table record #%d from "%s" to "%s"' % (
                name_id, oldrecord, record)
            modified = True

    trademark_names = ['Noto', 'Arimo', 'Tinos', 'Cousine']
    trademark_name = None
    font_family = name_records[1]
    for name in trademark_names:
        if font_family.find(name) != -1:
            trademark_name = name
            break
    if not trademark_name:
        print 'no trademarked name in \'%s\'' % font_family
    else:
        trademark_line = TRADEMARK_TEMPLATE % trademark_name
        if name_records[7] != trademark_line:
            old_line = name_records[7]
            font_data.set_name_record(font, 7, trademark_line)
            modified = True
            print 'Updated name table record 7 from "%s" to "%s"' % (old_line, trademark_line)

    if name_records[11] != NOTO_URL:
        font_data.set_name_record(font, 11, NOTO_URL)
        modified = True
        print 'Updated name table record 11 to "%s"' % NOTO_URL

    if name_records[_LICENSE_ID] != _SIL_LICENSE:
        font_data.set_name_record(font, _LICENSE_ID, _SIL_LICENSE)
        modified = True
        print 'Updated license id'

    if name_records[_LICENSE_URL_ID] != _SIL_LICENSE_URL:
        font_data.set_name_record(font, _LICENSE_URL_ID, _SIL_LICENSE_URL)
        modified = True
        print 'Updated license url'

    # TODO: check preferred family/subfamily(16&17)

    return modified


def fix_attachlist(font):
    """Fix duplicate attachment points in GDEF table."""
    modified = False
    try:
        attach_points = font['GDEF'].table.AttachList.AttachPoint
    except (KeyError, AttributeError):
        attach_points = []

    for attach_point in attach_points:
        points = sorted(set(attach_point.PointIndex))
        if points != attach_point.PointIndex:
            attach_point.PointIndex = points
            attach_point.PointCount = len(points)
            modified = True

    if modified:
        print 'Fixed GDEF.AttachList'

    return modified


def drop_hints(font):
    """Drops a font's hint."""
    modified = False
    glyf_table = font['glyf']
    for glyph_index in range(len(glyf_table.glyphOrder)):
        glyph_name = glyf_table.glyphOrder[glyph_index]
        glyph = glyf_table[glyph_name]
        if glyph.numberOfContours > 0:
            if glyph.program.bytecode:
                glyph.program.bytecode = array.array('B')
                modified = True
                print 'Dropped hints from glyph "%s"' % glyph_name
    return modified


def drop_tables(font, tables):
    """Drops the listed tables from a font."""
    modified = False
    for table in tables:
        if table in font:
            modified = True
            print 'Dropped table "%s"' % table
            modified = True
            del font[table]
    return modified


TABLES_TO_DROP = [
    # FontForge internal tables
    'FFTM', 'PfEd',
    # Microsoft VOLT internatl tables
    'TSI0', 'TSI1', 'TSI2', 'TSI3',
    'TSI5', 'TSID', 'TSIP', 'TSIS',
    'TSIV',
]

def fix_path(file_path, is_hinted):
    file_path = re.sub(r'_(?:un)?hinted', '', file_path)
    if 'hinted/' in file_path:
        # '==' is higher precedence than 'in'
        if ('unhinted/' in file_path) == is_hinted:
            if is_hinted:
                file_path = file_path.replace('unhinted/', 'hinted/')
            else:
                file_path = file_path.replace('hinted/', 'unhinted/')
    else:
        file_path = os.path.join('hinted' if is_hinted else 'unhinted', file_path)

    # fix Naskh, assume Arabic if unspecified
    file_path = re.sub(r'NotoNaskh(-|UI-)', r'NotoNaskhArabic\1', file_path)

    # fix SansEmoji
    file_path = re.sub('NotoSansEmoji', 'NotoEmoji', file_path)

    # fix Nastaliq
    file_path = re.sub('Nastaliq-', 'NastaliqUrdu-', file_path)

    return file_path


def fix_os2_unicoderange(font):
    os2_bitmap = font_data.get_os2_unicoderange_bitmap(font)
    expected_bitmap = font_data.get_cmap_unicoderange_bitmap(font)
    if os2_bitmap != expected_bitmap:
        old_bitmap_string = font_data.unicoderange_bitmap_to_string(os2_bitmap)
        font_data.set_os2_unicoderange_bitmap(font, expected_bitmap)
        bitmap_string = font_data.unicoderange_bitmap_to_string(expected_bitmap)
        print 'Change unicoderanges from:\n  %s\nto:\n  %s' % (
            old_bitmap_string, bitmap_string)
        return True
    return False


def fix_linegap(font):
    modified = False
    hhea_table = font["hhea"]
    if hhea_table.lineGap != 0:
        print 'hhea lineGap was %s, setting to 0' % hhea_table.lineGap
        hhea_table.lineGap = 0
        modified = True
    vhea_table = font.get("vhea")
    if vhea_table and vhea_table.lineGap != 0:
        print 'vhea lineGap was %s, setting to 0' % vhea_table.lineGap
        vhea_table.lineGap = 0
        modified = True
    os2_table = font["OS/2"]
    if os2_table.sTypoLineGap != 0:
        print 'os/2 sTypoLineGap was %d, setting to 0' % os2_table.sTypoLineGap
        os2_table.sTypoLineGap = 0
        modified = True
    return modified


def fix_font(src_root, dst_root, file_path, is_hinted, save_unmodified):
    """Fix font under src_root and write to similar path under dst_root, modulo
    fixes to the filename.  If is_hinted is false, strip hints.  If unmodified,
    don't write destination unless save_unmodified is true."""

    src_file = os.path.join(src_root, file_path)

    print 'Font file: %s' % src_file
    font = ttLib.TTFont(src_file)
    modified = False

    modified |= fix_revision(font)
    modified |= fix_fstype(font)
    modified |= fix_vendor_id(font)
    modified |= fix_name_table(font)
    modified |= fix_attachlist(font)
    modified |= fix_os2_unicoderange(font)
    # leave line gap for non-noto fonts alone, metrics are more constrained there
    if font_data.font_name(font).find('Noto') != -1:
      modified |= fix_linegap(font)

    tables_to_drop = TABLES_TO_DROP
    if not is_hinted:
        modified |= drop_hints(font)
        tables_to_drop += ['fpgm', 'prep', 'cvt']

    modified |= drop_tables(font, tables_to_drop)

    fixed_path = fix_path(file_path, is_hinted)
    if fixed_path != file_path:
        print 'changed file_path from "%s" to "%s"' % (file_path, fixed_path)
        modified = True

    if not modified:
        print 'No modification necessary'
    if modified or save_unmodified:
        # wait until we need it before we create the dest directory
        dst_file = os.path.join(dst_root, fixed_path)
        dst_dir = path.dirname(dst_file)
        if not path.isdir(dst_dir):
            os.makedirs(dst_dir)
        font.save(dst_file)
        print 'Wrote %s' % dst_file


def fix_fonts(src_root, dst_root, name_pat, save_unmodified):
    src_root = path.abspath(src_root)
    dst_root = path.abspath(dst_root)
    name_rx = re.compile(name_pat)
    for root, dirs, files in os.walk(src_root):
        for file in files:
            if path.splitext(file)[1] not in ['.ttf', '.ttc', '.otf']:
                continue
            src_file = path.join(root, file)
            file_path = src_file[len(src_root)+1:] # +1 to ensure no leading slash.
            if not name_rx.search(file_path):
                continue
            is_hinted = root.endswith('/hinted') or '_hinted' in file
            fix_font(src_root, dst_root, file_path, is_hinted, save_unmodified)


def main():
    default_src_root = notoconfig.values.get('alpha')
    default_dst_root = notoconfig.values.get('autofix')

    parser = argparse.ArgumentParser()
    parser.add_argument('name_pat', help='regex for files to fix, '
                        'searches relative path from src root')
    parser.add_argument('--src_root', help='root of src files (default %s)' %
                        default_src_root, default=default_src_root)
    parser.add_argument('--dst_root', help='root of destination (default %s)' %
                        default_dst_root, default=default_dst_root)
    parser.add_argument('--save_unmodified', help='save even unmodified files',
                        action='store_true')
    args = parser.parse_args()

    if not args.src_root:
        # not on command line and not in user's .notoconfig
        print 'no src root specified.'
        return

    src_root = path.expanduser(args.src_root)
    if not path.isdir(src_root):
        print '%s does not exist or is not a directory' % src_root
        return

    dst_root = path.expanduser(args.dst_root)
    if not path.isdir(dst_root):
        print '%s does not exist or is not a directory' % dst_root
        return

    fix_fonts(src_root, dst_root, args.name_pat, args.save_unmodified)


if __name__ == '__main__':
    main()
